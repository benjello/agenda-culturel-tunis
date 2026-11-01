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
from scrapers.commun import slug
from scrapers.sources import billetterie_sktech, facebook, facebook_programmes, ical, tunis_events_cinema, jsonld, liste_fiches, pathe, rss, teskerti

FIX = Path(__file__).parent / "fixtures"
FUTUR = dt.date.today().year + 1


def jours(e):
    return [d.date().isoformat() for d in e.seances]


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

    def test_lieu_dans_un_header(self):
        with faux_reseau({"/evenement/fuite": "teskerti-header.html"}):
            e = teskerti.lire_fiche("https://teskerti.tn/evenement/fuite", "theatre")
        self.assertEqual(e.lieu, "Théâtre Le 4ème Art")


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
        self.assertEqual([(f.titre, jours(f), f.duree, f.film, f.categorie) for f in films],
                         [("El Sett", ["2026-11-02"], 155, True, "cinema")])


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
                 mock.patch.object(ecriture, "FICHIER_ETAT", d / "etat.json"), \
                 mock.patch.object(lanceur.doublons, "marquer", return_value=0), \
                 mock.patch.object(lanceur.films, "ecrire", return_value=0):
                code = lanceur.main([])
            etat = json.loads((d / "etat.json").read_text())
            self.assertEqual(code, 0)
            self.assertTrue(etat["vide"]["ok"])
            self.assertEqual(etat["vide"]["nb"], 0)
            self.assertFalse(etat["panne"]["ok"])
            self.assertIn("site modifié", etat["panne"]["erreur"])
            self.assertTrue((ancien / "vieux.md").exists())

    def test_attente_et_frequence(self):
        from scrapers import __main__ as lanceur
        hier = (dt.datetime.now() - dt.timedelta(days=1)).isoformat(timespec="seconds")
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "etat.json").write_text(json.dumps({"lent": {"ok": True, "nb": 2, "dernier_succes": hier}}))
            sources = [{"id": "sans-cle", "nom": "A", "scraper": "x"},
                       {"id": "lent", "nom": "B", "scraper": "x", "tous_les_jours": 3}]
            appels = []

            def lancer(s):
                appels.append(s["id"])
                raise commun.EnAttente("clé absente")
            with mock.patch.object(lanceur, "charger_sources", return_value=sources), \
                 mock.patch.object(lanceur, "lancer", lancer), \
                 mock.patch.object(ecriture, "DOSSIER_AUTO", d / "auto"), \
                 mock.patch.object(ecriture, "FICHIER_ETAT", d / "etat.json"), \
                 mock.patch.object(lanceur.doublons, "marquer", return_value=0), \
                 mock.patch.object(lanceur.films, "ecrire", return_value=0):
                code = lanceur.main([])
            etat = json.loads((d / "etat.json").read_text())
            self.assertEqual(code, 0)
            self.assertEqual(appels, ["sans-cle"])  # « lent » relu hier : pas relancé
            self.assertEqual(etat["sans-cle"]["attente"], "clé absente")
            self.assertEqual(etat["lent"]["nb"], 2)


