import os
import requests
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime, timedelta

# --- 1. SETUP ---
load_dotenv(override=True)
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY")
teams_response = supabase.table("Teams").select("team_id, name").execute()
# Create a dictionary to map lowercase team names to their API IDs
name_to_id = {team["name"].strip().lower() : team["team_id"] for team in teams_response.data}

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
    "A": ["Mexico", "South Korea", "Czechia", "South Africa"], # Mexico, South Korea, Czechia, South Africa
    "B": ["Canada", "Switzerland", "Bosnia & Herzegovina", "Qatar"],   # Placeholder: Argentina, England, Morocco, Switzerland (Replace with FotMob data)
    "C": ["Brazil", "Morocco", "Scotland", "Haiti"],
    "D": ["USA", "Australia", "Paraguay", "Türkiye"],
    "E": ["Germany", "Ivory Coast", "Ecuador", "Curaçao"],
    "F": ["Netherlands", "Japan",  "Sweden", "Tunisia"],
    "G": ["Egypt", "Iran", "Belgium", "New Zealand"],
    "H": ["Spain", "Uruguay", "Cape Verde Islands", "Saudi Arabia"],
    "I": ["Norway", "France", "Senegal", "Iraq"],
    "J": ["Argentina", "Austria", "Jordan", "Algeria"],
    "K": ["Colombia", "Congo DR", "Portugal", "Uzbekistan"],
    "L": ["England", "Ghana", "Panama", "Croatia"]
}

# --- 3. GENERATE FIXTURES ---
# The World Cup started on June 12, 2026.
# We will spread Matchday 1, 2, and 3 across the proper timeline.
tournament_start = datetime(2026, 6, 12, 12, 0, 0) # 12:00 UTC
match_id_counter = 8000000 # Use high IDs to avoid any real API clashes

fixtures_to_insert = []


for group_name, team_names in GROUPS.items():
    team_ids = []
    for name in team_names:
        tid = name_to_id.get(name.lower())
        if tid is not None:
            team_ids.append(tid)
        else:
            print(f"Team '{name}' not found locally. Searching API-Football...")
            search_url = f"https://v3.football.api-sports.io/teams?search={name}"
            try:
                res = requests.get(search_url, headers={
                    'x-rapidapi-host': 'v3.football.api-sports.io',
                    'x-rapidapi-key': FOOTBALL_API_KEY
                })
                data = res.json()
                if data.get("response") and len(data["response"]) > 0:
                    # Grab the best match from the API
                    api_team = data["response"][0]["team"]
                    new_id = api_team["id"]
                    new_name = api_team["name"]
                    new_logo = api_team["logo"]

                    # Insert the missing team into Supabase!
                    supabase.table("Teams").upsert({
                        "team_id": new_id,
                        "name": new_name,
                        "logo_url": new_logo
                    }).execute()

                    print(f"  -> Successfully found and saved {new_name} (ID: {new_id})")
                    name_to_id[name.lower()] = new_id # Update local dictionary
                    team_ids.append(new_id)
                else:
                    print(f"  -> WARNING: Could not find '{name}' in API. Check spelling on FotMob.")
            except Exception as e:
                print(f"  -> Error fetching '{name}' from API: {e}")
    
    if len(team_ids) == 4:
        GROUPS[group_name] = team_ids
    else:
        print(f"Skipping Group {group_name} because it is missing valid team IDs.")
        
for group_name, teams in GROUPS.items():
    t1, t2, t3, t4 = teams[0], teams[1], teams[2], teams[3]
    
    # Matchday 1
    fixtures_to_insert.append({"match_id": match_id_counter + 1, "date": (tournament_start).isoformat(), "home_team_id": t1, "away_team_id": t2, "status": "NS", "league_name": "World Cup"})
    fixtures_to_insert.append({"match_id": match_id_counter + 2, "date": (tournament_start + timedelta(hours=4)).isoformat(), "home_team_id": t3, "away_team_id": t4, "status": "NS", "league_name": "World Cup"})
    
    # Matchday 2 (Approx 4 days later)
    md2_date = tournament_start + timedelta(days=6)
    fixtures_to_insert.append({"match_id": match_id_counter + 3, "date": (md2_date).isoformat(), "home_team_id": t1, "away_team_id": t3, "status": "NS", "league_name": "World Cup"})
    fixtures_to_insert.append({"match_id": match_id_counter + 4, "date": (md2_date + timedelta(hours=4)).isoformat(), "home_team_id": t4, "away_team_id": t2, "status": "NS", "league_name": "World Cup"})
    
    # Matchday 3 (Approx 8 days later)
    md3_date = tournament_start + timedelta(days=15)
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