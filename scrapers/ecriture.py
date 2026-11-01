"""Écrit le résultat d'un scraper dans le site.

- Événements : un fichier Markdown par événement dans _events/auto/<source>/,
  exactement comme ceux saisis à la main. Le dossier est réécrit à chaque passage.
  Les films à l'affiche sont des événements comme les autres (catégorie cinéma,
  « film: true », une séance par jour de projection).
- Programmes publiés en image (affiches) : _data/programmes/<source>.json.
- État des sources : _data/etat_sources.json (dernier passage, succès, nombre d'événements).
"""
from __future__ import annotations

import datetime as dt
import json
import shutil

from .commun import RACINE, Evenement, Publication, est_discret, slug

DOSSIER_AUTO = RACINE / "_events" / "auto"
DOSSIER_PROGRAMMES = RACINE / "_data" / "programmes"
FICHIER_ETAT = RACINE / "_data" / "etat_sources.json"


def _yaml(v) -> str:
    # Une chaîne JSON est aussi une chaîne YAML valide : pas de souci d'apostrophes ou de « : ».
    return json.dumps(v, ensure_ascii=False)


def _date(d: dt.datetime) -> str:
    return d.strftime("%Y-%m-%d %H:%M") if (d.hour or d.minute) else d.strftime("%Y-%m-%d")


def ecrire(source: dict, resultat: list) -> int:
    """Range le résultat d'un scraper : événements et programmes (affiches)."""
    evenements = [x for x in resultat if isinstance(x, Evenement)]
    publications = [x for x in resultat if isinstance(x, Publication)]
    if publications or source.get("scraper") == "facebook_programmes":
        ecrire_publications(source, publications)
    n = ecrire_evenements(source, evenements)
    return n if evenements or not publications else len(publications)


def ecrire_evenements(source: dict, evenements: list[Evenement]) -> int:
    aujourd_hui = dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    for e in evenements:  # séances passées retirées : l'événement commence à la prochaine
        if e.seances:
            e.seances = [s for s in e.seances if s >= aujourd_hui] or e.seances
            e.debut = e.seances[0]
    a_venir = [e for e in evenements if (e.fin or e.debut) >= aujourd_hui]
    dossier = DOSSIER_AUTO / source["id"]
    if dossier.exists():
        shutil.rmtree(dossier)
    dossier.mkdir(parents=True)
    vus = set()
    for e in a_venir:
        nom = f"{e.debut:%Y-%m-%d}-{slug(e.titre)[:60]}"
        if nom in vus:  # même titre le même jour, dans un autre lieu
            nom += "-" + slug(e.lieu)[:30]
        if nom in vus:
            continue
        vus.add(nom)
        champs = {
            "title": e.titre,
            "date": _date(e.debut),
            "end_date": _date(e.fin) if e.fin and e.fin.date() != e.debut.date() else None,
            "venue": e.lieu or source["nom"],
            "address": e.adresse or None,
            "category": e.categorie or source.get("categorie") or "autre",
            "price": e.prix or None,
            "link": e.lien,
            "source": source["id"],
            "source_name": source["nom"],
            "seances": [_date(s) for s in e.seances] if len(e.seances) > 1 else None,
            "image": e.image or None,
            "film": True if e.film else None,
            "imdb": e.imdb or None,
            "duration": e.duree or None,
            "genres": e.genres or None,
            "discret": True if est_discret(e.titre) else None,
        }
        lignes = ["---"] + [f"{k}: {_yaml(v)}" for k, v in champs.items() if v is not None]
        lignes += ["auto: true", "---", ""]
        # Le nom de fichier commence par la date ; on force la date complète dans le front matter.
        (dossier / f"{nom}.md").write_text("\n".join(lignes).replace(
            f'date: "{champs["date"]}"', f'date: {champs["date"]}'))
    return len(vus)


def ecrire_publications(source: dict, publications: list[Publication]) -> int:
    DOSSIER_PROGRAMMES.mkdir(parents=True, exist_ok=True)
    data = {
        "id": source["id"], "nom": source["nom"], "url": source["url"],
        "mis_a_jour": dt.date.today().isoformat(),
        "publications": [p.en_dict() for p in publications],
    }
    (DOSSIER_PROGRAMMES / f"{source['id']}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return len(publications)


def lire_etat() -> dict:
    try:
        return json.loads(FICHIER_ETAT.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def ecrire_etat(etat: dict) -> None:
    FICHIER_ETAT.write_text(json.dumps(etat, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
