"""Tests hors ligne des scrapers : python3 -m unittest discover tests

Les pages de tests/fixtures/ imitent la structure des vrais sites. Si un site
change, enregistrer la nouvelle page (python3 -m scrapers --debug) et l'ajouter ici.
"""
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scrapers import commun, ecriture
from scrapers.sources import billetterie_sktech, ical, jsonld, liste_fiches, pathe, rss, teskerti

FIX = Path(__file__).parent / "fixtures"
FUTUR = dt.date.today().year + 1


def fixture(nom):
    return (FIX / nom).read_text().replace("{AN}", str(FUTUR))


def faux_reseau(pages):
    def telecharger(url):
        for motif, nom in pages.items():
            if url.rstrip("/").endswith(motif):
                return fixture(nom)
        raise AssertionError(f"page inattendue : {url}")
    return mock.patch.object(commun, "telecharger", telecharger)


class Dates(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(commun.dates_fr("07 Novembre 2026 à 19:30"), [dt.datetime(2026, 11, 7, 19, 30)])
        self.assertEqual(commun.dates_fr("01 Novembre 2026, 11:00"), [dt.datetime(2026, 11, 1, 11, 0)])
        self.assertEqual(commun.dates_fr("le 1er déc. 2026 à 20h"), [dt.datetime(2026, 12, 1, 20, 0)])
        self.assertEqual(commun.dates_fr("5 février 2027"), [dt.datetime(2027, 2, 5)])


class BilletterieSktech(unittest.TestCase):
    def test_el_teatro(self):
        src = {"id": "el-teatro", "nom": "El Teatro", "url": "https://billetterie.elteatrotunis.com/fr/programmes",
               "options": {"lieu": "El Teatro"}}
        with faux_reseau({"/fr/programmes": "sktech-programmes.html", "/fr/programme/le_fou": "sktech-le-fou.html",
                          "/fr/programme/vieux": "sktech-vieux.html"}), mock.patch("time.sleep"):
            evs = billetterie_sktech.recuperer(src)
        self.assertEqual(len(evs), 1)  # le spectacle passé est ignoré
        e = evs[0]
        self.assertEqual(e.titre, "Le Fou | المجنون")
        self.assertEqual(e.debut, dt.datetime(FUTUR, 11, 7, 19, 30))
        self.assertEqual(e.fin, dt.datetime(FUTUR, 11, 14, 19, 30))
        self.assertEqual(len(e.seances), 5)
        self.assertEqual(e.prix, "25 DT")
        self.assertEqual(e.lien, "https://billetterie.elteatrotunis.com/fr/programme/le_fou")


class Teskerti(unittest.TestCase):
    def test_categories_et_fiches(self):
        with faux_reseau({"teskerti.tn": "teskerti-accueil.html", "/category/spectacle": "teskerti-cat-spectacle.html",
                          "/category/cinema": "teskerti-cat-cinema.html",
                          "/evenement/taha-desouky": "teskerti-taha.html",
                          "/evenement/poids-plume-le-rio": "teskerti-poids-plume.html"}), mock.patch("time.sleep"):
            evs = teskerti.recuperer({"id": "teskerti", "nom": "Teskerti", "url": "https://teskerti.tn/"})
        par_titre = {e.titre: e for e in evs}
        self.assertEqual(set(par_titre), {"TAHA DESOUKY", "Poids plume"})  # la catégorie sport est exclue
        t = par_titre["TAHA DESOUKY"]
        self.assertEqual(t.debut, dt.datetime(FUTUR, 11, 5, 20, 0))
        self.assertEqual(t.lieu, "Théâtre municipal de Tunis")
        self.assertEqual(t.adresse, "2 Rue de Grèce, Tunis")
        self.assertEqual(t.categorie, "spectacle")
        self.assertEqual(t.prix, "À partir de 30 DT")
        self.assertEqual(par_titre["Poids plume"].categorie, "cinema")
        self.assertEqual(par_titre["Poids plume"].lieu, "Le Rio")


    def test_ignore_les_liens_de_menu(self):
        with faux_reseau({"/evenement/mirage": "teskerti-espace-pro.html"}):
            e = teskerti.lire_fiche("https://teskerti.tn/evenement/mirage", "theatre")
        self.assertEqual(e.titre, "Mirage")
        self.assertEqual((e.lieu, e.adresse), ("Théâtre Le 4ème Art", "7 Av. de Paris"))


    def test_lieu_sous_le_titre(self):
        with faux_reseau({"/evenement/la-chaussure": "teskerti-chaussure.html", "/evenement/e-fest": "teskerti-efest.html"}):
            e = teskerti.lire_fiche("https://teskerti.tn/evenement/la-chaussure", "theatre")
            f = teskerti.lire_fiche("https://teskerti.tn/evenement/e-fest", "autre")
        self.assertEqual((e.lieu, e.adresse), ("Théâtre Le 4ème Art", "7 Av. de Paris"))
        self.assertEqual((f.lieu, f.adresse), ("Carthage Thalasso Resort", "Gammarth"))


class JsonLd(unittest.TestCase):
    def test_evenement_schema_org(self):
        with faux_reseau({"exemple.tn/agenda": "jsonld.html"}):
            evs = jsonld.recuperer({"id": "x", "nom": "X", "url": "https://exemple.tn/agenda"})
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0].titre, "Concert de oud")
        self.assertEqual(evs[0].lieu, "Dar Ben Abdallah")
        self.assertEqual(evs[0].debut, dt.datetime(FUTUR, 12, 3, 20, 0))


