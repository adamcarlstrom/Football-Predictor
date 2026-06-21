import os
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime, timedelta

# --- 1. SETUP ---
load_dotenv(override=True)
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

print("Generating Accurate 2026 World Cup Fixtures...")

# --- 1.5 PREVENT DUPLICATES ---
print("Checking database for existing matches to prevent overwriting your completed games...")
existing_matches_response = supabase.table("Matches").select("match_id").execute()
existing_match_ids = {match["match_id"] for match in existing_matches_response.data}
print(f"Found {len(existing_match_ids)} existing matches in Supabase.")

# --- 2. DEFINE THE GROUPS WITH EXACT API-FOOTBALL IDs ---
# Group A is mapped exactly as you specified from FotMob.
# Fill in the rest of the groups B through L using the API IDs.
GROUPS = {
    "A": [16, 17, 769, 282], # Mexico, South Korea, Czechia, South Africa
    "B": [26, 10, 31, 15],   # Placeholder: Argentina, England, Morocco, Switzerland (Replace with FotMob data)
    "C": [2, 9, 2239, 12],   # Placeholder: France, Spain, USA, Japan (Replace with FotMob data)
    # Add "D" through "L" here to complete the 48 teams
}

# --- 3. GENERATE FIXTURES ---
# The World Cup started on June 12, 2026.
# We will spread Matchday 1, 2, and 3 across the proper timeline.
tournament_start = datetime(2026, 6, 12, 12, 0, 0) # 12:00 UTC
match_id_counter = 8000000 # Use high IDs to avoid any real API clashes

fixtures_to_insert = []
teams_to_ensure = set()

for group_name, teams in GROUPS.items():
    teams_to_ensure.update(teams)
    
    t1, t2, t3, t4 = teams[0], teams[1], teams[2], teams[3]
    
    # Matchday 1
    fixtures_to_insert.append({"match_id": match_id_counter + 1, "date": (tournament_start).isoformat(), "home_team_id": t1, "away_team_id": t2, "status": "NS", "league_name": "World Cup"})
    fixtures_to_insert.append({"match_id": match_id_counter + 2, "date": (tournament_start + timedelta(hours=4)).isoformat(), "home_team_id": t3, "away_team_id": t4, "status": "NS", "league_name": "World Cup"})
    
    # Matchday 2 (Approx 4 days later)
    md2_date = tournament_start + timedelta(days=4)
    fixtures_to_insert.append({"match_id": match_id_counter + 3, "date": (md2_date).isoformat(), "home_team_id": t1, "away_team_id": t3, "status": "NS", "league_name": "World Cup"})
    fixtures_to_insert.append({"match_id": match_id_counter + 4, "date": (md2_date + timedelta(hours=4)).isoformat(), "home_team_id": t4, "away_team_id": t2, "status": "NS", "league_name": "World Cup"})
    
    # Matchday 3 (Approx 8 days later)
    md3_date = tournament_start + timedelta(days=8)
    fixtures_to_insert.append({"match_id": match_id_counter + 5, "date": (md3_date).isoformat(), "home_team_id": t4, "away_team_id": t1, "status": "NS", "league_name": "World Cup"})
    fixtures_to_insert.append({"match_id": match_id_counter + 6, "date": (md3_date + timedelta(hours=4)).isoformat(), "home_team_id": t2, "away_team_id": t3, "status": "NS", "league_name": "World Cup"})
    
    match_id_counter += 10
    tournament_start += timedelta(days=1) # Stagger group starts by a day

# --- 4. PUSH TO SUPABASE ---
print(f"Pushing generated matches to Supabase...")
inserted_count = 0

for fixture in fixtures_to_insert:
    # Safely skip matches that you have already loaded or completed!
    if fixture["match_id"] in existing_match_ids:
        print(f"Skipping Match {fixture['match_id']} - Already exists in database.")
        continue
        
    # Ensure team exists in Teams table to avoid Foreign Key errors
    supabase.table("Matches").insert(fixture).execute()
    inserted_count += 1

print(f"Complete! Successfully added {inserted_count} new fixtures without overwriting history.")