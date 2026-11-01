"""Publications d'un compte Instagram (clubs, bars, salles), via Apify.

Même principe que facebook_programmes : on lit les dernières publications avec image,
on garde l'image dans le site et on lit son texte (OCR). Le lecteur choisi en tire
ensuite les événements : par défaut une affiche = un événement (« une_affiche_par_evenement »),
avec la date trouvée dans la légende ou sur l'image.

Clé : variable d'environnement APIFY_TOKEN.

Options :
  compte   nom du compte (instagram.com/<compte>)
  lieu     nom du lieu
  max      nombre de publications avec image à garder (défaut 6)
  jours    ne lire que les publications de moins de N jours (défaut 21)
  lecteur  défaut : une_affiche_par_evenement
"""
from __future__ import annotations

import hashlib
import os

from .. import lecteurs
from ..commun import RACINE, EnAttente, Publication
from .facebook import appeler_apify, _date
from .facebook_programmes import DOSSIER_IMAGES, enregistrer_image, lire_image

ACTEUR = "apify/instagram-scraper"


def images_de(item: dict) -> list[str]:
    if item.get("type") == "Video":
        return []
    urls = [u for u in item.get("images") or [] if isinstance(u, str)]
    return urls or ([item["displayUrl"]] if item.get("displayUrl") else [])


def lire_publications(source: dict) -> list[Publication]:
    cle = os.environ.get("APIFY_TOKEN")
    if not cle:
        raise EnAttente("clé APIFY_TOKEN pas encore configurée")
    o = source.get("options", {})
    compte = o.get("compte") or source["url"]
    url = compte if compte.startswith("http") else f"https://www.instagram.com/{compte}/"
    items = appeler_apify(o.get("acteur", ACTEUR), {
        "directUrls": [url], "resultsType": "posts", "resultsLimit": o.get("resultats", 12),
        "onlyPostsNewerThan": f"{o.get('jours', 21)} days"}, cle)
    if not isinstance(items, list):
        raise RuntimeError(f"réponse Apify inattendue : {str(items)[:200]}")
    erreurs = [i for i in items if i.get("error")]
    avec_image = [i for i in items if not i.get("error") and images_de(i)]
    print(f"  {source['id']} : {len(items)} publication(s) lue(s), {len(avec_image)} avec image")
    if erreurs and not avec_image:
        raise RuntimeError(f"Apify : {str(erreurs[0])[:250]}")
    avec_image.sort(key=lambda i: i.get("timestamp") or "", reverse=True)

    dossier = DOSSIER_IMAGES / source["id"]
    dossier.mkdir(parents=True, exist_ok=True)
    gardees, publications = set(), []
    for item in avec_image[:o.get("max", 6)]:
        lien = item.get("url") or url
        debut = _date(item.get("timestamp"))
        chemins, ocr = [], []
        for n, uri in enumerate(images_de(item)[:2]):
            nom = hashlib.sha1(f"{lien}#{n}".encode()).hexdigest()[:12]
            gardees.add(f"{nom}.jpg")
            try:
                chemin = enregistrer_image(uri, dossier, nom)
            except Exception as exc:  # noqa: BLE001 — une image injoignable ne bloque pas la source
                print(f"  image illisible ({exc.__class__.__name__}) : {lien}")
                continue
            chemins.append(chemin)
            ocr.append(lire_image(RACINE / chemin))
        publications.append(Publication(
            lien=lien, date=debut.date().isoformat() if debut else "",
            texte=(item.get("caption") or "").strip(), images=chemins,
            ocr="\n\n".join(t for t in ocr if t)))
    for f in dossier.iterdir():
        if f.name not in gardees:
            f.unlink()
    return publications


def recuperer(source: dict) -> list:
    """Les événements lus sur les affiches (les publications elles-mêmes ne sont pas affichées)."""
    o = source.get("options", {})
    publications = lire_publications(source)
    for p in publications:  # dans le journal, pour régler le lecteur
        txt = " ".join(p.texte.split())[:110]
        ocr = " ".join(p.ocr.split())[:80]
        print(f"    {p.date} | {txt} | ocr: {ocr}")
    lecteur = lecteurs.LECTEURS[o.get("lecteur", "une_affiche_par_evenement")]
    lieu = o.get("lieu") or source["nom"]
    evts = [e for e in lecteur([p.en_dict() for p in publications], [], lieu) if e]
    for e in evts:
        e.categorie = source.get("categorie", e.categorie)
    print(f"  {source['id']} : {len(evts)} événement(s) lu(s) sur les affiches")
    return evts
