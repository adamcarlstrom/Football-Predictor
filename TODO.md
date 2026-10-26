# TODO

- [ ] **Shared feature module.** Feature engineering is duplicated in three places: `ml_pipeline/train_model.py`, `fetch_and_predict()` and `run_local_prediction()` in `backend/backend.py`. Move it into one module that training and both prediction paths import, so they can't drift apart. This includes the match-importance mapping, which the backend currently hardcodes inline instead of reusing `get_match_importance()`.
