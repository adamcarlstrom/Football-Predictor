# Backend: FastAPI & Algorithms

The backend acts as the gateway between the React frontend, the Supabase PostgreSQL database, the pre-trained Machine Learning model, and the third-party football data provider.

## Tech Stack

* Framework: FastAPI (Python)

* Database: Supabase (PostgreSQL) via supabase-py

* Math/Logic: Math (Poisson), Pandas

## Core Architecture

### The Cache-First API Design

To bypass restrictive rate limits on external data providers, the /api/matches endpoint employs a Cache-First Architecture:

* It queries the Supabase database for matches matching the requested date window.

* If data exists locally, it serves it immediately to reduce token usage.

* Semi-Automatic Auto-Updater: If a match in the database is marked as "Not Started" but the current UTC time is > 3 hours past kickoff, the backend autonomously fetches the final score, updates the database, and returns the fresh data to the client.

### Live Feature Engineering & Model Inference

When the /api/matches/{id}/predict endpoint is called, the backend dynamically queries Supabase to engineer live features for the Random Forest model:

* Calculates 10-game rolling averages (Win Rate, Goal Difference, Goals For, Goals Against).

* Isolates Head-to-Head (H2H) match history between the two specific teams.

* Calculates Elo rating differentials and exact rest days.
These features are piped into the .joblib ML model to output exact Win/Draw/Loss probabilities.

### Expected Goals (xG) via Poisson Distribution

To translate percentage probabilities into discrete scorelines, the backend features a generate_poisson_scoreline() algorithm.

* Averages a team's 10-game offensive output with their opponent's defensive weakness, blended with historical H2H goals.

* Scales this baseline Expected Goals (lambda) based on the ML model's confidence.

* Iterates through a 7x7 grid to find the highest-probability valid scoreline.

### DFS Backtracking Knockout Simulator

Simulating the Group Stage is deterministic (Points -> GD -> GF). However, mapping the Round of 32 in the expanded 2026 format requires assigning the 8 best 3rd-place teams based on FIFA's Annex C rules (495 possible combinations).
The backend utilizes a Depth-First Search (DFS) Constraint Satisfaction Algorithm to recursively test group combinations and slot advancing teams into valid matchups, guaranteeing a mathematically sound tournament bracket.
