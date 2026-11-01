#!/usr/bin/env python3
"""Récupère les films à l'affiche des cinémas Pathé de Tunis.

Écrit le résultat dans _data/cinema.json, que la page /cinema/ affiche.
Sans dépendance : uniquement la bibliothèque standard de Python.

Usage : python3 scripts/cinemas.py [--fixture fichier.json]

Le site pathe.tn est le même que pathe.fr. On essaie d'abord son API JSON
(la plus fiable), puis, si elle ne répond pas, on lit la page HTML du cinéma.
Si rien n'est trouvé, l'ancien fichier est conservé pour ne pas vider la page.
"""
import datetime as dt
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

BASE = "https://www.pathe.tn"
CINEMAS = [
    {"id": "cinema-pathe-tunis-city", "name": "Pathé Tunis City"},
    {"id": "cinema-pathe-azur-city", "name": "Pathé Azur City"},
]
OUT = Path(__file__).resolve().parent.parent / "_data" / "cinema.json"
DAYS_AHEAD = 7
UA = "Mozilla/5.0 (compatible; agenda-culturel-tunis/1.0; +https://benjello.github.io/agenda-culturel-tunis/)"


def get(url, as_json=True):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, text/html"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode("utf-8", "replace")
    return json.loads(body) if as_json else body


def log(msg):
    print(msg, file=sys.stderr)


def film_catalog():
    """slug -> infos du film (titre, durée, genres, affiche), via /api/shows."""
    try:
        data = get(f"{BASE}/api/shows?language=fr")
    except Exception as e:  # noqa: BLE001
        log(f"  catalogue indisponible : {e}")
        return {}
    shows = data.get("shows", data) if isinstance(data, dict) else data
    catalog = {}
    for s in shows if isinstance(shows, list) else []:
        slug = s.get("slug")
        if slug:
            catalog[slug] = s
    return catalog


def poster_url(info):
    p = info.get("posterPath")
    if isinstance(p, dict):
        p = p.get("md") or p.get("lg") or next(iter(p.values()), None)
    return p if isinstance(p, str) and p.startswith("http") else None


def from_api(cinema, catalog, today, end, data=None):
    if data is None:
        data = get(f"{BASE}/api/cinema/{cinema['id']}/shows?language=fr")
    shows = data.get("shows", data) if isinstance(data, dict) else {}
    films = []
    for slug, show in shows.items():
        days = sorted(d for d in (show.get("days") or {}) if today <= d[:10] <= end)
        if not days:
            continue
        info = catalog.get(slug, {})
        films.append({
            "title": info.get("title") or slug.replace("-", " ").capitalize(),
            "url": f"{BASE}/fr/films/{slug}",
            "duration": info.get("duration"),
            "genres": info.get("genres") or [],
            "poster": poster_url(info),
            "days": [d[:10] for d in days],
        })
    return films


def from_html(cinema):
    page = get(f"{BASE}/fr/cinemas/{cinema['id']}", as_json=False)
    films, seen = [], set()
    for slug, inner in re.findall(r'href="/fr/films/([a-z0-9-]+)"[^>]*>(.*?)</a>', page, re.S):
        title = html.unescape(re.sub(r"<[^>]+>", " ", inner)).strip()
        title = re.sub(r"\s+", " ", title)
        if slug in seen or not title:
            continue
        seen.add(slug)
        films.append({"title": title, "url": f"{BASE}/fr/films/{slug}", "duration": None,
                      "genres": [], "poster": None, "days": []})
    return films


def scrape(fixture=None):
    today_d = dt.date.today()
    today, end = today_d.isoformat(), (today_d + dt.timedelta(days=DAYS_AHEAD)).isoformat()
    fx = json.loads(Path(fixture).read_text()) if fixture else None
    catalog = (fx or {}).get("catalog") or ({} if fx else film_catalog())
    result = []
    for c in CINEMAS:
        log(f"{c['name']} :")
        films = []
        try:
            # En mode test, les données viennent du fichier au lieu du réseau.
            data = fx["cinemas"].get(c["id"], {}) if fx else None
            films = from_api(c, catalog, today, end, data)
            log(f"  API : {len(films)} films")
        except Exception as e:  # noqa: BLE001
            log(f"  API indisponible : {e}")
        if not films and not fx:
            try:
                films = from_html(c)
                log(f"  page HTML : {len(films)} films")
            except Exception as e:  # noqa: BLE001
                log(f"  page HTML indisponible : {e}")
        films.sort(key=lambda f: f["title"].lower())
        result.append({"name": c["name"], "url": f"{BASE}/fr/cinemas/{c['id']}", "films": films})
    return result


def main():
    fixture = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--fixture" else None
    cinemas = scrape(fixture)
    if not any(c["films"] for c in cinemas):
        log("Aucun film trouvé : on garde l'ancien fichier.")
        sys.exit(1)
    OUT.write_text(json.dumps({"updated": dt.date.today().isoformat(), "cinemas": cinemas},
                              ensure_ascii=False, indent=2) + "\n")
    log(f"Écrit : {OUT}")


if __name__ == "__main__":
    main()
