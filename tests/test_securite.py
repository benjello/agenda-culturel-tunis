"""Sécurité : pas de clé d'API dans les fichiers publics, pas de HTML ni de lien dangereux
venu des sources, intégrité de Leaflet sur la carte."""
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests

from scrapers import commun, critiques, ecriture, propositions
from scrapers.commun import image_sure, lien_sur, masquer_secrets, sans_balises
from scrapers.sources import facebook

FUTUR = dt.date.today().year + 1


class Outils(unittest.TestCase):
    def test_masquer_secrets(self):
        msg = ("402 Client Error: Payment Required for url: https://api.apify.com/v2/acts/a~b/"
               "run-sync-get-dataset-items?token=apify_api_SECRET123&x=1")
        self.assertNotIn("SECRET123", masquer_secrets(msg))
        self.assertIn("token=***&x=1", masquer_secrets(msg))
        self.assertNotIn("abc", masquer_secrets("…/find/tt1?api_key=abc&language=fr-FR"))
        self.assertEqual(masquer_secrets("Authorization: Bearer abc.def"), "Authorization: Bearer ***")

    def test_sans_balises(self):
        self.assertEqual(sans_balises('Concert <img src=x onerror="alert(1)">'), 'Concert img src=x onerror="alert(1)"')
        self.assertEqual(sans_balises(["<b>A</b>", "B"]), ["bA/b", "B"])
        self.assertIsNone(sans_balises(None))

    def test_lien_sur(self):
        self.assertEqual(lien_sur(" https://x.tn/a?b=1 "), "https://x.tn/a?b=1")
        for mauvais in ["javascript:alert(1)", "javascript://x.tn/%0aalert(1)", "data:text/html,x",
                        'https://x.tn/" onmouseover="alert(1)', "https://x.tn/<script>", "", None]:
            self.assertEqual(lien_sur(mauvais), "", mauvais)

    def test_image_sure(self):
        self.assertEqual(image_sure("assets/programmes/fb-x/1.jpg"), "assets/programmes/fb-x/1.jpg")
        self.assertEqual(image_sure("https://x.tn/a.jpg"), "https://x.tn/a.jpg")
        for mauvais in ["javascript:alert(1)", "../../x", 'a.jpg" onerror="x']:
            self.assertEqual(image_sure(mauvais), "", mauvais)


class CleApify(unittest.TestCase):
    def test_cle_dans_l_en_tete_pas_dans_l_adresse(self):
        rep = mock.Mock(json=lambda: [])
        with mock.patch.object(requests, "post", return_value=rep) as post:
            facebook.appeler_apify("apify/x", {}, "SECRET")
        self.assertNotIn("SECRET", post.call_args.args[0])
        self.assertNotIn("params", post.call_args.kwargs)
        self.assertEqual(post.call_args.kwargs["headers"], {"Authorization": "Bearer SECRET"})

    def test_erreur_enregistree_sans_cle(self):
        from scrapers import __main__ as principal
        source = {"id": "fb-x", "nom": "X", "scraper": "facebook"}
        erreur = requests.HTTPError("402 Client Error: for url: https://api.apify.com/v2/acts?token=SECRET <b>")
        etat = {}
        with mock.patch.object(principal, "charger_sources", return_value=[source]), \
             mock.patch.object(principal, "lancer", side_effect=erreur), \
             mock.patch.object(principal, "lire_etat", return_value=etat), \
             mock.patch.object(principal, "ecrire_etat"), \
             mock.patch.object(principal.doublons, "marquer", return_value=0), \
             mock.patch.object(principal.festivals, "rattacher", return_value=0), \
             mock.patch.object(principal.films, "ecrire", return_value=0), \
             mock.patch.object(principal.controle, "main"), \
             mock.patch("sys.stderr"):
            principal.main([])
        self.assertNotIn("SECRET", etat["fb-x"]["erreur"])
        self.assertNotIn("<", etat["fb-x"]["erreur"])


class TextesVenusDAilleurs(unittest.TestCase):
    def test_evenement_nettoye(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(ecriture, "DOSSIER_AUTO", Path(d)):
            e = commun.Evenement(titre="Soirée <script>alert(1)</script>", debut=dt.datetime(FUTUR, 11, 7, 20),
                                 lien="javascript:alert(1)", lieu="<b>Le Bar</b>", image="javascript:x",
                                 artistes=["<i>DJ</i>"], description="[clic](javascript:alert(1))")
            ecriture.ecrire_evenements({"id": "src", "nom": "Source"}, [e])
            texte = next(Path(d, "src").glob("*.md")).read_text()
        self.assertNotIn("<", texte)
        self.assertNotIn("link:", texte)
        self.assertNotIn("image:", texte)
        self.assertIn("\\[clic](", texte)  # le Markdown n'en fait pas un lien

    def test_article_de_presse_nettoye(self):
        aujourd_hui = dt.date.today().isoformat()
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "presse.json"
            n = critiques.garder([{"titre": "<img src=x>Expo", "lien": "https://x.tn/a", "date": aujourd_hui},
                                  {"titre": "Piège", "lien": "javascript:alert(1)", "date": aujourd_hui}], f)
            self.assertEqual(n, 1)
            self.assertEqual(json.loads(f.read_text())[0]["titre"], "img src=xExpo")

    def test_proposition_nettoyee(self):
        corps = ("### Titre\n\n<script>x</script>Concert\n\n### Date et heure\n\n2026-11-21 20h30\n\n"
                 "### Lieu\n\nDar <b>Lasram</b>\n\n### Lien\n\njavascript:alert(1)\n\n"
                 "### Description et affiche (facultatif)\n\nVoir [ici](javascript:alert(1)) et [là](https://x.tn).\n\n"
                 '<img src="https://github.com/user-attachments/assets/abc-123" alt="affiche">')
        _, contenu = propositions.evenement(corps)
        self.assertNotIn("<", contenu)
        self.assertNotIn("javascript", contenu)
        self.assertIn('link: ""', contenu)
        self.assertIn('image: "https://github.com/user-attachments/assets/abc-123"', contenu)
        self.assertIn("[là](https://x.tn)", contenu)


class Carte(unittest.TestCase):
    def test_leaflet_avec_integrite(self):
        page = (commun.RACINE / "carte.html").read_text()
        for balise in [l for l in page.splitlines() if "cdnjs.cloudflare.com" in l]:
            self.assertIn('integrity="sha512-', balise)
            self.assertIn('crossorigin="anonymous"', balise)


if __name__ == "__main__":
    unittest.main()
