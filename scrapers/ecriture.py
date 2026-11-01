"""Écrit le résultat d'un scraper dans le site.

- Événements : un fichier Markdown par événement dans _events/auto/<source>/,
  exactement comme ceux saisis à la main. Le dossier est réécrit à chaque passage.
- Films : _data/cinemas/<source>.json, affiché par la page Cinéma.
- État des sources : _data/etat_sources.json (dernier passage, succès, nombre d'événements).
"""
from __future__ import annotations

import datetime as dt
import json
import shutil

from .commun import RACINE, Evenement, Film, slug

DOSSIER_AUTO = RACINE / "_events" / "auto"
DOSSIER_CINEMAS = RACINE / "_data" / "cinemas"
FICHIER_ETAT = RACINE / "_data" / "etat_sources.json"


def _yaml(v) -> str:
    # Une chaîne JSON est aussi une chaîne YAML valide : pas de souci d'apostrophes ou de « : ».
    return json.dumps(v, ensure_ascii=False)


def _date(d: dt.datetime) -> str:
    return d.strftime("%Y-%m-%d %H:%M") if (d.hour or d.minute) else d.strftime("%Y-%m-%d")


def ecrire_evenements(source: dict, evenements: list[Evenement]) -> int:
    aujourd_hui = dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    a_venir = [e for e in evenements if (e.fin or e.debut) >= aujourd_hui]
    dossier = DOSSIER_AUTO / source["id"]
    if dossier.exists():
        shutil.rmtree(dossier)
    dossier.mkdir(parents=True)
    vus = set()
    for e in a_venir:
        nom = f"{e.debut:%Y-%m-%d}-{slug(e.titre)[:60]}"
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
        }
        lignes = ["---"] + [f"{k}: {_yaml(v)}" for k, v in champs.items() if v is not None]
        lignes += ["auto: true", "---", ""]
        # Le nom de fichier commence par la date ; on force la date complète dans le front matter.
        (dossier / f"{nom}.md").write_text("\n".join(lignes).replace(
            f'date: "{champs["date"]}"', f'date: {champs["date"]}'))
    return len(vus)


def ecrire_films(source: dict, films: list[Film]) -> int:
    DOSSIER_CINEMAS.mkdir(parents=True, exist_ok=True)
    data = {
        "id": source["id"], "nom": source["nom"], "url": source["url"],
        "mis_a_jour": dt.date.today().isoformat(),
        "films": [f.en_dict() for f in sorted(films, key=lambda f: f.titre.lower())],
    }
    (DOSSIER_CINEMAS / f"{source['id']}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return len(films)


def lire_etat() -> dict:
    try:
        return json.loads(FICHIER_ETAT.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def ecrire_etat(etat: dict) -> None:
    FICHIER_ETAT.write_text(json.dumps(etat, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
