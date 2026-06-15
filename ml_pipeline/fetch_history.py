import os
import time
import requests
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables from the backend folder
load_dotenv(dotenv_path="../backend/.env", override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

headers = {
    'x-rapidapi-host': 'v3.football.api-sports.io',
    'x-rapidapi-key': FOOTBALL_API_KEY
}

# Key International League IDs from API-Football
# 1: World Cup, 4: Euro, 9: Copa America, 10: Friendlies, 2: Champions League (if you expand later)
TARGET_LEAGUES = [1, 4, 9, 10] 
SEASONS = [2018, 2019, 2020, 2021, 2022, 2023, 2024]

def fetch_and_store_season(league_id, season):
    print(f"Fetching League {league_id} for Season {season}...")
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season={season}"
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Error fetching data: {response.text}")
        return

    data = response.json().get("response", [])
    print(f"Found {len(data)} matches. Processing...")

    for fixture in data:
        status = fixture["fixture"]["status"]["short"]
        
        # Only save finished matches for historical training
        if status not in ['FT', 'AET', 'PEN']:
            continue
            
        home_team = fixture["teams"]["home"]
        away_team = fixture["teams"]["away"]
        score = fixture["score"]["penalty"] if status == 'PEN' else fixture["score"]["fulltime"]

        # 1. Upsert Teams
        for team in [home_team, away_team]:
            supabase.table("Teams").upsert({
                "team_id": team["id"],
                "name": team["name"],
                "logo_url": team["logo"]
            }).execute()

        # 2. Determine match winner (if penalties)
        winner_id = None
        if status == 'PEN':
            if fixture["teams"]["home"]["winner"]:
                winner_id = home_team["id"]
            elif fixture["teams"]["away"]["winner"]:
                winner_id = away_team["id"]

        # 3. Upsert Match
        match_payload = {
            "match_id": fixture["fixture"]["id"],
            "date": fixture["fixture"]["date"],
            "home_team_id": home_team["id"],
            "away_team_id": away_team["id"],
            "home_goals": score.get("home"),
            "away_goals": score.get("away"),
            "status": status,
            "match_winner_id": winner_id
            # Note: Detailed stats like possession require a separate endpoint call per match,
            # which would burn through your 100/day limit. For MVP ML, goals and results are enough.
        }
        
        supabase.table("Matches").upsert(match_payload).execute()

    print(f"Finished League {league_id} Season {season}.\n")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    for league in TARGET_LEAGUES:
        for season in SEASONS:
            fetch_and_store_season(league, season)
            
            # CRITICAL: Pause for 7 seconds to respect the 10 requests/minute API limit
            time.sleep(7) 
            
    print("Historical data ingestion complete!")