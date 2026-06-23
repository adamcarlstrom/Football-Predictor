# World Cup Predictor & Tournament Simulator

## Overview

Motivated by a bracket-prediction competition with friends and family during the 2026 World Cup, this project was built to leverage data engineering and machine learning to gain a predictive edge.

Rather than relying on basic score guessing, this application is a fully autonomous, full-stack Machine Learning platform. It ingests historical international match data, trains a Random Forest model, calculates Expected Goals (xG) using a Poisson distribution, and deterministically maps out the entire 48-team tournament bracket based on strict FIFA regulations.

## Core Features

* Machine Learning Predictions: Predicts match outcomes (Win/Draw/Loss) using historical Elo ratings, 10-game form, rest days, and Head-to-Head (H2H) records.

* Statistical Scorelines: Utilizes a Poisson distribution to convert ML probabilities into realistic, discrete scorelines (e.g., 3-1).

* Cache-First Architecture: An efficient ETL pipeline that minimizes third-party API costs by dynamically saving, fetching, and semi-automatically updating live fixtures in a PostgreSQL database.

* Deterministic Bracket Simulator: A custom DFS Backtracking algorithm that resolves FIFA's Annex C 3rd-place advancing rules to generate an accurate Knockout tree.

* Responsive UI: A tabbed dashboard built with React and CSS Grid to view daily fixtures and simulate the full tournament.

## Architecture & Modules

This repository is organized into three main modules. Detailed technical documentation for each can be found below:

* Frontend (React + Vite): The user interface and client-side logic.

* Backend (FastAPI): The API gateway, database communicator, and mathematical engine.

* ML Pipeline (Python): The training environment, feature engineering, and data seeding scripts.

## Tech Stack

* Frontend: React, TypeScript, Vite, CSS Grid

* Backend: Python, FastAPI, Uvicorn, Requests

* Database: Supabase (PostgreSQL)

* Machine Learning: Scikit-Learn, Pandas, NumPy, Joblib

* External Data: API-Football (RapidAPI)

### Quick Start

Clone the repository: ```git clone https://github.com/yourusername/football-predictor.git```

Set up your ```.env file with your SUPABASE_URL, SUPABASE_KEY, and FOOTBALL_API_KEY.```

Start the backend: ```cd backend && uvicorn backend:app --reload```

Start the frontend: ```cd frontend && npm run dev```
