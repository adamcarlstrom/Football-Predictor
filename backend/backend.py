from collections import defaultdict
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

    if not(match_id >= 8000000):
        print("Match from API")
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
        print("Match info fetched: ", fixture_info)
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
    else:
        # match does not exist within API, only within database...
        fetched_match = supabase.table("Matches").select(
            "match_id, date, status, home_goals, away_goals, home_team_id, away_team_id,"
            "home:Teams!home_team_id(name, logo_url), "
            "away:Teams!away_team_id(name, logo_url), "
            "prediction:Predictions(home_win_prob, draw_prob, away_win_prob, predicted_home_goals, predicted_away_goals)"
        ).eq("league_name","World Cup").eq("match_id", match_id).execute()
        fetched_match_data = fetched_match.data[0]
        print(fetched_match_data)
        match_details = {
        "match_id": match_id,
        "date": fetched_match_data["date"],
        "home_team_id": fetched_match_data["home_team_id"],
        "home_team_name": fetched_match_data["home"]["name"],
        "home_team_logo": fetched_match_data["home"]["logo_url"],
        "away_team_id": fetched_match_data["away_team_id"],
        "away_team_name": fetched_match_data["away"]["name"],
        "away_team_logo": fetched_match_data["away"]["logo_url"],
        "status": fetched_match_data["status"], # e.g., 'NS' for Not Started
        "league_name": "World Cup"
        }
        
        
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
        gf_avg = goals_for / len(matches)
        ga_avg = goals_against / len(matches)
        
        # Calculate rest days
        last_match_date = pd.to_datetime(matches[0]["date"])
        current_date = pd.to_datetime(match_date)
        rest_days = min(abs((current_date - last_match_date).days), 14)
        
        print(f"> RESULT FOR {team_id}: Win Rate: {win_rate:.2f}, GD/Match: {gd:.2f}, Rest: {rest_days} days\n")
        
        return {"win_rate": win_rate, "gd": gd, "rest_days": rest_days,
            "gf_avg": gf_avg, 
            "ga_avg": ga_avg  
            }

    # Fetch live stats for both teams
    home_stats = get_live_team_stats(home_id)
    away_stats = get_live_team_stats(away_id)
    
    
    h2h_res = supabase.table("Matches").select("*").in_("status", ["FT", "AET", "PEN"]).or_(f"and(home_team_id.eq.{home_id},away_team_id.eq.{away_id}),and(home_team_id.eq.{away_id},away_team_id.eq.{home_id})").lt("date", match_date).order("date", desc=True).limit(3).execute()
    h2h_matches = h2h_res.data
    
    if not h2h_matches:
        live_h2h_win_diff = 0.0
        live_h2h_gd_diff = 0.0
        h2h_home_gf_avg = None
        h2h_away_gf_avg = None
    else:
        h_wins = 0; a_wins = 0; h_goals = 0; a_goals = 0
        for m in h2h_matches:
            if m["home_team_id"] == home_id:
                h_g, a_g = m["home_goals"], m["away_goals"]
            else:
                h_g, a_g = m["away_goals"], m["home_goals"]
                
            if h_g > a_g: h_wins += 1
            elif a_g > h_g: a_wins += 1
            h_goals += h_g
            a_goals += a_g
            
        live_h2h_win_diff = (h_wins - a_wins) / len(h2h_matches)
        live_h2h_gd_diff = (h_goals - a_goals) / len(h2h_matches)
        
        h2h_home_gf_avg = h_goals / len(h2h_matches)
        h2h_away_gf_avg = a_goals / len(h2h_matches)
    
    home_team_data = supabase.table("Teams").select("current_elo").eq("team_id", home_id).single().execute()
    away_team_data = supabase.table("Teams").select("current_elo").eq("team_id", away_id).single().execute()
    
    # Default to 1500 if the database fetch fails or the column is empty
    home_elo = home_team_data.data.get("current_elo") or 1500.0
    away_elo = away_team_data.data.get("current_elo") or 1500.0

    # Construct the 5 features exactly as the model expects them
    home_gf = home_stats["gf_avg"]
    home_ga = home_stats["ga_avg"]
    away_gf = away_stats["gf_avg"]
    away_ga = away_stats["ga_avg"]
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
        'match_importance': live_importance,
        'h2h_win_diff': live_h2h_win_diff, 
        'h2h_gd_diff': live_h2h_gd_diff
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

    pred_home_goals, pred_away_goals = generate_poisson_scoreline(
        home_prob, draw_prob, away_prob, 
        home_gf, home_ga, away_gf, away_ga, h2h_home_gf_avg, h2h_away_gf_avg
    )
    
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

