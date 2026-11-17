"""Page programme d'El Teatro (elteatrotunisie.com), hors ligne."""
import datetime as dt
import pathlib
import unittest

from bs4 import BeautifulSoup

from scrapers.sources.elteatro_programme import extraire

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "elteatro_programme.html"
URL = "https://elteatrotunisie.com/programme-de-la-saison/"


class ElTeatroProgramme(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        soup = BeautifulSoup(FIXTURE.read_text(encoding="utf-8"), "html.parser")
        cls.spectacles = {e.titre: e for e in extraire(soup, "El Teatro", dt.datetime(2026, 9, 1), URL)}

    def test_titres_et_nombre(self):
        self.assertEqual(set(self.spectacles), {
            "موسم العودة إلى المسرح", "Vorrei non vorrei", "Courtes mais bonnes",
            "Harmonie", "Le fou", "Le Quatrième Humain"})

    def test_heure_avec_minutes_et_sans(self):
        fou = self.spectacles["Le fou"]
        self.assertIn(dt.datetime(2026, 11, 8, 17, 0), fou.seances)   # « 8 Novembre 2026 A 17h »
        self.assertEqual(len(fou.seances), 5)

    def test_quatrieme_humain(self):
        q = self.spectacles["Le Quatrième Humain"]
        self.assertEqual(q.debut, dt.datetime(2026, 12, 17, 19, 30))
        self.assertEqual(q.fin, dt.datetime(2026, 12, 27, 17, 0))
        self.assertEqual(len(q.seances), 8)
        self.assertEqual(q.lien, URL)

    def test_passe_filtre(self):
        apres = extraire(BeautifulSoup(FIXTURE.read_text(encoding="utf-8"), "html.parser"),
                         "El Teatro", dt.datetime(2026, 11, 13), URL)
        fou = [e for e in apres if e.titre == "Le fou"][0]
        self.assertEqual(fou.seances, [dt.datetime(2026, 11, 13, 19, 30), dt.datetime(2026, 11, 14, 19, 30)])

    def test_date_sans_heure_ignoree(self):
        self.assertNotIn("Journées théâtrales de Carthage", self.spectacles)


if __name__ == "__main__":
    unittest.main()
