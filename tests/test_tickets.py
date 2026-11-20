"""Balayage des tickets (scrapers/tickets.py) : tout hors ligne, avec une date fixe.

  python3 -m unittest tests.test_tickets -v
"""
import unittest
from datetime import datetime, timedelta, timezone

from scrapers import tickets

MAINTENANT = datetime(2026, 11, 20, tzinfo=timezone.utc)


def issue(numero, jours, etiquettes=(), pr=False):
    """Une issue (ou PR) dont la dernière activité date de `jours` jours."""
    date = MAINTENANT - timedelta(days=jours)
    donnee = {
        "number": numero,
        "title": f"Ticket {numero}",
        "updated_at": date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "labels": [{"name": nom} for nom in etiquettes],
    }
    if pr:
        donnee["pull_request"] = {}
    return donnee


class Plan(unittest.TestCase):
    def test_inactive_depuis_longtemps_avertie(self):
        actions = tickets.plan([issue(1, 70)], MAINTENANT)
        self.assertEqual(actions, [(1, "avertir")])

    def test_recente_non_touchee(self):
        self.assertEqual(tickets.plan([issue(2, 5)], MAINTENANT), [])

    def test_a_trier_depuis_14_jours_fermee(self):
        actions = tickets.plan([issue(3, 20, [tickets.ETIQUETTE_TRI])], MAINTENANT)
        self.assertEqual(actions, [(3, "fermer")])

    def test_a_trier_recente_gardee(self):
        self.assertEqual(tickets.plan([issue(4, 5, [tickets.ETIQUETTE_TRI])], MAINTENANT), [])

    def test_alerte_jamais_touchee(self):
        self.assertEqual(tickets.plan([issue(5, 200, ["alerte"])], MAINTENANT), [])

    def test_pull_request_ignoree(self):
        self.assertEqual(tickets.plan([issue(6, 200, pr=True)], MAINTENANT), [])


class Resolues(unittest.TestCase):
    def test_pr_fusionnee_ferme_l_issue(self):
        prs = [{"number": 9, "merged_at": "2026-11-19T10:00:00Z", "body": "Résumé\n\nCloses #7"}]
        self.assertEqual(tickets.resolues(prs), {7})

    def test_pr_non_fusionnee_ignoree(self):
        prs = [{"number": 9, "merged_at": None, "body": "Closes #7"}]
        self.assertEqual(tickets.resolues(prs), set())

    def test_issue_resolue_fermee_au_balayage(self):
        actions = tickets.plan([issue(7, 1)], MAINTENANT, {7})
        self.assertEqual(actions, [(7, "resolue")])


class Fermeture(unittest.TestCase):
    def test_closes_reconnu(self):
        self.assertFalse(tickets.pr_sans_fermeture("Résumé.\n\nCloses #12"))
        self.assertFalse(tickets.pr_sans_fermeture("fixes #3"))
        self.assertFalse(tickets.pr_sans_fermeture("Resolves #7"))

    def test_sans_fermeture_signale(self):
        self.assertTrue(tickets.pr_sans_fermeture("Refs #3 seulement"))
        self.assertTrue(tickets.pr_sans_fermeture(None))
        self.assertTrue(tickets.pr_sans_fermeture(""))


class Rapport(unittest.TestCase):
    def test_compte_et_actions(self):
        issues = [issue(1, 70), issue(2, 5), issue(3, 200, pr=True)]
        actions = tickets.plan(issues, MAINTENANT)
        texte = tickets.rapport(issues, actions, MAINTENANT, appliquees=False)
        self.assertIn("2 issue(s) ouverte(s)", texte)
        self.assertIn("#1 Ticket 1 : avertissement", texte)
        self.assertIn("à appliquer avec --appliquer", texte)

    def test_au_dela_du_seuil_signale(self):
        issues = [issue(n, 1) for n in range(tickets.SEUIL_OUVERTES + 1)]
        texte = tickets.rapport(issues, [], MAINTENANT, appliquees=True)
        self.assertIn("Au-delà du seuil", texte)


if __name__ == "__main__":
    unittest.main()
