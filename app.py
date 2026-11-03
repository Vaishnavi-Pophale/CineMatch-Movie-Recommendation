from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os, time
from functools import wraps
from config import DB_PATH, SECRET_KEY
from model.recommender import MovieRecommender, MOVIES_FILE, RATINGS_FILE

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["JSON_SORT_KEYS"] = False
recommender = None
request_log = []

def get_model():
    global recommender
    if recommender is None:
        if not MOVIES_FILE.exists() or not RATINGS_FILE.exists():
            raise RuntimeError("Dataset missing. Run: python data/generate_dataset.py")
        recommender = MovieRecommender()
    return recommender


def build_chat_reply(message, model, user_id=None):
    """Simple local movie assistant; uses the project's recommender and needs no API key."""
    import re
    text = (message or "").strip()
    lower = text.lower()
    if not text:
        return {"reply": "Type a movie question and I'll help you find something to watch.", "movies": []}

    def pack(items):
        return [{"movieId": int(x.get("movieId", 0)), "title": str(x.get("title", "")),
                 "year": int(x.get("year", 0) or 0), "genres": str(x.get("genres", "")),
                 "overview": str(x.get("overview", ""))[:180],
                 "reason": str(x.get("reason", ""))} for x in items]

    if any(word in lower for word in ["hello", "hi", "hey", "good morning", "good evening"]):
        return {"reply": "Hey! 🎬 I'm CineBot. I can recommend movies, find films by genre, suggest movies similar to a title, or show popular picks. What are you in the mood for?", "movies": []}

    if any(word in lower for word in ["help", "what can you do", "how to use"]):
        return {"reply": "Try asking me things like:\n• Recommend comedy movies\n• I feel bored / I want something exciting\n• Start movie quiz / Surprise me\n• Suggest movies similar to Inception\n• Recommend based on my ratings\n• Add Inception to my watchlist\n• Search movies about space\nYou can also use the microphone, clear the chat, or tap a quick suggestion.", "movies": []}

    if any(word in lower for word in ["popular", "trending", "top rated", "best movies", "top movies"]):
        items = model.top_rated(5)
        return {"reply": "Here are some popular, highly rated picks from the CineMatch catalogue:", "movies": pack(items)}

    # Mood-based discovery and interactive movie quiz.
    mood_map = {
        "happy": ["Comedy", "Animation", "Adventure"],
        "sad": ["Drama", "Romance"],
        "romantic": ["Romance"],
        "scared": ["Horror", "Thriller"],
        "excited": ["Action", "Adventure", "Sci-Fi"],
        "bored": ["Mystery", "Thriller", "Comedy"],
        "relaxed": ["Comedy", "Documentary", "Romance"],
        "thoughtful": ["Drama", "Mystery", "Sci-Fi"],
        "motivated": ["Drama", "Adventure"]
    }
    mood_aliases = {
        "laugh": "happy", "funny": "happy", "exciting": "excited", "excitement": "excited",
        "adrenaline": "excited", "romance": "romantic", "love": "romantic",
        "suspense": "scared", "scary": "scared", "chill": "relaxed", "calm": "relaxed",
        "inspired": "motivated", "motivation": "motivated", "boredom": "bored"
    }
    mood = next((key for key in mood_map if key in lower), None)
    if mood is None:
        alias = next((key for key in mood_aliases if key in lower), None)
        mood = mood_aliases.get(alias) if alias else None
    if mood and any(word in lower for word in ["mood", "feel", "feeling", "i am", "i'm", "want", "something", "movie", "recommend"]):
        picks = []
        for genre in mood_map[mood]:
            picks.extend(model.search(genre=genre, limit=4))
        unique = {int(x["movieId"]): x for x in picks}
        items = list(unique.values())[:5]
        return {"reply": f"If you're feeling {mood}, here are some {', '.join(mood_map[mood])} picks. 🎭", "movies": pack(items), "suggestions": ["Surprise me", "Show popular movies", "Start movie quiz"]}

    if any(term in lower for term in ["movie quiz", "start quiz", "help me choose", "what should i watch"]):
        return {"reply": "Let's find your next movie! What kind of experience do you want right now?", "movies": [], "suggestions": ["I want to laugh", "I want excitement", "I want romance", "I want suspense", "I want something thoughtful"]}

    if any(term in lower for term in ["surprise me", "random movie", "pick for me", "choose for me"]):
        import random
        candidates = model.top_rated(min(30, len(model.movies)))
        chosen = random.choice(candidates) if candidates else []
        return {"reply": "Surprise! Here's a movie picked for you. 🍿", "movies": pack([chosen] if chosen else [])}

    if any(term in lower for term in ["my taste", "based on my ratings", "based on my rating", "for me", "personalized"]):
        if not user_id:
            return {"reply": "Log in and rate a few movies first. Then I can personalize recommendations using your ratings.", "movies": [], "suggestions": ["Show popular movies", "Recommend comedy movies"]}
        with db() as con:
            rows = con.execute("SELECT movie_id,rating FROM ratings WHERE user_id=?", (user_id,)).fetchall()
        extras = [{"userId": user_id, "movieId": r["movie_id"], "rating": r["rating"]} for r in rows]
        return {"reply": "Here are recommendations based on your ratings and movie taste:", "movies": pack(model.personalized(user_id, 5, extra_ratings=extras))}

    # Add a named movie to the signed-in user's watchlist.
    if "watchlist" in lower and any(word in lower for word in ["add", "save", "put"]):
        if not user_id:
            return {"reply": "Please log in first, then I can save movies to your watchlist.", "movies": []}
        cleaned = re.sub(r"\b(add|save|put|to|in|my|the|watchlist|please)\b", " ", text, flags=re.I).strip(" \"'.,!?")
        matches = model.search(cleaned, limit=1) if cleaned else []
        if not matches:
            return {"reply": "Which movie should I add? Type its title, for example: Add Inception to my watchlist.", "movies": []}
        movie_id = int(matches[0]["movieId"])
        with db() as con:
            con.execute("INSERT OR IGNORE INTO watchlist(user_id,movie_id) VALUES(?,?)", (user_id, movie_id))
        return {"reply": f"Added {matches[0]['title']} to your watchlist! ✅", "movies": pack(matches)}

    # Similar-title requests: locate a movie title mentioned after a cue phrase.
    similar_cues = ["similar to", "like", "movies like", "same as", "related to"]
    if any(cue in lower for cue in similar_cues):
        cleaned = lower
        for cue in similar_cues:
            cleaned = cleaned.replace(cue, " ")
        cleaned = re.sub(r"[^a-z0-9 ]", " ", cleaned)
        candidates = model.search(cleaned.strip(), limit=1) if cleaned.strip() else []
        if not candidates:
            # Try matching the longest title contained in the user's message.
            matches = model.movies[model.movies.title.apply(lambda t: str(t).lower() in lower)]
            candidates = matches.head(1).drop(columns=["soup"]).to_dict("records")
        if candidates:
            base = candidates[0]
            items = model.similar(int(base["movieId"]), 5)
            return {"reply": f"If you enjoyed {base['title']}, you may also like these movies:", "movies": pack(items)}

    # Genre recommendation. Match against genres actually present in the dataset.
    genres = sorted({g.strip() for value in model.movies.genres.astype(str) for g in value.split("|") if g.strip()}, key=len, reverse=True)
    matched_genre = next((g for g in genres if g.lower() in lower), None)
    recommendation_words = ["recommend", "suggest", "movie", "movies", "watch", "something", "film", "films"]
    if matched_genre and any(word in lower for word in recommendation_words):
        if user_id:
            with db() as con:
                rows = con.execute("SELECT movie_id,rating FROM ratings WHERE user_id=?", (user_id,)).fetchall()
            extras = [{"userId": user_id, "movieId": r["movie_id"], "rating": r["rating"]} for r in rows]
            items = model.personalized(user_id, 5, extra_ratings=extras, genre=matched_genre)
        else:
            items = model.search(genre=matched_genre, limit=5)
            items = [model._format(model.movies[model.movies.movieId == int(x["movieId"])].iloc[0], 0, f"{matched_genre} genre match") for x in items]
        return {"reply": f"Here are {matched_genre} movies you can explore:", "movies": pack(items)}

    # General catalogue search, based on title or plot keywords.
    stop = {"find", "show", "me", "some", "movie", "movies", "about", "with", "recommend", "suggest", "please", "search", "for", "watch", "a", "an", "the"}
    terms = [w for w in re.findall(r"[a-z0-9]+", lower) if w not in stop]
    query = " ".join(terms)
    results = model.search(query, limit=5) if query else []
    if results:
        return {"reply": "I found these matches in the movie catalogue:", "movies": pack(results)}

    return {"reply": "I can help with movie recommendations, genres, popular picks, similar movies, and catalogue searches. Try: ‘Recommend action movies’ or ‘Movies similar to Inception’. You can also type ‘help’ to see examples.", "movies": []}

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
          email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS ratings(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
          movie_id INTEGER NOT NULL, rating REAL NOT NULL CHECK(rating >= 1 AND rating <= 5),
          UNIQUE(user_id, movie_id));
        CREATE TABLE IF NOT EXISTS watchlist(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
          movie_id INTEGER NOT NULL, UNIQUE(user_id, movie_id));
        ''')

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to use this feature.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped

@app.before_request
def track_request():
    request_log.append({"time": time.strftime("%H:%M:%S"), "path": request.path})
    if len(request_log) > 200:
        del request_log[:-200]

@app.route("/")
def index():
    m = get_model()
    q, genre = request.args.get("q", ""), request.args.get("genre", "")
    year_from, year_to = request.args.get("year_from"), request.args.get("year_to")
    movies = m.search(q, genre, year_from, year_to, 60)
    genres = sorted({g for item in m.movies.genres for g in str(item).split("|")})
    return render_template("index.html", movies=movies, genres=genres, q=q, selected_genre=genre,
                           trending=m.top_rated(6))

@app.route("/movie/<int:movie_id>", methods=["GET", "POST"])
def movie_detail(movie_id):
    m = get_model()
    movie = m.get_movie(movie_id)
    if not movie:
        flash("Movie not found.", "danger")
        return redirect(url_for("index"))
    if request.method == "POST":
        if "user_id" not in session:
            flash("Log in to rate a movie.", "warning")
            return redirect(url_for("login"))
        rating = float(request.form.get("rating", 0))
        if not 1 <= rating <= 5:
            flash("Choose a rating from 1 to 5.", "danger")
        else:
            with db() as con:
                con.execute("INSERT INTO ratings(user_id,movie_id,rating) VALUES(?,?,?) "
                            "ON CONFLICT(user_id,movie_id) DO UPDATE SET rating=excluded.rating",
                            (session["user_id"], movie_id, rating))
            flash("Your rating has been saved.", "success")
        return redirect(url_for("movie_detail", movie_id=movie_id))
    return render_template("movie.html", movie=movie, similar=m.similar(movie_id, 8))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username, email = request.form.get("username", "").strip(), request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if len(username) < 3 or "@" not in email or len(password) < 8:
            flash("Use a username (3+ chars), valid email and password (8+ chars).", "danger")
        else:
            try:
                with db() as con:
                    con.execute("INSERT INTO users(username,email,password_hash) VALUES(?,?,?)",
                                (username, email, generate_password_hash(password)))
                flash("Account created. Please log in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Username or email already exists.", "danger")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identity, password = request.form.get("identity", "").strip(), request.form.get("password", "")
        with db() as con:
            user = con.execute("SELECT * FROM users WHERE username=? OR email=?", (identity, identity.lower())).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"], session["username"] = user["id"], user["username"]
            flash("Welcome back!", "success")
            return redirect(url_for("dashboard"))
        flash("Incorrect username/email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    m = get_model()
    with db() as con:
        rows = con.execute("SELECT movie_id,rating FROM ratings WHERE user_id=?", (session["user_id"],)).fetchall()
    extra = [{"userId": session["user_id"], "movieId": r["movie_id"], "rating": r["rating"]} for r in rows]
    recs = m.personalized(session["user_id"], 12, extra_ratings=extra)
    rated = []
    for r in rows:
        movie = m.get_movie(r["movie_id"])
        if movie:
            movie["my_rating"] = r["rating"]
            rated.append(movie)
    return render_template("dashboard.html", recommendations=recs, rated=rated)

@app.route("/watchlist")
@login_required
def watchlist():
    with db() as con:
        rows = con.execute("SELECT movie_id FROM watchlist WHERE user_id=?", (session["user_id"],)).fetchall()
    items = [get_model().get_movie(r["movie_id"]) for r in rows]
    return render_template("watchlist.html", movies=[x for x in items if x])

@app.post("/watchlist/<int:movie_id>")
@login_required
def toggle_watchlist(movie_id):
    if not get_model().get_movie(movie_id):
        return jsonify({"error": "Movie not found"}), 404
    with db() as con:
        exists = con.execute("SELECT id FROM watchlist WHERE user_id=? AND movie_id=?",
                             (session["user_id"], movie_id)).fetchone()
        if exists:
            con.execute("DELETE FROM watchlist WHERE user_id=? AND movie_id=?", (session["user_id"], movie_id))
            status = "removed"
        else:
            con.execute("INSERT INTO watchlist(user_id,movie_id) VALUES(?,?)", (session["user_id"], movie_id))
            status = "added"
    flash(f"Movie {status} to your watchlist.", "success")
    return redirect(request.referrer or url_for("index"))

@app.post("/api/chat")
def api_chat():
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", ""))[:500]
    try:
        result = build_chat_reply(message, get_model(), session.get("user_id"))
        return jsonify(result)
    except Exception as exc:
        app.logger.exception("Chatbot request failed")
        return jsonify({"reply": "Sorry, I couldn't process that just now. Please try another movie question.", "movies": []}), 500

@app.route("/api/health")
def api_health():
    m = get_model()
    return jsonify({"status": "healthy", "service": "CineMatch", "movies": len(m.movies),
                    "model": "TF-IDF + cosine similarity + popularity blend"})

@app.route("/api/movies")
def api_movies():
    return jsonify(get_model().search(request.args.get("q", ""), request.args.get("genre", ""), limit=100))

@app.route("/api/recommend/movie/<int:movie_id>")
def api_similar(movie_id):
    if not get_model().get_movie(movie_id):
        return jsonify({"error": "Movie not found"}), 404
    return jsonify({"query": get_model().get_movie(movie_id), "recommendations": get_model().similar(movie_id, request.args.get("n", 10))})

@app.route("/api/recommend/user/<int:user_id>")
def api_user_recs(user_id):
    return jsonify({"user_id": user_id, "recommendations": get_model().personalized(user_id, request.args.get("n", 10))})

@app.route("/api/metrics")
def api_metrics():
    m = get_model()
    return jsonify({"movie_count": len(m.movies), "rating_count": len(m.ratings),
                    "genre_count": len({g for s in m.movies.genres for g in str(s).split("|")}),
                    "tracked_requests": len(request_log)})

@app.route("/api/monitoring")
def api_monitoring():
    return jsonify({"request_count": len(request_log), "recent_requests": request_log[-20:]})

@app.errorhandler(500)
def server_error(_):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=8000, debug=True)
