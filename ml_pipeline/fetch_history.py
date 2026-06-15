import os
import time
import requests
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv(override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

headers = {
    'x-rapidapi-host': 'v3.football.api-sports.io',
    'x-rapidapi-key': FOOTBALL_API_KEY
}

# --- THE OPTIMIZED TOURNAMENT MAP ---
# Only fetch the exact years these tournaments actually took place
TOURNAMENT_MAP = {
    1: [2022], # World Cup # 2018, 2026 not available
    4: [2024], # Euro Championship # 2020 not available
    5: [2022,2024], # Nations League # only 2022-2024 available
    6: [2023], # AFCON # 2025 
    7: [2023] , # Asian CUP
    9: [2024], # Copa America # 2019, 2021 not available
    10: [2022, 2023, 2024], # Friendlies (limiting to recent years to save tokens)
     
}

def fetch_and_store_season(league_id, season):
    print(f"Fetching League {league_id} for Season {season}...")
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season={season}"
    
    response = requests.get(url, headers=headers)
    
    # 1. Check for standard HTTP crashes
    if response.status_code != 200:
        print(f"HTTP Error: {response.text}")
        return

    json_data = response.json()
    
    # 2. NEW: Check for API-Football's "Silent Errors" (like rate limits)
    api_errors = json_data.get("errors")
    if api_errors:
        # Sometimes errors is an empty list [], sometimes it's a dict.
        if isinstance(api_errors, dict) and len(api_errors) > 0:
            print(f"API SILENT ERROR TRIPPED: {api_errors}")
            return
        elif isinstance(api_errors, list) and len(api_errors) > 0:
            print(f"API SILENT ERROR TRIPPED: {api_errors}")
            return

    data = json_data.get("response", [])
    print(f"Found {len(data)} matches. Processing...")

    for fixture in data:
        status = fixture["fixture"]["status"]["short"]
        if status not in ['FT', 'AET', 'PEN']:
            continue
            
        home_team = fixture["teams"]["home"]
        away_team = fixture["teams"]["away"]
        score = fixture["score"]["penalty"] if status == 'PEN' else fixture["score"]["fulltime"]

        for team in [home_team, away_team]:
            supabase.table("Teams").upsert({
                "team_id": team["id"],
                "name": team["name"],
                "logo_url": team["logo"]
            }).execute()

        winner_id = None
        if status == 'PEN':
            if fixture["teams"]["home"]["winner"]:
                winner_id = home_team["id"]
            elif fixture["teams"]["away"]["winner"]:
                winner_id = away_team["id"]

        match_payload = {
            "match_id": fixture["fixture"]["id"],
            "date": fixture["fixture"]["date"],
            "home_team_id": home_team["id"],
            "away_team_id": away_team["id"],
            "home_goals": score.get("home"),
            "away_goals": score.get("away"),
            "status": status,
            "match_winner_id": winner_id,
            "league_name": fixture["league"]["name"]
        }
        
        supabase.table("Matches").upsert(match_payload).execute()

    print(f"Finished League {league_id} Season {season}.\n")

if __name__ == "__main__":
    # Loop through our exact, optimized dictionary
    for league, seasons in TOURNAMENT_MAP.items():
        for season in seasons:
            fetch_and_store_season(league, season)
            time.sleep(7) 
            
    print("Historical data ingestion complete!")