"""Programmes publiés en image sur une page Facebook (cinémas surtout), via Apify.

Beaucoup de salles ne créent pas d'événements Facebook : elles publient chaque
semaine une image avec le programme. Ce scraper récupère les dernières
publications avec image, enregistre les images dans le site, et lit le texte
des images :
- « ocr_facebook » : le texte que Facebook a lui-même lu sur l'image (fourni par Apify) ;
- « ocr » : le texte lu par Tesseract (OCR libre), s'il est installé.

La page Cinéma affiche l'image, le texte et le lien vers la publication.
L'étape suivante sera d'écrire, pour chaque salle, un lecteur de ce texte qui
en tire les films et les séances (les programmes ont un format récurrent).

Clé : variable d'environnement APIFY_TOKEN (voir facebook.py).

Options :
  page     nom de la page (facebook.com/<page>)
  max      nombre de publications avec image à garder (défaut 3)
  jours    ne lire que les publications de moins de N jours (défaut 21)
"""
from __future__ import annotations

import hashlib
import io
import os
import shutil
import subprocess

from ..commun import RACINE, EnAttente, Publication, _session, propre
from .facebook import appeler_apify, _date

ACTEUR = "apify/facebook-posts-scraper"
DOSSIER_IMAGES = RACINE / "assets" / "programmes"
LARGEUR_MAX = 1400


def images_de(item: dict) -> list[tuple[str, str]]:
    """(url de l'image, texte lu par Facebook) pour chaque photo de la publication."""
    sortie = []
    for m in item.get("media") or []:
        if not isinstance(m, dict):
            continue
        if m.get("__typename", "Photo") != "Photo":
            continue  # vidéos : pas de programme lisible
        photo = m.get("photo_image") if isinstance(m.get("photo_image"), dict) else {}
        uri = photo.get("uri") or m.get("thumbnail")
        if uri:
            sortie.append((uri, propre(m.get("ocrText") or "")))
    return sortie


def enregistrer_image(url: str, dossier, nom: str) -> str:
    """Télécharge l'image une seule fois (même nom = même publication), réduite et en JPEG."""
    chemin = dossier / f"{nom}.jpg"
    if not chemin.exists():
        r = _session.get(url, timeout=60)
        r.raise_for_status()
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
            if img.width > LARGEUR_MAX:
                img = img.resize((LARGEUR_MAX, round(img.height * LARGEUR_MAX / img.width)))
            img.save(chemin, "JPEG", quality=82)
        except ImportError:
            chemin.write_bytes(r.content)
    return str(chemin.relative_to(RACINE))


def lire_image(chemin) -> str:
    """Texte de l'image par Tesseract (français + arabe + anglais), vide s'il n'est pas installé."""
    if not shutil.which("tesseract"):
        return ""
    langues = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True).stdout.split()
    l = "+".join(x for x in ("fra", "ara", "eng") if x in langues) or "eng"
    r = subprocess.run(["tesseract", str(chemin), "stdout", "-l", l, "--psm", "4"],
                       capture_output=True, text=True, timeout=120)
    return "\n".join(ligne.strip() for ligne in r.stdout.splitlines() if ligne.strip())


def recuperer(source: dict) -> list[Publication]:
    cle = os.environ.get("APIFY_TOKEN")
    if not cle:
        raise EnAttente("clé APIFY_TOKEN pas encore configurée")
    o = source.get("options", {})
    page = o.get("page") or source["url"]
    url = page if page.startswith("http") else f"https://www.facebook.com/{page}"
    items = appeler_apify(o.get("acteur", ACTEUR), {
        "startUrls": [{"url": url}], "resultsLimit": o.get("resultats", 12),
        "onlyPostsNewerThan": f"{o.get('jours', 21)} days"}, cle)
    if not isinstance(items, list):
        raise RuntimeError(f"réponse Apify inattendue : {str(items)[:200]}")
    erreurs = [i for i in items if i.get("error")]
    avec_image = [i for i in items if not i.get("error") and images_de(i)]
    print(f"  {source['id']} : {len(items)} publication(s) lue(s), {len(avec_image)} avec image")
    if erreurs and not avec_image:
        raise RuntimeError(f"Apify : {str(erreurs[0])[:250]}")
    avec_image.sort(key=lambda i: i.get("time") or "", reverse=True)

    dossier = DOSSIER_IMAGES / source["id"]
    dossier.mkdir(parents=True, exist_ok=True)
    gardees, publications = set(), []
    for item in avec_image[:o.get("max", 3)]:
        lien = item.get("topLevelUrl") or item.get("url") or url
        debut = _date(item.get("time") or item.get("timestamp"))
        chemins, ocr_fb, ocr = [], [], []
        for n, (uri, texte_fb) in enumerate(images_de(item)[:4]):
            nom = hashlib.sha1(f"{lien}#{n}".encode()).hexdigest()[:12]
            gardees.add(f"{nom}.jpg")
            chemin = enregistrer_image(uri, dossier, nom)
            chemins.append(chemin)
            if texte_fb:
                ocr_fb.append(texte_fb)
            ocr.append(lire_image(RACINE / chemin))
        publications.append(Publication(
            lien=lien, date=debut.date().isoformat() if debut else "",
            texte=(item.get("text") or "").strip(), images=chemins,
            ocr_facebook="\n\n".join(ocr_fb), ocr="\n\n".join(t for t in ocr if t)))
    for f in dossier.iterdir():  # images des publications qui ne sont plus affichées
        if f.name not in gardees:
            f.unlink()
    return publications
