"""Lecteurs de programmes publiés en image : tirent films et jours de séance du
texte d'une publication Facebook et du texte lu sur l'image (OCR).

Chaque salle publie toujours le même genre de programme ; on choisit le lecteur
dans le registre (options.lecteur). Les titres sont rapprochés des films déjà
connus (tunis.events, Pathé…) pour avoir un nom propre et le même lien IMDb.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import unicodedata

from .commun import MOIS, RACINE, Film, propre, slug

_MOIS = "|".join(sorted(MOIS, key=len, reverse=True))
# « Vendredi 30 octobre à 19h », « 1er novembre », « ler novembre » (OCR), sans année.
_RE_JOUR = re.compile(r"\b(\d{1,2}|1er|ler)\s+(" + _MOIS + r")\b\.?(?!\s*\d{4})", re.IGNORECASE)
_RE_PERIODE = re.compile(r"du\s+(\d{1,2})(?:er)?\s*(?:(" + _MOIS + r")\s*)?(?:\d{4}\s*)?au\s+(\d{1,2})(?:er)?\s+("
                         + _MOIS + r")\s+(\d{4})", re.IGNORECASE)


def _annee(mois: int, ref: dt.date) -> int:
    """Année d'une date sans année, vue depuis la date de publication."""
    if mois < ref.month - 6:
        return ref.year + 1
    if mois > ref.month + 6:
        return ref.year - 1
    return ref.year


def jours_sans_annee(texte: str, ref: dt.date) -> list[str]:
    res = set()
    for j, m in _RE_JOUR.findall(texte):
        mois = MOIS[m.lower()]
        jour = 1 if j.lower() in ("1er", "ler") else int(j)
        try:
            res.add(dt.date(_annee(mois, ref), mois, jour).isoformat())
        except ValueError:
            continue
    return sorted(res)


def periode(texte: str) -> list[str]:
    """« du 02 au 09 Novembre 2026 » → tous les jours de la période."""
    m = _RE_PERIODE.search(texte)
    if not m:
        return []
    j1, m1, j2, m2, a = m.groups()
    fin = dt.date(int(a), MOIS[m2.lower()], int(j2))
    debut = dt.date(int(a), MOIS[(m1 or m2).lower()], int(j1))
    if debut > fin:
        debut = debut.replace(year=debut.year - 1)
    return [(debut + dt.timedelta(days=i)).isoformat() for i in range((fin - debut).days + 1)]


def titres_connus() -> list[str]:
    """Titres des films des autres cinémas (fichiers _data/cinemas/)."""
    titres = []
    for f in sorted((RACINE / "_data" / "cinemas").glob("*.json")):
        try:
            titres += [x["titre"] for x in json.loads(f.read_text()).get("films", [])]
        except (json.JSONDecodeError, KeyError):
            continue
    return titres


def _cle(titre: str) -> str:
    """Partie principale d'un titre : « Shaun le Mouton : La Bêêête… » → shaun-le-mouton."""
    return slug(re.split(r"\s[:/–-]\s|\s/\s", titre)[0])


_HARAKAT = re.compile("[\u064B-\u0652\u0670\u0640]")  # voyelles et allongements arabes


def _arabe(texte: str) -> list[str]:
    return [m for m in re.findall(r"[\u0600-\u06FF][\u0600-\u06FF\s]{2,}", _HARAKAT.sub("", texte))]


def titre_connu(texte: str, connus: list[str]) -> str | None:
    s = f"-{slug(texte)}-"
    arabe = _HARAKAT.sub("", texte)
    for t in sorted(connus, key=len, reverse=True):
        cle = _cle(t)
        if len(cle) >= 4 and f"-{cle}-" in s:
            return t
        if any(len(a.strip()) >= 3 and a.strip() in arabe for a in _arabe(t)):
            return t
    return None


def _a_venir(jours: list[str]) -> list[str]:
    aujourd_hui = dt.date.today().isoformat()
    return [j for j in jours if j >= aujourd_hui]


def normaliser(texte: str) -> str:
    """Lettres « 𝗪𝗲𝗲𝗸𝗲𝗻𝗱 » (gras Unicode) → « Weekend »."""
    return unicodedata.normalize("NFKC", texte)


def liste_films(publications: list[dict], connus: list[str]) -> list[Film]:
    """Programme de la semaine en texte : « À l'affiche du 02 au 09 Novembre » + une ligne « 🎬 Titre » par film.
    (Alhambra Zéphyr.) Seule la publication la plus récente qui a ce format compte."""
    for p in publications:
        texte = normaliser(p.get("texte", ""))
        jours = _a_venir(periode(texte))
        lignes = [propre(l.split("🎬", 1)[1]) for l in texte.splitlines() if "🎬" in l]
        if jours and lignes:
            return [Film(titre=titre_connu(t, connus) or t, lien=p["lien"], jours=jours) for t in lignes if t]
    return []


def un_film_par_affiche(publications: list[dict], connus: list[str]) -> list[Film]:
    """Une affiche par film, avec ses jours de projection (Ciné 350)."""
    films: dict[str, Film] = {}
    for p in publications:
        texte, ocr = normaliser(p.get("texte", "")), p.get("ocr") or ""
        ref = dt.date.fromisoformat(p["date"]) if p.get("date") else dt.date.today()
        jours = _a_venir(jours_sans_annee(f"{texte}\n{ocr}", ref))
        if not jours:
            continue
        titre = titre_connu(f"{texte}\n{ocr}", connus)
        if not titre:  # ligne avant « Un film de … »
            lignes = [propre(l) for l in ocr.splitlines()]
            i = next((i for i, l in enumerate(lignes) if re.match(r"un film d", l, re.I)), None)
            titre = lignes[i - 1] if i else None
        if not titre:  # titre entre guillemets dans la publication
            m = re.search(r"[«\"“]\s*([^»\"”]{2,60}?)\s*[»\"”]", texte)
            titre = m.group(1) if m else None
        titre = titre or propre(re.sub(r"[^\w\s'’:-]", " ", texte.splitlines()[0] if texte else "")) or "Film"
        f = films.setdefault(slug(titre) or titre, Film(titre=titre, lien=p["lien"]))
        f.jours = sorted(set(f.jours) | set(jours))
    return list(films.values())


LECTEURS = {"liste_films": liste_films, "un_film_par_affiche": un_film_par_affiche}
