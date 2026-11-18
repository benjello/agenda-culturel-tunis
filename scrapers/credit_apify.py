"""Consommation du crédit Apify (Instagram, Facebook) : _data/apify.json et alerte.

Lit https://api.apify.com/v2/users/me/limits avec APIFY_TOKEN. Écrit la dépense du mois
dans _data/apify.json (affichée sur la page Santé). L'alerte n'est imprimée (texte Markdown,
le workflow en fait un ticket GitHub) que si le crédit risque de manquer avant le
renouvellement : soit déjà épuisé, soit dépense prévue en fin de cycle au-dessus de la limite.

  python3 -m scrapers.credit_apify > alerte-apify.md
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

import requests

from . import commun
from .commun import RACINE

FICHIER = RACINE / "_data" / "apify.json"


def _jour(texte: str | None) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(texte or "")[:10])
    except ValueError:
        return None


def prevision(depense: float, debut: dt.date | None, fin: dt.date | None, auj: dt.date) -> float | None:
    """Dépense prévue à la fin du cycle, au rythme observé depuis son début.

    Sans date de début, on suppose un cycle d'un mois se terminant à `fin`.
    """
    if fin is None:
        return None
    if debut is None:
        debut = fin - dt.timedelta(days=30)
    total = (fin - debut).days
    ecoule = max((auj - debut).days, 1)
    if total <= 0:
        return None
    return round(depense * total / ecoule, 2)


def lire(token: str) -> dict:
    r = requests.get("https://api.apify.com/v2/users/me/limits",
                     headers={"Authorization": f"Bearer {token}"}, timeout=30)
    r.raise_for_status()
    d = r.json().get("data") or {}
    depense = float((d.get("current") or {}).get("monthlyUsageUsd") or 0)
    limite = float((d.get("limits") or {}).get("maxMonthlyUsageUsd") or 0)
    cycle = d.get("monthlyUsageCycle") or {}
    auj = dt.date.today()
    fin = _jour(cycle.get("endAt"))
    return {"jour": auj.isoformat(), "depense": round(depense, 2), "limite": round(limite, 2),
            "pourcent": round(100 * depense / limite) if limite else None,
            "fin_cycle": str(cycle.get("endAt") or "")[:10],
            "prevision": prevision(depense, _jour(cycle.get("startAt")), fin, auj)}


def alerte(c: dict) -> str:
    if c.get("pourcent") is None:
        return ""
    prev = c.get("prevision")
    limite = c["limite"]
    epuise = c["pourcent"] >= 100
    risque = prev is not None and prev > limite
    if not (epuise or risque):
        return ""
    if epuise:
        constat = f"Le crédit Apify du mois est **épuisé** : {c['depense']} $ sur {limite} $ ({c['pourcent']} %)."
    else:
        constat = (f"Au rythme actuel, le crédit Apify du mois sera **épuisé avant le renouvellement** : "
                   f"{c['depense']} $ dépensés sur {limite} $ ({c['pourcent']} %), "
                   f"soit environ {prev} $ prévus en fin de cycle.")
    return (f"{constat}\n\n"
            f"Tant qu'il n'est pas rechargé, les comptes Instagram et les pages Facebook ne sont plus lus "
            f"(les sites, flux RSS et journaux continuent).\n\n"
            f"Recharge du crédit : {c['fin_cycle'] or 'voir la console Apify, Billing'}. "
            f"Pour augmenter la limite mensuelle ou le plan : console Apify, Billing.\n\n"
            f"Ce ticket se ferme tout seul quand le crédit ne risque plus de manquer.\n")


def main() -> int:
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        print("pas de APIFY_TOKEN", file=sys.stderr)
        return 0
    try:
        c = lire(token)
    except (requests.RequestException, ValueError) as exc:
        print(f"crédit Apify illisible : {commun.masquer(str(exc))}", file=sys.stderr)
        return 0
    FICHIER.write_text(json.dumps(c, ensure_ascii=False, indent=1) + "\n")
    print(f"Apify : {c['depense']} $ sur {c['limite']} $ ({c['pourcent']} %), "
          f"prévu en fin de cycle : {c['prevision']} $", file=sys.stderr)
    sys.stdout.write(alerte(c))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
