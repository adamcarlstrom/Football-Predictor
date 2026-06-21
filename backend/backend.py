import os
import requests
import math
import pandas as pd
import joblib
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime, timezone ,timedelta

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

    # HELPER: Quick function to get a team's last nr matches from Supabase
    def get_live_team_stats(team_id):
        # Query the database for the last nr matches this team played BEFORE today
        nr = 10
        res = supabase.table("Matches").select("*").in_("status", ["FT", "AET", "PEN"]).or_(f"home_team_id.eq.{team_id},away_team_id.eq.{team_id}").lt("date", match_date).order("date", desc=True).limit(nr).execute()
        
        matches = res.data
        if not matches:
            print(f"DEBUG: No historical matches found for (ID: {team_id})")
            return {"win_rate": 0.0, "gd": 0.0, "rest_days": 14}
            
        wins = 0
        goals_for = 0
        goals_against = 0
        
        print(f"\n--- DEBUG: Last {len(matches)} matches for {team_id} ---")
                
        for m in matches:
            is_home = m["home_team_id"] == team_id
            team_goals = m["home_goals"] if is_home else m["away_goals"]
            opp_goals = m["away_goals"] if is_home else m["home_goals"]
            
            print(f"Date: {m['date'][:10]} | Goals For: {team_goals} | Goals Against: {opp_goals} | Status: {m['status']}")
            
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
        
        print(f"> RESULT FOR {team_id}: Win Rate: {win_rate:.2f}, GD/Match: {gd:.2f}, Rest: {rest_days} days\n")
        
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
    if league_name == "World Cup": live_importance = 5
    elif league_name in ["Euro Championship", "Copa America"]: live_importance = 4
    elif league_name in ["Asian Cup", "Africa Cup of Nations"]: live_importance = 3
    elif league_name in ["UEFA Nations League"]: live_importance = 2
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
    
    # Get the exact order of the classes the model learned
    classes = ml_model.classes_
    
    # Safely extract the probabilities by matching the class number 
    # (0 = Home, 1 = Draw, 2 = Away) to its index in the array
    try:
        home_index = list(classes).index(0)
        draw_index = list(classes).index(1)
        away_index = list(classes).index(2)
        
        home_prob = probabilities[home_index]
        draw_prob = probabilities[draw_index]
        away_prob = probabilities[away_index]
    except ValueError:
        # Fallback if classes are somehow missing (rare)
        home_prob, draw_prob, away_prob = probabilities[0], probabilities[1], probabilities[2]

    pred_home_goals, pred_away_goals = generate_poisson_scoreline(home_prob, draw_prob, away_prob)
    
    # Map the probabilities to the database payload
    prediction_data = {
        "match_id": match_details["match_id"],
        "home_win_prob": round(float(home_prob), 4),
        "draw_prob": round(float(draw_prob), 4),
        "away_win_prob": round(float(away_prob), 4),
        "predicted_home_goals": pred_home_goals,
        "predicted_away_goals": pred_away_goals
    }
    
    # Save the prediction probabilities to Supabase
    supabase.table("Predictions").upsert(prediction_data).execute()
    print(prediction_data)
    return {
        "match_info": match_details,
        "prediction": prediction_data
    }
    
