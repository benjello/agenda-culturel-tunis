"""Archive les événements passés avant que les scrapers ne les effacent.

Chaque passage des scrapers réécrit _events/auto/ et n'y garde que ce qui est à venir.
Ce script, lancé juste avant, recopie les événements terminés dans archives/donnees/AAAA.json
(un fichier par année, lu par la page /archives/ pour la recherche).

  python3 -m scrapers.archives            # archive ce qui est passé dans _events/ (gardé `conservation_jours` jours)
  python3 -m scrapers.archives --purger   # retire aussi les événements saisis à la main terminés depuis trop longtemps
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys

import yaml

from .commun import RACINE, propre, reglage

DOSSIER = RACINE / "archives" / "donnees"
RESUME = 240  # caractères de la notice gardés pour la recherche


def _lire(texte: str, chemin: str) -> dict | None:
    """Front matter + début de la notice → entrée d'archive, ou None si illisible."""
    m = re.match(r"^---\n(.*?)\n---\n?(.*)", texte, re.S)
    if not m:
        return None
    try:
        tete = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return None
    if not tete.get("title") or not tete.get("date") or tete.get("doublon") or tete.get("film"):
        return None
    debut = tete["date"]
    fin = tete.get("end_date") or debut
    heure = debut.strftime("%H:%M") if isinstance(debut, dt.datetime) else ""
    entree = {
        "titre": propre(str(tete["title"])),
        "debut": str(debut)[:10],
        "fin": str(fin)[:10],
        "heure": "" if heure == "00:00" else heure,
        "lieu": propre(str(tete.get("venue") or "")),
        "ville": tete.get("ville") or "",
        "categorie": tete.get("category") or "autre",
        "lien": tete.get("link") or "",
        "source": tete.get("source_name") or tete.get("source") or "",
        "resume": propre(re.sub(r"<[^>]+>|[#*_>\[\]]", " ", m.group(2)))[:RESUME],
        "fichier": chemin,
    }
    return entree


def _cle(e: dict) -> str:
    return f"{e['debut']}|{e['lieu'].lower()}|{e['titre'].lower()[:60]}"


def _charger() -> dict[str, dict[str, dict]]:
    annees = {}
    for f in DOSSIER.glob("[0-9][0-9][0-9][0-9].json"):  # pas index.json (le décompte par année)
        liste = json.loads(f.read_text())
        annees[f.stem] = {_cle(e): e for e in liste}
    return annees


def _ajouter(annees: dict, e: dict, aujourd_hui: str) -> bool:
    if e["fin"] >= aujourd_hui:
        return False
    a = annees.setdefault(e["debut"][:4], {})
    k = _cle(e)
    if k in a:
        return False
    a[k] = e
    return True


def _limite(aujourd_hui: dt.date, jours: int) -> str:
    return (aujourd_hui - dt.timedelta(days=jours)).isoformat()


def archiver(jours: int | None = None, aujourd_hui: dt.date | None = None) -> int:
    """Garde les événements terminés depuis moins de `jours` jours (réglage `conservation_jours`)."""
    jours = reglage("conservation_jours", 30) if jours is None else jours
    aujourd_hui = aujourd_hui or dt.date.today()
    limite = _limite(aujourd_hui, jours)
    annees = _charger()
    n = 0
    for f in sorted((RACINE / "_events").rglob("*.md")):
        if f.name == "README.md":
            continue
        e = _lire(f.read_text(), str(f.relative_to(RACINE)))
        n += bool(e and e["fin"] >= limite and _ajouter(annees, e, aujourd_hui.isoformat()))
    # Les entrées trop anciennes sortent ; une année devenue vide n'a plus de fichier.
    retirees = 0
    for annee, entrees in list(annees.items()):
        gardees = {k: e for k, e in entrees.items() if e["fin"] >= limite}
        retirees += len(entrees) - len(gardees)
        if gardees:
            annees[annee] = gardees
        else:
            del annees[annee]
    DOSSIER.mkdir(parents=True, exist_ok=True)
    if n or retirees:
        for f in DOSSIER.glob("[0-9][0-9][0-9][0-9].json"):
            if f.stem not in annees:
                f.unlink()
        for annee, entrees in annees.items():
            liste = sorted(entrees.values(), key=lambda e: (e["debut"], e["heure"], e["titre"]))
            (DOSSIER / f"{annee}.json").write_text(json.dumps(liste, ensure_ascii=False, indent=0) + "\n")
    # Index des années, lu par la page /archives/
    index = {a: len(e) for a, e in sorted(annees.items(), reverse=True)}
    (DOSSIER / "index.json").write_text(json.dumps(index) + "\n")
    print(f"archives : {n} ajouté(s), {retirees} retiré(s) (plus de {jours} jours), {sum(index.values())} en tout")
    return n


def purger(jours: int | None = None, aujourd_hui: dt.date | None = None) -> int:
    """Supprime les événements saisis à la main (_events/manuel, _events/propositions) terminés
    depuis plus de `jours` jours. Les événements auto partent déjà d'eux-mêmes (ecriture.py)."""
    jours = reglage("conservation_jours", 30) if jours is None else jours
    limite = _limite(aujourd_hui or dt.date.today(), jours)
    n = 0
    for dossier in ("manuel", "propositions"):
        for f in sorted((RACINE / "_events" / dossier).glob("*.md")):
            e = _lire(f.read_text(), str(f.relative_to(RACINE)))
            if e and e["fin"] < limite:
                f.unlink()
                n += 1
    print(f"purge : {n} événement(s) saisi(s) à la main retiré(s) (terminés avant le {limite})")
    return n


def main(argv: list[str]) -> int:
    archiver()
    # Suppression des événements saisis à la main : désactivée tant que « purger_manuels » est faux.
    if "--purger" in argv or reglage("purger_manuels", False):
        purger()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
