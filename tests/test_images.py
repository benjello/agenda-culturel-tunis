import datetime as dt
import unittest
from unittest import mock

from scrapers import images

T = dt.datetime(2026, 11, 17, 12)


class TestImages(unittest.TestCase):
    def test_signatures(self):
        self.assertTrue(images.est_une_image(b"\xff\xd8\xff\xe0abc"))
        self.assertTrue(images.est_une_image(b"\x89PNG\r\n"))
        self.assertTrue(images.est_une_image(b"RIFF\x00\x00\x00\x00WEBP"))
        self.assertFalse(images.est_une_image(b"<html><body>403"))

    def test_locale(self):
        self.assertEqual(images.verifier_locale("assets/absent.jpg")[0], "cassee")

    def test_retrait_apres_deux_echecs(self):
        f = images.mettre_a_jour(None, "cassee", "HTTP 403", T)
        self.assertFalse(images.doit_retirer(f))
        f = images.mettre_a_jour(f, "cassee", "HTTP 403", T)
        self.assertTrue(images.doit_retirer(f))
        f = images.mettre_a_jour(f, "ok", "", T)
        self.assertFalse(images.doit_retirer(f))

    def test_relecture(self):
        ok = images.mettre_a_jour(None, "ok", "", T)
        self.assertFalse(images.a_relire(ok, T + dt.timedelta(days=1)))
        self.assertTrue(images.a_relire(ok, T + dt.timedelta(days=8)))
        self.assertTrue(images.a_relire(images.mettre_a_jour(None, "cassee", "x", T), T))

    def _rep(self, code, type_, corps):
        r = mock.Mock(status_code=code, headers={"Content-Type": type_})
        r.iter_content.return_value = iter([corps])
        return r

    def test_externe(self):
        cas = [(200, "image/jpeg", b"\xff\xd8\xff", "ok"), (403, "text/html", b"", "cassee"),
               (200, "text/html", b"<html>", "cassee"), (200, "image/jpeg", b"<html>", "cassee"),
               (503, "text/html", b"", "incertaine")]
        for code, t, corps, attendu in cas:
            with mock.patch("requests.get", return_value=self._rep(code, t, corps)):
                self.assertEqual(images.verifier_externe("https://x/a.jpg")[0], attendu)


if __name__ == "__main__":
    unittest.main()
