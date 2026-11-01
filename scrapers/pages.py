"""Fiches du site faites à partir des événements : lieux, organisateurs, artistes.

GitHub Pages ne fait pas tourner d'extension Jekyll : une fiche = un fichier.
Ce script écrit, après chaque passage des scrapers :
- _lieux/<slug>.md      une fiche par lieu précis qui a quelque chose à venir
- _collectifs/<id>.md   une fiche par source (lieu, collectif, festival qui publie sa programmation)
- _artistes/<slug>.md   une fiche par artiste : _data/artistes.yml, plus les noms lus dans
                        les titres (« Rencontre avec Sonia Hanihina »)
- _data/lieux.json      nom du lieu tel qu'écrit dans un événement → fiche, et coordonnées pour la carte
- _data/geo.json        coordonnées trouvées par OpenStreetMap (Nominatim), gardées d'un passage à l'autre

  python3 -m scrapers.pages            fiches + coordonnées des nouveaux lieux
  python3 -m scrapers.pages --sans-geo fiches seulement
"""
from __future__ import annotations

import argparse
import hashlib
import collections
import json
import re
import time
import unicodedata

import requests
import yaml

from .commun import RACINE, slug

LIEUX, COLLECTIFS, ARTISTES = RACINE / "_lieux", RACINE / "_collectifs", RACINE / "_artistes"
FICHIER_LIEUX, FICHIER_GEO = RACINE / "_data" / "lieux.json", RACINE / "_data" / "geo.json"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
GEO_PAR_PASSAGE = 25   # Nominatim demande 1 requête par seconde au plus : on y va doucement

# Même règle que _includes/lien-carte.html : pas de fiche pour « Tunis » ou « X et Y ».
_VAGUE = re.compile(r"^(?:tunis|tunisie|en ligne|online|tba|tbd|à venir|secret location)$|voir l'article|voir l'annonce|\bet\b| / |plusieurs", re.I)
# « Rencontre avec Sonia Hanihina », « Yoga with Judit » : 2 à 4 mots en capitales après avec/with.
_AVEC = re.compile(r"\b(?:[Aa]vec|[Ww]ith)\s+((?:[A-ZÀ-Ý][\w'’-]+)(?:\s+(?:[A-ZÀ-Ý][\w'’-]+|ben|bel|el|de|du)){1,3})")
_PAS_NOM = re.compile(r"^(?:Le|La|Les|Un|Une|Des|Vous|Nous|Papa|Maman)\b")


