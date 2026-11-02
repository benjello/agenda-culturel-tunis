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
import re

import yaml

from .commun import RACINE
from .doublons import _ecrire, _lire, _norm
from .ecriture import DOSSIER_AUTO

DOSSIER = RACINE / "_events" / "festivals"


def _y(v) -> str:
    return json.dumps(v, ensure_ascii=False)


def a_ecrire(festivals: list[dict], titres_manuels: list[str], aujourd_hui: dt.date) -> list[dict]:
    res = []
    for f in festivals:
        if not f.get("debut") or f.get("date_estimee") or f.get("sans_fiche"):
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


def _motif(mots: list[str]):
    """Mots entiers, sans casse ni accents : « Jaou » ne trouve pas « Jaouhar »."""
    return re.compile(r"\b(?:" + "|".join(re.escape(_norm(m)) for m in mots) + r")\b") if mots else None


def rattacher(festivals: list[dict], dossier=DOSSIER_AUTO) -> int:
    """Étiquette chaque événement de l'agenda avec le festival auquel il appartient (champ « festival »).

    Un événement est relié à un festival si :
    - son titre contient un des mots du festival (`mots` dans _data/festivals.yml) ;
    - ou le début de sa notice le cite, sauf pour les sigles (« JTC », « JCC » : trop ambigus dans un texte) ;
    et si ses dates tombent pendant le festival (3 jours de marge avant, pour les avant-premières).
    Les événements d'une source de presse ou du calendrier des festivals gardent le leur.
    Renvoie le nombre d'événements étiquetés ; refait à chaque passage (rien n'est gardé d'un passage à l'autre)."""
    regles = []
    for f in festivals:
        mots = [m.strip() for m in str(f.get("mots") or f["nom"]).split("|") if m.strip()]
        debut, fin = f.get("debut"), f.get("fin") or f.get("debut")
        marge = (debut - dt.timedelta(days=3)) if debut else None
        regles.append((f["id"], _motif(mots), _motif([m for m in mots if len(m) >= 4 and m != m.upper()]), marge, fin))
    n = 0
    for chemin in sorted(dossier.glob("*/*.md")):
        champs, corps = _lire(chemin)
        if not champs or champs.get("source") == "festivals" or str(champs.get("source", "")).startswith("presse"):
            continue
        avant = champs.pop("festival", None)
        debut_e = str(champs.get("date"))[:10]
        fin_e = str(champs.get("end_date") or debut_e)[:10]
        titre, texte = _norm(champs.get("title")), _norm(corps[:600])
        trouve = None
        for id_, dans_titre, dans_texte, marge, fin in regles:
            if marge and (fin_e < marge.isoformat() or debut_e > fin.isoformat()):
                continue
            if (dans_titre and dans_titre.search(titre)) or (dans_texte and dans_texte.search(texte)):
                trouve = id_
                break
        if trouve:
            champs["festival"] = trouve
            n += 1
        if trouve != avant:
            if not isinstance(champs.get("date"), str):
                champs["date"] = str(champs.get("date"))[:16]
            auto = champs.pop("auto", True)
            champs["auto"] = auto
            _ecrire(chemin, champs, corps)
    return n


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
