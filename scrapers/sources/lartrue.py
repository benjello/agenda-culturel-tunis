"""Scraper de L'Art Rue (lartrue.org) : association d'art contemporain de la médina de Tunis (Dream City…).

Le site n'a ni flux RSS ni JSON-LD : la page `/fr/agenda` liste des vignettes
(`li.focus-contents__item--agenda`) avec une date, une discipline et un titre,
et se charge par pages (`?page=N`, 9 vignettes par page).

La date de la vignette est lue en clair (« 12 novembre 2026 », « 12 - 14 novembre 2026 »,
« 12 novembre - 3 décembre 2026 »). Les vignettes sans date précise (projets de coopération datés
« 2023-2027 ») sont ignorées : ce ne sont pas des rendez-vous à Tunis.

Options :
  lieu   : lieu par défaut (L'Art Rue, Dar Bach Hamba)
  pages  : nombre maximal de pages à lire (5 par défaut)
"""
from __future__ import annotations

import datetime as dt
import re
from urllib.parse import urljoin

from ..commun import Evenement, page, propre, toutes_dates

LIEU = "L'Art Rue, Dar Bach Hamba, Médina de Tunis"

_MOIS = r"[A-Za-zéèêûôîà.]+"
_RE_MEME_MOIS = re.compile(rf"\b(\d{{1,2}})(?:er)?\s*(?:-|–|—|>|au|to)\s*(\d{{1,2}}\s+{_MOIS}\s+\d{{4}})", re.I)


def dates_de_la_vignette(texte: str) -> list[dt.datetime]:
    """Début et fin de la vignette ; liste vide si elle n'a pas de date précise."""
    texte = propre(texte).replace("\xa0", " ")
    m = _RE_MEME_MOIS.search(texte)
    if m:  # « 12 - 14 novembre 2026 » : le premier jour prend le mois et l'année du second
        fin = toutes_dates(m.group(2))
        if fin:
            f = fin[-1]
            try:
                return [f.replace(day=int(m.group(1))), f]
            except ValueError:
                return fin
    return toutes_dates(texte)


def lire_liste(soup, base: str, lieu: str, aujourd_hui: dt.datetime) -> list[Evenement]:
    res = []
    for li in soup.select("li.focus-contents__item--agenda"):
        a = li.find("a", href=True)
        titre = propre((li.select_one(".heading") or li).get_text(" "))
        date = li.select_one("p.date")
        dates = dates_de_la_vignette(date.get_text(" ")) if date else []
        if not a or not titre or not dates:
            continue
        if (dates[-1]) < aujourd_hui:
            continue
        genre = li.select_one(".genre")
        img = li.select_one("img.item__img")
        # La vignette enregistrée localement n'a pas d'adresse utile : on prend le repli distant s'il y en a un.
        image = ""
        if img:
            m = re.search(r"this\.src='([^']+)'", img.get("onerror", ""))
            image = m.group(1) if m else (img["src"] if img.get("src", "").startswith("http") else "")
        res.append(Evenement(titre=titre, debut=dates[0], fin=dates[-1] if len(dates) > 1 else None,
                             lien=urljoin(base, a["href"]), lieu=lieu, image=image,
                             genres=[propre(genre.get_text())] if genre and propre(genre.get_text()) else []))
    return res


def recuperer(source: dict) -> list[Evenement]:
    opts = source.get("options") or {}
    lieu = opts.get("lieu", LIEU)
    aujourd_hui = dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    base = source["url"]
    evenements, vus = [], set()
    for n in range(1, int(opts.get("pages", 5)) + 1):
        soup = page(f"{base}?page={n}" if n > 1 else base)
        vignettes = soup.select("li.focus-contents__item--agenda")
        if not vignettes:
            break
        for e in lire_liste(soup, base, lieu, aujourd_hui):
            if e.lien not in vus:
                vus.add(e.lien)
                evenements.append(e)
        if len(vignettes) < 9:
            break
    return evenements
