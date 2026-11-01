"""Billetteries en ligne faites par SK TECH : El Teatro et Théâtre de l'Opéra de Tunis.

Les deux sites ont la même structure :
  /fr/programmes            liste des spectacles
  /fr/programme/<nom>       un spectacle, avec un tableau des séances
                            (« 07 Novembre 2026 à 19:30 »)

Options :
  lieu : nom du lieu affiché (les fiches ne le répètent pas toujours)
"""
from __future__ import annotations

import datetime as dt
import re
import time
from urllib.parse import urljoin

from ..commun import Evenement, dates_fr, meta, page, propre


def spectacles(soup, base: str) -> list[str]:
    vus = []
    for a in soup.find_all("a", href=re.compile(r"/fr/programme/[^/?#]+")):
        url = urljoin(base, a["href"]).split("?")[0].split("#")[0]
        if url not in vus:
            vus.append(url)
    return vus


def lire_spectacle(soup, url: str, lieu: str, aujourd_hui: dt.datetime) -> Evenement | None:
    titre = propre((soup.find("h1") or soup.find("h2") or soup.new_tag("x")).get_text(" ")) or meta(soup, "og:title")
    titre = re.sub(r"\s*::.*$", "", titre)  # « Le fou :: Théatre de l'opéra Tunis »
    seances = sorted(d for d in set(dates_fr(soup.get_text(" "))) if d >= aujourd_hui)
    if not titre or not seances:
        return None
    prix = re.search(r"(\d+(?:[.,]\d+)?)\s*DT", soup.get_text(" "))
    return Evenement(titre=titre, debut=seances[0], fin=seances[-1] if len(seances) > 1 else None,
                     seances=seances, lien=url, lieu=lieu,
                     prix=f"{prix.group(1).replace('.000', '')} DT" if prix else "")


def recuperer(source: dict) -> list[Evenement]:
    lieu = (source.get("options") or {}).get("lieu", source["nom"])
    aujourd_hui = dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    evenements = []
    for url in spectacles(page(source["url"]), source["url"]):
        try:
            e = lire_spectacle(page(url), url, lieu, aujourd_hui)
            if e:
                evenements.append(e)
        except Exception:  # noqa: BLE001
            continue
        time.sleep(0.5)
    return evenements
