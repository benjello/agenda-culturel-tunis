"""Sources silencieuses : rien annoncé depuis 30 jours (lieu fermé, compte changé, scraper cassé).

Sources en panne : la lecture échoue depuis JOURS_PANNE jours ou plus (page changée, site qui
bloque, compte privé, flux illisible).

Écrit la liste en Markdown sur la sortie standard (vide s'il n'y en a pas). Le workflow
des scrapers en fait une issue GitHub (« Sources silencieuses » ou « Sources en panne »),
mise à jour chaque jour et fermée quand tout va bien. La même règle colore la page
« Santé des sources ».

  python3 -m scrapers.alerte            # sources silencieuses
  python3 -m scrapers.alerte panne      # sources en panne
"""
from __future__ import annotations

import datetime as dt

import yaml

from .commun import RACINE
from .ecriture import lire_etat

JOURS = 30
JOURS_PANNE = 2  # une panne d'un soir (site en maintenance) ne justifie pas d'alerte


def silencieuses(maintenant: dt.datetime | None = None) -> list[tuple[dict, dict, int]]:
    """(source, état, jours sans rien) pour chaque source active muette depuis JOURS jours."""
    maintenant = maintenant or dt.datetime.now()
    sources = yaml.safe_load((RACINE / "_data" / "sources.yml").read_text()) or []
    etat = lire_etat()
    res = []
    for s in sources:
        if not s.get("actif", True):
            continue
        e = etat.get(s["id"]) or {}
        depuis = e.get("dernier_non_vide") or e.get("premier_passage")
        if not depuis:
            continue
        jours = (maintenant - dt.datetime.fromisoformat(depuis)).days
        if jours >= JOURS:
            res.append((s, e, jours))
    return sorted(res, key=lambda x: -x[2])


def en_panne(maintenant: dt.datetime | None = None) -> list[tuple[dict, dict, int]]:
    """(source, état, jours en panne) pour chaque source active dont la lecture échoue depuis JOURS_PANNE jours.
    Une source « en attente » (clé manquante, crédit épuisé) n'est pas une panne."""
    maintenant = maintenant or dt.datetime.now()
    sources = yaml.safe_load((RACINE / "_data" / "sources.yml").read_text()) or []
    etat = lire_etat()
    res = []
    for s in sources:
        e = etat.get(s["id"]) or {}
        if not s.get("actif", True) or e.get("ok") is not False or e.get("attente"):
            continue
        depuis = e.get("panne_depuis") or e.get("dernier_succes") or e.get("premier_passage") or e.get("dernier_passage")
        if not depuis:
            continue
        jours = (maintenant - dt.datetime.fromisoformat(depuis)).days
        if jours >= JOURS_PANNE:
            res.append((s, e, jours))
    return sorted(res, key=lambda x: -x[2])


def rapport_panne(liste) -> str:
    if not liste:
        return ""
    lignes = [f"Ces sources actives ne se lisent plus depuis {JOURS_PANNE} jours ou plus. "
              "À réparer : page qui a changé de forme, site qui bloque les robots, compte devenu privé.", "",
              "| Source | Jours en panne | Dernier succès | Erreur |", "|---|---|---|---|"]
    for s, e, j in liste:
        lignes.append(f"| [{s['nom']}]({s['url']}) (`{s['id']}`) | {j} | {(e.get('dernier_succes') or '—')[:10]} "
                      f"| {(e.get('erreur') or '').replace('|', '/')[:120]} |")
    lignes += ["", "Pour mettre une source en pause : `actif: false` dans `_data/sources.yml`.",
               "Cette issue est mise à jour chaque jour par le workflow des scrapers, et fermée quand la liste est vide."]
    return "\n".join(lignes)


def rapport(liste) -> str:
    if not liste:
        return ""
    lignes = [f"Ces sources actives n'ont rien annoncé depuis {JOURS} jours ou plus. "
              "À vérifier : lieu fermé, compte renommé, page qui a changé de forme.", "",
              "| Source | Jours sans rien | Dernière lecture | Erreur |", "|---|---|---|---|"]
    for s, e, j in liste:
        lignes.append(f"| [{s['nom']}]({s['url']}) (`{s['id']}`) | {j} | {(e.get('dernier_succes') or '—')[:10]} "
                      f"| {(e.get('erreur') or '').replace('|', '/')[:80]} |")
    lignes += ["", "Pour mettre une source en pause : `actif: false` dans `_data/sources.yml`.",
               "Cette issue est mise à jour chaque jour par le workflow des scrapers, et fermée quand la liste est vide."]
    return "\n".join(lignes)


if __name__ == "__main__":
    import sys
    print(rapport_panne(en_panne()) if sys.argv[1:] == ["panne"] else rapport(silencieuses()))
