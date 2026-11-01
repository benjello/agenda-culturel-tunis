"""Séances de cinéma de tunis.events : un seul site pour plusieurs salles de Tunis.

tunis.events (billetterie) publie sur https://tunis.events/cinema les films à
l'affiche de plusieurs salles (Colisée, Palace, CinéMadart, Agora, Pathé…) en
schema.org : un objet par film, par salle et par jour, avec le lien vers la
réservation. C'est aussi le seul moyen de lire Pathé, dont le site bloque GitHub.

Résultat : un fichier par salle dans _data/cinemas/ (page Cinéma), comme les
autres cinémas. Les salles hors Grand Tunis sont écartées.

Options :
  exclure   mots qui écartent une salle (défaut : Sousse, Sfax, Nabeul, Bizerte…)
"""
from __future__ import annotations

import datetime as dt
import json

from ..commun import Film, json_ld_evenements, page, propre, slug
from ..ecriture import DOSSIER_CINEMAS
from .jsonld import _date, _lieu

EXCLURE = ("sousse", "sfax", "nabeul", "hammamet", "bizerte", "monastir", "djerba", "kairouan", "gabes")
PREFIXE = "tunis-events-"


def recuperer(source: dict) -> dict[str, dict]:
    """{salle: {"adresse": …, "films": {titre: Film}}}"""
    exclure = tuple(m.lower() for m in source.get("options", {}).get("exclure", EXCLURE))
    salles: dict[str, dict] = {}
    for o in json_ld_evenements(page(source["url"])):
        debut, titre = _date(o.get("startDate")), propre(o.get("name"))
        lieu, adresse = _lieu(o.get("location") or {})
        if not (debut and titre and lieu) or any(m in f"{lieu} {adresse}".lower() for m in exclure):
            continue
        # Un objet couvre une journée (parfois de 00:00 à 23:59) : on garde le jour.
        jour = debut.date().isoformat()
        s = salles.setdefault(lieu, {"adresse": adresse, "films": {}})
        f = s["films"].setdefault(titre, Film(titre=titre, lien=o.get("url") or source["url"],
                                              affiche=_image(o.get("image"))))
        if jour not in f.jours:
            f.jours.append(jour)
    if not salles:
        raise RuntimeError("aucune séance en schema.org sur la page (site modifié ?)")
    return salles


def _image(v):
    if isinstance(v, list):
        v = v[0] if v else None
    if isinstance(v, dict):
        v = v.get("url")
    return v if isinstance(v, str) else None


def ecrire(source: dict, salles: dict[str, dict]) -> int:
    """Un fichier _data/cinemas/tunis-events-<salle>.json par salle ; les anciens sont remplacés."""
    DOSSIER_CINEMAS.mkdir(parents=True, exist_ok=True)
    for ancien in DOSSIER_CINEMAS.glob(f"{PREFIXE}*.json"):
        ancien.unlink()
    aujourd_hui = dt.date.today().isoformat()
    n = 0
    for lieu, s in sorted(salles.items()):
        films = [f for f in s["films"].values() if any(j >= aujourd_hui for j in f.jours)]
        for f in films:
            f.jours = sorted(j for j in f.jours if j >= aujourd_hui)
        if not films:
            continue
        data = {"id": PREFIXE + slug(lieu), "nom": lieu, "url": source["url"], "adresse": s["adresse"],
                "via": "tunis.events", "mis_a_jour": aujourd_hui,
                "films": [f.en_dict() for f in sorted(films, key=lambda f: f.titre.lower())]}
        (DOSSIER_CINEMAS / f"{data['id']}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        n += len(films)
    return n
