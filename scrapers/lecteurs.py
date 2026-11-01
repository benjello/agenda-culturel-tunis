"""Lecteurs de programmes publiés en image : tirent films et jours de séance du
texte d'une publication Facebook et du texte lu sur l'image (OCR).

Chaque salle publie toujours le même genre de programme ; on choisit le lecteur
dans le registre (options.lecteur). Les titres sont rapprochés des films déjà
connus (tunis.events, Pathé…) pour avoir un nom propre et le même lien IMDb.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import unicodedata

from .commun import MOIS, RACINE, Evenement, film, propre, resume, slug, toutes_dates, prix_du_texte

_MOIS = "|".join(sorted(MOIS, key=len, reverse=True))
# « Vendredi 30 octobre à 19h », « 1er novembre », « ler novembre » (OCR), sans année.
_RE_JOUR = re.compile(r"\b(\d{1,2}|1er|ler)\s+(" + _MOIS + r")\b\.?(?!\s*\d{4})", re.IGNORECASE)
_RE_PERIODE = re.compile(r"du\s+(\d{1,2})(?:er)?\s*(?:(" + _MOIS + r")\s*)?(?:\d{4}\s*)?au\s+(\d{1,2})(?:er)?\s+("
                         + _MOIS + r")\s+(\d{4})", re.IGNORECASE)


def _annee(mois: int, ref: dt.date) -> int:
    """Année d'une date sans année, vue depuis la date de publication."""
    if mois < ref.month - 6:
        return ref.year + 1
    if mois > ref.month + 6:
        return ref.year - 1
    return ref.year


def jours_sans_annee(texte: str, ref: dt.date) -> list[str]:
    res = set()
    for j, m in _RE_JOUR.findall(texte):
        mois = MOIS[m.lower()]
        jour = 1 if j.lower() in ("1er", "ler") else int(j)
        try:
            res.add(dt.date(_annee(mois, ref), mois, jour).isoformat())
        except ValueError:
            continue
    return sorted(res)


def periode(texte: str) -> list[str]:
    """« du 02 au 09 Novembre 2026 » → tous les jours de la période."""
    m = _RE_PERIODE.search(texte)
    if not m:
        return []
    j1, m1, j2, m2, a = m.groups()
    fin = dt.date(int(a), MOIS[m2.lower()], int(j2))
    debut = dt.date(int(a), MOIS[(m1 or m2).lower()], int(j1))
    if debut > fin:
        debut = debut.replace(year=debut.year - 1)
    return [(debut + dt.timedelta(days=i)).isoformat() for i in range((fin - debut).days + 1)]


def titres_connus() -> list[str]:
    """Titres des films déjà dans l'agenda (événements « film: true » des autres sources)."""
    titres = set()
    for f in sorted((RACINE / "_events" / "auto").glob("*/*.md")):
        texte = f.read_text()
        if "\nfilm: true\n" in texte:
            m = re.search(r'^title: (".*")$', texte, re.M)
            if m:
                titres.add(json.loads(m.group(1)))
    return sorted(titres)


def _cle(titre: str) -> str:
    """Partie principale d'un titre : « Shaun le Mouton : La Bêêête… » → shaun-le-mouton."""
    return slug(re.split(r"\s[:/–-]\s|\s/\s", titre)[0])


_HARAKAT = re.compile("[\u064B-\u0652\u0670\u0640]")  # voyelles et allongements arabes


def _arabe(texte: str) -> list[str]:
    return [m for m in re.findall(r"[\u0600-\u06FF][\u0600-\u06FF\s]{2,}", _HARAKAT.sub("", texte))]


def titre_connu(texte: str, connus: list[str]) -> str | None:
    s = f"-{slug(texte)}-"
    arabe = _HARAKAT.sub("", texte)
    for t in sorted(connus, key=len, reverse=True):
        cle = _cle(t)
        if len(cle) >= 4 and f"-{cle}-" in s:
            return t
        if any(len(a.strip()) >= 3 and a.strip() in arabe for a in _arabe(t)):
            return t
    return None


def _a_venir(jours: list[str]) -> list[str]:
    aujourd_hui = dt.date.today().isoformat()
    return [j for j in jours if j >= aujourd_hui]


def normaliser(texte: str) -> str:
    """Lettres « 𝗪𝗲𝗲𝗸𝗲𝗻𝗱 » (gras Unicode) → « Weekend »."""
    return unicodedata.normalize("NFKC", texte)


