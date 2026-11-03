from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

BASE = Path(__file__).resolve().parents[1]
MOVIES_FILE = BASE / "data" / "movies.csv"
RATINGS_FILE = BASE / "data" / "ratings.csv"
ARTIFACT = BASE / "model" / "recommender.joblib"

class MovieRecommender:
    def __init__(self, movies=None, ratings=None):
        self.movies = movies.copy() if movies is not None else pd.read_csv(MOVIES_FILE)
        self.ratings = ratings.copy() if ratings is not None else pd.read_csv(RATINGS_FILE)
        self._prepare()

    def _prepare(self):
        required = {"movieId", "title", "genres", "overview", "director", "cast", "year"}
        missing = required - set(self.movies.columns)
        if missing:
            raise ValueError(f"movies.csv missing columns: {sorted(missing)}")
        self.movies = self.movies.drop_duplicates("movieId").fillna("")
        self.movies["movieId"] = self.movies["movieId"].astype(int)
        self.movies["year"] = pd.to_numeric(self.movies["year"], errors="coerce").fillna(0).astype(int)
        for col in ["genres", "overview", "director", "cast", "title"]:
            self.movies[col] = self.movies[col].astype(str).fillna("")
        self.movies["soup"] = (
            self.movies["genres"].str.replace("|", " ", regex=False).str.lower() + " " +
            self.movies["genres"].str.replace("|", " ", regex=False).str.lower() + " " +
            self.movies["director"].str.replace(" ", "", regex=False).str.lower() + " " +
            self.movies["cast"].str.replace("|", " ", regex=False).str.replace(" ", "", regex=False).str.lower() + " " +
            self.movies["overview"].str.lower()
        )
        self.vectorizer = TfidfVectorizer(stop_words="english", sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform(self.movies["soup"])
        self.similarity = cosine_similarity(self.matrix, dense_output=True)
        self.id_to_idx = {int(mid): i for i, mid in enumerate(self.movies["movieId"])}
        if not self.ratings.empty:
            self.ratings = self.ratings.dropna(subset=["userId", "movieId", "rating"])
            self.ratings["movieId"] = self.ratings["movieId"].astype(int)
            self.ratings["rating"] = pd.to_numeric(self.ratings["rating"], errors="coerce").fillna(0)
            self.ratings = self.ratings[self.ratings["movieId"].isin(self.id_to_idx)]
        self.popularity = self.ratings.groupby("movieId").agg(
            rating_count=("rating", "count"), avg_rating=("rating", "mean")
        ) if not self.ratings.empty else pd.DataFrame()
        self.max_count = max(1, int(self.popularity["rating_count"].max())) if not self.popularity.empty else 1

    def all_movies(self):
        return self.movies.drop(columns=["soup"]).to_dict("records")

    def get_movie(self, movie_id):
        row = self.movies[self.movies.movieId == int(movie_id)]
        return None if row.empty else row.iloc[0].drop(labels=["soup"]).to_dict()

    def search(self, q="", genre="", year_from=None, year_to=None, limit=100):
        df = self.movies
        if q:
            df = df[df.title.str.contains(q, case=False, na=False) | df.overview.str.contains(q, case=False, na=False)]
        if genre:
            df = df[df.genres.str.contains(genre, case=False, na=False)]
        if year_from:
            df = df[df.year >= int(year_from)]
        if year_to:
            df = df[df.year <= int(year_to)]
        return df.drop(columns=["soup"]).head(limit).to_dict("records")

    def _pop_score(self, movie_id):
        if self.popularity.empty or movie_id not in self.popularity.index:
            return 0.0
        row = self.popularity.loc[movie_id]
        # Smooth popularity so one rating does not dominate.
        return float((row.avg_rating / 5.0) * (row.rating_count / self.max_count))

    def similar(self, movie_id, n=10):
        movie_id = int(movie_id)
        if movie_id not in self.id_to_idx:
            return []
        idx = self.id_to_idx[movie_id]
        scores = self.similarity[idx]
        ranked = np.argsort(scores)[::-1]
        output = []
        for j in ranked:
            candidate = self.movies.iloc[int(j)]
            if int(candidate.movieId) == movie_id:
                continue
            score = float(scores[j])
            output.append(self._format(candidate, score, "Content similarity"))
            if len(output) >= int(n):
                break
        return output

    def personalized(self, user_id, n=10, extra_ratings=None, genre=None):
        user_id = int(user_id)
        history = self.ratings[self.ratings.userId == user_id].copy() if not self.ratings.empty else pd.DataFrame()
        if extra_ratings:
            extra = pd.DataFrame(extra_ratings)
            if not extra.empty:
                history = pd.concat([history, extra], ignore_index=True)
        if history.empty:
            candidates = self.movies.copy()
            candidates["score"] = candidates.movieId.map(lambda x: self._pop_score(int(x)))
            reason = "Popular starter picks — rate movies to personalize your results"
        else:
            liked = history[history.rating >= 3.5]
            seen = set(history.movieId.astype(int))
            if liked.empty:
                liked = history.nlargest(min(5, len(history)), "rating")
            weighted = []
            weights = []
            for row in liked.itertuples():
                idx = self.id_to_idx.get(int(row.movieId))
                if idx is not None:
                    weighted.append(self.matrix[idx].toarray().ravel())
                    weights.append(max(0.1, float(row.rating) - 2.5))
            if weighted:
                profile = np.average(np.vstack(weighted), axis=0, weights=weights)
                norm = np.linalg.norm(profile)
                if norm:
                    profile = profile / norm
                content_scores = self.matrix.dot(profile).ravel()
            else:
                content_scores = np.zeros(len(self.movies))
            candidates = self.movies[~self.movies.movieId.isin(seen)].copy()
            candidates["content_score"] = candidates.index.map(lambda i: float(content_scores[i]))
            candidates["pop_score"] = candidates.movieId.map(lambda x: self._pop_score(int(x)))
            candidates["score"] = 0.82 * candidates.content_score + 0.18 * candidates.pop_score
            reason = "Matched to your highly rated movies, with a popularity boost"
        if genre:
            candidates = candidates[candidates.genres.str.contains(genre, case=False, na=False)]
        candidates = candidates.sort_values("score", ascending=False).head(int(n))
        return [self._format(row, float(row.score), reason) for _, row in candidates.iterrows()]

    def top_rated(self, n=10):
        if self.popularity.empty:
            return self.movies.head(n).apply(lambda r: self._format(r, 0, "Catalogue pick"), axis=1).tolist()
        stats = self.popularity.copy()
        stats["score"] = stats.avg_rating * np.log1p(stats.rating_count)
        ids = stats.sort_values("score", ascending=False).head(n).index
        return [self._format(self.movies[self.movies.movieId == int(mid)].iloc[0],
                             float(stats.loc[mid, "avg_rating"]) / 5, "Highly rated by users")
                for mid in ids if not self.movies[self.movies.movieId == int(mid)].empty]

    def _format(self, row, score, reason):
        d = row.drop(labels=["soup"], errors="ignore").to_dict() if hasattr(row, "drop") else dict(row)
        d["score"] = round(float(score), 4)
        d["reason"] = reason
        d["genres_list"] = str(d.get("genres", "")).split("|")
        return d

def train_and_save():
    model = MovieRecommender()
    joblib.dump(model, ARTIFACT)
    print(f"Model ready: {len(model.movies)} movies. Saved to {ARTIFACT}")

if __name__ == "__main__":
    train_and_save()