def _cle(texte: str) -> str:
    t = unicodedata.normalize("NFKD", (texte or "").replace("’", "'")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _slug(nom: str) -> str:
    """Slug lisible ; pour un nom en arabe (rien de latin), un code stable."""
    s = slug(nom)[:60]
    return s if s != "evenement" else "lieu-" + hashlib.sha1(nom.encode()).hexdigest()[:8]


def evenements() -> list[dict]:
    res = []
    for f in sorted((RACINE / "_events").rglob("*.md")):
        m = re.match(r"^---\n(.*?)\n---", f.read_text(), re.S)
        if m:
            try:
                e = yaml.safe_load(m.group(1)) or {}
            except yaml.YAMLError:
                continue
            res.append(e)
    return res


def _ecrire(fichier, champs: dict) -> None:
    lignes = ["---"] + [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in champs.items() if v not in (None, "", [])]
    texte = "\n".join(lignes + ["---", ""])
    if not fichier.exists() or fichier.read_text() != texte:
        fichier.write_text(texte)


def lieux(evts: list[dict]) -> dict[str, dict]:
    """Un lieu par nom normalisé : « Théâtre de l'Opéra » et « Theatre de l’Opera » ne font qu'un."""
    groupes: dict[str, dict] = {}
    alias = {_cle(k): v for k, v in (yaml.safe_load((RACINE / "_data" / "lieux_alias.yml").read_text()) or {}).items()}
    for e in evts:
        nom = str(e.get("venue") or "").strip()
        if not nom or _VAGUE.search(nom) or len(nom) > 90:
            continue
        cible = alias.get(_cle(nom), nom)
        g = groupes.setdefault(_cle(cible), {"noms": collections.Counter(), "adresse": "", "ville": "", "n": 0, "nom": ""})
        if cible in alias.values():  # nom choisi dans lieux_alias.yml
            g["nom"] = cible
        g["noms"][nom] += 1
        g["adresse"] = g["adresse"] or str(e.get("address") or "")
        g["ville"] = g["ville"] or str(e.get("ville") or "tunis")
        g["n"] += 1
    return groupes


def _geocoder(requete: str) -> list[float] | None:
    r = requests.get(NOMINATIM, params={"q": requete, "format": "json", "limit": 1, "countrycodes": "tn"},
                     headers={"User-Agent": "agenda-culturel-tunis (https://github.com/benjello/agenda-culturel-tunis)"},
                     timeout=20)
    r.raise_for_status()
    res = r.json()
    return [round(float(res[0]["lat"]), 5), round(float(res[0]["lon"]), 5)] if res else None


def coordonnees(groupes: dict[str, dict], geo: dict, avec_reseau: bool) -> None:
    faits = 0
    for cle, g in sorted(groupes.items(), key=lambda kv: -kv[1]["n"]):
        nom = g["nom"] or g["noms"].most_common(1)[0][0]
        if cle in geo or not avec_reseau or faits >= GEO_PAR_PASSAGE:
            continue
        essais = [", ".join(x for x in (nom, g["adresse"]) if x), nom.split(",")[0]]
        geo[cle] = None
        for q in dict.fromkeys(essais):
            try:
                geo[cle] = _geocoder(q)
            except (requests.RequestException, ValueError, KeyError) as exc:
                print(f"  carte : {q} illisible ({exc.__class__.__name__})")
                del geo[cle]
                return  # réseau ou service indisponible : on réessaiera au prochain passage
            faits += 1
            time.sleep(1.1)
            if geo[cle]:
                break
    if faits:
        print(f"  carte : {faits} recherche(s) de lieu sur OpenStreetMap")


def ecrire_lieux(groupes: dict[str, dict], geo: dict) -> dict:
    LIEUX.mkdir(exist_ok=True)
    manuels = {_cle(k): v for k, v in (yaml.safe_load((RACINE / "_data" / "lieux_coords.yml").read_text()) or {}).items()}
    index, carte, fichiers = {}, [], set()
    for cle, g in groupes.items():
        nom = g["nom"] or g["noms"].most_common(1)[0][0]
        s = _slug(nom)
        point = manuels.get(cle) or geo.get(cle)
        fichier = LIEUX / f"{s}.md"
        fichiers.add(fichier.name)
        noms = sorted(g["noms"])
        _ecrire(fichier, {"title": nom, "noms": noms, "adresse": g["adresse"], "ville": g["ville"],
                          "lat": point[0] if point else None, "lon": point[1] if point else None})
        for n in noms:
            index[n] = s
        if point:
            carte.append({"slug": s, "nom": nom, "ville": g["ville"], "lat": point[0], "lon": point[1], "n": g["n"]})
    for f in LIEUX.glob("*.md"):
        if f.name not in fichiers:
            f.unlink()
    carte.sort(key=lambda x: -x["n"])
    return {"index": index, "carte": carte}


def ecrire_collectifs(evts: list[dict]) -> int:
    sources = yaml.safe_load((RACINE / "_data" / "sources.yml").read_text()) or []
    actives = {e.get("source") for e in evts}
    COLLECTIFS.mkdir(exist_ok=True)
    gardes = {s["id"] for s in sources if s.get("actif", True) or s["id"] in actives}
    for f in COLLECTIFS.glob("*.md"):
        if f.stem not in gardes:
            f.unlink()
    n = 0
    for s in sources:
        if s["id"] not in gardes:
            continue
        reseau = re.search(r"(instagram|facebook)\.com/([^/?#]+)", s.get("url", ""))
        _ecrire(COLLECTIFS / f"{s['id']}.md", {
            "title": s["nom"], "source": s["id"], "type": s.get("type"), "url_source": s.get("url"),
            "reseau": reseau.group(1) if reseau else None, "categorie": s.get("categorie")})
        n += 1
    return n


def artistes_des_titres(evts: list[dict]) -> dict[str, str]:
    """{slug: nom} des noms lus après « avec » dans les titres."""
    res = {}
    for e in evts:
        for m in _AVEC.finditer(str(e.get("title") or "")):
            nom = m.group(1).strip(" -’'")
            if not _PAS_NOM.match(nom):
                res.setdefault(_slug(nom), nom)
    return res


def ecrire_artistes(evts: list[dict]) -> int:
    connus = yaml.safe_load((RACINE / "_data" / "artistes.yml").read_text()) or []
    ARTISTES.mkdir(exist_ok=True)
    fiches = {}
    for a in connus:
        fiches[slug(a["nom"])] = {"title": a["nom"], "mots": [m.lower() for m in a.get("mots") or [a["nom"]]],
                                  "instagram": a.get("instagram"), "facebook": a.get("facebook"),
                                  "site": a.get("site"), "genre": a.get("genre")}
    for s, nom in artistes_des_titres(evts).items():
        fiches.setdefault(s, {"title": nom, "mots": [nom.lower()]})
    for f in ARTISTES.glob("*.md"):
        if f.stem not in fiches:
            f.unlink()
    for s, champs in fiches.items():
        _ecrire(ARTISTES / f"{s}.md", champs)
    return len(fiches)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sans-geo", action="store_true", help="ne pas chercher les coordonnées des lieux")
    args = p.parse_args(argv)
    evts = evenements()
    groupes = lieux(evts)
    try:
        geo = json.loads(FICHIER_GEO.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        geo = {}
    coordonnees(groupes, geo, not args.sans_geo)
    FICHIER_GEO.write_text(json.dumps(geo, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    donnees = ecrire_lieux(groupes, geo)
    FICHIER_LIEUX.write_text(json.dumps(donnees, ensure_ascii=False, indent=1) + "\n")
    nc, na = ecrire_collectifs(evts), ecrire_artistes(evts)
    print(f"{len(groupes)} lieux ({len(donnees['carte'])} sur la carte), {nc} organisateurs, {na} artistes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
