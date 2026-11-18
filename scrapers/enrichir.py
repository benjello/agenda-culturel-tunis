"""Fiches plus riches, depuis des sources ouvertes et gratuites :

- photos des artistes et des lieux : Wikidata (propriété P18, image sur Wikimedia Commons) ;
- accès fauteuil, horaires, site et type (cinéma, théâtre…) des lieux et des musées : OpenStreetMap (Overpass),
  une seule requête pour toute la Tunisie.

Les réponses sont gardées dans _data/enrichi.json (clé : identifiant de la fiche) pour ne pas
réinterroger chaque jour : un nom déjà cherché n'est recherché à nouveau qu'après 30 jours.

  python3 -m scrapers.enrichir
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import unicodedata

import requests
import yaml

from .commun import RACINE
from .doublons import _lire
from .wikidata import TUNISIE, UA, _api, _valeurs
from .wikidata import _entites as _entites_base


def _entites(ids: list[str]) -> dict:
    return _entites_base(ids, props="claims|labels|aliases", langues="fr|en|ar")


FICHIER = RACINE / "_data" / "enrichi.json"
MANUELLES = RACINE / "_data" / "images_manuelles.yml"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
            "https://overpass.private.coffee/api/interpreter"]
MAX_RECHERCHES = 60          # recherches Wikidata par passage
REESSAI_JOURS = 30
HUMAIN = "Q5"
P_IMAGE, P_NATURE, P_PAYS, P_NATIONALITE = "P18", "P31", "P17", "P27"
# Un « lieu » qui est en fait un pays, une ville ou une commune : sa photo (un paysage) ne représente pas la salle.
NATURES_NON_LIEU = {"Q6256", "Q3624078", "Q515", "Q1549591", "Q486972", "Q532", "Q15284", "Q3957", "Q5119", "Q35657",
                    "Q1620908", "Q15617994"}
# Licences libres acceptées (nom court donné par Wikimedia Commons)
LICENCE_LIBRE = re.compile(r"^(CC[ -]BY|CC0|CC[ -]ZERO|Public domain|PD|GFDL|FAL|Attribution)", re.I)

# Lieux culturels dans OpenStreetMap
REQUETE_OSM = """[out:json][timeout:120];
area["ISO3166-1"="TN"][admin_level=2]->.tn;
(
  nwr["tourism"~"^(museum|gallery)$"](area.tn);
  nwr["amenity"~"^(theatre|cinema|arts_centre|library|community_centre)$"](area.tn);
);
out tags center;"""


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    t = re.sub(r"\b(le|la|les|l|de|du|des|d|et|the|of)\b", " ", re.sub(r"[^a-z0-9 ]", " ", t))
    return " ".join(t.split())


def commons(fichier: str, largeur: int = 400) -> dict:
    nom = fichier.replace(" ", "_")
    return {"image": f"https://commons.wikimedia.org/wiki/Special:FilePath/{nom}?width={largeur}",
            "credit": f"https://commons.wikimedia.org/wiki/File:{nom}"}


def acceptable(e: dict, genre: str) -> bool:
    """Un artiste : une personne tunisienne ; un lieu : en Tunisie, et pas un pays ni une ville. Évite les homonymes."""
    if genre == "artiste":
        return HUMAIN in _valeurs(e, P_NATURE) and TUNISIE in _valeurs(e, P_NATIONALITE)
    return TUNISIE in _valeurs(e, P_PAYS) and not (set(_valeurs(e, P_NATURE)) & NATURES_NON_LIEU)


def noms_de(e: dict) -> set[str]:
    """Libellés et alias Wikidata (fr, en, ar), normalisés."""
    res = set()
    for l in ("fr", "en", "ar"):
        v = (e.get("labels") or {}).get(l, {}).get("value")
        if v:
            res.add(_norm(v))
        res |= {_norm(a.get("value", "")) for a in (e.get("aliases") or {}).get(l, [])}
    res.discard("")
    return res


def meme_nom(nom: str, e: dict) -> bool:
    """Le nom de la fiche désigne bien cette entité Wikidata : mêmes mots, ou (au moins deux mots) tous les mots du
    plus court dans le plus long. « Moez » seul ne suffit jamais : trop de homonymes (un joueur de tennis…)."""
    n = set(_norm(nom).split())
    for autre in noms_de(e):
        a = set(autre.split())
        if not n or not a:
            continue
        if n == a or (min(len(n), len(a)) >= 2 and (n <= a or a <= n)):
            return True
    return False


def manuelles() -> dict:
    """_data/images_manuelles.yml : « refuses » (clés dont la photo est écartée) et « imposees » (clé → fichier Commons)."""
    try:
        d = yaml.safe_load(MANUELLES.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        d = {}
    return {"refuses": set(d.get("refuses") or []), "imposees": d.get("imposees") or {}}


def infos_commons(fichier: str) -> dict | None:
    """Auteur et licence d'un fichier Wikimedia Commons ; None si l'API ne répond pas (on réessaiera)."""
    nom = "File:" + fichier.replace("_", " ")
    r = requests.get(COMMONS_API, params={"action": "query", "format": "json", "titles": nom, "prop": "imageinfo",
                                           "iiprop": "extmetadata", "iiextmetadatafilter": "Artist|LicenseShortName|LicenseUrl"},
                     headers=UA, timeout=30)
    r.raise_for_status()
    pages = (r.json().get("query") or {}).get("pages") or {}
    meta = {}
    for p in pages.values():
        meta = ((p.get("imageinfo") or [{}])[0]).get("extmetadata") or {}
    if not meta:
        return None
    nettoyer = lambda t: " ".join(html.unescape(re.sub(r"<[^>]+>", " ", t or "")).split())
    return {"auteur": nettoyer((meta.get("Artist") or {}).get("value"))[:80],
            "licence": nettoyer((meta.get("LicenseShortName") or {}).get("value")),
            "licence_url": ((meta.get("LicenseUrl") or {}).get("value") or "").strip()}


def licence_libre(infos: dict | None) -> bool:
    return bool(infos and LICENCE_LIBRE.match(infos.get("licence", "")))


def fichier_commons(entree: dict) -> str:
    """Nom du fichier Commons, lu dans le lien de crédit d'une entrée."""
    return requests.utils.unquote(entree["credit"].rsplit("File:", 1)[-1])


