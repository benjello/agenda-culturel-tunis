"""Transforme une proposition de source (issue GitHub validée) en entrée du registre des sources.

Lancé par le workflow « Source validée » quand l'étiquette « valide » est posée sur une issue
« Proposer une source » (ouverte sur GitHub ou par le formulaire sans compte). Lit le texte de
l'issue dans la variable ISSUE_BODY, ajoute l'entrée à la fin de _data/sources.yml (le texte
existant et ses commentaires restent intacts) et affiche l'identifiant ajouté.

Le scraper se déduit de l'adresse : Instagram, Facebook, flux RSS, calendrier iCal, sinon lecture
du schema.org de la page (scraper « jsonld »). Les PDF restent « à étudier » (actif: false).
"""
from __future__ import annotations

import os
import re
import sys
from urllib.parse import urlparse

import yaml

from .commun import RACINE, slug
from .ecriture import _yaml
from .propositions import champs

REGISTRE = RACINE / "_data" / "sources.yml"
RESEAUX_INSTAGRAM = {"instagram.com", "www.instagram.com"}
RESEAUX_FACEBOOK = {"facebook.com", "www.facebook.com", "m.facebook.com", "fb.com", "web.facebook.com"}


def _compte(url: str) -> str:
    """Premier élément du chemin : instagram.com/<compte>/, facebook.com/<page>."""
    morceaux = [m for m in urlparse(url).path.split("/") if m]
    return morceaux[0] if morceaux else ""


def deduire(url: str) -> dict:
    """Scraper, options et type pour une adresse. Lève ValueError si elle n'est pas exploitable."""
    u = urlparse(url)
    if u.scheme not in ("http", "https") or "." not in u.netloc:
        raise ValueError(f"adresse invalide : {url!r}")
    hote, chemin = u.netloc.lower(), u.path.lower()
    base = {"type": "lieu", "genre": "lieu"}
    if hote in RESEAUX_INSTAGRAM:
        compte = _compte(url)
        if not compte or compte in {"p", "reel", "explore", "stories"}:
            raise ValueError("adresse de publication, pas de compte Instagram (attendu instagram.com/<compte>)")
        return {**base, "scraper": "instagram", "tous_les_jours": 3, "options": {"compte": compte, "resultats": 8}}
    if hote in RESEAUX_FACEBOOK:
        page = _compte(url)
        if not page or page in {"events", "groups", "watch", "photo", "permalink.php", "profile.php"}:
            raise ValueError("adresse de page Facebook attendue (facebook.com/<page>)")
        return {**base, "scraper": "facebook_programmes", "tous_les_jours": 3, "options": {"page": page}}
    if chemin.endswith((".rss", ".atom")) or re.search(r"/(feed|rss)(\.xml)?/?$", chemin) or chemin.endswith("/feed/"):
        return {"type": "agenda", "genre": "agenda", "scraper": "rss", "options": {}}
    if chemin.endswith(".ics"):
        return {**base, "scraper": "ical", "options": {}}
    if chemin.endswith(".pdf"):
        return {**base, "scraper": "pdf_programme", "actif": False, "options": {},
                "note": "PDF : lecteur à écrire ou à régler à la main."}
    return {**base, "scraper": "jsonld", "options": {}}


def entree(corps: str, numero: str = "", existantes: list[dict] | None = None) -> dict:
    """L'entrée du registre pour une issue. Lève ValueError si la source est inutilisable ou déjà connue."""
    c = champs(corps)
    nom = c.get("lieu, collectif ou organisateur", "").strip()
    url = c.get("adresse de la page", "").strip()
    if not nom or not url:
        raise ValueError("nom ou adresse manquant")
    existantes = existantes if existantes is not None else yaml.safe_load(REGISTRE.read_text(encoding="utf-8")) or []
    propre_url = url.rstrip("/").lower()
    for s in existantes:
        if str(s.get("url", "")).rstrip("/").lower() == propre_url:
            raise ValueError(f"déjà dans le registre : {s['id']}")
    reglages = deduire(url)
    options = {"lieu": nom, **reglages.pop("options")}
    base_id = slug(nom)[:40].strip("-") or "source"
    ids = {s["id"] for s in existantes}
    ident, n = base_id, 2
    while ident in ids:
        ident, n = f"{base_id}-{n}", n + 1
    actif = reglages.pop("actif", True)
    note = reglages.pop("note", "")
    mention = f"Proposée par le formulaire (issue #{numero}), à vérifier au premier passage." if numero else "Proposée par le formulaire, à vérifier au premier passage."
    return {"id": ident, "nom": nom, "url": url, **{k: reglages[k] for k in ("type", "genre", "scraper")},
            "categorie": "autre", "actif": actif,
            **({"tous_les_jours": reglages["tous_les_jours"]} if "tous_les_jours" in reglages else {}),
            "options": options, "note": f"{note} {mention}".strip()}


def en_yaml(e: dict) -> str:
    """Le texte YAML d'une entrée, dans le même style que le reste du fichier."""
    lignes = [f"- id: {e['id']}", f"  nom: {_yaml(e['nom'])}", f"  url: {_yaml(e['url'])}"]
    for k in ("type", "genre", "scraper", "categorie"):
        lignes.append(f"  {k}: {e[k]}")
    lignes.append(f"  actif: {'true' if e['actif'] else 'false'}")
    if "tous_les_jours" in e:
        lignes.append(f"  tous_les_jours: {e['tous_les_jours']}")
    if e["options"]:
        lignes.append("  options:")
        lignes += [f"    {k}: {_yaml(v)}" for k, v in e["options"].items()]
    lignes.append(f"  note: {_yaml(e['note'])}")
    return "\n".join(lignes) + "\n"


def main() -> int:
    e = entree(os.environ.get("ISSUE_BODY", ""), os.environ.get("ISSUE_NUMBER", ""))
    texte = REGISTRE.read_text(encoding="utf-8").rstrip("\n") + "\n\n" + en_yaml(e)
    REGISTRE.write_text(texte, encoding="utf-8")
    print(e["id"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