def liste_films(publications: list[dict], connus: list[str], lieu: str = "") -> list[Evenement]:
    """Programme de la semaine en texte : « À l'affiche du 02 au 09 Novembre » + une ligne « 🎬 Titre » par film.
    (Alhambra Zéphyr.) Seule la publication la plus récente qui a ce format compte."""
    for p in publications:
        texte = normaliser(p.get("texte", ""))
        jours = _a_venir(periode(texte))
        lignes = [propre(l.split("🎬", 1)[1]) for l in texte.splitlines() if "🎬" in l]
        if jours and lignes:
            return [film(titre_connu(t, connus) or t, p["lien"], lieu, jours) for t in lignes if t]
    return []


def un_film_par_affiche(publications: list[dict], connus: list[str], lieu: str = "") -> list[Evenement]:
    """Une affiche par film, avec ses jours de projection (Ciné 350)."""
    films: dict[str, dict] = {}
    for p in publications:
        texte, ocr = normaliser(p.get("texte", "")), p.get("ocr") or ""
        ref = dt.date.fromisoformat(p["date"]) if p.get("date") else dt.date.today()
        jours = _a_venir(jours_sans_annee(f"{texte}\n{ocr}", ref))
        if not jours:
            continue
        titre = titre_connu(f"{texte}\n{ocr}", connus)
        if not titre:  # ligne avant « Un film de … »
            lignes = [propre(l) for l in ocr.splitlines()]
            i = next((i for i, l in enumerate(lignes) if re.match(r"un film d", l, re.I)), None)
            titre = lignes[i - 1] if i else None
        if not titre:  # titre entre guillemets dans la publication
            m = re.search(r"[«\"“]\s*([^»\"”]{2,60}?)\s*[»\"”]", texte)
            titre = m.group(1) if m else None
        titre = titre or propre(re.sub(r"[^\w\s'’:-]", " ", texte.splitlines()[0] if texte else "")) or "Film"
        f = films.setdefault(slug(titre) or titre, {"titre": titre, "lien": p["lien"], "jours": set(),
                                                     "image": (p.get("images") or [""])[0]})
        f["jours"] |= set(jours)
    return [film(f["titre"], f["lien"], lieu, f["jours"], image=f["image"]) for f in films.values()]


_RE_JJMM = re.compile(r"(?<![\d/.])(\d{1,2})[/.](\d{1,2})(?![\d/.])")
_RE_HEURE = re.compile(r"(?<!\d)([01]?\d|2[0-3])\s*[hH:](?:\s*([0-5]\d))?(?!\d)")


def _titre_affiche(texte: str) -> str:
    """Première ligne parlante d'une légende : sans #hashtags, @comptes ni émojis."""
    for ligne in normaliser(texte).splitlines():
        l = re.sub(r"[#@]\S+", " ", ligne)
        l = propre(re.sub(r"[^\w\s'’&:!?.,()+-]", " ", l))
        if len(re.findall(r"[^\W\d_]", l)) >= 3:
            return l[:90].rstrip(" .,:-")
    return ""


# Publications qui ne sont pas des événements : recrutement, horaires, cours à l'année…
_PAS_EVENEMENT = re.compile(r"recrut|candidature|offre d.emploi|ouvre exceptionnel|horaires d.ouverture|"
                            r"formation professionnelle|inscriptions? (?:ouvertes|en cours)|fermeture|"
                            # comptes rendus d'un événement passé
                            r"\bhier\b|a eu lieu|merci [àa] (?:tous|toutes|vous)|retour sur|mise [àa] jour", re.I)


_EXPO = re.compile(r"\bexposition|\bexhibition|\bvernissage|\bexpo\b|معرض", re.I)
_JUSQU = re.compile(r"(?:jusqu.?au|until|au|→|-)\s*((?:\w+\s+)?\d{1,2}(?:er)?\s+\w+(?:\s+\d{4})?)", re.I)
EXPO_JOURS = 30  # durée supposée d'une expo quand l'affiche ne dit pas jusqu'à quand


_MAJUSCULES = re.compile(r"\b([A-ZÀ-Ü][A-ZÀ-Ü'’ -]{3,40}[A-ZÀ-Ü])\b")
_DE_ARTISTE = re.compile(r"(?:solo exhibition|exposition(?: personnelle)?|exhibition)\s+(?:of|de|by|du peintre|de l.artiste)\s+"
                         r"((?:[A-ZÀ-Ü][\w'’-]+\s?){1,4})")


def _titre_expo(texte: str) -> str:
    """Le nom d'une expo est souvent en capitales dans la légende (« COSMOSE »), l'artiste après « exposition de »."""
    noms = [m for m in _MAJUSCULES.findall(texte) if not re.fullmatch(r"(?:EXPOSITION|EXHIBITION|VERNISSAGE|SOLO|OPEN|NEW)", m.strip())]
    if not noms:
        return ""
    titre = noms[0].strip().title() if len(noms[0]) > 4 else noms[0].strip()
    a = _DE_ARTISTE.search(texte)
    return f"{titre} – {a.group(1).strip()}" if a and a.group(1).strip().lower() not in titre.lower() else titre


