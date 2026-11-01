"""Séances de cinéma de tunis.events (Colisée, Palace, CinéMadart, Agora, Pathé…).

tunis.events regroupe les séances de plusieurs salles de Tunis. Le site est fait
avec Next.js : les données sont dans la page, pas dans des balises simples.
Première version : lit le schema.org s'il existe, sinon signale la structure à
étudier (lancer avec --debug pour garder la page).
"""
from __future__ import annotations

from ..commun import json_ld_evenements, page
from .jsonld import depuis_json_ld


def recuperer(source: dict):
    soup = page(source["url"])
    evs = depuis_json_ld(json_ld_evenements(soup), source["url"])
    if not evs:
        scripts = soup.find_all("script")
        raise RuntimeError(f"structure à étudier : {len(scripts)} scripts, "
                           f"__NEXT_DATA__={'oui' if soup.find(id='__NEXT_DATA__') else 'non'}, "
                           f"liens séance={len(soup.select('a[href*=session]'))}")
    return evs
