"""Traduction automatique des titres et des notices : français, arabe, anglais.

Outil libre et gratuit, sans service en ligne : les modèles d'Argos Translate
(https://github.com/argosopentech/argos-translate, licence MIT / CC0), lus directement avec
CTranslate2 et SentencePiece. Pas de PyTorch : l'installation reste légère.

Chaque texte est traduit une seule fois. Les traductions sont gardées dans
_data/traductions.json :
  titres   { titre d'origine : { en, ar, fr } }   (sans la langue d'origine)
  notices  { _events/…/x.md : { cle, en, ar, fr } } (cle : empreinte du texte d'origine)
Le site montre la traduction quand le lecteur choisit عربي ou EN (assets/site.js).

Pas de modèle direct entre le français et l'arabe : on passe par l'anglais.
Les titres de films, les noms propres d'un seul mot et les titres déjà bilingues
(« هروب | FUITE ») ne sont pas traduits.

  python3 -m scrapers.traduire            traduit ce qui est nouveau
  python3 -m scrapers.traduire --essai    traduit trois phrases (vérifier l'installation)
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import time
import zipfile
from pathlib import Path

import requests

from .commun import RACINE
from .doublons import _lire
from .langues import est_dans, langue_sure, langues_du_texte

FICHIER = RACINE / "_data" / "traductions.json"
DOSSIER_MODELES = Path(os.environ.get("MODELES_TRADUCTION", Path.home() / ".cache" / "agenda-traduction"))
MODELES = {
    ("fr", "en"): "https://argos-net.com/v1/translate-fr_en-1_9.argosmodel",
    ("en", "fr"): "https://argos-net.com/v1/translate-en_fr-1_9.argosmodel",
    ("en", "ar"): "https://argos-net.com/v1/translate-en_ar-1_0.argosmodel",
    ("ar", "en"): "https://argos-net.com/v1/translate-ar_en-1_0.argosmodel",
}
LANGUES = ("fr", "ar", "en")
MAX_TEXTES = 400          # textes nouveaux par passage (le reste attend le passage suivant)
MAX_SECONDES = 20 * 60

_ARABE = re.compile(r"[؀-ۿ]")
_LATIN = re.compile(r"[A-Za-zÀ-ÿ]")
_ANGLAIS = re.compile(r"\b(?:the|and|with|of|for|night|live|party|festival|session|in|at|by|from|your|you|our)\b", re.I)
_FRANCAIS = re.compile(r"\b(?:le|la|les|des|du|de|et|avec|pour|une|un|au|aux|sur|dans|en)\b", re.I)
_PHRASES = re.compile(r"(?<=[.!?؟…])\s+|\n+")
_LIEN = re.compile(r"\s*\(?\bhttps?://[^\s)\]]+\)?|\s*\bwww\.\S+")


def langue(texte: str) -> str:
    """Langue dominante d'un texte (fr par défaut quand rien ne tranche)."""
    ar, lat = len(_ARABE.findall(texte)), len(_LATIN.findall(texte))
    if ar > lat:
        return "ar"
    return "en" if len(_ANGLAIS.findall(texte)) > len(_FRANCAIS.findall(texte)) else "fr"


def melange(texte: str) -> bool:
    """Le texte d'origine mêle plusieurs langues (annonce bilingue, notice arabe + synopsis français)."""
    return len(langues_du_texte(texte)) > 1


def a_traduire(titre: str) -> bool:
    """Un nom propre (« Hyperculte », « BAKMA ») ou un titre déjà bilingue n'a pas besoin de traduction."""
    if len(_ARABE.findall(titre)) >= 3 and len(_LATIN.findall(titre)) >= 3:
        return False
    mots = re.findall(r"[^\W\d_]{2,}", titre)
    return len(mots) >= 2


