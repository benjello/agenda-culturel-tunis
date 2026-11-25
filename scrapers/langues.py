"""Détection des langues d'un texte, et contrôle des descriptions qui mêlent les langues.

Outils (sans réseau) utilisés par traduire.py et libelles.py :
  langue_sure(texte)      « fr », « en », « ar », ou None quand le texte est trop court ou ambigu
  phrases(texte)          découpe en phrases
  langues_du_texte(t)     ensemble des langues des phrases assez longues (plus d'une : texte mélangé)
  est_dans(texte, langue) vrai si tout le texte est dans cette langue (une traduction ratée laisse des phrases d'origine)

Contrôle :  python3 -m scrapers.langues [--strict]
Passe en revue les notices des événements, les descriptifs et les traductions ; liste ce qui mêle les langues
(résumé du workflow, et _data/controle_langues.json). --strict : code de sortie 1 s'il reste un défaut dans
les traductions (elles sont produites par le robot, donc un défaut y est un bogue, pas un texte source).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from .commun import RACINE

ARABE = re.compile(r"[؀-ۿݐ-ݿ]")
LATIN = re.compile(r"[A-Za-zÀ-ÿ]")
_ANGLAIS = re.compile(r"\b(?:the|and|with|of|for|your|you|our|is|are|will|from|this|that|to|in|at|by|his|her|who|an|was|be|it)\b", re.I)
_FRANCAIS = re.compile(r"\b(?:le|la|les|des|du|de|et|avec|pour|une|un|au|aux|sur|dans|en|est|qui|que|ce|cette|son|sa|ses|par|ou|où)\b", re.I)
_ACCENTS = re.compile(r"[éèêàâçùûôîï]", re.I)
_BRUIT = re.compile(r"https?://\S+|www\.\S+|[@#]\S+|\[\^?\d+\]|\bhttps?\b")
_PHRASES = re.compile(r"(?<=[.!?؟…])\s+|\n+|\s+[|•·]\s+|\s+-{2,}\s+|\s+[–—]\s+")
LETTRES_MIN = 25     # une phrase plus courte (un nom, un titre) n'a pas de langue sûre
LANGUES = ("fr", "ar", "en")


def _lettres(t: str) -> str:
    return _BRUIT.sub(" ", t)


def langue_sure(texte: str) -> str | None:
    """Langue du texte, ou None quand il est trop court ou qu'on hésite entre le français et l'anglais."""
    t = _lettres(texte)
    ar, lat = len(ARABE.findall(t)), len(LATIN.findall(t))
    if ar + lat < 8:
        return None
    if ar >= lat * 2:
        return "ar"
    if ar * 2 > lat:        # mi-arabe mi-latin : mélange à l'intérieur de la phrase
        return None
    en, fr = len(_ANGLAIS.findall(t)), len(_FRANCAIS.findall(t)) + len(_ACCENTS.findall(t)) // 2
    if en >= 2 and en >= 2 * fr:
        return "en"
    if fr >= 2 and fr >= 2 * en:
        return "fr"
    return None


def phrases(texte: str) -> list[str]:
    return [p.strip() for p in _PHRASES.split(texte) if p and p.strip()]


def langues_du_texte(texte: str) -> set[str]:
    """Langues des phrases assez longues pour être sûres. Plus d'une : le texte mêle les langues."""
    res = set()
    for p in phrases(texte):
        if len(ARABE.findall(_lettres(p))) + len(LATIN.findall(_lettres(p))) >= LETTRES_MIN or ARABE.search(p):
            if l := langue_sure(p):
                res.add(l)
    return res


def est_dans(texte: str, langue: str) -> bool:
    """Aucune phrase du texte n'est sûrement dans une autre langue (un nom propre, un titre, un lien passent)."""
    for p in phrases(texte):
        if len(ARABE.findall(_lettres(p))) + len(LATIN.findall(_lettres(p))) < 12:
            continue
        if langue == "ar":
            t = _lettres(p)
            if not ARABE.search(t):
                if langue_sure(p) in ("fr", "en"):   # une phrase de la langue d'origine laissée telle quelle
                    return False
            elif len(re.findall(r"[A-Za-zÀ-ÿ]{3,}", t)) >= 3 and len(LATIN.findall(t)) > len(ARABE.findall(t)) * 0.5:
                return False
        else:
            l = langue_sure(p)
            if l is not None and l != langue:
                return False
    return True


# ---------------------------------------------------------------- contrôle

def _corps_evenements():
    from .doublons import _lire
    for dossier in ("_events",):
        for f in sorted((RACINE / dossier).rglob("*.md")):
            if f.name == "README.md":
                continue
            champs, corps = _lire(f)
            if champs and not champs.get("doublon"):
                yield str(f.relative_to(RACINE)), corps.strip()


def _json(nom: str):
    try:
        return json.loads((RACINE / "_data" / nom).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def controler() -> dict:
    """{ « sources » : textes d'origine mélangés, « traductions » : traductions qui ne sont pas dans leur langue }"""
    sources, traductions = [], []
    for chemin, corps in _corps_evenements():
        if len(langues_du_texte(corps)) > 1:
            sources.append(chemin)
    d = _json("descriptifs.json")
    for url, e in ((d.get("pages") or {}).items() if isinstance(d, dict) else []):
        t = e.get("texte") if isinstance(e, dict) else None
        if isinstance(t, str) and len(langues_du_texte(t)) > 1:
            sources.append(f"descriptifs : {url}")
    tr = _json("traductions.json")
    for chemin, n in (tr.get("notices") or {}).items():
        for l in LANGUES:
            if isinstance(n.get(l), str) and not est_dans(n[l], l):
                traductions.append(f"{chemin} [{l}]")
    for texte, n in _json("libelles.json").items():
        for l in LANGUES:
            if isinstance(n.get(l), str) and not est_dans(n[l], l):
                traductions.append(f"libellé « {texte[:50]} » [{l}]")
    return {"sources": sorted(set(sources)), "traductions": sorted(set(traductions))}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    res = controler()
    (RACINE / "_data" / "controle_langues.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n")
    lignes = [f"Contrôle des langues : {len(res['sources'])} texte(s) d'origine mêlant les langues, "
              f"{len(res['traductions'])} traduction(s) hors de leur langue"]
    for titre, cle in (("Textes d'origine mêlés (traduits phrase par phrase)", "sources"),
                       ("Traductions fautives (à reprendre)", "traductions")):
        if res[cle]:
            lignes += ["", f"{titre} :"] + [f"- {x}" for x in res[cle][:40]]
    print("\n".join(lignes))
    return 1 if "--strict" in argv and res["traductions"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
