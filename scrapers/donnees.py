"""Branche « donnees » : tout ce que le robot produit y vit, en un seul commit remplacé à chaque passage.

`main` ne garde que le code (et les événements saisis à la main) ; l'historique des données n'est
pas conservé, ce qui évite que le dépôt grossisse à chaque passage (affiches, JSON, caches).

  python3 -m scrapers.donnees recuperer    # restaure les données de la branche dans le dossier de travail
  python3 -m scrapers.donnees enregistrer  # remplace la branche par un commit sans parent (push --force)
  python3 -m scrapers.donnees chemins      # liste les chemins gérés (pour .gitignore, contrôle)
"""
from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .commun import RACINE

BRANCHE = "donnees"

# Données générées par le robot (reprises de l'ancienne étape « Enregistrer » de scrapers.yml).
CHEMINS = [
    "_events/auto",
    "_events/festivals",
    "_data/etat_sources.json",
    "_data/films.json",
    "_data/critiques.json",
    "_data/presse.json",
    "_data/wikidata.json",
    "_data/controle.json",
    "_data/images.json",
    "_data/traductions.json",
    "_data/libelles.json",
    "_data/bilan.json",
    "_data/apify.json",
    "_data/descriptifs.json",
    "_data/enrichi.json",
    "_data/lieux.json",
    "_data/geo.json",
    "_data/programmes",
    "_cache/publications",
    "assets/programmes",
    "assets/images",
    "_lieux",
    "_collectifs",
    "_artistes",
    "archives/donnees",
]


class BrancheAbsente(RuntimeError):
    pass


def _git(*args: str, env: dict | None = None, racine: Path | None = None, entree: bytes | None = None,
         binaire: bool = False):
    r = subprocess.run(["git", *args], cwd=racine or RACINE, capture_output=True, input=entree,
                       env={**os.environ, **(env or {})})
    if r.returncode:
        raise RuntimeError(f"git {' '.join(args)} : {r.stderr.decode(errors='replace').strip()}")
    return r.stdout if binaire else r.stdout.decode().strip()


def recuperer(racine: Path | None = None, origine: str = "origin") -> int:
    """Restaure les données de la branche. Sans branche, on s'arrête : repartir de zéro
    perdrait les caches (Wikidata, traductions, géo) et les affiches."""
    racine = racine or RACINE
    try:
        _git("fetch", "--depth=1", origine, BRANCHE, racine=racine)
    except RuntimeError as e:
        raise BrancheAbsente(f"branche « {BRANCHE} » introuvable sur « {origine} » : arrêt, "
                             f"rien n'est repris de zéro. {e}") from e
    archive = _git("archive", "FETCH_HEAD", racine=racine, binaire=True)
    subprocess.run(["tar", "-x", "-C", str(racine)], input=archive, check=True)
    print(f"données restaurées depuis {origine}/{BRANCHE}")
    return 0


def enregistrer(racine: Path | None = None, origine: str = "origin", pousser: bool = True) -> str:
    """Un commit sans parent avec les CHEMINS présents, poussé de force sur la branche.
    On ne change jamais de branche : un index temporaire sert à construire l'arbre."""
    racine = racine or RACINE
    with tempfile.TemporaryDirectory() as d:
        env = {"GIT_INDEX_FILE": str(Path(d) / "index")}
        presents = [c for c in CHEMINS if (racine / c).exists()]
        if presents:
            _git("add", "-f", "--", *presents, env=env, racine=racine)
        arbre = _git("write-tree", env=env, racine=racine)
    message = f"Données du {dt.date.today().isoformat()}"
    ident = {"GIT_AUTHOR_NAME": "github-actions[bot]", "GIT_COMMITTER_NAME": "github-actions[bot]",
             "GIT_AUTHOR_EMAIL": "41898099+github-actions[bot]@users.noreply.github.com",
             "GIT_COMMITTER_EMAIL": "41898099+github-actions[bot]@users.noreply.github.com"}
    for k in list(ident):  # on garde l'identité de l'environnement si elle existe déjà
        ident[k] = os.environ.get(k, ident[k])
    commit = _git("commit-tree", arbre, "-m", message, env=ident, racine=racine)
    if pousser:
        _git("push", "--force", origine, f"{commit}:refs/heads/{BRANCHE}", racine=racine)
    print(f"données enregistrées : {commit[:10]} ({len(presents)} chemins)")
    return commit


def main(argv: list[str]) -> int:
    action = argv[0] if argv else ""
    if action == "recuperer":
        try:
            return recuperer()
        except BrancheAbsente as e:
            print(f"::error::{e}", file=sys.stderr)
            return 1
    if action == "enregistrer":
        enregistrer()
        return 0
    if action == "chemins":
        print("\n".join(CHEMINS))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