def image_wikidata(nom: str, genre: str) -> dict | None:
    """Première entité qui porte bien le nom de la fiche, au bon pays, avec une image sous licence libre.
    Dans le doute, pas d'image : mieux vaut aucune photo qu'une mauvaise."""
    trouves = _api(action="wbsearchentities", search=nom, language="fr", uselang="fr", limit=5).get("search", [])
    ids = [t["id"] for t in trouves]
    if not ids:
        return None
    entites = _entites(ids)
    for i in ids:
        e = entites.get(i) or {}
        images = _valeurs(e, P_IMAGE)
        if images and acceptable(e, genre) and meme_nom(nom, e):
            r = {"qid": i, **commons(images[0])}
            infos = infos_commons(images[0])
            if not licence_libre(infos):
                continue
            return {**r, **infos}
    return None


def imposee(fichier: str) -> dict | None:
    """Photo choisie à la main (images_manuelles.yml) : on ne garde que si sa licence est libre."""
    infos = infos_commons(fichier)
    return {**commons(fichier), **infos, "manuelle": True} if licence_libre(infos) else None


def reverifier(cache: dict, aujourd_hui: dt.date, noms: dict[str, str]) -> None:
    """Photos déjà gardées : vérifie qu'elles portent le bon nom (Wikidata) et une licence libre, ajoute auteur et
    licence. Une photo qui ne passe pas est retirée. Une panne réseau garde la photo et réessaie au prochain passage."""
    a_voir = [k for k, v in cache["images"].items() if not v.get("manuelle") and v.get("verifie") != aujourd_hui.isoformat()
              and not v.get("licence")]
    if not a_voir:
        return
    entites = _entites(sorted({cache["images"][k]["qid"] for k in a_voir}))
    for k in a_voir:
        v = cache["images"][k]
        e = entites.get(v["qid"]) or {}
        genre = k.split(":", 1)[0]
        if not (acceptable(e, genre) and meme_nom(noms.get(k, ""), e)):
            print(f"  photo retirée (mauvais nom ou mauvais type) : {k}")
            del cache["images"][k]
            continue
        infos = infos_commons(fichier_commons(v))
        if infos is None:
            continue
        if not licence_libre(infos):
            print(f"  photo retirée (licence non libre) : {k}")
            del cache["images"][k]
            continue
        v.update(infos)
        v["verifie"] = aujourd_hui.isoformat()


def fiches(dossier: str) -> list[tuple[str, str]]:
    res = []
    for f in sorted((RACINE / dossier).glob("*.md")):
        c, _ = _lire(f)
        if c and c.get("title"):
            res.append((f.stem, str(c["title"]).split(",")[0].strip()))
    return res


# Étiquette OpenStreetMap → type de lieu du site (_data/types_lieux.yml)
TYPES_OSM = {"cinema": "cinema", "theatre": "theatre", "gallery": "galerie", "museum": "musee",
             "library": "bibliotheque", "arts_centre": "centre_art", "community_centre": "centre"}


