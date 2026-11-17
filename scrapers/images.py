"""Contrôle des images d'événements, après chaque passage des scrapers.

Une vignette dont l'image ne charge pas laissait un cadre vide sur la carte. Ce script
vérifie chaque ligne « image: » des événements :
- image du dépôt (assets/…) : le fichier doit exister et être une vraie image ;
- image externe (https://…) : le site doit répondre 200 avec une vraie image, sans référent
  (comme le navigateur du lecteur, qui n'en envoie pas non plus : voir referrerpolicy).

Une image cassée est retirée de la fiche : la carte n'a plus de vignette, plutôt qu'un cadre vide.
Une panne passagère (délai dépassé, 5xx) ne retire rien tout de suite : il faut CASSEE_APRES
passages ratés de suite. Les images qui marchent ne sont relues que tous les JOURS_RELECTURE jours.
Le résultat est gardé dans _data/images.json (cache + bilan affiché sur « État des sources »).

  python3 -m scrapers.images
"""
from __future__ import annotations

import datetime as dt
import json
import re
from concurrent.futures import ThreadPoolExecutor

import requests

from .commun import ENTETES, RACINE

CACHE = RACINE / "_data" / "images.json"
CASSEE_APRES = 2      # passages ratés de suite avant de retirer l'image
JOURS_RELECTURE = 7   # une image qui marche est relue une fois par semaine
LIGNE_IMAGE = re.compile(r'^image:[ \t]*"?([^"\n]*)"?[ \t]*\n', re.M)
SIGNATURES = (b"\xff\xd8\xff", b"\x89PNG", b"GIF8", b"RIFF", b"<svg", b"<?xml")  # jpeg, png, gif, webp, svg


def est_une_image(debut: bytes) -> bool:
    return any(debut.startswith(s) for s in SIGNATURES) or debut[4:12] in (b"ftypavif", b"ftypheic")


def verifier_externe(url: str) -> tuple[str, str]:
    """('ok'|'cassee'|'incertaine', détail)."""
    entetes = {**ENTETES, "Accept": "image/avif,image/webp,image/*,*/*;q=0.8"}
    try:
        r = requests.get(url, headers=entetes, timeout=20, stream=True)
    except requests.RequestException as exc:
        return "incertaine", type(exc).__name__
    try:
        if r.status_code >= 500 or r.status_code == 429:
            return "incertaine", f"HTTP {r.status_code}"
        if r.status_code != 200:
            return "cassee", f"HTTP {r.status_code}"
        if not r.headers.get("Content-Type", "").lower().startswith("image/"):
            return "cassee", "pas une image : " + r.headers.get("Content-Type", "?")[:40]
        debut = next(r.iter_content(64), b"")
        return ("ok", "") if est_une_image(debut) else ("cassee", "contenu illisible")
    except requests.RequestException as exc:
        return "incertaine", type(exc).__name__
    finally:
        r.close()


def verifier_locale(chemin: str) -> tuple[str, str]:
    f = RACINE / chemin
    if not f.is_file():
        return "cassee", "fichier absent"
    return ("ok", "") if est_une_image(f.read_bytes()[:64]) else ("cassee", "fichier illisible")


def verifier(url: str) -> tuple[str, str]:
    return verifier_externe(url) if "://" in url else verifier_locale(url)


def a_relire(fiche: dict | None, maintenant: dt.datetime) -> bool:
    if not fiche or fiche.get("etat") != "ok":
        return True  # jamais vue, ou ratée : on réessaie à chaque passage
    return maintenant - dt.datetime.fromisoformat(fiche["verifiee"]) > dt.timedelta(days=JOURS_RELECTURE)


def mettre_a_jour(fiche: dict | None, etat: str, detail: str, maintenant: dt.datetime) -> dict:
    fiche = dict(fiche or {})
    fiche.update(etat=etat, detail=detail, verifiee=maintenant.isoformat(timespec="seconds"))
    fiche["echecs"] = 0 if etat == "ok" else fiche.get("echecs", 0) + 1
    return fiche


def doit_retirer(fiche: dict) -> bool:
    return fiche.get("etat") != "ok" and fiche.get("echecs", 0) >= CASSEE_APRES


def main() -> int:
    maintenant = dt.datetime.now()
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    fichiers = {}
    for f in (RACINE / "_events").rglob("*.md"):
        m = LIGNE_IMAGE.search(f.read_text(encoding="utf-8").split("\n---", 2)[0] + "\n")
        if m and m.group(1):
            fichiers[f] = m.group(1)
    urls = sorted(set(fichiers.values()))
    # les images qui ne sont plus dans aucun événement sortent du cache
    cache = {u: c for u, c in cache.items() if u in urls}
    a_verifier = [u for u in urls if a_relire(cache.get(u), maintenant)]
    with ThreadPoolExecutor(8) as pool:
        for u, (etat, detail) in zip(a_verifier, pool.map(verifier, a_verifier)):
            cache[u] = mettre_a_jour(cache.get(u), etat, detail, maintenant)
    retirees = 0
    for f, u in fichiers.items():
        if doit_retirer(cache[u]):
            texte = f.read_text(encoding="utf-8")
            f.write_text(LIGNE_IMAGE.sub("", texte, count=1), encoding="utf-8")
            retirees += 1
            print(f"✗ {f.name} : image retirée ({cache[u]['detail']}) {u}")
    cassees = [u for u, c in cache.items() if c["etat"] != "ok"]
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Images : {len(urls)} distinctes, {len(a_verifier)} vérifiées, {len(cassees)} en échec, {retirees} fiche(s) sans image.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
