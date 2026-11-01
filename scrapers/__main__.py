"""Lance les scrapers des sources actives et met à jour le site.

Usage :
  python3 -m scrapers                 toutes les sources actives
  python3 -m scrapers teskerti        une ou plusieurs sources, par id
  python3 -m scrapers --debug         garde les pages téléchargées dans debug/

Si un scraper échoue, les événements déjà récupérés pour cette source sont gardés :
une panne ne vide jamais le site. Le résultat de chaque source est noté dans
_data/etat_sources.json.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib
import sys
import traceback

import yaml

from . import commun
from .commun import RACINE, Film
from .ecriture import ecrire_etat, ecrire_evenements, ecrire_films, lire_etat


def charger_sources() -> list[dict]:
    return yaml.safe_load((RACINE / "_data" / "sources.yml").read_text()) or []


def lancer(source: dict):
    module = importlib.import_module(f".sources.{source['scraper']}", __package__)
    return module.recuperer(source)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("ids", nargs="*", help="ids des sources à lancer (par défaut : toutes les actives)")
    p.add_argument("--debug", action="store_true", help="garder les pages téléchargées dans debug/")
    args = p.parse_args(argv)
    if args.debug:
        commun.DEBUG_DIR = RACINE / "debug"

    sources = [s for s in charger_sources() if (s["id"] in args.ids if args.ids else s.get("actif", True))]
    if args.ids and len(sources) < len(set(args.ids)):
        print(f"Sources inconnues : {set(args.ids) - {s['id'] for s in sources}}", file=sys.stderr)
    etat = lire_etat()
    maintenant = dt.datetime.now().isoformat(timespec="seconds")
    echecs = 0
    for s in sources:
        e = etat.setdefault(s["id"], {})
        e["dernier_passage"] = maintenant
        try:
            resultat = lancer(s)
            # Une liste vide n'est pas une panne : la source peut n'avoir rien à venir.
            # Les scrapers lèvent une erreur quand la page elle-même est méconnaissable.
            est_cinema = s.get("type") == "cinema" or (resultat and isinstance(resultat[0], Film))
            n = (ecrire_films if est_cinema else ecrire_evenements)(s, resultat)
            e.update(ok=True, nb=n, erreur=None, dernier_succes=maintenant)
            print(f"✓ {s['id']} : {n}")
        except Exception as exc:  # noqa: BLE001 — une source en panne ne doit pas arrêter les autres
            echecs += 1
            e.update(ok=False, erreur=f"{type(exc).__name__}: {exc}"[:300])
            print(f"✗ {s['id']} : {e['erreur']}", file=sys.stderr)
            if args.debug:
                traceback.print_exc()
    ecrire_etat(etat)
    print(f"{len(sources) - echecs}/{len(sources)} sources à jour.")
    return 1 if sources and echecs == len(sources) else 0


if __name__ == "__main__":
    sys.exit(main())
