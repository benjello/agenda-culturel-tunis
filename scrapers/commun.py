"""Outils partagés par tous les scrapers : téléchargement, dates, format commun."""
from __future__ import annotations

import datetime as dt
import json
import re
import unicodedata
from dataclasses import dataclass, field, asdict
from pathlib import Path

import requests
from bs4 import BeautifulSoup

RACINE = Path(__file__).resolve().parent.parent
DEBUG_DIR: Path | None = None  # rempli par --debug

# En-têtes d'un navigateur ordinaire : certains sites refusent les robots trop visibles.
ENTETES = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",
}
_session = requests.Session()
_session.headers.update(ENTETES)


def telecharger(url: str) -> str:
    r = _session.get(url, timeout=30)
    r.raise_for_status()
    r.encoding = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else "utf-8"
    if DEBUG_DIR:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        (DEBUG_DIR / (slug(url)[:120] + ".html")).write_text(r.text)
    return r.text


def telecharger_json(url: str):
    return json.loads(telecharger(url))


def page(url: str) -> BeautifulSoup:
    return BeautifulSoup(telecharger(url), "html.parser")


def slug(texte: str) -> str:
    t = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-") or "evenement"


def propre(texte: str | None) -> str:
    return re.sub(r"\s+", " ", texte or "").strip()


MOIS = {
    "janvier": 1, "janv": 1, "fevrier": 2, "février": 2, "fevr": 2, "févr": 2, "mars": 3,
    "avril": 4, "avr": 4, "mai": 5, "juin": 6, "juillet": 7, "juil": 7, "aout": 8, "août": 8,
    "septembre": 9, "sept": 9, "octobre": 10, "oct": 10, "novembre": 11, "nov": 11,
    "decembre": 12, "décembre": 12, "dec": 12, "déc": 12,
}
_RE_DATE = re.compile(
    r"(\d{1,2})(?:er)?\s+(" + "|".join(sorted(MOIS, key=len, reverse=True)) + r")\.?\s+(\d{4})"
    r"(?:\s*(?:,|à|a|-|–)?\s*(\d{1,2})\s*[:hH]\s*(\d{2})?)?",
    re.IGNORECASE,
)


def dates_fr(texte: str) -> list[dt.datetime]:
    """Toutes les dates françaises d'un texte : « 07 Novembre 2026 à 19:30 », « 5 nov. 2026 »…"""
    res = []
    for j, m, a, h, mn in _RE_DATE.findall(texte):
        try:
            res.append(dt.datetime(int(a), MOIS[m.lower()], int(j), int(h or 0), int(mn or 0)))
        except ValueError:
            continue
    return res


def json_ld_evenements(soup: BeautifulSoup) -> list[dict]:
    """Événements schema.org (JSON-LD) présents dans une page, s'il y en a."""
    trouves = []

    def parcourir(obj):
        if isinstance(obj, list):
            for o in obj:
                parcourir(o)
        elif isinstance(obj, dict):
            t = obj.get("@type")
            types = t if isinstance(t, list) else [t]
            if any(isinstance(x, str) and x.endswith("Event") for x in types):
                trouves.append(obj)
            for k in ("@graph", "itemListElement", "item", "subEvent"):
                if k in obj:
                    parcourir(obj[k])

    for s in soup.find_all("script", type="application/ld+json"):
        try:
            parcourir(json.loads(s.string or ""))
        except (json.JSONDecodeError, TypeError):
            continue
    return trouves


def meta(soup: BeautifulSoup, nom: str) -> str:
    tag = soup.find("meta", attrs={"property": nom}) or soup.find("meta", attrs={"name": nom})
    return propre(tag.get("content")) if tag and tag.get("content") else ""


@dataclass
class Evenement:
    """Format commun : ce que chaque scraper doit produire pour un événement."""
    titre: str
    debut: dt.datetime
    lien: str                      # page d'origine (fiche du lieu, billetterie…)
    lieu: str = ""
    fin: dt.datetime | None = None
    adresse: str = ""
    categorie: str = ""
    prix: str = ""
    seances: list[dt.datetime] = field(default_factory=list)


@dataclass
class Film:
    """Format des cinémas : un film et ses jours de projection."""
    titre: str
    lien: str
    jours: list[str] = field(default_factory=list)   # dates AAAA-MM-JJ
    duree: int | None = None                          # minutes
    genres: list[str] = field(default_factory=list)
    affiche: str | None = None

    def en_dict(self):
        return asdict(self)
