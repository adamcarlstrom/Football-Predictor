import os
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
import joblib

# --- 1. SETUP & EXTRACTION ---
load_dotenv(override=True)
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

print("1. Extracting historical matches from Supabase...")
# Fetch all matches, ordered by date. Chronological order is critical for rolling averages!
response = supabase.table("Matches").select("*").in_("status", ["FT", "AET", "PEN"]).order("date").execute()
df = pd.DataFrame(response.data)

# Convert dates from strings to actual datetime objects
df['date'] = pd.to_datetime(df['date'])

# --- 2. TARGET VARIABLE CREATION ---
print("2. Creating the Target Variable (Who won?)...")
# We need to tell the model the actual outcome so it can learn.
# 0 = Home Win, 1 = Draw, 2 = Away Win
def determine_outcome(row):
    if row['status'] == 'PEN':
        return 1 # Penalties are mathematically a Draw in open play
    if row['home_goals'] > row['away_goals']:
        return 0
    elif row['home_goals'] < row['away_goals']:
        return 2
    else:
        return 1

df['outcome'] = df.apply(determine_outcome, axis=1)

# --- 3. FEATURE ENGINEERING (The Magic) ---
print("3. Engineering Features (Calculating rolling averages)...")
# We need to calculate how good a team is based on their past 5 matches.
# To do this, we create a chronological ledger of every game a team plays.

team_stats = {} # Dictionary to hold the rolling history of every team

# These lists will become our new columns in the dataframe
features = {
    'home_win_rate_diff': [],
    'home_gd_diff': [],
    'elo_diff': [],
    'rest_days_diff': [],
    'match_importance': [],
    'h2h_win_diff': [],  # Head to Head Win Difference
    'h2h_gd_diff': []    # Head to Head Goal Difference
}

h2h_stats = {} # NEW: Dictionary to hold the historical rivalry between any two teams

def determine_outcome(row):
    if row['status'] == 'PEN': return 1
    if row['home_goals'] > row['away_goals']: return 0
    elif row['home_goals'] < row['away_goals']: return 2
    else: return 1

def calculate_rest_days(current_date, last_match_date):
    if pd.isna(last_match_date) or last_match_date is None:
        return 14 # Assume fully rested if it's their first recorded match
    difference = abs((current_date - last_match_date).days)
    return min(difference, 14)

def get_match_importance(league):
    match league:
        case "World Cup":
            return (5,60)
        case "Africa Cup of Nations":
            return (3,40)
        case "Asian Cup":
            return (3,35)
        case "Copa America":
            return (4,45)
        case "Euro Championship":
            return (4,50)
        case "UEFA Nations League":
            return (2,30)
        case "Friendlies":
            return (1,15)
        case _:
            return (1,15)
        
def calculate_new_elo(home_elo, away_elo, actual_outcome, k_factor, home_goals, away_goals, league_name):
    # Add a flat 50-point artificial bump to the home team ONLY for the expectation math
    neutral_leagues = ["World Cup", "Euro Championship", "Copa America", "Africa Cup of Nations", "Asian Cup"]
    home_advantage = 0 if league_name in neutral_leagues else 100
    
    # Expected outcome math for Home Team with HFA factored in
    expected_home = 1 / (1 + 10 ** ((away_elo - (home_elo + home_advantage)) / 400))
    expected_away = 1 - expected_home
    
    # Map our outcome (0, 1, 2) to ELO points (1, 0.5, 0)
    if actual_outcome == 0: # Home Win
        home_points, away_points = 1, 0
    elif actual_outcome == 2: # Away Win
        home_points, away_points = 0, 1
    else: # Draw
        home_points, away_points = 0.5, 0.5
    
    if home_goals is None or away_goals is None:
        g_multiplier = 1.0
    else:
        gd = abs(home_goals - away_goals)
        if gd <= 1:
            g_multiplier = 1.0
        elif gd == 2:
            g_multiplier = 1.5
        else:
            g_multiplier = (11 + gd) / 8.0
        
    home_shift = k_factor * g_multiplier * (home_points - expected_home)
    away_shift = k_factor * g_multiplier * (away_points - expected_away)
    
    new_home_elo = home_elo + home_shift
    new_away_elo = away_elo + away_shift
    return new_home_elo, new_away_elo