def osm_index(elements: list[dict]) -> dict:
    """{nom normalisé : étiquettes utiles}"""
    res = {}
    for el in elements:
        t = el.get("tags") or {}
        infos = {k: t[k] for k in ("wheelchair", "opening_hours", "website") if t.get(k)}
        genre = TYPES_OSM.get(t.get("amenity") or "") or TYPES_OSM.get(t.get("tourism") or "")
        if genre:
            infos["type"] = genre
        if not infos:
            continue
        for cle in ("name", "name:fr", "name:en", "name:ar"):
            if t.get(cle):
                res.setdefault(_norm(t[cle]), infos)
    return res


def chercher_osm(index: dict, nom: str) -> dict | None:
    n = _norm(nom)
    if not n:
        return None
    if n in index:
        return index[n]
    # « Théâtre municipal de Tunis » ↔ « Théâtre municipal » : un nom contient l'autre (3 mots au moins)
    for k, v in index.items():
        court, long_ = sorted((k, n), key=len)
        if len(court.split()) >= 3 and court in long_:
            return v
    return None


def _overpass(requete: str) -> list[dict]:
    """Essaie les serveurs Overpass l'un après l'autre (souvent saturés)."""
    erreur = None
    for url in OVERPASS:
        try:
            r = requests.post(url, data={"data": requete}, headers=UA, timeout=180)
            r.raise_for_status()
            return r.json().get("elements", [])
        except (requests.RequestException, ValueError) as exc:
            erreur = exc
    raise erreur


def lire() -> dict:
    try:
        d = json.loads(FICHIER.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        d = {}
    return {"images": d.get("images") or {}, "osm": d.get("osm") or {}, "vu": d.get("vu") or {}}


def main() -> int:
    cache = lire()
    aujourd_hui = dt.date.today()
    limite = (aujourd_hui - dt.timedelta(days=REESSAI_JOURS)).isoformat()
    # 1. Photos (Wikidata), seulement si le nom correspond et la licence est libre ; sinon rien
    n = 0
    mains = manuelles()
    noms = {f"{g}:{c}": nom for g, d in (("artiste", "_artistes"), ("lieu", "_lieux")) for c, nom in fiches(d)}
    for k in mains["refuses"]:
        cache["images"].pop(k, None)
    try:
        for k, fichier in mains["imposees"].items():
            if k not in cache["images"] or not cache["images"][k].get("manuelle"):
                r = imposee(fichier)
                if r:
                    cache["images"][k] = r
                    print(f"  photo choisie à la main : {k}")
        reverifier(cache, aujourd_hui, noms)
    except (requests.RequestException, ValueError) as exc:
        print(f"  vérification des photos : {exc} (on garde celles d'avant, nouvel essai au prochain passage)")
    for genre, dossier in (("artiste", "_artistes"), ("lieu", "_lieux")):
        for cle, nom in fiches(dossier):
            k = f"{genre}:{cle}"
            if k in cache["images"] or k in mains["refuses"] or cache["vu"].get(k, "") > limite or n >= MAX_RECHERCHES:
                continue
            n += 1
            try:
                r = image_wikidata(nom, genre)
            except (requests.RequestException, ValueError) as exc:
                print(f"  wikidata : {nom} : {exc}")
                break
            cache["vu"][k] = aujourd_hui.isoformat()
            if r:
                cache["images"][k] = r
                print(f"  photo : {nom} → {r['qid']}")
    # 2. Accès, horaires (OpenStreetMap)
    try:
        index = osm_index(_overpass(REQUETE_OSM))
        musees = yaml.safe_load((RACINE / "_data" / "musees.yml").read_text()) or []
        osm = {}
        for cle, nom in fiches("_lieux"):
            t = chercher_osm(index, nom)
            if t:
                osm[f"lieu:{cle}"] = t
                print(f"  OSM : {nom} → {t}")
        for m in musees:
            t = chercher_osm(index, m["nom"]) or next((chercher_osm(index, x) for x in m.get("mots") or [] if chercher_osm(index, x)), None)
            if t:
                osm[f"musee:{m['nom']}"] = t
        cache["osm"] = osm
    except (requests.RequestException, ValueError) as exc:
        print(f"  OpenStreetMap : {exc} (on garde les données d'avant)")
    FICHIER.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    print(f"Fiches enrichies : {len(cache['images'])} photos, {len(cache['osm'])} lieux avec accès ou horaires "
          f"({n} recherche(s) Wikidata)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
