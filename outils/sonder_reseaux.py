"""Sonde ponctuelle des pages Facebook, comptes Instagram et sites bloqués.

Sert à remplir les bilans de sources : date de la dernière publication,
texte ou image, comptes Instagram trouvés par recherche. N'écrit rien dans
le site : le rapport sort dans le résumé de l'action GitHub et dans les logs.
Clé Apify : variable APIFY_TOKEN. Coût : quelques centimes par passage.
"""
from __future__ import annotations

import os
import re
import unicodedata
import sys
import urllib.robotparser
from urllib.parse import urlparse

import requests
import yaml

API = "https://api.apify.com/v2/acts/{}/run-sync-get-dataset-items"
UA = "Mozilla/5.0 (compatible; agenda-culturel-tunis/1.0; +https://github.com/benjello/agenda-culturel-tunis)"
lignes: list[str] = []


def dire(t: str = "") -> None:
    print(t, flush=True)
    lignes.append(t)


def apify(acteur: str, entree: dict) -> list[dict]:
    r = requests.post(API.format(acteur.replace("/", "~")), params={"token": os.environ["APIFY_TOKEN"]},
                      json=entree, timeout=600)
    r.raise_for_status()
    d = r.json()
    return d if isinstance(d, list) else []


def court(t, n=90) -> str:
    return re.sub(r"\s+", " ", str(t or "")).strip()[:n].replace("|", "/")


def _une_page(p: str) -> list[dict]:
    url = p if p.startswith("http") else f"https://www.facebook.com/{p}"
    return apify("apify/facebook-posts-scraper", {"startUrls": [{"url": url}], "resultsLimit": 2})


def facebook(pages: list[str]) -> None:
    # Une page par appel : Apify renvoie parfois l'adresse canonique de la page
    # (identifiant numérique, autre nom), qu'on ne saurait pas relier à la demande.
    dire("## Facebook (2 dernières publications par page)\n")
    dire("| Page | Dernière publication | Texte ou image | Extrait |")
    dire("|---|---|---|---|")
    for p in pages:
        try:
            its = _une_page(p)
        except Exception as e:  # noqa: BLE001
            dire(f"| {p} | erreur | | {court(e, 80)} |")
            continue
        bons = [i for i in its if not i.get("error")]
        if not bons:
            err = court(its[0].get("error") if its else "rien renvoyé (page introuvable, privée ou sans publication ?)", 80)
            dire(f"| {p} | — | — | {err} |")
            continue
        bons.sort(key=lambda i: str(i.get("time") or i.get("timestamp") or ""), reverse=True)
        i = bons[0]
        image = "image" if (i.get("media") or i.get("ocrText")) else "texte"
        if i.get("text") and image == "image":
            image = "texte + image"
        dire(f"| {p} | {str(i.get('time') or i.get('timestamp') or '?')[:10]} | {image} | {court(i.get('text'))} |")
    dire()


def instagram(comptes: list[str]) -> None:
    dire("## Instagram (profils)\n")
    dire("| Compte | Abonnés | Dernière publication | Site / bio |")
    dire("|---|---|---|---|")
    try:
        items = apify("apify/instagram-scraper", {
            "directUrls": [f"https://www.instagram.com/{c}/" for c in comptes],
            "resultsType": "details", "resultsLimit": 1})
    except Exception as e:  # noqa: BLE001
        dire(f"| (tous) | erreur : {court(e, 200)} | | |")
        return
    vus = {}
    for i in items:
        if i.get("username"):
            vus[i["username"].lower()] = i
    for c in comptes:
        i = vus.get(c.lower())
        if not i:
            dire(f"| {c} | — | introuvable | |")
            continue
        dates = sorted((str(p.get("timestamp") or "") for p in i.get("latestPosts") or []), reverse=True)
        dire(f"| {c} | {i.get('followersCount', '?')} | {dates[0][:10] if dates else '?'} | "
             f"{court(i.get('externalUrl') or '', 50)} {court(i.get('biography'), 60)} |")
    dire()


def chercher(noms: list[str]) -> None:
    dire("## Instagram : comptes trouvés par recherche (3 premiers résultats)\n")
    dire("| Recherche | Comptes trouvés (abonnés) |")
    dire("|---|---|")
    for n in noms:
        # la recherche Instagram refuse apostrophes, tirets et accents
        q = re.sub(r"[^a-z0-9 ]", " ", unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower())
        q = re.sub(r"\s+", " ", q).strip()
        try:
            items = apify("apify/instagram-search-scraper", {"search": q, "searchType": "user", "searchLimit": 3})
        except Exception as e:  # noqa: BLE001
            dire(f"| {n} | erreur : {court(e, 120)} |")
            continue
        trouves = []
        for i in items[:3]:
            u = i.get("username") or i.get("url")
            if u:
                trouves.append(f"`{u}` ({i.get('followersCount', '?')}) {court(i.get('fullName'), 40)}")
        dire(f"| {n} | {' ; '.join(trouves) or 'aucun'} |")
    dire()


def sites(urls: list[str]) -> None:
    dire("## Sites (lecture directe depuis GitHub)\n")
    dire("| URL | robots.txt autorise ? | Code HTTP | Taille | Dernière date vue | Formats |")
    dire("|---|---|---|---|---|---|")
    for u in urls:
        base = f"{urlparse(u).scheme}://{urlparse(u).netloc}"
        rp = urllib.robotparser.RobotFileParser(base + "/robots.txt")
        try:
            rp.read()
            autorise = "oui" if rp.can_fetch("*", u) else "non"
        except Exception:  # noqa: BLE001
            autorise = "?"
        if autorise == "non":
            dire(f"| {u} | non (pas lu) | | | | |")
            continue
        try:
            r = requests.get(u, headers={"User-Agent": UA}, timeout=40)
        except Exception as e:  # noqa: BLE001
            dire(f"| {u} | {autorise} | erreur {court(e, 60)} | | | |")
            continue
        t = r.text
        dates = sorted(set(re.findall(r"20(?:2[4-7])-[01]\d-[0-3]\d", t)))
        fmts = [f for f, motif in [("JSON-LD", "application/ld+json"), ("RSS", "application/rss+xml"),
                                   ("RSS", "<rss"), ("iCal", "text/calendar"), ("iCal", ".ics")] if motif in t]
        dire(f"| {u} | {autorise} | {r.status_code} | {len(t)} | {dates[-1] if dates else '—'} | {', '.join(sorted(set(fmts))) or '—'} |")
    dire()


def main() -> None:
    conf = yaml.safe_load(open(sys.argv[1] if len(sys.argv) > 1 else "outils/sonde.yml", encoding="utf-8"))
    dire("# Sonde des réseaux et sites bloqués\n")
    if conf.get("sites"):
        sites(conf["sites"])
    if not os.environ.get("APIFY_TOKEN"):
        dire("Pas de clé APIFY_TOKEN : Facebook et Instagram non sondés.")
    else:
        if conf.get("facebook"):
            facebook(conf["facebook"])
        if conf.get("instagram"):
            instagram(conf["instagram"])
        if conf.get("chercher_instagram"):
            chercher(conf["chercher_instagram"])
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write("\n".join(lignes) + "\n")
    open("sonde-rapport.md", "w", encoding="utf-8").write("\n".join(lignes) + "\n")


if __name__ == "__main__":
    main()
