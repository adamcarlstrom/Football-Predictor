import os
import requests
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables from the .env file
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(title="Football Prediction Portfolio API")

# Enable CORS so your React frontend can communicate with this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your specific frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Football API backend is active"}

@app.post("/api/matches/{match_id}/predict")
def fetch_and_predict(match_id: int):
    """
    Triggered on-demand when a user clicks 'Fetch Prediction' on the frontend.
    Fetches fixture details from API-Football, cleans it, and returns a baseline prediction.
    """
    # 1. Fetch match data from API-Football
    url = f"https://v3.football.api-sports.io/fixtures?id={match_id}"
    headers = {
        'x-rapidapi-host': 'v3.football.api-sports.io',
        'x-rapidapi-key': FOOTBALL_API_KEY
    }
    
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
        "status": fixture_info["fixture"]["status"]["short"] # e.g., 'NS' for Not Started
    }

    # 3. Cache the teams in Supabase if they don't exist yet to avoid foreign key violations
    for prefix in ["home", "away"]:
        supabase.table("teams").upsert({
            "team_id": match_details[f"{prefix}_team_id"],
            "name": match_details[f"{prefix}_team_name"],
            "logo_url": match_details[f"{prefix}_team_logo"]
        }).execute()

    # 4. Save/Update the match data in your matches table
    supabase.table("matches").upsert({
        "match_id": match_details["match_id"],
        "date": match_details["date"],
        "home_team_id": match_details["home_team_id"],
        "away_team_id": match_details["away_team_id"],
        "status": match_details["status"]
    }).execute()

    # 5. Placeholder Baseline ML Logic
    # Right now, we will simulate a baseline prediction (e.g., 40% Home Win, 30% Draw, 30% Away Win)
    # This will be replaced by your real scikit-learn model once you train it on historical data.
    prediction_data = {
        "match_id": match_details["match_id"],
        "home_win_prob": 0.4000,
        "draw_prob": 0.3000,
        "away_win_prob": 0.3000
    }
    
    # Save the prediction probabilities to Supabase
    supabase.table("predictions").upsert(prediction_data).execute()

    # 6. Return the finalized payload to your React frontend
    return {
        "match_info": match_details,
        "prediction": prediction_data
    }