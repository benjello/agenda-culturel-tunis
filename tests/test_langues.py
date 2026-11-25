"""Tests hors ligne : détection des langues mêlées et traductions qui restent dans leur langue.

python3 -m unittest tests.test_langues"""
import unittest

from scrapers import langues as lg
from scrapers import libelles, traduire as tr

FR = "Enfilez un casque et vivez une expérience immersive au cœur des œuvres entre art et cinéma."
EN = "Join us this November for a special film series hosted in collaboration with the cinema."
AR = "فيلم يجمع بين الغموض والتشويق والتحقيق بطولة محمد علي بن جمعة وسميرة مقرون"


class Detection(unittest.TestCase):
    def test_langue_de_phrases(self):
        self.assertEqual(lg.langue_sure(FR), "fr")
        self.assertEqual(lg.langue_sure(EN), "en")
        self.assertEqual(lg.langue_sure(AR), "ar")
        self.assertIsNone(lg.langue_sure("Hyperculte"))

    def test_melange(self):
        self.assertEqual(lg.langues_du_texte(f"{FR}\n{AR}"), {"fr", "ar"})
        self.assertEqual(lg.langues_du_texte(f"{FR}\n\\---\n{EN}"), {"fr", "en"})
        self.assertEqual(lg.langues_du_texte(FR + " Du 4 au 7 mai, à Tunis."), {"fr"})

    def test_noms_propres_et_liens_ne_comptent_pas(self):
        self.assertTrue(lg.est_dans("Concert de Hyperculte au Théâtre El Teatro https://exemple.tn/x @el_teatro", "fr"))
        self.assertTrue(lg.est_dans("سيني مادارت (Instagram)", "ar"))

    def test_traduction_hors_de_sa_langue(self):
        self.assertFalse(lg.est_dans(f"{EN} {AR}", "ar"))      # première phrase restée en anglais
        self.assertFalse(lg.est_dans(f"{AR}\n{FR}", "ar"))
        self.assertTrue(lg.est_dans(AR, "ar"))
        self.assertFalse(lg.est_dans(FR, "en"))


class Faux(tr.Traducteur):
    """Traducteur sans modèle : « traduit » en préfixant la langue, et recopie les phrases qui contiennent « REBELLE »."""
    def __init__(self):
        self.appels = []

    def _direct(self, phrases, de, vers, beam=2):
        self.appels.append((de, vers, list(phrases)))
        mots = {"ar": AR, "en": EN, "fr": FR}
        return [p if "REBELLE" in p else mots[vers] for p in phrases]


class TraductionPhraseParPhrase(unittest.TestCase):
    def test_chaque_phrase_part_de_sa_langue(self):
        f = Faux()
        res = f.traduire([f"{AR}\n{FR}"], "ar", "fr", mixte=True)
        self.assertEqual(res, [f"{FR}\n{FR}"])
        # la phrase arabe est traduite depuis l'arabe, la française n'est pas retraduite
        self.assertIn(("ar", "en", [AR]), f.appels)
        self.assertFalse(any(p == [FR] for _, _, p in f.appels))

    def test_phrase_recopiee_donne_un_texte_vide(self):
        f = Faux()
        res = f.traduire([f"{FR} REBELLE ici et là, dans la ville de Tunis aujourd'hui."], "fr", "en")
        self.assertEqual(res, [""])

    def test_lien_remis_apres_traduction(self):
        f = Faux()
        res = f.traduire([f"{FR} (https://exemple.tn/page)"], "fr", "en")
        self.assertIn("https://exemple.tn/page", res[0])
        self.assertTrue(all("https" not in p for _, _, ps in f.appels for p in ps))


class Purge(unittest.TestCase):
    def test_traductions_fautives_retirees(self):
        cache = {"titres": {}, "echecs": {}, "notices": {
            "a.md": {"cle": "1", "ar": f"{EN} {AR}", "en": EN},
            "b.md": {"cle": "2", "ar": AR}}}
        self.assertEqual(tr.purger(cache), 1)
        self.assertNotIn("ar", cache["notices"]["a.md"])
        self.assertEqual(cache["notices"]["b.md"]["ar"], AR)

    def test_libelles_fautifs_retires(self):
        cache = {"x": {"de": "fr", "ar": f"{EN} {AR}"}, "y": {"de": "fr", "ar": AR}}
        self.assertEqual(libelles.purger(cache), 1)
        self.assertEqual(list(cache), ["y"])


class NoticesDuDepot(unittest.TestCase):
    def test_notices_saisies_a_la_main_dans_une_seule_langue(self):
        """Les fiches écrites à la main ne mêlent pas les langues : le texte source est à corriger sinon."""
        mixtes = [chemin for chemin, corps in lg._corps_evenements() if "manuel" in chemin and len(lg.langues_du_texte(corps)) > 1]
        self.assertEqual(mixtes, [])


if __name__ == "__main__":
    unittest.main()
