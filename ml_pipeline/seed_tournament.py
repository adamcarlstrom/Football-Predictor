import os
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime, timedelta

# --- 1. SETUP ---
load_dotenv(override=True)
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

print("Generating Custom 2026 World Cup...")

# --- 2. DEFINE THE TEAMS (Using the 32 seeded teams we gave ELOs to) ---
# We will create 8 groups of 4 teams.
GROUPS = {
    "A": [2, 13, 30, 23],  # France, Senegal, Peru, Saudi Arabia
    "B": [9, 15, 22, 11],  # Spain, Switzerland, Iran, Panama
    "C": [26, 16, 24, 32], # Argentina, Mexico, Poland, Egypt
    "D": [10, 3, 18, 19]   # England, Croatia, Iceland, Nigeria
    # ... You can add E, F, G, H later! Let's start with 4 groups.
}

# --- 3. GENERATE FIXTURES ---
# The World Cup starts on June 11, 2026.
start_date = datetime(2026, 6, 11, 15, 0, 0) # 15:00 UTC
match_id_counter = 9000000 # Use high IDs so they don't clash with real API IDs

fixtures_to_insert = []

for group_name, teams in GROUPS.items():
    # In a group of 4, everybody plays everybody (6 matches total per group)
    # Matchday 1
    fixtures_to_insert.append({"match_id": match_id_counter + 1, "date": (start_date).isoformat(), "home_team_id": teams[0], "away_team_id": teams[1], "status": "NS", "league_name": "World Cup"})
    fixtures_to_insert.append({"match_id": match_id_counter + 2, "date": (start_date).isoformat(), "home_team_id": teams[2], "away_team_id": teams[3], "status": "NS", "league_name": "World Cup"})
    
    # Matchday 2 (3 days later)
    fixtures_to_insert.append({"match_id": match_id_counter + 3, "date": (start_date + timedelta(days=3)).isoformat(), "home_team_id": teams[0], "away_team_id": teams[2], "status": "NS", "league_name": "World Cup"})
    fixtures_to_insert.append({"match_id": match_id_counter + 4, "date": (start_date + timedelta(days=3)).isoformat(), "home_team_id": teams[3], "away_team_id": teams[1], "status": "NS", "league_name": "World Cup"})
    
    # Matchday 3 (6 days later)
    fixtures_to_insert.append({"match_id": match_id_counter + 5, "date": (start_date + timedelta(days=6)).isoformat(), "home_team_id": teams[3], "away_team_id": teams[0], "status": "NS", "league_name": "World Cup"})
    fixtures_to_insert.append({"match_id": match_id_counter + 6, "date": (start_date + timedelta(days=6)).isoformat(), "home_team_id": teams[1], "away_team_id": teams[2], "status": "NS", "league_name": "World Cup"})
    
    match_id_counter += 10 # Increment counter safely
    start_date += timedelta(days=1) # Next group starts the next day

# --- 4. PUSH TO SUPABASE ---
print(f"Pushing {len(fixtures_to_insert)} generated matches to Supabase...")
for fixture in fixtures_to_insert:
    supabase.table("Matches").upsert(fixture).execute()

print("Complete! The API paywall has been bypassed.")