# Helper function to grab the fully joined data from Supabase
def fetch_joined_db_data(start_of_window,end_of_window):
    return supabase.table("Matches").select(
        "match_id, date, status, home_goals, away_goals, "
        "home:Teams!home_team_id(name, logo_url), "
        "away:Teams!away_team_id(name, logo_url), "
        "prediction:Predictions(home_win_prob, draw_prob, away_win_prob, predicted_home_goals, predicted_away_goals)"
    ).eq("league_name","World Cup").gte("date", start_of_window).lte("date", end_of_window).order("date").execute()

@app.get("/api/api_update_call")
def get_api_update_call(date:str = None):
    if date:
        target_date_str = date
    else:
        target_date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    print("Update API call for date: ",date)
    url = f"https://v3.football.api-sports.io/fixtures?date={target_date_str}&timezone=Europe/Stockholm"
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
    return {"status": "success", "message": f"Successfully pulled and saved matches for {target_date_str}"}

@app.get("/api/matches")
def get_matches_by_date(date: str = None):
    """
    Fetches World Cup matches for a specific date. 
    If no date is provided, defaults to today.
    """
    if date:
        target_date_str = date
    else:
        target_date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
    target_dt = datetime.strptime(target_date_str, "%Y-%m-%d")
    start_of_window = (target_dt - timedelta(days=1)).strftime("%Y-%m-%dT22:00:00+00:00")
    end_of_window = (target_dt ).strftime("%Y-%m-%dT22:00:00+00:00")

    # --- 1. THE CACHE CHECK ---
    db_response = fetch_joined_db_data(start_of_window,end_of_window)
    
    # --- 1.5 THE DUPLICATE SWEEPER ---
    if db_response.data:
        seen_matchups = {}
        duplicates_to_delete = []

        for m in db_response.data:
            # Sort names to create a unique identifier regardless of who is home vs away
            matchup_key = tuple(sorted([m["home"]["name"], m["away"]["name"]]))
            
            if matchup_key in seen_matchups:
                existing_match = seen_matchups[matchup_key]
                # Compare match IDs. Mark the HIGHER ID (fake one) for deletion
                if m["match_id"] > existing_match["match_id"]:
                    duplicates_to_delete.append(m["match_id"])
                else:
                    duplicates_to_delete.append(existing_match["match_id"])
                    seen_matchups[matchup_key] = m  # Keep the lower ID in our verified list
            else:
                seen_matchups[matchup_key] = m

        if duplicates_to_delete:
            print(f"Sweeping {len(duplicates_to_delete)} duplicate fake matches from database...")
            for bad_id in duplicates_to_delete:
                supabase.table("Predictions").delete().eq("match_id", bad_id).execute()
                supabase.table("Matches").delete().eq("match_id", bad_id).execute()
            # Refetch clean data after sweeping
            db_response = fetch_joined_db_data(start_of_window, end_of_window)

    needs_refresh = False
    if db_response.data:
        current_time = datetime.now(timezone.utc)
        for m in db_response.data:
            if m["status"] in ["NS", "1H", "2H", "HT"]:
                date_str = m["date"].replace("Z", "+00:00")
                match_time = datetime.fromisoformat(date_str)
                
                if current_time > (match_time + timedelta(hours=3)) and current_time < (match_time + timedelta(hours=48)):
                    print(f"Match {m['match_id']} should be finished. Auto-updating...")
                    try:
                        up_url = f"https://v3.football.api-sports.io/fixtures?id={m['match_id']}"
                        headers = {
                            'x-rapidapi-host': 'v3.football.api-sports.io',
                            'x-rapidapi-key': FOOTBALL_API_KEY
                        }
                        up_res = requests.get(up_url, headers=headers)
                        up_data = up_res.json()
                        
                        if up_data.get("response"):
                            fix = up_data["response"][0]
                            new_status = fix["fixture"]["status"]["short"]
                            if new_status in ["FT", "AET", "PEN"]:
                                supabase.table("Matches").update({
                                    "status": new_status,
                                    "home_goals": fix["goals"]["home"],
                                    "away_goals": fix["goals"]["away"]
                                }).eq("match_id", m["match_id"]).execute()
                                needs_refresh = True
                                print(f"Successfully updated match {m['match_id']} to {new_status} ({fix['goals']['home']}-{fix['goals']['away']})")
                    except Exception as e:
                        print(f"Failed to auto-update match {m['match_id']}: {e}")
                        
        if needs_refresh:
            db_response = fetch_joined_db_data(start_of_window,end_of_window)

    # --- 1.6 THE HORIZON SYNC (Check for Tomorrow's Real Games) ---
    current_date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    current_dt = datetime.strptime(current_date_str, "%Y-%m-%d")
    
    # Is the requested date today or tomorrow or yesterday?
    is_horizon = (target_dt == current_dt) or (target_dt == current_dt + timedelta(days=1)) or (target_dt == current_dt - timedelta(days=1)) 
    
    # Are there fake matches sitting in the database for this date?
    has_fakes = any(m["match_id"] >= 8000000 for m in db_response.data) if db_response.data else False
    
    # If it's today/tomorrow AND we have fakes, ignore the local DB and force an API fetch!
    force_api_sync = is_horizon and has_fakes

    if db_response.data and len(db_response.data) > 0 and not force_api_sync:
        print(f"CACHE HIT: Serving matches for {target_date_str} from Supabase")
        # print(db_response.data)
        return {"matches": db_response.data}

    # --- 2. CACHE MISS OR HORIZON SYNC: Fetch from API ---
    if force_api_sync:
        print(f"FAKE MATCHES DETECTED for {target_date_str}. Forcing API sync to replace them...")
    else:
        print(f"CACHE MISS: Fetching Matches for {target_date_str} from API-Football")
    
    url = f"https://v3.football.api-sports.io/fixtures?date={target_date_str}&timezone=Europe/Stockholm"
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
            
            print(f"\n--- API DATA FOR {target_date_str} ---")
            found_leagues = set()
            for fix in data.get("response", []):
                found_leagues.add(fix["league"]["name"])
            print(f"Leagues playing on this date: {found_leagues}")
            
        except Exception as e:
            raise HTTPException(status_code=500, detail="Failed to fetch matches for date")
    
    # --- 3. SAVE THE NEW DATA & PRUNE FAKES ---
    for fixture in data.get("response", []):
        if fixture["league"]["name"] == 'World Cup':
            match_id = fixture["fixture"]["id"]
            home_team = fixture["teams"]["home"]
            away_team = fixture["teams"]["away"]
            
            # FAKE MATCH RECONCILIATION
            try:
                fake_match_check = supabase.table("Matches").select("match_id").eq("home_team_id", home_team["id"]).eq("away_team_id", away_team["id"]).gte("match_id", 8000000).execute()
                if fake_match_check.data:
                    for fm in fake_match_check.data:
                        print(f"Purging fake match {fm['match_id']} and replacing with real API match {match_id}")
                        supabase.table("Predictions").delete().eq("match_id", fm['match_id']).execute()
                        supabase.table("Matches").delete().eq("match_id", fm['match_id']).execute()
            except Exception as e:
                print(f"Error purging fake matches: {e}")
            
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
    db_response = fetch_joined_db_data(start_of_window,end_of_window)
    # print(db_response.data)
    return {"matches": db_response.data}

