from pathlib import Path
import random
import pandas as pd

random.seed(42)
OUT = Path(__file__).resolve().parent
genres = ["Action", "Adventure", "Animation", "Comedy", "Crime", "Drama",
          "Fantasy", "Horror", "Mystery", "Romance", "Sci-Fi", "Thriller"]
directors = ["Ava Martin", "Rohan Mehta", "Mia Chen", "Daniel Brooks", "Sara Khan",
             "Noah Patel", "Isha Rao", "Leo Williams"]
actors = ["Aarav Shah", "Emma Wilson", "Kabir Joshi", "Olivia Brown", "Zoya Ali",
          "Liam Davis", "Anaya Kapoor", "Ethan Miller", "Maya Singh", "Ryan Clark"]
story_words = {
    "Action": "hero mission chase rescue danger secret agent",
    "Comedy": "funny friendship family awkward journey laughter",
    "Romance": "love relationship heartbreak wedding emotions",
    "Horror": "haunted house ghost dark mystery nightmare",
    "Sci-Fi": "space future robot technology alien time travel",
    "Drama": "family ambition struggle life emotional journey",
    "Mystery": "detective clues investigation hidden truth",
    "Thriller": "suspense crime danger conspiracy escape",
    "Adventure": "journey treasure exploration survival",
    "Fantasy": "magic kingdom dragon mythical power",
    "Animation": "animated colourful friendship imagination",
    "Crime": "police investigation criminal evidence"
}
adjectives = ["Hidden", "Last", "Eternal", "Silent", "Golden", "Broken", "Midnight",
              "Rising", "Forgotten", "Electric", "Crimson", "Beyond"]
nouns = ["Promise", "Horizon", "Kingdom", "Echo", "Journey", "Secret", "Dream",
         "Shadow", "Empire", "Garden", "Miracle", "Code"]

movies = []
for mid in range(1, 301):
    g = random.sample(genres, random.randint(1, 3))
    title = f"{random.choice(adjectives)} {random.choice(nouns)} ({random.randint(1985, 2025)})"
    words = " ".join(story_words[x] for x in g)
    overview = f"A story about {words} and an unexpected challenge that changes everything."
    movies.append({
        "movieId": mid, "title": title, "genres": "|".join(g),
        "overview": overview, "director": random.choice(directors),
        "cast": "|".join(random.sample(actors, 3)), "year": random.randint(1985, 2025)
    })
movie_df = pd.DataFrame(movies).drop_duplicates("title")
movie_df.to_csv(OUT / "movies.csv", index=False)

ratings = []
for uid in range(1, 101):
    preferred = random.sample(genres, 3)
    for movie in random.sample(movies, random.randint(18, 45)):
        overlap = len(set(movie["genres"].split("|")) & set(preferred))
        score = min(5, max(1, round(random.gauss(3.0 + overlap * 0.65, 0.8) * 2) / 2))
        ratings.append({
            "userId": uid, "movieId": movie["movieId"], "rating": score,
            "timestamp": 1700000000 + random.randint(0, 90000000)
        })
pd.DataFrame(ratings).drop_duplicates(["userId", "movieId"]).to_csv(OUT / "ratings.csv", index=False)
print(f"Generated {len(movie_df)} movies and {len(ratings)} ratings in {OUT}")
