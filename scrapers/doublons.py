"""Repère les événements annoncés par plusieurs sources (ex. El Teatro et Teskerti).

Deux événements sont considérés comme le même s'ils commencent au même moment
dans le même lieu. Sans heure (films, expositions : seulement un jour), il faut
en plus que le titre commence pareil. On garde celui de la source la plus proche du lieu (le site du
lieu avant une billetterie, une billetterie avant un agrégateur) ; les autres sont
marqués « doublon » et ne s'affichent pas, mais leur lien est ajouté à l'événement
gardé (« Aussi sur : Teskerti »).

Lancé automatiquement à la fin de « python3 -m scrapers ».
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from .commun import slug
from .ecriture import DOSSIER_AUTO, _yaml

PRIORITE = {"lieu": 0, "cinema": 0, "billetterie": 1, "agenda": 2}
_FM = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)


def _lire(f: Path):
    m = _FM.match(f.read_text())
    if not m:
        return None, ""
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


def _ecrire(f: Path, champs: dict, corps: str):
    lignes = ["---"]
    for k, v in champs.items():
        if k == "date":
            lignes.append(f"date: {v}")
        else:
            lignes.append(f"{k}: {_yaml(v)}")
    f.write_text("\n".join(lignes + ["---", corps]).rstrip("\n") + "\n")


def _cle_lieu(lieu: str) -> str:
    # « El Teatro التياترو » et « El Teatro » → « el-teatro »
    return slug(lieu)[:12]


def marquer(sources: list[dict], dossier: Path = DOSSIER_AUTO) -> int:
    types = {s["id"]: s.get("type", "agenda") for s in sources}
    evts = []
    for f in sorted(dossier.glob("*/*.md")):
        champs, corps = _lire(f)
        if not champs:
            continue
        champs.pop("doublon", None)
        champs.pop("autres_sources", None)
        if not isinstance(champs.get("date"), str):
            champs["date"] = str(champs.get("date"))[:16]
        evts.append((f, champs, corps))
    groupes: dict[tuple, list] = {}
    for e in evts:
        c = e[1]
        date = str(c["date"])[:16]
        cle = (date, _cle_lieu(c.get("venue", "")))
        if len(date) <= 10 or date.endswith("00:00"):
            cle += (slug(str(c.get("title", "")))[:8],)
        groupes.setdefault(cle, []).append(e)
    n = 0
    for groupe in groupes.values():
        groupe.sort(key=lambda e: (PRIORITE.get(types.get(e[1].get("source")), 3), e[1].get("source", "")))
        garde = groupe[0]
        autres = [e for e in groupe[1:] if e[1].get("source") != garde[1].get("source")]
        if autres:
            garde[1]["autres_sources"] = [{"name": e[1].get("source_name"), "link": e[1].get("link"), "source": e[1].get("source")} for e in autres]
            for e in autres:
                e[1]["doublon"] = True
                n += 1
    for f, champs, corps in evts:
        # « auto: true » en dernier, comme à l'écriture
        auto = champs.pop("auto", True)
        champs["auto"] = auto
        _ecrire(f, champs, corps)
    return n