def generate_poisson_scoreline(prob_home, prob_draw, prob_away, home_gf, home_ga, away_gf, away_ga, h2h_home_gf=None, h2h_away_gf=None):
    """
    Translates ML win probabilities and 10-game offensive/defensive form into realistic scorelines.
    """
    # 1. Base Expected Goals (xG) based on 10-game form
    # Home offense vs Away defense
    base_home_xg = (home_gf + away_ga) / 2.0
    # base_home_xg = (base_home_xg +  h2h_home_goals) / 2 # Weigh h2h goals more heavily
    # Away offense vs Home defense
    base_away_xg = (away_gf + home_ga) / 2.0
    # base_away_xg = (base_away_xg + h2h_away_goals) / 2.0 # Weigh h2h goals more heavily
    
    if h2h_home_gf is not None and h2h_away_gf is not None:
        base_home_xg = (base_home_xg + h2h_home_gf) / 2.0
        base_away_xg = (base_away_xg + h2h_away_gf) / 2.0

    # 2. Scale by ML Probability (Baseline chance in a 3-way match is ~33.3%)
    # If the model gives them an 80% chance to win, their xG skyrockets.
    lambda_home = max(0.1, base_home_xg * (prob_home / 0.333))
    lambda_away = max(0.1, base_away_xg * (prob_away / 0.333))

    def get_poisson_prob(k, lam):
        return ((lam ** k) * math.exp(-lam)) / math.factorial(k)

    # Calculate probabilities up to 6 goals
    home_probs = [get_poisson_prob(i, lambda_home) for i in range(7)]
    away_probs = [get_poisson_prob(i, lambda_away) for i in range(7)]

    favored_outcome = 0 
    if prob_draw >= prob_home and prob_draw >= prob_away:
        favored_outcome = 1
    elif prob_away >= prob_home and prob_away >= prob_draw:
        favored_outcome = 2

    best_prob = -1
    best_score = (0, 0)

    # Search a 7x7 grid to allow for 6-0 blowouts
    for h in range(7):
        for a in range(7):
            joint_prob = home_probs[h] * away_probs[a]
            
            is_valid = False
            if favored_outcome == 0 and h > a: is_valid = True
            elif favored_outcome == 1 and h == a: is_valid = True
            elif favored_outcome == 2 and h < a: is_valid = True

            if is_valid and joint_prob > best_prob:
                best_prob = joint_prob
                best_score = (h, a)

    return best_score


