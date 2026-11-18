"""Fiches plus riches : prix des billetteries, langue, photos Wikidata, infos OpenStreetMap (hors ligne)."""
import unittest


class Prix(unittest.TestCase):
    def test_offre(self):
        from scrapers.sources.jsonld import prix_offre
        self.assertEqual(prix_offre({"price": 0}), "Gratuit")
        self.assertEqual(prix_offre({"price": "20", "priceCurrency": "TND"}), "20 TND")
        self.assertEqual(prix_offre({"price": "20", "priceCurrency": "TND", "availability": "https://schema.org/SoldOut"}),
                         "20 TND · Complet")
        self.assertEqual(prix_offre({"availability": "SoldOut"}), "Complet")
        self.assertEqual(prix_offre({}), "")


class Langue(unittest.TestCase):
    def test_langues(self):
        from scrapers.commun import langues_annoncees as l
        self.assertEqual(l("Philo-Art pour enfants en français"), ["fr"])
        self.assertEqual(l("Hamlet", "Une pièce en arabe tunisien, surtitrée."), ["ar"])
        self.assertEqual(l("Le Temps suspendu", "Projection en VOSTFR."), ["vo"])
        self.assertEqual(l("Foire du livre : traduire le savoir en arabe"), [])
        self.assertEqual(l("Concert de jazz"), [])


class Enrichir(unittest.TestCase):
    def test_wikidata_homonymes(self):
        from scrapers.enrichir import acceptable
        def e(**claims):
            return {"claims": {p: [{"mainsnak": {"datavalue": {"value": {"id": v}}}}] for p, v in claims.items()}}
        self.assertTrue(acceptable(e(P31="Q5", P27="Q948"), "artiste"))
        self.assertFalse(acceptable(e(P31="Q5", P27="Q142"), "artiste"))   # homonyme français
        self.assertTrue(acceptable(e(P17="Q948"), "lieu"))
        self.assertFalse(acceptable(e(P17="Q142"), "lieu"))

    def test_lieu_pas_un_pays_ni_une_ville(self):
        from scrapers.enrichir import acceptable
        def e(**claims):
            return {"claims": {p: [{"mainsnak": {"datavalue": {"value": {"id": v}}}}] for p, v in claims.items()}}
        self.assertFalse(acceptable(e(P17="Q948", P31="Q6256"), "lieu"))   # la Tunisie elle-même
        self.assertFalse(acceptable(e(P17="Q948", P31="Q515"), "lieu"))    # une ville
        self.assertTrue(acceptable(e(P17="Q948", P31="Q24354"), "lieu"))   # un théâtre

    def test_meme_nom(self):
        from scrapers.enrichir import meme_nom
        e = {"labels": {"fr": {"value": "Moez Echargui"}}, "aliases": {"en": [{"value": "Moez Ben Echargui"}]}}
        self.assertFalse(meme_nom("Moez", e))                  # un seul mot : homonymes possibles
        self.assertTrue(meme_nom("Moez Echargui", e))
        self.assertFalse(meme_nom("Moez Trabelsi", e))
        theatre = {"labels": {"fr": {"value": "Cité de la culture de Tunis"}}}
        self.assertTrue(meme_nom("Cité de la culture", theatre))
        self.assertFalse(meme_nom("Théâtre municipal de Tunis", theatre))

    def test_licence(self):
        from scrapers.enrichir import licence_libre
        self.assertTrue(licence_libre({"licence": "CC BY-SA 4.0"}))
        self.assertTrue(licence_libre({"licence": "Public domain"}))
        self.assertTrue(licence_libre({"licence": "CC0"}))
        self.assertFalse(licence_libre({"licence": ""}))
        self.assertFalse(licence_libre({"licence": "Copyrighted free use"}))
        self.assertFalse(licence_libre(None))

    def test_infos_commons(self):
        from unittest import mock
        from scrapers import enrichir
        rep = mock.Mock()
        rep.json.return_value = {"query": {"pages": {"1": {"imageinfo": [{"extmetadata": {
            "Artist": {"value": '<a href="//x">Jean &amp; Dupont</a>'},
            "LicenseShortName": {"value": "CC BY-SA 4.0"},
            "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0"}}}]}}}}
        with mock.patch.object(enrichir.requests, "get", return_value=rep):
            i = enrichir.infos_commons("Fichier.jpg")
        self.assertEqual(i["auteur"], "Jean & Dupont")
        self.assertEqual(i["licence"], "CC BY-SA 4.0")
        rep.json.return_value = {"query": {"pages": {"-1": {"missing": ""}}}}
        with mock.patch.object(enrichir.requests, "get", return_value=rep):
            self.assertIsNone(enrichir.infos_commons("Absent.jpg"))

    def test_reverifier_retire_les_mauvaises_photos(self):
        import datetime as dt
        from unittest import mock
        from scrapers import enrichir
        def ent(qid, label, nature, nat):
            return {"claims": {"P31": [{"mainsnak": {"datavalue": {"value": {"id": nature}}}}],
                               "P27": [{"mainsnak": {"datavalue": {"value": {"id": nat}}}}]}, "labels": {"fr": {"value": label}}}
        cache = {"images": {
            "artiste:anouar-brahem": {"qid": "Q1", "credit": "https://commons.wikimedia.org/wiki/File:A.jpg"},
            "artiste:moez": {"qid": "Q2", "credit": "https://commons.wikimedia.org/wiki/File:B.jpg"}}}
        noms = {"artiste:anouar-brahem": "Anouar Brahem", "artiste:moez": "Moez"}
        entites = {"Q1": ent("Q1", "Anouar Brahem", "Q5", "Q948"), "Q2": ent("Q2", "Moez Echargui", "Q5", "Q948")}
        libre = {"auteur": "X", "licence": "CC BY 4.0", "licence_url": ""}
        with mock.patch.object(enrichir, "_entites", return_value=entites), \
                mock.patch.object(enrichir, "infos_commons", return_value=libre):
            enrichir.reverifier(cache, dt.date(2026, 11, 18), noms)
        self.assertIn("artiste:anouar-brahem", cache["images"])
        self.assertEqual(cache["images"]["artiste:anouar-brahem"]["licence"], "CC BY 4.0")
        self.assertNotIn("artiste:moez", cache["images"])

    def test_commons(self):
        from scrapers.enrichir import commons
        c = commons("Théâtre municipal de Tunis.jpg")
        self.assertIn("Special:FilePath/Théâtre_municipal_de_Tunis.jpg", c["image"])
        self.assertIn("File:Théâtre_municipal_de_Tunis.jpg", c["credit"])

    def test_osm(self):
        from scrapers.enrichir import chercher_osm, osm_index
        index = osm_index([
            {"tags": {"name": "Théâtre Municipal de Tunis", "wheelchair": "limited"}},
            {"tags": {"name": "Musée national du Bardo", "opening_hours": "Tu-Su 09:30-16:30"}},
            {"tags": {"name": "Sans info"}},
        ])
        self.assertEqual(chercher_osm(index, "Théâtre municipal de Tunis"), {"wheelchair": "limited"})
        self.assertEqual(chercher_osm(index, "Musée National du Bardo")["opening_hours"], "Tu-Su 09:30-16:30")
        self.assertIsNone(chercher_osm(index, "Sans info"))
        self.assertIsNone(chercher_osm(index, "El Teatro"))


if __name__ == "__main__":
    unittest.main()
