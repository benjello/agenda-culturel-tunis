"""Concerts, soirées et clubs de tunis.events (billetterie), filtrés sur le Grand Tunis.

tunis.events décrit ses événements en schema.org, comme pour le cinéma (voir
tunis_events_cinema). On lit plusieurs rubriques et on écarte les villes hors Grand Tunis.

Options :
  pages    liste de { url, categorie } (rubriques à lire)
  exclure  mots qui écartent un lieu (défaut : Sousse, Sfax, Nabeul, Hammamet…)
"""
from __future__ import annotations

from ..commun import Evenement, json_ld_evenements, page
from .jsonld import depuis_json_ld
from .tunis_events_cinema import EXCLURE


def recuperer(source: dict) -> list[Evenement]:
    opts = source.get("options") or {}
    exclure = tuple(m.lower() for m in opts.get("exclure", EXCLURE))
    pages = opts.get("pages") or [{"url": source["url"], "categorie": source.get("categorie", "autre")}]
    vus, res, lus = set(), [], 0
    for p in pages:
        objets = json_ld_evenements(page(p["url"]))
        lus += len(objets)
        for e in depuis_json_ld(objets, p["url"]):
            if any(m in f"{e.lieu} {e.adresse}".lower() for m in exclure) or (e.lien, e.debut) in vus:
                continue
            vus.add((e.lien, e.debut))
            e.categorie = p.get("categorie") or e.categorie
            res.append(e)
    if not lus:
        raise RuntimeError("aucun événement en schema.org sur les pages (site modifié ?)")
    return res