# --- TOURNAMENT SIMULATOR ENDPOINTS ---
@app.get("/api/tournament/groups")
def get_group_standings():
    """Extracts the 12 groups, calculates actual/predicted standings, and finds advancing teams."""
    # 1. Fetch all WC matches
    res = supabase.table("Matches").select("*, home:Teams!home_team_id(*), away:Teams!away_team_id(*), prediction:Predictions(*)").eq("league_name", "World Cup").gte("date", "2026-06-11").execute()
    matches = res.data

    # 2. Extract groups using a graph traversal (Teams that play each other are in the same group)
    adj = defaultdict(set)
    team_dict = {}
    for m in matches:
        # Only use the first ~72 matches (group stage) to build the clusters
        adj[m["home_team_id"]].add(m["away_team_id"])
        adj[m["away_team_id"]].add(m["home_team_id"])
        team_dict[m["home_team_id"]] = m["home"]
        team_dict[m["away_team_id"]] = m["away"]

    visited = set()
    groups = []
    # Identify connected components (Groups of 4)
    for t_id in list(team_dict.keys()):
        if t_id not in visited:
            group_members = set([t_id])
            queue = [t_id]
            while queue:
                curr = queue.pop(0)
                for neighbor in adj[curr]:
                    if neighbor not in visited and neighbor not in group_members:
                        group_members.add(neighbor)
                        queue.append(neighbor)
            for member in group_members: visited.add(member)
            if len(group_members) == 4:
                groups.append(list(group_members))

    # Sort groups alphabetically by the first team's name to assign stable Group Letters (A-L)
    groups.sort(key=lambda g: sorted([team_dict[tid]["name"] for tid in g])[0])
    group_labels = "ABCDEFGHIJKL"

    standings = []
    # 3. Calculate points and goals
    for idx, g_teams in enumerate(groups[:12]):
        g_label = group_labels[idx]
        g_standings = {tid: {"id": tid, "name": team_dict[tid]["name"], "logo": team_dict[tid]["logo_url"], "group": g_label, "pts": 0, "gf": 0, "ga": 0, "gd": 0, "played": 0} for tid in g_teams}
        
        # Process matches in this group
        for m in matches:
            if m["home_team_id"] in g_teams and m["away_team_id"] in g_teams:
                h_id = m["home_team_id"]
                a_id = m["away_team_id"]
                
                # Determine goals: Use actual if played, otherwise predicted
                if m["status"] in ["FT", "AET", "PEN"]:
                    hg, ag = m["home_goals"], m["away_goals"]
                else:
                    # Use Prediction
                    if m.get("prediction") and len(m["prediction"]) > 0:
                        pred = m["prediction"][0] if isinstance(m["prediction"], list) else m["prediction"]
                        hg, ag = pred["predicted_home_goals"], pred["predicted_away_goals"]
                    else:
                        # Fallback predict it locally if missing
                        _,_,_, hg, ag = run_local_prediction(h_id, a_id, m["date"])
                
                if hg is not None and ag is not None:
                    g_standings[h_id]["played"] += 1; g_standings[a_id]["played"] += 1
                    g_standings[h_id]["gf"] += hg; g_standings[a_id]["gf"] += ag
                    g_standings[h_id]["ga"] += ag; g_standings[a_id]["ga"] += hg
                    g_standings[h_id]["gd"] += (hg - ag); g_standings[a_id]["gd"] += (ag - hg)
                    
                    if hg > ag: g_standings[h_id]["pts"] += 3
                    elif ag > hg: g_standings[a_id]["pts"] += 3
                    else:
                        g_standings[h_id]["pts"] += 1; g_standings[a_id]["pts"] += 1

        # Sort this group: Pts -> GD -> GF
        sorted_group = sorted(g_standings.values(), key=lambda x: (x["pts"], x["gd"], x["gf"]), reverse=True)
        # Assign ranks
        for rank, team in enumerate(sorted_group):
            team["rank"] = rank + 1
        standings.append({"group": g_label, "teams": sorted_group})

    # 4. Extract advancers (Top 2 per group + Best 8 3rd places)
    all_3rds = [g["teams"][2] for g in standings]
    sorted_3rds = sorted(all_3rds, key=lambda x: (x["pts"], x["gd"], x["gf"]), reverse=True)
    best_8_3rds = [t["id"] for t in sorted_3rds[:8]]

    for g in standings:
        for t in g["teams"]:
            if t["rank"] <= 2 or t["id"] in best_8_3rds:
                t["advances"] = True
            else:
                t["advances"] = False

    return {"groups": standings, "advancing_3rds": sorted_3rds[:8]}

