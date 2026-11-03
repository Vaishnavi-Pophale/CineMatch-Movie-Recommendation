import unittest
import pandas as pd
from model.recommender import MovieRecommender

class RecommenderTests(unittest.TestCase):
    def setUp(self):
        movies = pd.DataFrame([
            {"movieId":1,"title":"Space Hero","genres":"Sci-Fi|Action","overview":"space mission hero","director":"A One","cast":"X|Y","year":2020},
            {"movieId":2,"title":"Galaxy Mission","genres":"Sci-Fi|Adventure","overview":"space alien mission","director":"A One","cast":"X|Z","year":2021},
            {"movieId":3,"title":"Love Story","genres":"Romance|Drama","overview":"love family story","director":"B Two","cast":"M|N","year":2019}
        ])
        ratings = pd.DataFrame([
            {"userId":1,"movieId":1,"rating":5,"timestamp":1},
            {"userId":1,"movieId":3,"rating":2,"timestamp":2},
            {"userId":2,"movieId":2,"rating":4,"timestamp":3}
        ])
        self.model = MovieRecommender(movies, ratings)

    def test_similar_excludes_query(self):
        result = self.model.similar(1, 2)
        self.assertTrue(all(x["movieId"] != 1 for x in result))
        self.assertEqual(result[0]["movieId"], 2)

    def test_unknown_movie(self):
        self.assertEqual(self.model.similar(999), [])

    def test_search_genre(self):
        result = self.model.search(genre="Romance")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["movieId"], 3)

    def test_personalized_excludes_seen(self):
        result = self.model.personalized(1, 5)
        self.assertTrue(all(x["movieId"] not in {1,3} for x in result))

if __name__ == "__main__":
    unittest.main()
