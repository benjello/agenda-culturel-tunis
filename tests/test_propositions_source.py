"""Source proposée (issue validée) → entrée du registre, sans réseau."""
import unittest

import yaml

from scrapers import propositions_source as ps
from scrapers.commun import RACINE


def issue(nom, url):
    return (f"### Lieu, collectif ou organisateur\n\n{nom}\n\n### Adresse de la page\n\n{url}\n\n"
            "### Quelle sorte de page ? (facultatif)\n\n_No response_\n\n### Vérification\n\n- [x] ok")


class SourceProposee(unittest.TestCase):
    def test_instagram(self):
        e = ps.entree(issue("Dar Lasram", "https://www.instagram.com/darlasram/"), "12", [])
        self.assertEqual((e["id"], e["scraper"], e["options"]["compte"]), ("dar-lasram", "instagram", "darlasram"))
        self.assertEqual(e["options"]["lieu"], "Dar Lasram")

    def test_facebook_rss_ical_site(self):
        self.assertEqual(ps.entree(issue("A", "https://www.facebook.com/lieu.a"), "", [])["options"]["page"], "lieu.a")
        self.assertEqual(ps.entree(issue("B", "https://b.tn/feed/"), "", [])["scraper"], "rss")
        self.assertEqual(ps.entree(issue("C", "https://c.tn/agenda.ics"), "", [])["scraper"], "ical")
        self.assertEqual(ps.entree(issue("D", "https://d.tn/programme"), "", [])["scraper"], "jsonld")
        pdf = ps.entree(issue("E", "https://e.tn/prog.pdf"), "", [])
        self.assertFalse(pdf["actif"])

    def test_refus(self):
        for url in ("https://www.instagram.com/p/ABC/", "https://www.facebook.com/events/123", "ftp://x.tn", "pas un lien"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                ps.entree(issue("X", url), "", [])
        with self.assertRaises(ValueError):
            ps.entree(issue("", "https://x.tn"), "", [])

    def test_doublon_et_id_unique(self):
        deja = [{"id": "dar-lasram", "url": "https://www.instagram.com/darlasram"}]
        with self.assertRaises(ValueError):
            ps.entree(issue("Autre nom", "https://www.instagram.com/darlasram/"), "", deja)
        e = ps.entree(issue("Dar Lasram", "https://d.tn/x"), "", deja)
        self.assertEqual(e["id"], "dar-lasram-2")

    def test_yaml_relu_et_valide_par_le_registre(self):
        e = ps.entree(issue("Théâtre « L'Étoile »", "https://www.instagram.com/etoile"), "7", [])
        lu = yaml.safe_load(ps.en_yaml(e))[0]
        self.assertEqual(lu, e)
        from tests.test_registre import CHAMPS, GENRES, TYPES
        self.assertLessEqual(set(lu), CHAMPS)
        self.assertIn(lu["type"], TYPES)
        self.assertIn(lu["genre"], GENRES)
        self.assertTrue((RACINE / "scrapers" / "sources" / f"{lu['scraper']}.py").exists())


if __name__ == "__main__":
    unittest.main()