def _exposition(p: dict, texte: str, ocr: str, tout: str, jours: set, ref: dt.date,
                aujourd_hui: dt.date, lieu: str) -> Evenement | None:
    """Une expo : du vernissage (ou de la première date) à la date de fin lue, sinon 30 jours après."""
    proches = sorted(j for j in jours if aujourd_hui - dt.timedelta(days=90) <= j <= aujourd_hui + dt.timedelta(days=120))
    if not proches and ref >= aujourd_hui - dt.timedelta(days=EXPO_JOURS):
        proches = [ref]  # « la galerie est ouverte ce week-end » : l'expo est visible depuis la publication
    if not proches:
        return None
    debut = proches[0]
    fin = None
    for m in _JUSQU.finditer(tout):
        bout = m.group(1)
        cand = [d.date() for d in toutes_dates(bout)] + [dt.date.fromisoformat(j) for j in jours_sans_annee(bout, ref)]
        cand = [c for c in cand if c > debut]
        if cand:
            fin = max(cand)
    if not fin and len(proches) > 1 and (proches[-1] - debut).days <= 120:
        fin = proches[-1]
    fin = fin or debut + dt.timedelta(days=EXPO_JOURS)
    if fin < aujourd_hui:
        return None
    titre = _titre_expo(texte) or _titre_affiche(texte) or _titre_affiche(ocr) or f"Exposition à {lieu}"
    m = re.search(r"📍\s*([^\n#]{3,80})", texte)
    ici = propre(m.group(1).replace("@", "")).rstrip(" .,") if m else lieu
    return Evenement(titre=titre, debut=dt.datetime(debut.year, debut.month, debut.day),
                     fin=dt.datetime(fin.year, fin.month, fin.day), lien=p["lien"], lieu=ici, categorie="expo",
                     image=(p.get("images") or [""])[0], prix=prix_du_texte(tout), description=resume(p.get("texte", "")))


def une_affiche_par_evenement(publications: list[dict], connus: list[str], lieu: str = "") -> list[Evenement]:
    """Une publication = une affiche = un événement (clubs, bars, concerts), à la date lue
    dans la légende ou sur l'image. Plusieurs dates sur une affiche : un événement par date."""
    aujourd_hui = dt.date.today()
    res, vus = [], set()
    for p in publications:
        texte, ocr = normaliser(p.get("texte", "")), p.get("ocr") or ""
        tout = f"{texte}\n{ocr}"
        if _PAS_EVENEMENT.search(texte[:300]):
            continue
        ref = dt.date.fromisoformat(p["date"]) if p.get("date") else aujourd_hui
        jours = {d.date() for d in toutes_dates(tout)}
        jours |= {dt.date.fromisoformat(j) for j in jours_sans_annee(tout, ref)}
        for j, m in _RE_JJMM.findall(tout):
            try:
                jours.add(dt.date(_annee(int(m), ref), int(m), int(j)))
            except ValueError:
                continue
        # Une exposition dure : le vernissage peut être passé alors qu'on peut encore la voir.
        if _EXPO.search(texte[:300] + "\n" + ocr[:300]):
            e = _exposition(p, texte, ocr, tout, jours, ref, aujourd_hui, lieu)
            if e and (e.debut.date(), e.titre) not in vus:
                vus.add((e.debut.date(), e.titre))
                res.append(e)
            continue
        jours = sorted(j for j in jours if aujourd_hui <= j <= aujourd_hui + dt.timedelta(days=120))[:7]
        if not jours:
            continue
        heures = {(int(h), int(mn or 0)) for h, mn in _RE_HEURE.findall(tout)}
        h, mn = heures.pop() if len(heures) == 1 else (0, 0)
        titre = _titre_affiche(texte) or _titre_affiche(ocr) or f"Soirée à {lieu}"
        # Artistes et collectifs jouent dans plusieurs lieux : « 📍 B7L9, La Marsa » dans la légende.
        m = re.search(r"📍\s*([^\n#]{3,80})", texte)
        ici = propre(m.group(1).replace("@", "")).rstrip(" .,") if m else lieu
        for j in jours:
            if (j, titre) in vus:
                continue
            vus.add((j, titre))
            res.append(Evenement(titre=titre, debut=dt.datetime(j.year, j.month, j.day, h, mn),
                                 lien=p["lien"], lieu=ici, image=(p.get("images") or [""])[0],
                                 prix=prix_du_texte(tout), description=resume(p.get("texte", ""))))
    return res


LECTEURS = {"liste_films": liste_films, "un_film_par_affiche": un_film_par_affiche,
            "une_affiche_par_evenement": une_affiche_par_evenement}