class Traducteur:
    def __init__(self, dossier: Path = DOSSIER_MODELES):
        import ctranslate2
        import sentencepiece
        self._ct, self._sp, self.dossier = ctranslate2, sentencepiece, dossier
        self._modeles: dict = {}

    def _modele(self, de: str, vers: str):
        if (de, vers) not in self._modeles:
            racine = self.dossier / f"{de}_{vers}"
            if not (racine / "ok").exists():
                print(f"  traduction : téléchargement du modèle {de} → {vers}")
                r = requests.get(MODELES[(de, vers)], timeout=300)
                r.raise_for_status()
                racine.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                    z.extractall(racine)
                (racine / "ok").write_text("")
            modele = next(p.parent for p in racine.rglob("model.bin"))
            sp = next(racine.rglob("sentencepiece.model"))
            self._modeles[(de, vers)] = (self._ct.Translator(str(modele), device="cpu", compute_type="int8"),
                                         self._sp.SentencePieceProcessor(model_file=str(sp)))
        return self._modeles[(de, vers)]

    def _direct(self, phrases: list[str], de: str, vers: str, beam: int = 2) -> list[str]:
        if not phrases:
            return []
        trad, sp = self._modele(de, vers)
        jetons = [sp.encode(p, out_type=str) for p in phrases]
        res = trad.translate_batch(jetons, beam_size=beam, max_decoding_length=256)
        # comme Argos : les jetons recollés, « ▁ » marquant les espaces ; « <unk> » (signe inconnu) est retiré
        return [re.sub(r"\s+", " ", "".join(r.hypotheses[0]).replace("▁", " ").replace("<unk>", "")).strip() for r in res]

    def _phrases(self, phrases: list[str], de: str, vers: str) -> list[str | None]:
        """Traduit des phrases ; None quand le résultat n'est pas dans la langue visée (modèle qui recopie l'original).

        Les liens sont retirés avant (le modèle recopie alors la phrase) et remis à la fin de la phrase."""
        if de == vers:
            return list(phrases)
        sans = [_LIEN.sub("", p).strip() for p in phrases]
        liens = [_LIEN.findall(p) for p in phrases]
        res = self._via(sans, de, vers)
        for i, r in enumerate(res):
            if r is not None and not est_dans(r, vers) or r == "" and sans[i]:
                nouveau = self._via([sans[i]], de, vers, beam=5)[0]    # un second essai, plus large
                res[i] = nouveau if nouveau and est_dans(nouveau, vers) else None
            if res[i] is not None and liens[i]:
                res[i] += " " + " ".join(x.strip() for x in liens[i])
        return res

    def _via(self, phrases: list[str], de: str, vers: str, beam: int = 2) -> list[str | None]:
        if not phrases:
            return []
        opt = {} if beam == 2 else {"beam": beam}
        if (de, vers) in MODELES:
            return self._direct(phrases, de, vers, **opt)
        pivot = self._direct(phrases, de, "en", **opt)
        return [r or None for r in self._direct(pivot, "en", vers, **opt)]

    def traduire(self, textes: list[str], de: str, vers: str, mixte: bool = False) -> list[str]:
        """Traduit une liste de textes, phrase par phrase ; fr ↔ ar passe par l'anglais.

        Chaque phrase part de sa propre langue (un texte arabe suivi d'un synopsis français est traduit en entier).
        Un texte dont une phrase n'a pas pu être traduite correctement donne « » : mieux vaut l'original que
        une traduction qui laisse des phrases dans l'autre langue. mixte : même quand vers == de, on traduit les
        phrases des autres langues, pour obtenir un texte entier dans la langue du lecteur."""
        if de == vers and not mixte:
            return list(textes)
        decoupe = [[p for p in _PHRASES.split(t) if p.strip()] for t in textes]
        plat = [p for ps in decoupe for p in ps]
        origine = [(langue_sure(p) if len(re.findall(r"[^\W\d_]", p)) >= 25 or _ARABE.search(p) else None) or de for p in plat]
        sortie: list[str | None] = [None] * len(plat)
        for src in LANGUES:
            idx = [i for i, o in enumerate(origine) if o == src]
            for i, r in zip(idx, self._phrases([plat[i] for i in idx], src, vers)):
                sortie[i] = r
        res, i = [], 0
        for t, ps in zip(textes, decoupe):
            morceaux = sortie[i:i + len(ps)]
            i += len(ps)
            if any(m is None for m in morceaux):
                res.append("")
            else:
                res.append("\n".join(morceaux) if "\n" in t else " ".join(morceaux))
        return res


def _cle(texte: str) -> str:
    return hashlib.sha1(texte.encode()).hexdigest()[:12]


def evenements() -> list[tuple[str, dict, str]]:
    res = []
    for f in sorted((RACINE / "_events").rglob("*.md")):
        if f.name == "README.md":
            continue
        champs, corps = _lire(f)
        if champs:   # les doublons gardent leur fiche (adresse directe) : leur notice se traduit aussi
            res.append((str(f.relative_to(RACINE)), champs, corps.strip()))
    return res