# Real-world baseline ELOs (Approximate strength as of early 2022)
INITIAL_ELOS = {
    1: 2030,   # Belgium
    2: 2140,   # France
    3: 1910,   # Croatia
    4: 1780,   # Russia
    5: 1840,   # Sweden
    6: 2150,   # Brazil
    7: 1930,   # Uruguay
    8: 1900,   # Colombia
    9: 2040,   # Spain
    10: 2050,  # England
    11: 1600,  # Panama
    12: 1800,  # Japan
    13: 1820,  # Senegal
    14: 1880,  # Serbia
    15: 1920,  # Switzerland
    16: 1880,  # Mexico
    17: 1790,  # South Korea
    18: 1680,  # Iceland
    19: 1740,  # Nigeria
    20: 1750,  # Australia
    21: 1900,  # Denmark
    22: 1810,  # Iran
    23: 1650,  # Saudi Arabia
    24: 1770,  # Poland
    25: 1950,  # Germany
    26: 2140,  # Argentina
    27: 2000,  # Portugal
    28: 1720,  # Tunisia
    29: 1680,  # Costa Rica
    30: 1850,  # Peru
    31: 1810,  # Morocco
    32: 1730   # Egypt
}

# We iterate through every match in chronological order
for index, row in df.iterrows():
    home = row['home_team_id']
    away = row['away_team_id']
    
    # Initialize teams in our ledger if we haven't seen them yet
    if home not in team_stats: 
        start_elo = INITIAL_ELOS.get(home, 1300)
        team_stats[home] = {'elo': start_elo,'last_match_date': None,'results': [], 'goals_for': [], 'goals_against': []}
    if away not in team_stats: 
        start_elo = INITIAL_ELOS.get(away, 1300)
        team_stats[away] = {'elo': start_elo,'last_match_date': None,'results': [], 'goals_for': [], 'goals_against': []}
    


    home_rest = calculate_rest_days(row['date'], team_stats[home]['last_match_date'])
    away_rest = calculate_rest_days(row['date'], team_stats[away]['last_match_date'])
    rest_diff = home_rest - away_rest
    elo_diff = team_stats[home]['elo'] - team_stats[away]['elo']
    importance_weight, k_factor = get_match_importance(row['league_name'])

    h2h_key_home_away = (home, away)
    h2h_key_away_home = (away, home)
    
    if h2h_key_home_away not in h2h_stats:
        h2h_stats[h2h_key_home_away] = []
        h2h_stats[h2h_key_away_home] = []
        
    recent_h2h = h2h_stats[h2h_key_home_away][-3:] # Look at the last 3 matchups
    if len(recent_h2h) == 0:
        h2h_win_diff = 0.0
        h2h_gd_diff = 0.0
    else:
        h_wins = sum(1 for h_g, a_g in recent_h2h if h_g > a_g)
        a_wins = sum(1 for h_g, a_g in recent_h2h if a_g > h_g)
        h_goals = sum(h_g for h_g, a_g in recent_h2h)
        a_goals = sum(a_g for h_g, a_g in recent_h2h)
        
        h2h_win_diff = (h_wins - a_wins) / len(recent_h2h)
        h2h_gd_diff = (h_goals - a_goals) / len(recent_h2h)
    
    # Calculate PRE-MATCH stats based on the last 5 games
    def get_recent_stats(team_id):
        stats = team_stats[team_id]
        if len(stats['results']) < 1:
            return {'win_rate': 0, 'gd': 0} # Default to 0 if it's their very first game
        
        nr_matches = 10
        # Look only at the last nr_matches matches
        recent_results = stats['results'][-nr_matches:]
        recent_gf = sum(stats['goals_for'][-nr_matches:])
        recent_ga = sum(stats['goals_against'][-nr_matches:])
        
        win_rate = recent_results.count('W') / len(recent_results)
        goal_diff = (recent_gf - recent_ga) / len(recent_results)
        return {'win_rate': win_rate, 'gd': goal_diff}

    home_prematch = get_recent_stats(home)
    away_prematch = get_recent_stats(away)
    
    # Save the relative differences to our feature lists
    features['home_win_rate_diff'].append(home_prematch['win_rate'] - away_prematch['win_rate'])
    features['home_gd_diff'].append(home_prematch['gd'] - away_prematch['gd'])
    features['elo_diff'].append(elo_diff)
    features['rest_days_diff'].append(rest_diff)
    features['match_importance'].append(importance_weight)
    features['h2h_win_diff'].append(h2h_win_diff) 
    features['h2h_gd_diff'].append(h2h_gd_diff)   
    
    # AFTER calculating pre-match stats, update the ledger with the current match's result
    # so it can be used for their next game.
    if row['outcome'] == 0:
        team_stats[home]['results'].append('W')
        team_stats[away]['results'].append('L')
    elif row['outcome'] == 2:
        team_stats[home]['results'].append('L')
        team_stats[away]['results'].append('W')
    else:
        team_stats[home]['results'].append('D')
        team_stats[away]['results'].append('D')
        
    team_stats[home]['goals_for'].append(row['home_goals'])
    team_stats[home]['goals_against'].append(row['away_goals'])
    team_stats[away]['goals_for'].append(row['away_goals'])
    team_stats[away]['goals_against'].append(row['home_goals'])
    
    
    
    new_home_elo, new_away_elo = calculate_new_elo(team_stats[home]['elo'], team_stats[away]['elo'], row['outcome'], k_factor, row['home_goals'],row['away_goals'],row['league_name'] )
    team_stats[home]['elo'] = new_home_elo
    team_stats[away]['elo'] = new_away_elo
    
    team_stats[home]['last_match_date'] = row['date']
    team_stats[away]['last_match_date'] = row['date']
    
    if row['home_goals'] is not None and row['away_goals'] is not None:
        h2h_stats[h2h_key_home_away].append((row['home_goals'], row['away_goals']))
        h2h_stats[h2h_key_away_home].append((row['away_goals'], row['home_goals']))

