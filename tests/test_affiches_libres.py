"""Affiches de films : repli sur Wikidata / Commons / Wikipédia, hors ligne."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scrapers import films, images, wikidata


def entite(**props):
    return {"claims": {p: [{"mainsnak": {"datavalue": {"value": v}}}] for p, v in props.items()}}


class TestAffichesLibres(unittest.TestCase):
    def test_affiche_wikidata_prioritaire(self):
        e = entite(P3383="Paper Tiger poster.jpg", P18="Autre.jpg")
        self.assertEqual(wikidata.affiche(e),
                         "https://commons.wikimedia.org/wiki/Special:FilePath/Paper_Tiger_poster.jpg?width=400")

    def test_image_puis_vignette_wikipedia(self):
        self.assertIn("Autre.jpg", wikidata.affiche(entite(P18="Autre.jpg")))
        e = {"claims": {}, "sitelinks": {"frwiki": {"title": "Paper Tiger"}}}
        with mock.patch.object(wikidata, "vignette_wikipedia", return_value="https://x/v.jpg"):
            self.assertEqual(wikidata.affiche(e), "https://x/v.jpg")

    def test_panne_wikipedia_sans_erreur(self):
        e = {"claims": {}, "sitelinks": {}}
        with mock.patch.object(wikidata, "vignette_wikipedia", side_effect=ValueError):
            self.assertEqual(wikidata.affiche(e), "")

    def test_film_sans_affiche_reprend_celle_de_wikidata(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(images, "DOSSIER", Path(d) / "assets" / "images"), \
                mock.patch.object(images, "RACINE", Path(d)), \
                mock.patch.object(images, "recuperer", return_value=("ok", "", b"\x89PNG....", "png")):
            liste = [{"titre": "A", "image": "", "affiche_libre": "https://c/a.png"},
                     {"titre": "B", "image": "assets/images/b.jpg", "affiche_libre": "https://c/b.png"},
                     {"titre": "C", "image": "", "affiche_libre": ""}]
            films.affiches_libres(liste)
        self.assertTrue(liste[0]["image"].startswith("assets/images/"))
        self.assertEqual(liste[1]["image"], "assets/images/b.jpg")
        self.assertEqual(liste[2]["image"], "")
        self.assertTrue(all("affiche_libre" not in f for f in liste))

    def test_image_introuvable_laisse_le_repli(self):
        with mock.patch.object(images, "recuperer", return_value=("cassee", "HTTP 404", b"", "")):
            liste = [{"titre": "A", "image": "", "affiche_libre": "https://c/a.png"}]
            films.affiches_libres(liste)
        self.assertEqual(liste[0]["image"], "")


if __name__ == "__main__":
    unittest.main()


class TestAffichesTmdb(unittest.TestCase):
    def test_tmdb_remplit_et_garde_en_cache(self):
        import os
        from scrapers import descriptifs as d
        with tempfile.TemporaryDirectory() as t, mock.patch.object(images, "DOSSIER", Path(t) / "assets" / "images"), \
                mock.patch.object(images, "RACINE", Path(t)), mock.patch.object(d, "RACINE", Path(t)), \
                mock.patch.dict(os.environ, {"TMDB_API_KEY": "k"}), \
                mock.patch.object(d, "tmdb_affiche", return_value="https://image.tmdb.org/t/p/w342/a.jpg") as api, \
                mock.patch.object(images, "recuperer", return_value=("ok", "", b"\xff\xd8\xff....", "jpg")):
            cache = {"affiches": {}}
            liste = [{"id": "a", "titre": "A", "image": ""}, {"id": "b", "titre": "B", "image": "x.jpg"}]
            self.assertEqual(d.affiches_tmdb(liste, cache, d.Budget(5, True)), 1)
            self.assertTrue(liste[0]["image"].startswith("assets/images/"))
            self.assertEqual(liste[1]["image"], "x.jpg")
            # passage suivant : films.json refait, l'affiche revient du cache sans nouvel appel
            liste = [{"id": "a", "titre": "A", "image": ""}]
            self.assertEqual(d.affiches_tmdb(liste, cache, d.Budget(5, True)), 1)
            self.assertEqual(api.call_count, 1)

    def test_sans_cle_rien_ne_change(self):
        import os
        from scrapers import descriptifs as d
        with mock.patch.dict(os.environ, {"TMDB_API_KEY": ""}):
            liste = [{"id": "a", "titre": "A", "image": ""}]
            self.assertEqual(d.affiches_tmdb(liste, {"affiches": {}}, d.Budget(5, True)), 0)