@app.post("/api/tournament/knockout")
def generate_knockout_bracket(payload: dict):
    groups_data = payload.get("groups", [])
    
    # Organize winners, runners up, and 3rds
    winners = {}; runners = {}; thirds = {}
    for g in groups_data:
        g_label = g["group"]
        for t in g["teams"]:
            if t["advances"]:
                if t["rank"] == 1: winners[g_label] = t
                elif t["rank"] == 2: runners[g_label] = t
                elif t["rank"] == 3: thirds[g_label] = t

    # GREEDY ALLOCATOR for 3rd Place Teams (Approximates the 495 combinations rules perfectly)
    unassigned_thirds = list(thirds.values())
    unassigned_thirds.sort(key=lambda x: (x["pts"], x["gd"], x["gf"]), reverse=True) # Give best teams priority
    
    def pop_best_3rd(allowed_groups):
        for t in unassigned_thirds:
            if t["group"] in allowed_groups:
                unassigned_thirds.remove(t)
                return t
        # Fallback if specific combo is exhausted
        if unassigned_thirds:
            return unassigned_thirds.pop(0)
        return {"name": "TBD", "logo": "", "id": 0}

    # Match R32 according to Wikipedia Layout
    r32_matches = [
        {"id": 73, "home": runners.get("A"), "away": runners.get("B")},
        {"id": 74, "home": winners.get("E"), "away": pop_best_3rd(["A","B","C","D","F"])},
        {"id": 75, "home": winners.get("F"), "away": runners.get("C")},
        {"id": 76, "home": winners.get("C"), "away": runners.get("F")},
        {"id": 77, "home": winners.get("I"), "away": pop_best_3rd(["C","D","F","G","H"])},
        {"id": 78, "home": runners.get("E"), "away": runners.get("I")},
        {"id": 79, "home": winners.get("A"), "away": pop_best_3rd(["C","E","F","H","I"])},
        {"id": 80, "home": winners.get("L"), "away": pop_best_3rd(["E","H","I","J","K"])},
        {"id": 81, "home": winners.get("D"), "away": pop_best_3rd(["B","E","F","I","J"])},
        {"id": 82, "home": winners.get("G"), "away": pop_best_3rd(["A","E","H","I","J"])},
        {"id": 83, "home": runners.get("K"), "away": runners.get("L")},
        {"id": 84, "home": winners.get("H"), "away": runners.get("J")},
        {"id": 85, "home": winners.get("B"), "away": pop_best_3rd(["E","F","G","I","J"])},
        {"id": 86, "home": winners.get("J"), "away": runners.get("H")},
        {"id": 87, "home": winners.get("K"), "away": pop_best_3rd(["D","E","I","J","L"])},
        {"id": 88, "home": runners.get("D"), "away": runners.get("G")},
    ]

    bracket = {"Round of 32": [], "Round of 16": [], "Quarter-Finals": [], "Semi-Finals": [], "Final": []}
    
    # Helper to simulate a round and return winners
    def simulate_round(matches, round_name, next_round_map=None):
        winners_list = []
        for m in matches:
            if not m.get("home") or not m.get("away") or m["home"]["id"] == 0 or m["away"]["id"] == 0:
                m["pred_hg"] = 0; m["pred_ag"] = 0
                winners_list.append({"name": "TBD", "logo": "", "id": 0})
                bracket[round_name].append(m)
                continue
                
            # Simulate locally
            hp, dp, ap, hg, ag = run_local_prediction(m["home"]["id"], m["away"]["id"], datetime.now(timezone.utc).isoformat())
            m["pred_hg"] = hg; m["pred_ag"] = ag
            
            # Resolve Knockout Draws via probabilities
            if hg == ag:
                if hp >= ap: m["pred_hg"] += 1
                else: m["pred_ag"] += 1
                
            winner = m["home"] if m["pred_hg"] > m["pred_ag"] else m["away"]
            m["winner"] = winner
            winners_list.append(winner)
            bracket[round_name].append(m)
        return winners_list

    # Simulate R32
    r32_winners = simulate_round(r32_matches, "Round of 32")
    
    # Build R16 (Following Wiki pairings)
    r16_matches = [
        {"id": 90, "home": r32_winners[0], "away": r32_winners[2]}, # 73 vs 75
        {"id": 89, "home": r32_winners[1], "away": r32_winners[4]}, # 74 vs 77
        {"id": 91, "home": r32_winners[3], "away": r32_winners[5]}, # 76 vs 78
        {"id": 92, "home": r32_winners[6], "away": r32_winners[7]}, # 79 vs 80
        {"id": 93, "home": r32_winners[10], "away": r32_winners[11]},# 83 vs 84
        {"id": 94, "home": r32_winners[8], "away": r32_winners[9]}, # 81 vs 82
        {"id": 95, "home": r32_winners[13], "away": r32_winners[15]},# 86 vs 88
        {"id": 96, "home": r32_winners[12], "away": r32_winners[14]} # 85 vs 87
    ]
    r16_winners = simulate_round(r16_matches, "Round of 16")
    
    # Build QF
    qf_matches = [
        {"id": 97, "home": r16_winners[1], "away": r16_winners[0]}, # 89 vs 90
        {"id": 98, "home": r16_winners[4], "away": r16_winners[5]}, # 93 vs 94
        {"id": 99, "home": r16_winners[2], "away": r16_winners[3]}, # 91 vs 92
        {"id": 100, "home": r16_winners[6], "away": r16_winners[7]},# 95 vs 96
    ]
    qf_winners = simulate_round(qf_matches, "Quarter-Finals")
    
    # Build SF
    sf_matches = [
        {"id": 101, "home": qf_winners[0], "away": qf_winners[1]}, # 97 vs 98
        {"id": 102, "home": qf_winners[2], "away": qf_winners[3]}, # 99 vs 100
    ]
    sf_winners = simulate_round(sf_matches, "Semi-Finals")
    
    # Build Final
    final_match = [{"id": 104, "home": sf_winners[0], "away": sf_winners[1]}]
    simulate_round(final_match, "Final")

    return bracket

