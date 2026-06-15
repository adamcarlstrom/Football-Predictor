import os
import requests
import pandas as pd
import joblib
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime, timezone

# Load environment variables from the .env file
load_dotenv(override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    # Get the absolute path to where backend.py lives
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(BASE_DIR, 'match_predictor.joblib')
    ml_model = joblib.load(model_path)
    print("Machine Learning Model loaded successfully!")
except Exception as e:
    print(f"Warning: Could not load ML model. {e}")
    ml_model = None

app = FastAPI(title="Football Prediction Portfolio API")

# Enable CORS so your React frontend can communicate with this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your specific frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("Server has started successfully")

@app.get("/")
def read_root():
    return {"message": "Football API backend is active"}

@app.post("/api/matches/{match_id}/predict")
def fetch_and_predict(match_id: int):
    """
    Triggered on-demand when a user clicks 'Fetch Prediction' on the frontend.
    Fetches fixture details from API-Football, cleans it, and returns a baseline prediction.
    """
    print("Prediction requested")
    # 1. Fetch match data from API-Football
    url = f"https://v3.football.api-sports.io/fixtures?id={match_id}"
    headers = {
        'x-rapidapi-host': 'v3.football.api-sports.io',
        'x-rapidapi-key': FOOTBALL_API_KEY
    }
    
    print("we will try")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reach Football API: {str(e)}")
        
    if not data.get("response"):
        raise HTTPException(status_code=404, detail="Match not found in external API")

    # 2. Extract and clean data using a temporary dictionary (or Pandas if processing arrays)
    fixture_info = data["response"][0]
    
    match_details = {
        "match_id": fixture_info["fixture"]["id"],
        "date": fixture_info["fixture"]["date"],
        "home_team_id": fixture_info["teams"]["home"]["id"],
        "home_team_name": fixture_info["teams"]["home"]["name"],
        "home_team_logo": fixture_info["teams"]["home"]["logo"],
        "away_team_id": fixture_info["teams"]["away"]["id"],
        "away_team_name": fixture_info["teams"]["away"]["name"],
        "away_team_logo": fixture_info["teams"]["away"]["logo"],
        "status": fixture_info["fixture"]["status"]["short"], # e.g., 'NS' for Not Started
        "league_name": fixture_info["league"]["name"]
    }

    # 3. Cache the teams in Supabase if they don't exist yet to avoid foreign key violations
    for prefix in ["home", "away"]:
        supabase.table("Teams").upsert({
            "team_id": match_details[f"{prefix}_team_id"],
            "name": match_details[f"{prefix}_team_name"],
            "logo_url": match_details[f"{prefix}_team_logo"]
        }).execute()

    print("Update tabless")
    # 4. Save/Update the match data in your matches table
    supabase.table("Matches").upsert({
        "match_id": match_details["match_id"],
        "date": match_details["date"],
        "home_team_id": match_details["home_team_id"],
        "away_team_id": match_details["away_team_id"],
        "status": match_details["status"]
    }).execute()

    # 5. Placeholder Baseline ML Logic
    # Right now, we will simulate a baseline prediction (e.g., 40% Home Win, 30% Draw, 30% Away Win)
    # This will be replaced by your real scikit-learn model once you train it on historical data.
    if ml_model is None:
        raise HTTPException(status_code=500, detail="ML Model is offline.")

    home_id = match_details["home_team_id"]
    away_id = match_details["away_team_id"]
    match_date = match_details["date"]

    # HELPER: Quick function to get a team's last 5 matches from Supabase
    def get_live_team_stats(team_id):
        # Query the database for the last 5 matches this team played BEFORE today
        res = supabase.table("Matches").select("*").or_(f"home_team_id.eq.{team_id},away_team_id.eq.{team_id}").lt("date", match_date).order("date", desc=True).limit(5).execute()
        
        matches = res.data
        if not matches:
            return {"win_rate": 0.0, "gd": 0.0, "rest_days": 14}
            
        wins = 0
        goals_for = 0
        goals_against = 0
        
        for m in matches:
            is_home = m["home_team_id"] == team_id
            team_goals = m["home_goals"] if is_home else m["away_goals"]
            opp_goals = m["away_goals"] if is_home else m["home_goals"]
            
            # Count goals (if not null)
            if team_goals is not None and opp_goals is not None:
                goals_for += team_goals
                goals_against += opp_goals
                
                # Count wins
                if m["status"] != 'PEN':
                    if team_goals > opp_goals:
                        wins += 1
                else:
                    if m["match_winner_id"] == team_id:
                        wins += 1
                        
        win_rate = wins / len(matches)
        gd = (goals_for - goals_against) / len(matches)
        
        # Calculate rest days
        last_match_date = pd.to_datetime(matches[0]["date"])
        current_date = pd.to_datetime(match_date)
        rest_days = min(abs((current_date - last_match_date).days), 14)
        
        return {"win_rate": win_rate, "gd": gd, "rest_days": rest_days}

    # Fetch live stats for both teams
    home_stats = get_live_team_stats(home_id)
    away_stats = get_live_team_stats(away_id)
    
    home_team_data = supabase.table("Teams").select("current_elo").eq("team_id", home_id).single().execute()
    away_team_data = supabase.table("Teams").select("current_elo").eq("team_id", away_id).single().execute()
    
    # Default to 1500 if the database fetch fails or the column is empty
    home_elo = home_team_data.data.get("current_elo") or 1500.0
    away_elo = away_team_data.data.get("current_elo") or 1500.0

    # Construct the 5 features exactly as the model expects them
    live_home_win_rate_diff = home_stats["win_rate"] - away_stats["win_rate"]
    live_home_gd_diff = home_stats["gd"] - away_stats["gd"]
    live_rest_days_diff = home_stats["rest_days"] - away_stats["rest_days"]
    live_elo_diff = home_elo - away_elo 
    
    # Simple importance mapping for the live match
    league_name = match_details["league_name"]
    if league_name == "World Cup": live_importance = 3
    elif league_name in ["Euro Championship", "Copa America", "Africa Cup of Nations", "Asian Cup"]: live_importance = 2
    elif league_name == "UEFA Nations League": live_importance = 2
    else: live_importance = 1

    # Create the input array (MUST MATCH THE EXACT ORDER OF YOUR TRAINING SCRIPT)
    X_live = pd.DataFrame([{
        'home_win_rate_diff': live_home_win_rate_diff,
        'home_gd_diff': live_home_gd_diff,
        'elo_diff': live_elo_diff,
        'rest_days_diff': live_rest_days_diff,
        'match_importance': live_importance
    }])

    # Ask the Random Forest for the probabilities!
    probabilities = ml_model.predict_proba(X_live)[0]

    # Map the probabilities to the database payload
    prediction_data = {
        "match_id": match_details["match_id"],
        "home_win_prob": round(float(probabilities[0]), 4),
        "draw_prob": round(float(probabilities[1]), 4),
        "away_win_prob": round(float(probabilities[2]), 4)
    }
    
    # Save the prediction probabilities to Supabase
    supabase.table("Predictions").upsert(prediction_data).execute()

    return {
        "match_info": match_details,
        "prediction": prediction_data
    }
    
@app.get("/api/matches/today")
def get_todays_matches():
    """
    Fetches a list of today's fixtures. Checks Supabase first to save API quota.
    If empty, fetches from API-Football and caches the result in Supabase.
    """
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start_of_day = f"{today_str}T00:00:00Z"
    end_of_day = f"{today_str}T23:59:59Z"
    
    # --- 1. THE CACHE CHECK ---
    # We ask Supabase for today's matches, and ask it to join the team names
    db_response = supabase.table("Matches").select(
        "match_id, home:Teams!home_team_id(name), away:Teams!away_team_id(name)"
    ).gte("date", start_of_day).lte("date", end_of_day).execute()
    
    # If Supabase has the data, return it immediately and STOP here.
    if db_response.data and len(db_response.data) > 0:
        print("CACHE HIT: Serving matches from Supabase")
        available_matches = []
        for row in db_response.data:
            home_name = row["home"]["name"] if row.get("home") else "Unknown"
            away_name = row["away"]["name"] if row.get("away") else "Unknown"
            available_matches.append({
                "match_id": row["match_id"],
                "label": f"{home_name} vs {away_name}"
            })
        return {"matches": available_matches}
    else:
        print("CACHE MISS: Fetching Matches from API")
        url = f"https://v3.football.api-sports.io/fixtures?date={today_str}"
        
        headers = {
            'x-rapidapi-host': 'v3.football.api-sports.io',
            'x-rapidapi-key': FOOTBALL_API_KEY
        }
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail="Failed to fetch daily matches")

        # --- 3. CACHE THE NEW DATA ---
        available_matches = []
        for fixture in data.get("response", []):
            # print(fixture["league"]["name"])
            if(fixture["league"]["name"] == 'World Cup'):
                match_id = fixture["fixture"]["id"]
                home_team = fixture["teams"]["home"]
                away_team = fixture["teams"]["away"]
                
                # Prepare the label for React
                available_matches.append({
                    "match_id": match_id,
                    "label": f"{home_team['name']} vs {away_team['name']}"
                })
                
                # Save Teams to Supabase
                for team in [home_team, away_team]:
                    supabase.table("Teams").upsert({
                        "team_id": team["id"],
                        "name": team["name"],
                        "logo_url": team["logo"]
                    }).execute()

                # Save Match to Supabase
                supabase.table("Matches").upsert({
                    "match_id": match_id,
                    "date": fixture["fixture"]["date"],
                    "home_team_id": home_team["id"],
                    "away_team_id": away_team["id"],
                    "status": fixture["fixture"]["status"]["short"]
                }).execute()

        return {"matches": available_matches}