@app.get("/api/matches")
def get_matches_by_date(date: str = None):
    """
    Fetches World Cup matches for a specific date. 
    If no date is provided, defaults to today.
    """
    # 1. Determine the target date
    if date:
        target_date_str = date
    else:
        target_date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    target_dt = datetime.strptime(target_date_str, "%Y-%m-%d")
    start_of_window = f"{target_date_str}T00:00:00+00:00"
    end_of_window = (target_dt + timedelta(days=1)).strftime("%Y-%m-%dT12:00:00+00:00")    
    start_of_day = f"{target_date_str}T00:00:00Z"
    end_of_day = f"{target_date_str}T23:59:59Z"

    # Helper function to grab the fully joined data from Supabase
    def fetch_joined_db_data():
        return supabase.table("Matches").select(
            "match_id, date, status, home_goals, away_goals, "
            "home:Teams!home_team_id(name, logo_url), "
            "away:Teams!away_team_id(name, logo_url), "
            "prediction:Predictions(home_win_prob, draw_prob, away_win_prob, predicted_home_goals, predicted_away_goals)"
        ).eq("league_name","World Cup").gte("date", start_of_window).lte("date", end_of_window).order("date").execute()

    # --- 1. THE CACHE CHECK ---
    db_response = fetch_joined_db_data()
    
    if db_response.data and len(db_response.data) > 0:
        print(f"CACHE HIT: Serving matches for {target_date_str} from Supabase")
        return {"matches": db_response.data}

    # --- 2. CACHE MISS: Fetch from API ---
    print(f"CACHE MISS: Fetching Matches for {target_date_str} from API-Football")
    url = f"https://v3.football.api-sports.io/fixtures?date={target_date_str}&timezone=America/New_York"
    headers = {
        'x-rapidapi-host': 'v3.football.api-sports.io',
        'x-rapidapi-key': FOOTBALL_API_KEY
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch matches for date")
    print("Here comes new data: " ,data)
    if(data == []):
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # --- NEW DEBUG BLOCK ---
            print(f"\n--- API DATA FOR {target_date_str} ---")
            found_leagues = set()
            for fix in data.get("response", []):
                found_leagues.add(fix["league"]["name"])
            print(f"Leagues playing on this date: {found_leagues}")
            # -----------------------
            
        except Exception as e:
            raise HTTPException(status_code=500, detail="Failed to fetch matches for date")
    
    # --- 3. SAVE THE NEW DATA ---
    for fixture in data.get("response", []):
        if fixture["league"]["name"] == 'World Cup':
            match_id = fixture["fixture"]["id"]
            home_team = fixture["teams"]["home"]
            away_team = fixture["teams"]["away"]
            
            for team in [home_team, away_team]:
                supabase.table("Teams").upsert({
                    "team_id": team["id"],
                    "name": team["name"],
                    "logo_url": team["logo"]
                }).execute()

            supabase.table("Matches").upsert({
                "match_id": match_id,
                "date": fixture["fixture"]["date"],
                "home_team_id": home_team["id"],
                "away_team_id": away_team["id"],
                "status": fixture["fixture"]["status"]["short"],
                "home_goals": fixture["goals"]["home"], 
                "away_goals": fixture["goals"]["away"],
                "league_name": fixture["league"]["name"]
            }).execute()

    # --- 4. RETURN RE-FETCHED DATA ---
    db_response = fetch_joined_db_data()
    print(db_response.data)
    return {"matches": db_response.data}

def generate_poisson_scoreline(prob_home, prob_draw, prob_away):
    """
    Translates ML win probabilities into an exact, discrete integer scoreline 
    using the Poisson distribution.
    """
    # 1. Map probabilities to Expected Goals (lambda)
    # Using a baseline of ~3.0 total goals per match
    lambda_home = max(0.1, 3.0 * prob_home + 0.5 * prob_draw)
    lambda_away = max(0.1, 3.0 * prob_away + 0.5 * prob_draw)

    # 2. Generate Poisson probabilities for 0 to 5 goals
    def get_poisson_prob(k, lam):
        return ((lam ** k) * math.exp(-lam)) / math.factorial(k)

    home_probs = [get_poisson_prob(i, lambda_home) for i in range(6)]
    away_probs = [get_poisson_prob(i, lambda_away) for i in range(6)]

    # 3. Determine the ML model's favored outcome to strictly align the UI
    favored_outcome = 0 # 0=Home, 1=Draw, 2=Away
    if prob_draw >= prob_home and prob_draw >= prob_away:
        favored_outcome = 1
    elif prob_away >= prob_home and prob_away >= prob_draw:
        favored_outcome = 2

    # 4. Search the 6x6 grid for the most likely valid scoreline
    best_prob = -1
    best_score = (0, 0)

    for h in range(6):
        for a in range(6):
            joint_prob = home_probs[h] * away_probs[a]
            
            # Check if this scoreline strictly matches the ML prediction
            is_valid = False
            if favored_outcome == 0 and h > a: is_valid = True
            elif favored_outcome == 1 and h == a: is_valid = True
            elif favored_outcome == 2 and h < a: is_valid = True

            if is_valid and joint_prob > best_prob:
                best_prob = joint_prob
                best_score = (h, a)

    return best_score