# --- SHARED ML PREDICTION LOGIC ---
def run_local_prediction(home_id, away_id, match_date, league_name="World Cup"):
    """Runs the Random Forest purely locally without API calls."""
    if ml_model is None:
        return 0.33, 0.33, 0.33, 1, 1 # Safe fallback

    def get_live_team_stats(team_id):
        nr = 10
        res = supabase.table("Matches").select("*").in_("status", ["FT", "AET", "PEN"]).or_(f"home_team_id.eq.{team_id},away_team_id.eq.{team_id}").lt("date", match_date).order("date", desc=True).limit(nr).execute()
        matches = res.data
        if not matches:
            return {"win_rate": 0.0, "gd": 0.0, "rest_days": 14, "gf_avg": 0.0, "ga_avg": 0.0}
            
        wins = 0; goals_for = 0; goals_against = 0
        for m in matches:
            is_home = m["home_team_id"] == team_id
            team_goals = m["home_goals"] if is_home else m["away_goals"]
            opp_goals = m["away_goals"] if is_home else m["home_goals"]
            if team_goals is not None and opp_goals is not None:
                goals_for += team_goals
                goals_against += opp_goals
                if m["status"] != 'PEN':
                    if team_goals > opp_goals: wins += 1
                else:
                    if m.get("match_winner_id") == team_id: wins += 1
                        
        win_rate = wins / len(matches)
        gd = (goals_for - goals_against) / len(matches)
        gf_avg = goals_for / len(matches)
        ga_avg = goals_against / len(matches)
        
        last_match_date = pd.to_datetime(matches[0]["date"])
        current_date = pd.to_datetime(match_date)
        rest_days = min(abs((current_date - last_match_date).days), 14)
        return {"win_rate": win_rate, "gd": gd, "rest_days": rest_days, "gf_avg": gf_avg, "ga_avg": ga_avg}

    home_stats = get_live_team_stats(home_id)
    away_stats = get_live_team_stats(away_id)
    
    h2h_res = supabase.table("Matches").select("*").in_("status", ["FT", "AET", "PEN"]).or_(f"and(home_team_id.eq.{home_id},away_team_id.eq.{away_id}),and(home_team_id.eq.{away_id},away_team_id.eq.{home_id})").lt("date", match_date).order("date", desc=True).limit(3).execute()
    h2h_matches = h2h_res.data
    
    if not h2h_matches:
        live_h2h_win_diff = 0.0
        live_h2h_gd_diff = 0.0
        h2h_home_gf_avg = None
        h2h_away_gf_avg = None
    else:
        h_wins = 0; a_wins = 0; h_goals = 0; a_goals = 0
        for m in h2h_matches:
            if m["home_team_id"] == home_id:
                h_g, a_g = m["home_goals"], m["away_goals"]
            else:
                h_g, a_g = m["away_goals"], m["home_goals"]
            if h_g > a_g: h_wins += 1
            elif a_g > h_g: a_wins += 1
            h_goals += h_g
            a_goals += a_g
            
        live_h2h_win_diff = (h_wins - a_wins) / len(h2h_matches)
        live_h2h_gd_diff = (h_goals - a_goals) / len(h2h_matches)
        h2h_home_gf_avg = h_goals / len(h2h_matches)
        h2h_away_gf_avg = a_goals / len(h2h_matches)
    
    home_team_data = supabase.table("Teams").select("current_elo").eq("team_id", home_id).single().execute()
    away_team_data = supabase.table("Teams").select("current_elo").eq("team_id", away_id).single().execute()
    
    home_elo = home_team_data.data.get("current_elo") if home_team_data.data else 1500.0
    away_elo = away_team_data.data.get("current_elo") if away_team_data.data else 1500.0

    X_live = pd.DataFrame([{
        'home_win_rate_diff': home_stats["win_rate"] - away_stats["win_rate"],
        'home_gd_diff': home_stats["gd"] - away_stats["gd"],
        'elo_diff': home_elo - away_elo,
        'rest_days_diff': home_stats["rest_days"] - away_stats["rest_days"],
        'match_importance': 5, # Fixed World Cup importance
        'h2h_win_diff': live_h2h_win_diff, 
        'h2h_gd_diff': live_h2h_gd_diff
    }])

    probabilities = ml_model.predict_proba(X_live)[0]
    classes = ml_model.classes_
    try:
        home_prob = probabilities[list(classes).index(0)]
        draw_prob = probabilities[list(classes).index(1)]
        away_prob = probabilities[list(classes).index(2)]
    except ValueError:
        home_prob, draw_prob, away_prob = probabilities[0], probabilities[1], probabilities[2]

    pred_h_g, pred_a_g = generate_poisson_scoreline(
        home_prob, draw_prob, away_prob, 
        home_stats["gf_avg"], home_stats["ga_avg"], 
        away_stats["gf_avg"], away_stats["ga_avg"], 
        h2h_home_gf_avg, h2h_away_gf_avg
    )
    
    return home_prob, draw_prob, away_prob, pred_h_g, pred_a_g
