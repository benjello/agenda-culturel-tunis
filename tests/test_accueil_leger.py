"""Accueil léger, tri par distance et « Ma soirée » : les textes de l'interface existent en fr, ar et en.

  python3 -m unittest tests.test_accueil_leger -v
"""
import unittest

import yaml

from scrapers.commun import RACINE

CLES = ["pres_de_moi", "pos_indispo", "pos_recherche", "pos_ok", "pos_refus",
        "voir_suite", "ma_soiree", "ma_soiree_note", "chevauche"]


class TestAccueilLeger(unittest.TestCase):
    def test_traductions(self):
        i18n = yaml.safe_load((RACINE / "_data" / "i18n.yml").read_text(encoding="utf-8"))
        for cle in CLES:
            self.assertTrue({"ar", "en"} <= set(i18n[cle]), cle)

    def test_cartes_ont_un_lieu_pour_le_tri(self):
        carte = (RACINE / "_includes" / "event-card.html").read_text(encoding="utf-8")
        self.assertIn("data-slug=", carte)


if __name__ == "__main__":
    unittest.main()
