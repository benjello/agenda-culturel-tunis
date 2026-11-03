"""PWA : le manifeste, les icônes et le service worker restent cohérents.

  python3 -m unittest tests.test_pwa -v
"""
import json
import re
import unittest

from PIL import Image

from scrapers.commun import RACINE


def manifeste():
    texte = (RACINE / "manifest.webmanifest").read_text(encoding="utf-8")
    texte = re.sub(r"^---.*?---\n", "", texte, flags=re.S)
    texte = re.sub(r"\{\{\s*'([^']*)'\s*\|\s*relative_url\s*\}\}", r"\1", texte)
    texte = re.sub(r"\{\{[^}]*\}\}", "x", texte)
    return json.loads(texte)


class TestPwa(unittest.TestCase):
    def test_champs_installabilite(self):
        m = manifeste()
        for champ in ("name", "short_name", "start_url", "display", "icons"):
            self.assertIn(champ, m)
        self.assertEqual(m["display"], "standalone")

    def test_icones_existent_et_ont_la_bonne_taille(self):
        m = manifeste()
        usages = {(i["purpose"], i["sizes"]) for i in m["icons"]}
        for but in ("any", "maskable"):
            for taille in ("192x192", "512x512"):
                self.assertIn((but, taille), usages)
        for i in m["icons"]:
            chemin = RACINE / i["src"].lstrip("/")
            self.assertTrue(chemin.exists(), chemin)
            self.assertEqual("%dx%d" % Image.open(chemin).size, i["sizes"])

    def test_service_worker_et_page_hors_ligne(self):
        sw = (RACINE / "sw.js").read_text(encoding="utf-8")
        self.assertIn("hors-ligne/", sw)
        self.assertTrue((RACINE / "hors-ligne.md").exists())


if __name__ == "__main__":
    unittest.main()
