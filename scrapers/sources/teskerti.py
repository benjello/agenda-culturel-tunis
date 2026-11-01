"""Teskerti (teskerti.tn), billetterie en ligne.

Couvre de nombreux lieux de Tunis qui n'ont pas de site : Théâtre municipal,
4ème Art, Le Rio, salle Africa, Ciné Alhambra Zéphyr…

1. La page d'accueil donne la liste des catégories (/category/<nom>).
2. Chaque catégorie donne ses événements (/evenement/<nom>).
3. Chaque fiche donne la date, l'heure, le lieu et le prix.

Options (facultatives) :
  categories_exclues : catégories ignorées (par défaut : sport, professionnel)
"""
from __future__ import annotations

import re
import time
from urllib.parse import urljoin

from ..commun import Evenement, dates_fr, json_ld_evenements, meta, page, propre, slug
from .jsonld import depuis_json_ld

BASE = "https://teskerti.tn/"
EXCLUES = {"sport", "professionnel"}
CATEGORIES = {"cinema": "cinema", "spectacle": "spectacle", "theatre": "theatre",
              "concert": "musique", "musique": "musique", "clubbing": "musique",
              "saisons-de-la-creation": "theatre", "humour": "spectacle", "stand-up": "spectacle"}
MOTS_LIEU = re.compile(r"\b(th[ée]âtre|theatre|salle|cin[ée]|cinema|espace|cit[ée]|centre|"
                       r"maison|club|h[ôo]tel|resort|palais|dar|rio|art|op[ée]ra|galerie|"
                       r"institut|zephyr|zéphyr|th[ée]atre)\b", re.I)


def liens(soup, motif: str) -> list[tuple[str, str]]:
    """(adresse absolue, texte) des liens dont l'adresse contient motif, sans doublons."""
    vus, res = set(), []
    for a in soup.find_all("a", href=True):
        url = urljoin(BASE, a["href"]).split("#")[0].split("?")[0]
        if motif in url and url not in vus:
            vus.add(url)
            res.append((url, propre(a.get_text(" "))))
    return res


def lieu_de_la_fiche(soup) -> tuple[str, str]:
    # 1) un élément dont la classe parle de lieu
    for el in soup.find_all(class_=re.compile(r"(lieu|venue|location|salle|place|adresse|address)", re.I)):
        t = propre(el.get_text(" "))
        if 2 < len(t) < 120:
            lignes = [propre(x) for x in el.get_text("\n").split("\n") if propre(x)]
            return lignes[0], ", ".join(lignes[1:2])
    # 2) une ligne courte qui ressemble à un nom de lieu
    for ligne in soup.get_text("\n").split("\n"):
        ligne = propre(ligne)
        if 3 < len(ligne) < 80 and MOTS_LIEU.search(ligne) and not dates_fr(ligne):
            return ligne, ""
    return "", ""


def lire_fiche(url: str, categorie: str) -> Evenement | None:
    soup = page(url)
    ld = depuis_json_ld(json_ld_evenements(soup), url)
    if ld:
        e = ld[0]
        e.categorie = categorie
        return e
    titre = meta(soup, "og:title") or propre((soup.find("h1") or soup.find("title") or soup).get_text(" "))
    titre = re.sub(r"\s*[|–-]\s*Teskerti.*$", "", titre, flags=re.I)
    dates = sorted(set(dates_fr(soup.get_text(" "))))
    if not titre or not dates:
        return None
    lieu, adresse = lieu_de_la_fiche(soup)
    prix = re.search(r"(?:à partir de|a partir de)\s*(\d+(?:[.,]\d+)?)\s*(?:TND|DT)", soup.get_text(" "), re.I)
    return Evenement(titre=titre, debut=dates[0], fin=dates[-1] if len(dates) > 1 else None,
                     seances=dates, lien=url, lieu=lieu, adresse=adresse, categorie=categorie,
                     prix=f"À partir de {prix.group(1)} DT" if prix else "")


def recuperer(source: dict) -> list[Evenement]:
    opts = source.get("options") or {}
    exclues = {slug(c) for c in opts.get("categories_exclues", EXCLUES)}
    accueil = page(BASE)
    categories = [(u, t) for u, t in liens(accueil, "/category/") if u.rstrip("/").split("/")[-1] not in exclues]
    a_lire: dict[str, str] = {}
    for url_cat, _ in categories:
        nom = url_cat.rstrip("/").split("/")[-1]
        cat = next((v for k, v in CATEGORIES.items() if k in nom), source.get("categorie", "autre"))
        for url_ev, _ in liens(page(url_cat), "/evenement/"):
            a_lire.setdefault(url_ev, cat)
        time.sleep(0.5)
    if not categories:  # si les catégories ne sont pas trouvées, on se contente de l'accueil
        a_lire = {u: source.get("categorie", "autre") for u, _ in liens(accueil, "/evenement/")}
    if not a_lire:
        raise RuntimeError("aucun lien /evenement/ trouvé sur teskerti.tn (site modifié ?)")
    evenements = []
    for url, cat in a_lire.items():
        try:
            e = lire_fiche(url, cat)
            if e:
                evenements.append(e)
        except Exception:  # noqa: BLE001 — une fiche illisible n'arrête pas les autres
            continue
        time.sleep(0.5)
    return evenements
