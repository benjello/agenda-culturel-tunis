"""El Teatro (Tunis) : page « programme de la saison » du site elteatrotunisie.com.

Le site n'a plus de fiche par spectacle : la page liste, pour chaque spectacle,
un titre (titre en graphie latine, parfois un sous-titre en arabe) suivi d'un
bloc de séances (« 24 septembre 2026 à 19h30 », « 17 Décembre 2026 A 17h »).
Les intitulés sans séance (festivals, Journées de Carthage) sont ignorés.

Options :
  lieu : nom du lieu affiché (par défaut le nom de la source)
"""
from __future__ import annotations

import datetime as dt
import re

from ..commun import Evenement, page

MOIS = {m: i for i, m in enumerate(
    ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
     "septembre", "octobre", "novembre", "décembre"], start=1)}
MOIS.update({"fevrier": 2, "aout": 8, "decembre": 12})

# Une séance porte forcément une heure : une date seule (festival, fin de manifestation) est ignorée.
_RE_SEANCE = re.compile(
    r"(\d{1,2})\s+([A-Za-zéûÉÛ]+)\s+(\d{4})\s*(?:à|a|A)?\s*(\d{1,2})h(\d{2})?(?!\d)", re.I)
_RE_ARABE = re.compile(r"[؀-ۿ]")


def _latin(texte: str) -> bool:
    return bool(re.search(r"[A-Za-zÀ-ÿ]", texte)) and not _RE_ARABE.search(texte)


def _seances(texte: str) -> list[dt.datetime]:
    res = []
    for jour, mois, annee, h, m in _RE_SEANCE.findall(texte):
        numero = MOIS.get(mois.lower())
        if not numero:
            continue
        try:
            res.append(dt.datetime(int(annee), numero, int(jour), int(h or 0), int(m or 0)))
        except ValueError:
            continue
    return res


def extraire(soup, lieu: str, aujourd_hui: dt.datetime, lien: str) -> list[Evenement]:
    """Une fiche Evenement par spectacle, à partir de la page programme."""
    corps = soup.find("main") or soup
    noeuds = corps.find_all(["h1", "h2", "h3", "h4", "h5", "div"])
    titres_vus: dict[str, Evenement] = {}
    titre_courant = ""      # dernier titre latin rencontré
    titre_arabe = ""        # repli si le spectacle n'a qu'un intitulé arabe
    for noeud in noeuds:
        if noeud.name in ("h1", "h2", "h3", "h4", "h5"):
            texte = " ".join(noeud.get_text(" ").split())
            if not texte or texte.lower().startswith(("de ", "par ", "programme", "saison")):
                continue
            if _latin(texte):
                titre_courant = texte
            else:
                titre_arabe = texte      # le dernier intitulé arabe avant le bloc de séances
            continue
        classes = " ".join(noeud.get("class", []))
        if "elementor-widget-icon-list" not in classes:
            continue
        seances = [s for s in _seances(noeud.get_text(" ")) if s >= aujourd_hui]
        titre = titre_courant or titre_arabe
        titre_arabe = ""
        if not titre or not seances:
            continue
        if titre in titres_vus:
            fiche = titres_vus[titre]
            fiche.seances = sorted(set(fiche.seances + seances))
        else:
            titres_vus[titre] = Evenement(titre=titre, debut=seances[0], lien=lien, lieu=lieu,
                                          categorie="theatre", seances=sorted(set(seances)))
    for fiche in titres_vus.values():
        fiche.fin = fiche.seances[-1] if len(fiche.seances) > 1 else None
        fiche.debut = fiche.seances[0]
    return list(titres_vus.values())


def recuperer(source: dict) -> list[Evenement]:
    opts = source.get("options") or {}
    lieu = opts.get("lieu", source["nom"])
    aujourd_hui = dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    evenements = extraire(page(source["url"]), lieu, aujourd_hui, source["url"])
    if not evenements:
        raise RuntimeError("aucun spectacle avec séances sur la page programme (site modifié ?)")
    return evenements
