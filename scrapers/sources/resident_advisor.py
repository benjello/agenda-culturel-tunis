"""Resident Advisor (ra.co) : soirées électro et clubs, Tunisie entière.

La page ra.co/events/tn/all est remplie en JavaScript à partir de l'API GraphQL du site
(ra.co/graphql). On interroge cette API comme le fait la page : d'abord l'identifiant
de la zone (« tn / all »), puis les soirées à venir de cette zone.

Options :
  pays    code pays de RA (défaut « tn »)
  zone    nom de zone dans l'adresse (défaut « all »)
  area    identifiant numérique de la zone, si on le connaît (évite la première requête)
  jours   combien de jours à l'avance (défaut 90)
"""
from __future__ import annotations

import datetime as dt

import requests

from ..commun import Evenement, propre

API = "https://ra.co/graphql"
ENTETES = {
    "Content-Type": "application/json",
    "Referer": "https://ra.co/events/tn/all",
    "Origin": "https://ra.co",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
}

ZONE = """query GET_AREA($areaUrlName: String, $countryUrlCode: String) {
  area(areaUrlName: $areaUrlName, countryUrlCode: $countryUrlCode) { id name }
}"""

SOIREES = """query GET_EVENT_LISTINGS($filters: FilterInputDtoInput, $pageSize: Int, $page: Int) {
  eventListings(filters: $filters, pageSize: $pageSize, page: $page) {
    data { event { id title date startTime endTime contentUrl cost
                   venue { name address area { name } } images { filename } } }
    totalResults
  }
}"""


def _graphql(requete: str, variables: dict) -> dict:
    r = requests.post(API, json={"query": requete, "variables": variables}, headers=ENTETES, timeout=30)
    r.raise_for_status()
    rep = r.json()
    if rep.get("errors"):
        raise RuntimeError(f"RA : {rep['errors'][0].get('message', rep['errors'])}"[:200])
    return rep.get("data") or {}


def _heure(v: str | None) -> dt.datetime | None:
    if not v:
        return None
    try:
        return dt.datetime.fromisoformat(v.replace("Z", "")[:19])
    except ValueError:
        return None


def depuis_listes(donnees: dict) -> list[Evenement]:
    res = []
    for item in (donnees.get("eventListings") or {}).get("data") or []:
        e = item.get("event") or {}
        debut = _heure(e.get("startTime")) or _heure(e.get("date"))
        if not e.get("title") or not debut:
            continue
        fin = _heure(e.get("endTime"))
        lieu = e.get("venue") or {}
        zone = ((lieu.get("area") or {}).get("name") or "").strip()
        nom_lieu = propre(lieu.get("name") or "")
        if zone and zone.lower() not in nom_lieu.lower() and zone.lower() not in ("all", "tunisia", "tunisie"):
            nom_lieu = f"{nom_lieu}, {zone}" if nom_lieu else zone
        images = e.get("images") or []
        res.append(Evenement(
            titre=propre(e["title"]), debut=debut,
            fin=fin if fin and fin.date() != debut.date() and (fin - debut).days >= 1 else None,
            lien=f"https://ra.co{e.get('contentUrl') or '/events/' + str(e.get('id'))}",
            lieu=nom_lieu, adresse=propre(lieu.get("address") or ""), categorie="musique",
            prix=propre(e.get("cost") or ""), image=(images[0].get("filename") or "") if images else ""))
    return res


def recuperer(source: dict) -> list[Evenement]:
    o = source.get("options") or {}
    area = o.get("area")
    if not area:
        zone = _graphql(ZONE, {"areaUrlName": o.get("zone", "all"), "countryUrlCode": o.get("pays", "tn")}).get("area")
        if not zone:
            raise RuntimeError("zone RA introuvable")
        area = int(zone["id"])
        print(f"  {source['id']} : zone RA {zone.get('name')} = {area} (à noter dans les options)")
    auj = dt.date.today()
    filtres = {"areas": {"eq": int(area)}, "listingDate": {
        "gte": auj.isoformat(), "lte": (auj + dt.timedelta(days=o.get("jours", 90))).isoformat()}}
    return depuis_listes(_graphql(SOIREES, {"filters": filtres, "pageSize": 50, "page": 1}))