class Rss(unittest.TestCase):
    def test_goethe(self):
        evs = rss.depuis_flux(fixture("goethe.rss"), {"id": "goethe", "nom": "Goethe-Institut Tunis", "url": "u",
                                                      "options": {"nettoyer_titre": r"\d{2}\.\d{2}\.\d{4},\s*"}})
        self.assertEqual(len(evs), 2)  # l'actualité sans date est ignorée
        self.assertEqual(evs[0].titre, "Lecture musicale : Rainer Maria Rilke, entre arabe et allemand")
        self.assertEqual(evs[0].debut, dt.datetime(FUTUR, 9, 26, 19, 0))
        self.assertEqual(evs[1].debut, dt.datetime(FUTUR, 9, 27))
        self.assertEqual(evs[0].lien, "https://www.goethe.de/ins/tn/fr/ver.cfm?event_id=27355849")


class Ical(unittest.TestCase):
    def test_ics(self):
        evs = ical.depuis_ics(fixture("agenda.ics"), {"id": "x", "nom": "X", "url": "u"})
        self.assertEqual([(e.titre, e.debut, e.lieu) for e in evs],
                         [("Soirée slam, poésie", dt.datetime(FUTUR, 12, 5, 19, 0), "Café culturel")])


class ListeFiches(unittest.TestCase):
    def test_dates_en_chiffres(self):
        src = {"id": "ift", "nom": "Institut français de Tunisie", "url": "https://www.institutfrancais-tunisie.com/list-agenda",
               "options": {"motif": "details-agenda", "lieu": "Institut français de Tunis"}}
        with faux_reseau({"/list-agenda": "ift-liste.html", "eventId=6509": "ift-fiche.html"}), mock.patch("time.sleep"):
            evs = liste_fiches.recuperer(src)
        self.assertEqual(len(evs), 1)  # deux liens vers la même fiche
        self.assertEqual(evs[0].titre, "What else ?")
        self.assertEqual(evs[0].debut, dt.datetime(FUTUR, 11, 4, 18, 0))
        self.assertEqual(evs[0].lieu, "Institut français de Tunis")


class Pathe(unittest.TestCase):
    def test_api(self):
        today = dt.date(2026, 11, 1)
        seances = {"shows": {"el-sett": {"days": {"2026-11-02": {}, "2026-12-30": {}}}, "vieux": {"days": {"2020-01-01": {}}}}}
        films = pathe.films_depuis_api(seances, {"el-sett": {"title": "El Sett", "duration": 155}}, today)
        self.assertEqual([(f.titre, f.jours, f.duree) for f in films], [("El Sett", ["2026-11-02"], 155)])


class Ecriture(unittest.TestCase):
    def test_fichiers_markdown(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(ecriture, "DOSSIER_AUTO", Path(d)):
            e = commun.Evenement(titre="L'Effet : papillon", debut=dt.datetime(FUTUR, 11, 7, 19, 30),
                                 fin=dt.datetime(FUTUR, 11, 9, 19, 30), lien="https://x.tn/a", lieu="Lartisto")
            passe = commun.Evenement(titre="Vieux", debut=dt.datetime(2020, 1, 1), lien="https://x.tn/b")
            n = ecriture.ecrire_evenements({"id": "src", "nom": "Source", "categorie": "theatre"}, [e, passe])
            self.assertEqual(n, 1)
            texte = next(Path(d, "src").glob("*.md")).read_text()
            self.assertIn(f"date: {FUTUR}-11-07 19:30\n", texte)
            self.assertIn('title: "L\'Effet : papillon"', texte)
            self.assertIn('category: "theatre"', texte)


if __name__ == "__main__":
    unittest.main()


class Lanceur(unittest.TestCase):
    def test_vide_ok_et_panne_garde_les_fichiers(self):
        from scrapers import __main__ as lanceur
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            ancien = d / "auto" / "panne"
            ancien.mkdir(parents=True)
            (ancien / "vieux.md").write_text("---\ntitle: x\n---\n")
            sources = [{"id": "vide", "nom": "Vide", "scraper": "x", "actif": True},
                       {"id": "panne", "nom": "Panne", "scraper": "x", "actif": True}]

            def lancer(s):
                if s["id"] == "panne":
                    raise RuntimeError("site modifié")
                return []
            with mock.patch.object(lanceur, "charger_sources", return_value=sources), \
                 mock.patch.object(lanceur, "lancer", lancer), \
                 mock.patch.object(ecriture, "DOSSIER_AUTO", d / "auto"), \
                 mock.patch.object(ecriture, "FICHIER_ETAT", d / "etat.json"):
                code = lanceur.main([])
            etat = json.loads((d / "etat.json").read_text())
            self.assertEqual(code, 0)
            self.assertTrue(etat["vide"]["ok"])
            self.assertEqual(etat["vide"]["nb"], 0)
            self.assertFalse(etat["panne"]["ok"])
            self.assertIn("site modifié", etat["panne"]["erreur"])
            self.assertTrue((ancien / "vieux.md").exists())