def lire() -> dict:
    try:
        d = json.loads(FICHIER.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        d = {}
    return {"titres": d.get("titres") or {}, "notices": d.get("notices") or {}, "echecs": d.get("echecs") or {}}


def attendues(corps: str) -> tuple[str, tuple[str, ...]]:
    """(langue d'origine, langues à fournir). Un texte qui mêle les langues est aussi traduit vers sa langue
    dominante : le lecteur lit alors un texte entier dans sa langue, sans passage dans une autre."""
    de = langue(corps)
    return de, LANGUES if melange(corps) else tuple(x for x in LANGUES if x != de)


def purger(cache: dict) -> int:
    """Retire des traductions déjà enregistrées celles qui ne sont pas dans leur langue
    (phrases d'origine laissées telles quelles par le modèle) ; elles seront refaites au passage suivant."""
    n = 0
    for chemin, e in list(cache["notices"].items()):
        mauvais = [x for x in LANGUES if isinstance(e.get(x), str) and not est_dans(e[x], x)]
        if mauvais:
            n += len(mauvais)
            for x in mauvais:
                del e[x]
            if not any(e.get(x) for x in LANGUES):
                del cache["notices"][chemin]
    for t, e in list(cache["titres"].items()):
        mauvais = [x for x in LANGUES if isinstance(e.get(x), str) and not est_dans(e[x], x)]
        for x in mauvais:
            del e[x]
        n += len(mauvais)
        if not any(e.get(x) for x in LANGUES):
            del cache["titres"][t]
    return n


def a_faire(evts: list, cache: dict) -> tuple[list, list]:
    """(titres, notices) qui n'ont pas encore de traduction."""
    titres, notices = [], []
    par_cle = {n["cle"]: n for n in cache["notices"].values() if n.get("cle")}   # même texte déjà traduit ailleurs
    for chemin, c, corps in evts:
        t = str(c.get("title") or "").strip()
        if t and not c.get("doublon") and not c.get("film") and a_traduire(t) and t not in cache["titres"] and t not in titres:
            titres.append(t)
        if corps and len(re.findall(r"[^\W\d_]", corps)) >= 20:
            n = cache["notices"].get(chemin)
            cle = _cle(corps)
            incomplet = bool(n) and n.get("cle") == cle and cache.get("echecs", {}).get(chemin) != cle \
                and any(not n.get(x) for x in attendues(corps)[1])
            if not n or n.get("cle") != cle or incomplet:
                if cle in par_cle and not incomplet:
                    cache["notices"][chemin] = par_cle[cle]
                else:
                    notices.append((chemin, corps))
    return titres, notices


def traduire_tout(traducteur, cache: dict, titres: list[str], notices: list) -> int:
    debut, n = time.monotonic(), 0
    # par langue d'origine : un lot par modèle, plus rapide
    for de in LANGUES:
        lot = [t for t in titres if langue(t) == de][:MAX_TEXTES]
        for vers in LANGUES:
            if vers != de and lot:
                for t, tr in zip(lot, traducteur.traduire(lot, de, vers)):
                    if tr:
                        cache["titres"].setdefault(t, {})[vers] = tr
        n += len(lot)
        lot_n = [x for x in notices if attendues(x[1])[0] == de][:MAX_TEXTES]
        for i in range(0, len(lot_n), 20):  # par paquets de 20 notices
            if time.monotonic() - debut > MAX_SECONDES:
                print("  traduction : temps écoulé, la suite au prochain passage")
                return n
            paquet = lot_n[i:i + 20]
            entrees = [{"cle": _cle(corps)} for _, corps in paquet]
            mixtes = [melange(corps) for _, corps in paquet]
            for vers in LANGUES:
                a_faire_ = [i for i, m in enumerate(mixtes) if vers != de or m]
                if a_faire_:
                    trad = traducteur.traduire([paquet[i][1] for i in a_faire_], de, vers, mixte=True)
                    for i, tr in zip(a_faire_, trad):
                        if tr:
                            entrees[i][vers] = tr
            for (chemin, corps), e in zip(paquet, entrees):
                cache["notices"][chemin] = e
                if any(not e.get(x) for x in attendues(corps)[1]):   # un échec ne se retente pas avant que le texte change
                    cache.setdefault("echecs", {})[chemin] = e["cle"]
            n += len(paquet)
    return n


def nettoyer(cache: dict, evts: list) -> None:
    """On ne garde que les traductions d'événements encore présents."""
    titres = {str(c.get("title") or "").strip() for _, c, _ in evts}
    chemins = {chemin for chemin, _, _ in evts}
    cache["titres"] = {k: v for k, v in sorted(cache["titres"].items()) if k in titres}
    cache["notices"] = {k: v for k, v in sorted(cache["notices"].items()) if k in chemins}
    cache["echecs"] = {k: v for k, v in sorted(cache.get("echecs", {}).items()) if k in chemins}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--essai", action="store_true", help="traduire trois phrases et s'arrêter")
    args = p.parse_args(argv)
    try:
        traducteur = Traducteur()
    except ImportError:
        print("traduction : installer ctranslate2 et sentencepiece (pip install -r requirements.txt)")
        return 0
    if args.essai:
        for t, de in [("Rencontre avec l'autrice autour de son dernier roman", "fr"),
                      ("محاضرة حول تاريخ المسرح التونسي", "ar"), ("Live session with local DJs", "en")]:
            print(de, "|", t, "|", {v: traducteur.traduire([t], de, v)[0] for v in LANGUES if v != de})
        return 0
    evts = evenements()
    cache = lire()
    retirees = purger(cache)
    if retirees:
        print(f"Traduction : {retirees} traduction(s) hors de leur langue retirées, à refaire")
    titres, notices = a_faire(evts, cache)
    n = traduire_tout(traducteur, cache, titres, notices) if titres or notices else 0
    nettoyer(cache, evts)
    FICHIER.write_text(json.dumps(cache, ensure_ascii=False, indent=1) + "\n")
    print(f"Traduction : {n} texte(s) traduit(s), {len(cache['titres'])} titres et {len(cache['notices'])} notices en tout")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
