# Core Pipeline

## Data Aggregation & Seeding (seed_tournament.py)

To map out the future tournament, an intelligent seeder script is used.

* Takes human-readable group assignments and autonomously maps them to official API IDs.

* If a team doesn't exist locally, it dynamically queries the API to fetch their metadata and saves it to the database on the fly.

* Prevents data duplication by cross-referencing Supabase before executing upsert operations.

## Feature Engineering

The model avoids data leakage by calculating features strictly prior to a match's kickoff. The core features engineered into the DataFrame include:

* Elo Differential: A custom-scaled rating system initialized to reflect global hierarchies.

* 10-Game Rolling Form: Calculates a team's recent Win Rate and Goal Difference average to capture momentum.

* Head-to-Head (H2H) Metrics: Scans the ledger for the last 3 matchups specifically between opposing teams to account for historical records.

* Rest Days: Computes the exact time elapsed since a team's previous match to account for fatigue.

* Tournament Importance: Weights games based on context, differentiating World Cup games from international friendlies.

## Model Training & Export

The cleaned Pandas DataFrame is split into training and testing sets.

* The data is passed into a Random Forest Classifier.

* A Random Forest was chosen because it handles non-linear relationships effectively, such as the compounding effect of high Elo combined with high rest days.

* The trained model is serialized into a match_predictor.joblib file, which is imported by the FastAPI backend to perform local inference without relying on external cloud APIs.
