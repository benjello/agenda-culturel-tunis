import unittest
from unittest import mock

from scrapers import commun
from scrapers.sources import facebook


class CleApify(unittest.TestCase):
    def test_cle_dans_en_tete_pas_dans_l_adresse(self):
        reponse = mock.Mock()
        reponse.json.return_value = []
        with mock.patch.object(facebook.requests, "post", return_value=reponse) as post:
            facebook.appeler_apify("acteur/x", {}, "apify_api_SECRET")
        url = post.call_args.args[0]
        self.assertNotIn("apify_api_SECRET", url)
        self.assertNotIn("params", post.call_args.kwargs)
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer apify_api_SECRET")

    def test_masquer_retire_les_jetons(self):
        message = ("HTTPError: 402 Client Error for url: https://api.apify.com/v2/acts/x/run"
                   "?token=apify_api_ABC123&format=json")
        propre = commun.masquer(message)
        self.assertNotIn("ABC123", propre)
        self.assertIn("token=***&format=json", propre)

    def test_masquer_laisse_le_reste(self):
        self.assertEqual(commun.masquer("Read timed out (read timeout=30)"), "Read timed out (read timeout=30)")


if __name__ == "__main__":
    unittest.main()
