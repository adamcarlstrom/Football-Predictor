# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Full-stack 2026 World Cup predictor: a React/Vite frontend, a single-file FastAPI backend, and offline ML pipeline scripts. All three share one Supabase (PostgreSQL) database and the API-Football (api-sports.io) data source. There is no test suite.

## Commands

A Python virtualenv lives at the repo root (`.venv/`), installed from `backend/requirements.txt` (which also covers the pipeline scripts). `scikit-learn` is pinned because `match_predictor.joblib` is a pickle: if you retrain with a different version, update the pin to match.

```bash
# Backend (serves on http://127.0.0.1:8000, which the frontend hardcodes)
cd backend && ../.venv/bin/uvicorn backend:app --reload

# Frontend
cd frontend && npm install
npm run dev      # Vite dev server
npm run build    # tsc -b && vite build (this is the type check)
npm run lint     # eslint

# ML pipeline (run from ml_pipeline/; each script writes to Supabase)
../.venv/bin/python fetch_history.py     # pull historical international matches from API-Football into Matches/Teams
../.venv/bin/python seed_tournament.py   # insert 2026 World Cup group fixtures
../.venv/bin/python train_model.py       # train RandomForest, write backend/match_predictor.joblib, push Elo to Teams
```

Each module has its own `.env` (`backend/.env`, `ml_pipeline/.env`; `load_dotenv()` searches upward from the script's folder, so a root `.env` is the fallback) with `SUPABASE_URL`, `SUPABASE_KEY`, `FOOTBALL_API_KEY`. API-Football calls cost quota, so avoid running scripts or endpoints that hit it without reason.

## Architecture

### Data flow
1. `fetch_history.py` fills the `Matches` and `Teams` tables (Supabase table names are capitalized). `TOURNAMENT_MAP` picks which league/season pairs to fetch.
2. `train_model.py` replays all finished matches (`FT`/`AET`/`PEN`) in date order, building features with no leakage (stats are read before the match updates them). It trains the model, writes `backend/match_predictor.joblib` (committed to git), and writes each team's final Elo to `Teams.current_elo`.
3. `backend/backend.py` loads the joblib at startup and rebuilds the same features live from Supabase at request time.

### Train/serve feature parity (the main pitfall)
Feature engineering exists in **three places** that must stay in sync:
- `ml_pipeline/train_model.py`: the training ledger (`features` dict, `get_match_importance`, Elo update)
- `backend/backend.py` `fetch_and_predict()`: the per-match `/predict` endpoint
- `backend/backend.py` `run_local_prediction()`: used by the group and knockout simulators

The model expects exactly these 7 columns in this order: `home_win_rate_diff, home_gd_diff, elo_diff, rest_days_diff, match_importance, h2h_win_diff, h2h_gd_diff`. Class labels: 0 = home win, 1 = draw (penalty shootouts count as draws), 2 = away win. If you add or change a feature, change all three places and retrain. Live Elo comes from `Teams.current_elo` (default 1500), so Elo is only as fresh as the last training run.

### Placeholder matches (`match_id >= 8000000`)
`seed_tournament.py` inserts World Cup fixtures with IDs starting at 8000000 so they can't clash with real API-Football IDs. The backend treats any ID at or above that as a "fake" match: `/predict` skips the API fixture lookup for it, and when the real fixture arrives from the API the fake row (and its `Predictions`) gets deleted. Keep this convention if you touch seeding or match syncing.

### Backend endpoints (`backend/backend.py`)
- `GET /api/matches?date=`: cache-first. Serves from Supabase. If a stored match is still unfinished 3 to 48 hours after kickoff, it fetches the result from API-Football and updates the row. It calls the API for the whole date only on a cache miss, or when the date is yesterday/today/tomorrow and placeholder matches are present. It also deletes duplicate matchups, keeping the lower (real) ID.
- `GET /api/api_update_call?date=`: force-refresh a date from API-Football.
- `POST /api/matches/{id}/predict`: fetch fixture, build features, predict, store in `Predictions`.
- `GET /api/tournament/groups`: group standings (Points, then GD, then GF), filling unplayed matches with model predictions.
- `POST /api/tournament/knockout`: builds the Round of 32. It assigns the 8 best third-placed teams to slots via DFS backtracking over FIFA Annex C constraints, then simulates the bracket.
- `generate_poisson_scoreline()`: turns W/D/L probabilities plus 10-game GF/GA (blended with H2H) into the most likely scoreline on a 7x7 grid, consistent with the predicted outcome.

### Frontend
Nearly everything is in `frontend/src/App.tsx` (tabs: daily fixtures and tournament simulator), using plain `fetch` against hardcoded `http://127.0.0.1:8000`. The backend allows all CORS origins.
