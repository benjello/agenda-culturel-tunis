import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scrapers.archives import _ajouter, _lire

FICHE = """---
title: "Concert de oud"
date: 2026-10-07 20:30:00
venue: "El Teatro"
ville: "tunis"
category: "musique"
link: "https://exemple.tn/oud"
---
Un **récital** de oud.
"""


class TestArchives(unittest.TestCase):
    def test_lire(self):
        e = _lire(FICHE, "_events/auto/x/2026-10-07-concert.md")
        self.assertEqual(e["titre"], "Concert de oud")
        self.assertEqual((e["debut"], e["fin"], e["heure"]), ("2026-10-07", "2026-10-07", "20:30"))
        self.assertEqual(e["resume"], "Un récital de oud.")

    def test_doublon_et_film_ignores(self):
        self.assertIsNone(_lire(FICHE.replace("ville:", "doublon: true\nville:"), "x"))
        self.assertIsNone(_lire(FICHE.replace("ville:", "film: true\nville:"), "x"))

    def test_ajouter_seulement_passe_et_une_fois(self):
        annees = {}
        e = _lire(FICHE, "x")
        self.assertFalse(_ajouter(annees, e, "2026-10-07"))  # encore en cours ce jour-là
        self.assertTrue(_ajouter(annees, e, "2026-10-08"))
        self.assertFalse(_ajouter(annees, dict(e, fichier="y"), "2026-10-08"))
        self.assertEqual(list(annees), ["2026"])


    def test_charger_ignore_index(self):
        """index.json (décompte par année) n'est pas un fichier d'événements : il faisait planter l'archivage."""
        from scrapers import archives
        e = {"titre": "A", "debut": "2026-11-01", "fin": "2026-11-01", "heure": "", "lieu": "Lieu", "source": "", "fichier": "x"}
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "2026.json").write_text(json.dumps([e]))
            (Path(d) / "index.json").write_text(json.dumps({"2026": 1}))
            with mock.patch.object(archives, "DOSSIER", Path(d)):
                self.assertEqual(list(archives._charger()), ["2026"])

    def _depot(self, d, fiches):
        racine = Path(d)
        (racine / "archives").mkdir()
        for dossier, nom, fin in fiches:
            f = racine / "_events" / dossier / nom
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(FICHE.replace("date: 2026-10-07 20:30:00", f"date: {fin} 20:30:00").replace('title: "Concert de oud"', f'title: "{nom}"'))
        return racine

    def test_archiver_ecarte_les_evenements_trop_anciens(self):
        import datetime as dt
        from scrapers import archives
        with tempfile.TemporaryDirectory() as d:
            racine = self._depot(d, [("auto/x", "recent.md", "2026-11-05"), ("auto/x", "ancien.md", "2026-09-01")])
            with mock.patch.object(archives, "RACINE", racine), mock.patch.object(archives, "DOSSIER", racine / "archives" / "donnees"):
                archives.archiver(jours=30, aujourd_hui=dt.date(2026, 11, 20))
                titres = [e["titre"] for e in json.loads((racine / "archives" / "donnees" / "2026.json").read_text())]
                self.assertEqual(titres, ["recent.md"])
                # plus tard, l'événement récent sort à son tour et le fichier d'année disparaît
                archives.archiver(jours=30, aujourd_hui=dt.date(2026, 12, 20))
                self.assertFalse((racine / "archives" / "donnees" / "2026.json").exists())
                self.assertEqual(json.loads((racine / "archives" / "donnees" / "index.json").read_text()), {})

    def test_purger_supprime_seulement_les_fichiers_manuels_trop_anciens(self):
        import datetime as dt
        from scrapers import archives
        with tempfile.TemporaryDirectory() as d:
            racine = self._depot(d, [("manuel", "ancien.md", "2026-09-01"), ("manuel", "recent.md", "2026-11-10"),
                                     ("propositions", "ancienne.md", "2026-09-01"), ("auto/x", "auto-ancien.md", "2026-09-01")])
            with mock.patch.object(archives, "RACINE", racine):
                self.assertEqual(archives.purger(jours=30, aujourd_hui=dt.date(2026, 11, 20)), 2)
                self.assertEqual(sorted(p.name for p in (racine / "_events").rglob("*.md")), ["auto-ancien.md", "recent.md"])
                # un délai plus long garde tout ce qui reste
                self.assertEqual(archives.purger(jours=200, aujourd_hui=dt.date(2026, 11, 20)), 0)


if __name__ == "__main__":
    unittest.main()
