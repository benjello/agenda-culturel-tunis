"""Les grands festivals dans l'agenda, dès que leurs dates sont connues.

Un festival de _data/festivals.yml avec des dates confirmées (debut, fin, sans
« date_estimee ») devient un événement de l'agenda, même avant que son programme
sorte : _events/festivals/<debut>-<id>.md. Ces fichiers sont refaits à chaque passage.

Pas de doublon avec un festival déjà écrit à la main dans _events/manuel (Fabrika).

  python3 -m scrapers.festivals
"""
from __future__ import annotations

import datetime as dt
import json

import yaml

from .commun import RACINE
from .doublons import _lire

DOSSIER = RACINE / "_events" / "festivals"


def _y(v) -> str:
    return json.dumps(v, ensure_ascii=False)


def a_ecrire(festivals: list[dict], titres_manuels: list[str], aujourd_hui: dt.date) -> list[dict]:
    res = []
    for f in festivals:
        if not f.get("debut") or f.get("date_estimee"):
            continue
        fin = f.get("fin") or f["debut"]
        if fin < aujourd_hui:
            continue
        mots = [m.strip().lower() for m in str(f.get("mots") or f["nom"]).split("|") if m.strip()]
        if any(m in t.lower() for t in titres_manuels for m in mots):
            continue
        res.append(f)
    return res


def fichier(f: dict) -> tuple[str, str]:
    nom = f"{f['debut']:%Y-%m-%d}-{f['id']}.md"
    titre = f["nom"] + (f" ({f['edition']})" if f.get("edition") else "")
    champs = {
        "title": titre, "end_date": f"{f['fin']:%Y-%m-%d}" if f.get("fin") and f["fin"] != f["debut"] else None,
        "venue": f.get("lieu") or "Tunis", "ville": f.get("ville") or "tunis", "category": f.get("genre") or "autre",
        "link": f.get("site") or f.get("facebook") or f.get("instagram") or f.get("source_dates"),
        "source": "festivals", "source_name": "Calendrier des festivals", "festival": f["id"],
    }
    lignes = ["---", f"title: {_y(titre)}", f"date: {f['debut']:%Y-%m-%d}"]
    lignes += [f"{k}: {_y(v)}" for k, v in champs.items() if k != "title" and v]
    lignes += ["---", ""]
    corps = ("Dates confirmées" + (f" ([source]({f['source_dates']}))" if f.get("source_dates") else "") + ". "
             + ("Le programme est publié." if f.get("programme") else "Le programme n'est pas encore publié : "
                "il paraît d'abord sur les réseaux du festival.") + "\n")
    return nom, "\n".join(lignes) + corps


def main() -> int:
    festivals = yaml.safe_load((RACINE / "_data" / "festivals.yml").read_text()) or []
    titres = []
    for f in (RACINE / "_events" / "manuel").glob("*.md"):
        c, _ = _lire(f)
        if c:
            titres.append(str(c.get("title") or ""))
    DOSSIER.mkdir(exist_ok=True)
    gardes = set()
    for f in a_ecrire(festivals, titres, dt.date.today()):
        nom, texte = fichier(f)
        gardes.add(nom)
        chemin = DOSSIER / nom
        if not chemin.exists() or chemin.read_text() != texte:
            chemin.write_text(texte)
    for f in DOSSIER.glob("*.md"):
        if f.name not in gardes:
            f.unlink()
    print(f"Festivals : {len(gardes)} dans l'agenda")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
