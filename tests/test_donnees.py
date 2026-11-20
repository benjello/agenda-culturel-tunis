import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scrapers import donnees

ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                          env={**os.environ, **ENV}).stdout.strip()


class TestDonnees(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.distant = base / "distant.git"
        git("init", "-q", "--bare", str(self.distant), cwd=base)
        self.depot = base / "depot"
        self.depot.mkdir()
        git("init", "-q", cwd=self.depot)
        git("remote", "add", "origin", str(self.distant), cwd=self.depot)
        (self.depot / "code.py").write_text("print(1)\n")
        git("add", "code.py", cwd=self.depot)
        git("commit", "-qm", "code", cwd=self.depot)

    def tearDown(self):
        self._tmp.cleanup()

    def _ecrire(self, chemin, texte):
        f = self.depot / chemin
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(texte)

    def test_enregistrer_deux_fois_un_seul_commit_sans_parent(self):
        self._ecrire("_events/auto/x/a.md", "un")
        self._ecrire("_data/films.json", "{}")
        self._ecrire("scrapers/autre.py", "pas une donnée")
        with mock.patch.dict(os.environ, ENV):
            donnees.enregistrer(self.depot)
            self._ecrire("_events/auto/x/b.md", "deux")
            donnees.enregistrer(self.depot)
        self.assertEqual(git("rev-list", "--count", "donnees", cwd=self.distant), "1")
        self.assertEqual(git("rev-list", "--parents", "-n1", "donnees", cwd=self.distant).count(" "), 0)
        fichiers = git("ls-tree", "-r", "--name-only", "donnees", cwd=self.distant).splitlines()
        self.assertEqual(sorted(fichiers), ["_data/films.json", "_events/auto/x/a.md", "_events/auto/x/b.md"])
        # le dossier de travail est resté sur sa branche, sans rien d'indexé
        self.assertEqual(git("diff", "--cached", "--name-only", cwd=self.depot), "")

    def test_enregistrer_prend_les_fichiers_ignores(self):
        self._ecrire(".gitignore", "_events/auto\n")
        self._ecrire("_events/auto/a.md", "x")
        with mock.patch.dict(os.environ, ENV):
            donnees.enregistrer(self.depot)
        self.assertIn("_events/auto/a.md", git("ls-tree", "-r", "--name-only", "donnees", cwd=self.distant))

    def test_recuperer_restaure_dans_un_clone_neuf(self):
        self._ecrire("_data/geo.json", '{"a": 1}')
        with mock.patch.dict(os.environ, ENV):
            donnees.enregistrer(self.depot)
        clone = Path(self._tmp.name) / "clone"
        git("clone", "-q", str(self.distant), str(clone), cwd=self._tmp.name)  # clone d'un distant sans HEAD valide
        git("remote", "set-url", "origin", str(self.distant), cwd=clone)
        donnees.recuperer(clone)
        self.assertEqual((clone / "_data" / "geo.json").read_text(), '{"a": 1}')

    def test_recuperer_sans_branche_s_arrete(self):
        with self.assertRaises(donnees.BrancheAbsente):
            donnees.recuperer(self.depot)

    def test_chemins_sans_doublon(self):
        self.assertEqual(len(donnees.CHEMINS), len(set(donnees.CHEMINS)))


if __name__ == "__main__":
    unittest.main()
