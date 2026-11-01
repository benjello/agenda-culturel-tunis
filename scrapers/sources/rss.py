"""Scraper générique : flux RSS ou Atom d'événements.

La date de l'événement est cherchée dans le titre puis dans la description
(« 26.09.2026 », « 26 septembre 2026 à 19h00 »). Les éléments sans date sont ignorés :
dans un flux d'actualités, seuls ceux qui annoncent une date passent.

Options :
  lieu          : nom du lieu par défaut
  nettoyer_titre: expression régulière à retirer du titre (facultatif)
  garder        : expression régulière : seuls les éléments dont le titre ou le texte la contiennent
                  sont gardés (pour écarter bourses, appels à candidatures…)
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

from ..commun import Evenement, propre, telecharger, toutes_dates

ATOM = "{http://www.w3.org/2005/Atom}"
_HEURE = re.compile(r"\b([01]?\d|2[0-3])\s*[hH:]\s*([0-5]\d)\b")


def _texte_html(h: str) -> str:
    return propre(BeautifulSoup(h or "", "html.parser").get_text(" "))


def elements(xml: str) -> list[dict]:
    racine = ET.fromstring(xml.encode() if isinstance(xml, str) else xml)
    res = []
    for it in racine.iter("item"):
        res.append({"titre": it.findtext("title", ""), "lien": it.findtext("link", ""),
                    "description": it.findtext("description", ""), "categorie": it.findtext("category", "")})
    for it in racine.iter(f"{ATOM}entry"):
        lien = it.find(f"{ATOM}link")
        res.append({"titre": it.findtext(f"{ATOM}title", ""), "lien": lien.get("href", "") if lien is not None else "",
                    "description": it.findtext(f"{ATOM}summary", "") or it.findtext(f"{ATOM}content", ""),
                    "categorie": ""})
    return res


def depuis_flux(xml: str, source: dict) -> list[Evenement]:
    opts = source.get("options") or {}
    lieu = opts.get("lieu", source["nom"])
    res = []
    for el in elements(xml):
        titre = propre(el["titre"])
        description = _texte_html(el["description"])
        dates = toutes_dates(titre)
        if dates and not any(d.hour or d.minute for d in dates):
            # heure souvent dans la description : « … le 26 septembre 2026 à 19h00 »
            precises = [d for d in toutes_dates(description) if d.date() == dates[0].date() and (d.hour or d.minute)]
            dates = precises or dates
        dates = dates or toutes_dates(description)
        heures = set(_HEURE.findall(description))
        if len(dates) == 1 and not (dates[0].hour or dates[0].minute) and len(heures) == 1:
            # « Le mardi 20 octobre 2026 à l'IRMC (17h30) » : une seule heure dans le texte
            h, mn = heures.pop()
            dates = [dates[0].replace(hour=int(h), minute=int(mn))]
        if not titre or not dates:
            continue
        if opts.get("garder") and not re.search(opts["garder"], f"{titre} {description}", re.I):
            continue
        if opts.get("nettoyer_titre"):
            titre = propre(re.sub(opts["nettoyer_titre"], "", titre))
        res.append(Evenement(titre=titre, debut=dates[0], fin=dates[-1] if len(dates) > 1 else None,
                             lien=propre(el["lien"]) or source["url"], lieu=lieu))
    return res


def recuperer(source: dict) -> list[Evenement]:
    xml = telecharger(source["url"])
    if not elements(xml):
        raise RuntimeError("flux vide ou illisible")
    return depuis_flux(xml, source)
