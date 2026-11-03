# CineMatch — Movie Suggestion System

A runnable content-based + hybrid movie recommender built with Python, Flask, Pandas and scikit-learn.

## Features
- Movie catalogue search and genre/year filters
- Similar-movie recommendations using TF-IDF + cosine similarity
- Personalized hybrid recommendations using ratings, content similarity and popularity
- User registration/login (password hashes)
- 1–5 star ratings and personal watchlist
- Trending/top-rated sections
- Recommendation explanations
- Metrics and health/monitoring API endpoints
- Unit tests

> The included dataset is synthetic/demo data. Replace it with a properly licensed dataset for real-world evaluation. Do not present demo metrics as real-user results.

## 1. Setup (Windows PowerShell)
```powershell
cd CineMatch
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```
If `py -3.11` is unavailable, use `python -m venv .venv`.

## 2. Generate data and train
```powershell
python data/generate_dataset.py
python -m model.recommender
```

## 3. Run the website
```powershell
python app.py
```
Open http://127.0.0.1:8000

## 4. Demo account
Register your own account from the website. No default password is shipped.

## 5. Run tests
With the server not required:
```powershell
python -m unittest discover -s tests -v
```

## Project structure
```text
CineMatch/
├── app.py
├── config.py
├── requirements.txt
├── data/
│   └── generate_dataset.py
├── model/
│   ├── __init__.py
│   └── recommender.py
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── movie.html
│   ├── dashboard.html
│   └── watchlist.html
├── static/
│   ├── css/style.css
│   └── js/app.js
└── tests/
    └── test_recommender.py
```

## Dataset format
`data/movies.csv`: movieId,title,genres,overview,director,cast,year
`data/ratings.csv`: userId,movieId,rating,timestamp

Genres and cast are pipe-separated. You can replace the generated CSVs with compatible, licensed data.

## Important notes
- SQLite stores accounts, ratings and watchlists locally in `cinematch.db`.
- Passwords are stored as Werkzeug hashes, not plain text.
- Set a strong `SECRET_KEY` environment variable before deployment.
- This is a student project starter, not a production-hardened streaming service.


## CineBot chatbot
A floating chat assistant is included on every page. It can answer greetings/help, recommend popular movies, filter recommendations by genre, find similar movies by title, and search the catalogue using plot/title keywords. It calls the local `/api/chat` Flask endpoint and reuses the TF-IDF/cosine-similarity recommender. No paid API key or internet connection is required for chatbot replies. Sign in to let genre recommendations use your saved ratings.

Example prompts: `Recommend action movies`, `Show popular movies`, `Movies similar to Inception`, `Find movies about space`, `help`.