# Add the new features back into our main dataframe
df['home_win_rate_diff'] = features['home_win_rate_diff']
df['home_gd_diff'] = features['home_gd_diff']

# Drop the very early matches (e.g., a team's first 5 games) because the rolling averages 
# aren't accurate yet since they didn't have enough history.
# For simplicity in this script, we'll just drop rows where both teams have 0 difference.
for key in features.keys():
    df[key] = features[key]

df_clean = df.dropna(subset=['home_win_rate_diff', 'home_gd_diff', 'elo_diff'])
# --- 4. MACHINE LEARNING TRAINING ---
print("4. Training the Random Forest Model...")
# Define our Inputs (X) and Target (y)
X = df_clean[['home_win_rate_diff', 'home_gd_diff', 'elo_diff', 'rest_days_diff', 'match_importance', 'h2h_win_diff', 'h2h_gd_diff']]
y = df_clean['outcome']

# Split data: 80% for training, 20% for testing to see if the model is actually smart
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Create the mathematical model
model = RandomForestClassifier(n_estimators=200, max_depth=6, random_state=42)

# TRAIN IT! (This is where the model finds the patterns)
model.fit(X_train, y_train)

# --- 5. EVALUATION & DEPLOYMENT ---
print("5. Evaluating Accuracy...")
# Ask the model to guess the outcomes of the 20% of data it has never seen
predictions = model.predict(X_test)
accuracy = accuracy_score(y_test, predictions)
print(f"Model Accuracy on unseen matches: {accuracy * 100:.2f}%")
print("\nDetailed Report:\n", classification_report(y_test, predictions))

# Freeze the brain and save it
print("6. Saving the model for the backend to use...")
# We save it directly into the backend folder so FastAPI can find it!
script_dir = os.path.dirname(os.path.abspath(__file__))
target_path = os.path.join(script_dir, '../backend/match_predictor.joblib')

joblib.dump(model, target_path)
print("Complete! The model 'match_predictor.joblib' is now ready in the backend.")

# --- 7. SAVE FINAL ELO RATINGS TO DATABASE ---
print("7. Pushing latest ELO ratings to Supabase...")

# Iterate through our ledger and update the Teams table
for team_id, stats in team_stats.items():
    final_elo = round(stats['elo'], 2) # Round to 2 decimals for clean data
    
    # Update the team's row with their new ELO rating
    supabase.table("Teams").update({"current_elo": final_elo}).eq("team_id", team_id).execute()

print("ELO sync complete! The backend now has live access to team strengths.")