class Facebook(unittest.TestCase):
    SOURCE = {"id": "cine-madart", "nom": "CinéMadart (Carthage)", "url": "https://www.facebook.com/CineMadart",
              "scraper": "facebook", "categorie": "cinema", "options": {"page": "CineMadart", "lieu": "CinéMadart"}}

    def test_sans_cle_en_attente(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(commun.EnAttente):
                facebook.recuperer(self.SOURCE)

    def test_conversion(self):
        items = [  # acteur officiel (heure UTC) et autre acteur (heure locale ISO)
            {"name": "Ciné-club : Les Silences du palais", "url": "https://www.facebook.com/events/123/?ref=x",
             "utcStartDate": f"{FUTUR}-11-05T18:30:00.000Z", "location": {"name": "CinéMadart", "streetAddress": "Carthage Dermech"}},
            {"name": "Avant-première", "url": "https://www.facebook.com/events/456/", "startISO": f"{FUTUR}-11-07T20:00:00+01:00"},
            {"name": "Annulé", "url": "https://www.facebook.com/events/789/", "utcStartDate": f"{FUTUR}-11-08T18:00:00Z", "isCanceled": True},
            {"error": "page introuvable"},
        ]
        with mock.patch.dict("os.environ", {"APIFY_TOKEN": "x"}), \
             mock.patch.object(facebook, "appeler_apify", return_value=items) as appel:
            evs = facebook.recuperer(self.SOURCE)
        self.assertEqual(appel.call_args[0][1]["startUrls"], ["https://www.facebook.com/CineMadart/upcoming_hosted_events"])
        self.assertEqual(len(evs), 2)
        self.assertEqual(evs[0].debut, dt.datetime(FUTUR, 11, 5, 19, 30))  # UTC+1 à Tunis
        self.assertEqual(evs[0].lien, "https://www.facebook.com/events/123/")
        self.assertEqual(evs[0].adresse, "Carthage Dermech")
        self.assertEqual(evs[1].debut, dt.datetime(FUTUR, 11, 7, 20, 0))
        self.assertEqual(evs[1].lieu, "CinéMadart")
        self.assertEqual(evs[1].categorie, "cinema")

    def test_url_groupe(self):
        self.assertEqual(facebook.url_evenements("https://www.facebook.com/groups/265611163490450/"),
                         "https://www.facebook.com/groups/265611163490450/events")


class FacebookProgrammes(unittest.TestCase):
    def test_publications_avec_image(self):
        source = {"id": "cine-test", "nom": "Ciné test", "url": "https://www.facebook.com/cinetest",
                  "scraper": "facebook_programmes", "options": {"page": "cinetest", "max": 2}}
        items = [
            {"text": "Sans image", "url": "https://www.facebook.com/p/1", "time": "2026-10-28T10:00:00.000Z"},
            {"text": "Programme du 29/10 au 4/11", "topLevelUrl": "https://www.facebook.com/p/2",
             "time": "2026-10-29T09:00:00.000Z",
             "media": [{"__typename": "Photo", "photo_image": {"uri": "https://scontent.x/a.jpg"},
                        "ocrText": "May be an image of text that says 'MER 29 20H00 FILM A'"}]},
            {"text": "Ancien", "url": "https://www.facebook.com/p/3", "time": "2026-10-20T09:00:00.000Z",
             "media": [{"__typename": "Video", "thumbnail": "https://scontent.x/v.jpg"}]},
        ]
        with tempfile.TemporaryDirectory() as d, \
             mock.patch.dict("os.environ", {"APIFY_TOKEN": "x"}), \
             mock.patch.object(facebook_programmes, "appeler_apify", return_value=items), \
             mock.patch.object(facebook_programmes, "RACINE", Path(d)), \
             mock.patch.object(facebook_programmes, "DOSSIER_IMAGES", Path(d) / "assets" / "programmes"), \
             mock.patch.object(facebook_programmes, "enregistrer_image",
                               side_effect=lambda url, dossier, nom: f"assets/programmes/cine-test/{nom}.jpg"), \
             mock.patch.object(facebook_programmes, "lire_image", return_value="MER 29 20H00 FILM A"):
            pubs = facebook_programmes.recuperer(source)
        self.assertEqual(len(pubs), 1)  # sans image et vidéo écartées
        self.assertEqual(pubs[0].lien, "https://www.facebook.com/p/2")
        self.assertEqual(pubs[0].date, "2026-10-29")
        self.assertIn("FILM A", pubs[0].ocr_facebook)
        self.assertEqual(pubs[0].ocr, "MER 29 20H00 FILM A")
        self.assertTrue(pubs[0].images[0].startswith("assets/programmes/cine-test/"))


class TunisEventsCinema(unittest.TestCase):
    def test_salles_et_jours(self):
        def ev(nom, lieu, jour, adresse="Tunis"):
            return {"@type": "Event", "name": nom, "startDate": f"{jour}T00:00:00+01:00",
                    "url": f"https://tunis.events/events/x/{slug(nom)}", "image": "https://api.tunis.events/storage/a.jpg",
                    "location": {"@type": "Place", "name": lieu, "address": {"streetAddress": adresse}}}
        objets = [ev("BAKMA", "CinéMadart", f"{FUTUR}-11-01"), ev("BAKMA", "CinéMadart", f"{FUTUR}-11-02"),
                  ev("BAKMA", "Pathé Tunis City", f"{FUTUR}-11-01"), ev("Bakma", "CinéMadart", f"{FUTUR}-11-03"), ev("Weekend", "Pathé Mall of Sousse", f"{FUTUR}-11-01", "Sousse")]
        html = '<script type="application/ld+json">' + json.dumps(objets) + "</script>"
        source = {"id": "tunis-events-cinema", "nom": "tunis.events", "url": "https://tunis.events/cinema"}
        with mock.patch.object(commun, "telecharger", return_value=html):
            films = tunis_events_cinema.recuperer(source)
        par_salle = {(f.lieu, f.titre): f for f in films}
        self.assertEqual(set(par_salle), {("CinéMadart", "BAKMA"), ("Pathé Tunis City", "BAKMA")})  # Sousse écarté
        madart = par_salle[("CinéMadart", "BAKMA")]  # « Bakma » fusionné avec « BAKMA »
        self.assertEqual(jours(madart), [f"{FUTUR}-11-01", f"{FUTUR}-11-02", f"{FUTUR}-11-03"])
        self.assertTrue(madart.film)
        self.assertEqual(madart.image, "https://api.tunis.events/storage/a.jpg")


class Lecteurs(unittest.TestCase):
    def setUp(self):
        from scrapers import lecteurs
        self.l = lecteurs

    def test_liste_films(self):
        texte = (f"À l'affiche du 02 au 09 Novembre {FUTUR} dans votre Cinéma Alhambra :\n\n"
                 "🎬 𝗪𝗲𝗲𝗸𝗲𝗻𝗱\n🎬 𝗗𝗮𝗿 𝗘𝗹 𝟯𝗲𝗿𝘀 دار العرس\n🎫 Les tickets sont disponibles")
        films = self.l.liste_films([{"texte": texte, "lien": "https://fb/p/1"}], ["Dar El 3ers - دار العرس"])
        self.assertEqual([f.titre for f in films], ["Weekend", "Dar El 3ers - دار العرس"])
        self.assertEqual(len(films[0].seances), 8)
        self.assertEqual(jours(films[0])[0], f"{FUTUR}-11-02")
        self.assertEqual(films[0].lieu, "")

    def test_un_film_par_affiche(self):
        pubs = [
            {"texte": "Rappel Japan Festival", "lien": "https://fb/p/2", "date": f"{FUTUR}-10-28",
             "ocr": "Le Maître du kabuki\nUn film de Lee Sang-il\nVendredi 30 octobre à 19h\n'et dimanche ler novembre à 13h"},
            {"texte": 'تذكير فيلم "بكْمَة" بقاعة Ciné 350', "lien": "https://fb/p/3", "date": f"{FUTUR}-10-28",
             "ocr": "Mercredi 29 Octobre\nJeudi 30 Octobre 16H00"},
        ]
        films = self.l.un_film_par_affiche(pubs, ["BAKMA - بكمة"])
        self.assertEqual(films[0].titre, "Le Maître du kabuki")
        self.assertEqual(jours(films[0]), [f"{FUTUR}-10-30", f"{FUTUR}-11-01"])
        self.assertEqual(films[1].titre, "BAKMA - بكمة")  # rapproché du titre connu, malgré les voyelles

    def test_annee_deduite(self):
        self.assertEqual(self.l.jours_sans_annee("samedi 3 janvier", dt.date(2026, 12, 20)), ["2027-01-03"])


class Doublons(unittest.TestCase):
    def test_meme_lieu_meme_heure(self):
        from scrapers import doublons
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            for src, nom, lieu, titre in [("el-teatro", "El Teatro", "El Teatro", "هروب|FUITE"),
                                          ("teskerti", "Teskerti", "El Teatro التياترو", "Fuite"),
                                          ("teskerti", "Teskerti", "Théâtre Le 4ème Art", "Cloche")]:
                (d / src).mkdir(exist_ok=True)
                (d / src / f"{slug(titre)}.md").write_text(
                    f'---\ntitle: "{titre}"\ndate: {FUTUR}-11-02 17:00\nvenue: "{lieu}"\n'
                    f'link: "https://{src}.tn/{slug(titre)}"\nsource: "{src}"\nsource_name: "{nom}"\nauto: true\n---\n')
            sources = [{"id": "el-teatro", "type": "lieu"}, {"id": "teskerti", "type": "billetterie"}]
            self.assertEqual(doublons.marquer(sources, d), 1)
            self.assertIn("doublon: true", (d / "teskerti" / "fuite.md").read_text())
            garde = (d / "el-teatro" / f"{slug('هروب|FUITE')}.md").read_text()
            self.assertIn('"name": "Teskerti"', garde)
            self.assertIn(f"date: {FUTUR}-11-02 17:00\n", garde)
            self.assertNotIn("doublon", (d / "teskerti" / "cloche.md").read_text())
            # relancer ne change rien
            self.assertEqual(doublons.marquer(sources, d), 1)


class Films(unittest.TestCase):
    def test_regroupe_les_salles_par_film(self):
        from scrapers import films
        demain = (dt.date.today() + dt.timedelta(days=1)).isoformat()
        hier = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            def ecrit(src, nom, titre, salle, jours, image=""):
                (d / src).mkdir(exist_ok=True)
                seances = "\n".join(f"  - {j}" for j in jours)
                (d / src / nom).write_text(f'---\ntitle: "{titre}"\ndate: {jours[0]}\nvenue: "{salle}"\n'
                                           f'seances:\n{seances}\nimage: "{image}"\nfilm: true\nsource: "{src}"\n---\n')
            ecrit("a", "1.md", "LAST CHANCE - لص شايح", "Le Palace", [demain], "x.jpg")
            ecrit("b", "2.md", "لص شايح", "Alhambra", [hier, demain])
            ecrit("b", "3.md", "Weekend", "Alhambra", [demain])
            ecrit("a", "4.md", "WEEKEND", "Le Palace", [demain])
            ecrit("a", "5.md", "Vieux film", "Le Palace", [hier])
            fs = films.regrouper(d)
        self.assertEqual(len(fs), 2)
        lc = next(f for f in fs if "LAST" in f["titre"])
        self.assertEqual(lc["titre"], "LAST CHANCE - لص شايح")
        self.assertEqual(lc["image"], "x.jpg")
        self.assertEqual([s["nom"] for s in lc["salles"]], ["Alhambra", "Le Palace"])
        self.assertEqual(lc["salles"][0]["jours"], [demain])  # jour passé retiré


class Conferences(unittest.TestCase):
    def sources(self):
        import yaml
        return {s["id"]: s for s in yaml.safe_load((commun.RACINE / "_data" / "sources.yml").read_text())}

    def test_beit_al_hikma_dates_en_arabe(self):
        evts = rss.depuis_flux(fixture("beit-al-hikma.xml"), self.sources()["beit-al-hikma"])
        self.assertEqual([e.debut.date() for e in evts], [dt.date(FUTUR, 11, 13), dt.date(FUTUR, 10, 22)])
        self.assertEqual(evts[1].titre, "تقديم كتاب : المناهج الجامعيّة للأستاذ يونس محسين")

    def test_irmc_garde_les_rencontres(self):
        evts = rss.depuis_flux(fixture("irmc.xml"), self.sources()["irmc"])
        self.assertEqual(len(evts), 1)
        self.assertEqual(evts[0].debut, dt.datetime(FUTUR, 10, 20, 17, 30))
