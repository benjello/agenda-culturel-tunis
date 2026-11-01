"""Sonde temporaire : essai réel de la source ift-pdf avec l'agenda en ligne (à retirer avant la fusion)."""
import yaml
from scrapers.sources import aec, pdf_programme
from scrapers import granularite
src = next(s for s in yaml.safe_load(open("_data/sources.yml")) if s["id"] == "ift-pdf")
o = src["options"]["aec"]
objets = aec.lire_api(dict(o, api_key=""), o["page"])  # la clé doit être relue dans la page
print("clé relue dans la page : oui,", len(objets), "objets")
evts = pdf_programme.recuperer(src)
n_fiche = sum(1 for e in evts if "details-agenda" in e.lien)
print(f"\nTOTAL {len(evts)} événements, {n_fiche} avec leur fiche")
for e in sorted(evts, key=lambda e: e.debut):
    print(f"{e.debut:%d/%m %H:%M} | {e.categorie:11} | {'film' if e.film else '    '} | {'FICHE' if 'details-agenda' in e.lien else 'pdf  '} | {e.titre[:60]} | {e.lieu[:40]}")
