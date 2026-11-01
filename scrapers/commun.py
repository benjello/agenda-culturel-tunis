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


class EnAttente(Exception):
    """La source n'a pas pu être lue, mais ce n'est pas une panne du site
    (clé d'accès pas encore configurée…). Les événements déjà récupérés sont gardés."""


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
    # mois en arabe : noms maghrébins (جانفي…) et orientaux (يناير…)
    "جانفي": 1, "يناير": 1, "فيفري": 2, "فبراير": 2, "مارس": 3, "أفريل": 4, "أبريل": 4, "افريل": 4,
    "ماي": 5, "مايو": 5, "جوان": 6, "يونيو": 6, "جويلية": 7, "يوليو": 7, "أوت": 8, "اوت": 8,
    "أغسطس": 8, "سبتمبر": 9, "أكتوبر": 10, "اكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12,
}
_RE_DATE = re.compile(
    r"(\d{1,2})(?:er)?\s+(" + "|".join(sorted(MOIS, key=len, reverse=True)) + r")\.?\s+(\d{4})"
    r"(?:\s*(?:,|à|a|-|–|\()?\s*(\d{1,2})\s*[:hH]\s*(\d{2})?)?",
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


_RE_NUM = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b(?:\D{0,12}?(\d{1,2})\s*[:hH]\s*(\d{2})?)?")


def dates_num(texte: str) -> list[dt.datetime]:
    """Dates écrites en chiffres : « 26.09.2026 », « 26/09/2026 à 19h00 »."""
    res = []
    for j, m, a, h, mn in _RE_NUM.findall(texte):
        try:
            res.append(dt.datetime(int(a), int(m), int(j), int(h or 0), int(mn or 0)))
        except ValueError:
            continue
    return res


def toutes_dates(texte: str) -> list[dt.datetime]:
    return sorted(set(dates_fr(texte) + dates_num(texte)))


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
    image: str = ""                # affiche, si la source en donne une
    film: bool = False             # film à l'affiche (séances = jours de projection)
    imdb: str = ""                 # identifiant IMDb (tt…), si connu
    duree: int | None = None       # minutes
    genres: list[str] = field(default_factory=list)
    description: str = ""          # notice : quelques lignes tirées de la source (légende, résumé)
    artistes: list[str] = field(default_factory=list)  # line-up, si la source le donne


@dataclass
class Publication:
    """Une publication Facebook avec image (programme, affiche) et le texte lu dessus."""
    lien: str
    date: str                                         # AAAA-MM-JJ
    texte: str = ""                                   # texte de la publication
    images: list[str] = field(default_factory=list)   # chemins dans le site (assets/…)
    ocr_facebook: str = ""                            # texte de l'image lu par Facebook
    ocr: str = ""                                     # texte de l'image lu par Tesseract

    def en_dict(self):
        return asdict(self)


def film(titre: str, lien: str, lieu: str, jours, adresse: str = "", **autres) -> Evenement | None:
    """Un film à l'affiche dans une salle, au même format que tout événement :
    catégorie cinéma, une séance par jour (« AAAA-MM-JJ ») ou par horaire (« AAAA-MM-JJ HH:MM »)."""
    seances = sorted({dt.datetime.fromisoformat(j[:16]) for j in jours})
    if not seances:
        return None
    return Evenement(titre=titre, debut=seances[0], fin=seances[-1], lien=lien, lieu=lieu, adresse=adresse,
                     categorie="cinema", seances=seances, film=True, **autres)


# Mots du titre qui disent la vraie catégorie, quand la rubrique de la source est trop large
# (tunis.events range ses « Movie Night » dans « Arts & culture »). Le premier qui correspond gagne.
_CATEGORIES_DU_TITRE = [
    ("cinema", r"movie night|cin[ée][- ]?club|\bprojection\b|\bfilm\b|\bcin[ée]ma\b|court[s]?[- ]m[ée]trage"),
    ("musique", r"\bconcert\b|\blive\b|\bdj\b|listening session|session d.[ée]coute|\bjazz\b|\brap\b|\bmalouf\b|\boud\b"),
    ("danse", r"\bdanse\b|\bdance\b|\bballet\b|\bsalsa\b|\btango\b|\bbachata\b"),
    ("conference", r"conf[ée]rence|table ronde|\bd[ée]bat\b|\btalk\b|\bmasterclass\b"),
    ("litterature", r"\blecture\b|\bpo[ée]sie\b|\bdédicace\b|\blivre\b"),
    ("expo", r"\bexposition\b|\bexpo\b|\bvernissage\b|\bexhibition\b"),
]


def categorie_du_titre(titre: str) -> str:
    """Catégorie déduite du titre, ou "" si rien de net."""
    for cat, motif in _CATEGORIES_DU_TITRE:
        if re.search(motif, titre, re.I):
            return cat
    return ""


_RE_LIEU = re.compile(r"\bLieu\s*:\s*([^\n]{3,150})", re.I)
_RE_PLAGE = re.compile(r"\b(\d{1,2})(?:er)?\s*(?:[–-]|au)\s*(\d{1,2})(?:er)?\s+([A-Za-zéèûôÉ.]+)\s+(\d{4})")


def details_page(texte: str) -> dict:
    """Ce que la page d'un événement dit mieux que le flux : « Lieu : … », « Dates : 3–5 décembre 2026 »."""
    res = {}
    m = _RE_LIEU.search(texte)
    if m:
        lieu = re.split(r"\s*(?:📅|🕒|⏰|Dates?\s*:|Horaires?\s*:|Heure\s*:)", m.group(1))[0]
        res["lieu"] = propre(lieu).strip(" .,;")
    m = _RE_PLAGE.search(texte)
    if m and m.group(3).lower() in MOIS:
        try:
            mois, an = MOIS[m.group(3).lower()], int(m.group(4))
            res["debut"] = dt.datetime(an, mois, int(m.group(1)))
            res["fin"] = dt.datetime(an, mois, int(m.group(2)))
        except ValueError:
            pass
    return res


# Cours et activités payantes récurrentes (yoga, fitness…) : gardés mais placés en bas de liste,
# pour que l'agenda mette en avant la création (concerts, pièces, expos).
_COMMERCIAL = re.compile(r"\byoga\b|pilates|fitness|zumba|m[ée]ditation|sophrologie|bien[- ][êe]tre|\bbrunch\b|"
                         r"happy hour|team ?building|cours (?:de|d')|\bcoaching\b|d[ée]veloppement personnel", re.I)


def est_discret(titre: str) -> bool:
    return bool(_COMMERCIAL.search(titre))


_FAMILLE = re.compile(r"jeune public|\benfants?\b|en famille|\bfamilial|\bkids?\b|\bjunior|marionnette|\bcontes?\b|"
                      r"atelier (?:pour )?(?:les )?(?:petits|enfants)|d[èe]s \d{1,2} ans|\bpetits\b|"
                      r"أطفال|للأطفال|الطفل|عرائس|العائلة", re.I)


def est_famille(*textes: str) -> bool:
    """Spectacle, atelier ou film pour les enfants ou à voir en famille."""
    return any(_FAMILLE.search(t or "") for t in textes)


def resume(texte: str, n: int = 500) -> str:
    """Notice courte : texte propre, coupé à la fin d'une phrase ou d'un mot."""
    t = re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", (texte or "").strip()))
    if len(t) <= n:
        return t
    coupe = t[:n]
    fin = max(coupe.rfind(". "), coupe.rfind("\n"))
    return (coupe[:fin + 1] if fin > n * 0.5 else coupe.rsplit(" ", 1)[0] + " …").strip()


_GRATUIT = re.compile(r"entr[ée]e (?:libre|gratuite)|acc[eè]s (?:libre|gratuit)|\bgratuit|free entry|\bfree\b|"
                      r"الدخول مجاني|دخول مجاني|مجانا", re.I)
_MONTANT = re.compile(r"(?<![\d.,])(\d{1,4}(?:[.,]\d{1,3})?)\s*(?:DT|TND|dinars?|د\.?ت)\b", re.I)


def prix_du_texte(texte: str) -> str:
    """« Gratuit », « 20 DT » ou « 10 à 30 DT » d'après une légende ou un article, sinon ""."""
    if _GRATUIT.search(texte or ""):
        return "Gratuit"
    montants = sorted({float(m.replace(",", ".")) for m in _MONTANT.findall(texte or "")} - {0.0})
    montants = [m for m in montants if m < 1000]  # « 1500 DT » : sans doute un prix ou une bourse, pas un billet
    if not montants:
        return ""
    f = lambda x: f"{x:g}"  # noqa: E731
    return f"{f(montants[0])} DT" if len(montants) == 1 else f"{f(montants[0])} à {f(montants[-1])} DT"
