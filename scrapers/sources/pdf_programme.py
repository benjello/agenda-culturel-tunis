"""Programme mensuel publié en PDF (Institut français de Tunisie : CALENDRIER-11-2026.pdf).

Le PDF est cherché dans wp-content/uploads, au mois courant et au mois suivant. Le texte est
extrait avec pdftotext (paquet poppler-utils) puis découpé : une ligne qui commence par une date
ouvre un événement, les lignes suivantes donnent le titre et le lieu.

Options :
  modele  adresse du PDF, avec {annee}, {mois} (mois du programme) et {annee_pub}, {mois_pub}
          (dossier d'envoi, souvent le mois précédent)
  lieu    lieu par défaut
"""
from __future__ import annotations

import datetime as dt
import re
import subprocess
import tempfile

from ..commun import MOIS, Evenement, _session, categorie_du_titre, propre, resume, titre_film, titre_generique

# Mot-clé de la colonne de droite d'une case → catégorie du site
_GENRES = {"exposition": "expo", "cinéma": "cinema", "cinema": "cinema", "concert": "musique", "musique": "musique",
           "théâtre": "theatre", "theatre": "theatre", "danse": "danse", "lecture": "litterature",
           "rencontre": "litterature", "débat": "conference", "conférence": "conference", "tables rondes": "conference",
           "atelier": "autre", "festival": "autre", "spectacle": "spectacle"}
_JOURS = re.compile(r"(?<![\d:h])(?:>>\s*)?(\d{2})(?:\s*&\s*\d{2}|\d{2})*(?![\d:h])")
_HEURE = re.compile(r"\b(\d{1,2})h(\d{2})?\b")
_ENTETE = re.compile(r"^\s*(?:PROGRAMME|(?:JANVIER|FÉVRIER|FEVRIER|MARS|AVRIL|MAI|JUIN|JUILLET|AOÛT|AOUT|SEPTEMBRE|"
                     r"OCTOBRE|NOVEMBRE|DÉCEMBRE|DECEMBRE)|INSTITUT FRANÇAIS DE \w+|WWW\.\S+)\s*$")
_LIEUX = re.compile(r"m[ée]diath[èe]que|auditorium|galerie|salle|jardin|cin[ée]ma|th[ée][âa]tre|hors les murs|"
                    r"cit[ée] de la culture|sidi bou|la marsa|carthage", re.I)


# Le texte des colonnes est souvent coupé (« alle de cinéma ») : on garde un nom de salle connu.
_SALLES = [(r"camus", "Salle Albert Camus"), (r"exposition|galerie", "Galerie"),
           (r"(?:s?a?l?le )?de cin[ée]ma|\bcin[ée]ma\b", "Salle de cinéma"), (r"m[ée]diath[èe]que", "Médiathèque"),
           (r"auditorium", "Auditorium"), (r"jardin", "Jardin"), (r"th[ée][âa]tre", "Théâtre")]


# « de Jérémie Périn, 2023, 1h25mn » : la notice d'un film.
_FICHE_FILM = re.compile(r"\b(?:19|20)\d{2}\s*,\s*\d{1,2}\s*h\s*\d{0,2}|\b\d{1,3}\s*min(?:utes)?\b|\br[ée]alis[ée] par\b|"
                         r"\bun film de\b", re.I)


def titre_precis(titre: str, notice: str) -> str:
    """Le nom de l'œuvre quand la case ne donne qu'un genre (« TABLES RONDES », « EXPOSITION ») :
    le premier titre entre guillemets de la notice, sinon le début de la notice avant « : »."""
    if not titre_generique(titre) and not re.match(r"(?i)avec\b", titre):
        return titre
    m = re.search(r"[«“\"]\s*([^»”\"]{3,70}?)\s*[»”\"]", notice)
    if m:
        return propre(m.group(1))
    m = re.match(r"\s*([^:.;!?]{3,60}?)\s*:", notice)
    if m and len(m.group(1).split()) >= 2:
        return propre(m.group(1))
    return titre


def _salle(texte: str) -> str:
    return next((nom for motif, nom in _SALLES if re.search(motif, texte, re.I)), "")


def _pdfs(modele: str) -> list[tuple[str, dt.date]]:
    auj = dt.date.today().replace(day=1)
    mois = [auj, (auj + dt.timedelta(days=32)).replace(day=1)]
    res = []
    for m in mois:
        for pub in [(m - dt.timedelta(days=1)).replace(day=1), m]:
            res.append((modele.format(annee=m.year, mois=f"{m.month:02d}", annee_pub=pub.year,
                                      mois_pub=f"{pub.month:02d}"), m))
    return res


def texte_pdf(url: str) -> str:
    r = _session.get(url, timeout=60)
    r.raise_for_status()
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(r.content)
        f.flush()
        return subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, text=True, check=True).stdout


def _blocs(texte: str) -> list[tuple[str, list[str]]]:
    """Une rangée de cases = un bloc entre deux lignes vides doubles, avec la ville de l'en-tête
    (le PDF couvre Tunis, Sousse et Sfax)."""
    res, cur, vides, ville = [], [], 0, ""
    for l in texte.splitlines():
        m = re.match(r"^\s*INSTITUT FRAN[ÇC]AIS DE (\w+)\s*$", l)
        if m:
            if cur:
                res.append((ville, cur))
                cur = []
            ville = m.group(1).capitalize()
        if _ENTETE.match(l):  # en-tête et pied de page
            vides += 2
            continue
        if l.strip():
            if vides >= 2 and cur:
                res.append((ville, cur))
                cur = []
            cur.append(l.rstrip())
            vides = 0
        else:
            vides += 1
    if cur:
        res.append((ville, cur))
    return res


def _colonnes(bloc: list[str]) -> list[tuple[int, int]]:
    """Bornes des colonnes : [texte A, côté A, texte B, côté B]. Les « côtés » portent jour, genre, lieu, heure."""
    largeur = max(len(l) for l in bloc)
    jours = [m.start() for l in bloc for m in _JOURS.finditer(l) if m.start() >= 25]
    if not jours:
        return []
    milieu = largeur * 0.62
    a = [p for p in jours if p < milieu]
    b = [p for p in jours if p >= milieu]
    cols = []
    if a:
        sa = max(min(a) - 3, 0)  # le genre (« EXPOSITION ») commence un peu avant le jour
        debuts = [m.start() for l in bloc for m in re.finditer(r"(?<=\s\s)\S", l) if sa + 12 < m.start() < (min(b) - 8 if b else largeur)]
        tb = min(debuts) if debuts else (min(b) - 40 if b else largeur)
        cols += [(0, sa), (sa, tb)]
        if b:
            cols += [(tb, min(b)), (min(b), largeur + 1)]
    return cols


def _case(texte: list[str], cote: list[str], mois: dt.date, lieu_defaut: str, lien: str) -> list[Evenement]:
    lignes = [propre(l) for l in texte if propre(l)]
    infos = [propre(l) for l in cote if propre(l)]
    if not lignes or not infos:
        return []
    titre = []
    for l in lignes:
        if l.upper() == l and re.search(r"[A-ZÀ-Ü]", l):
            titre.append(l)
        else:
            break
    notice = " ".join(lignes[len(titre):])
    titre = " ".join(titre) or lignes[0]
    jours = []
    for l in infos:
        if re.fullmatch(r"(?:>>\s*)?[\d\s&]+", l):
            jours += [int(j) for j in re.findall(r"\d{2}", l.replace(" ", "").replace("&", ""))]
    genre = next((_GENRES[k] for l in infos for k in _GENRES if k in l.lower()), "")
    salle = _salle(" ".join(l for l in infos if l.upper() != l))
    lieu = f"{salle}, {lieu_defaut}" if salle else lieu_defaut
    h = next((m for l in infos for m in [_HEURE.search(l)] if m), None)
    res = []
    for j in sorted(set(jours)):
        try:
            d = dt.datetime(mois.year, mois.month, j, int(h.group(1)) if h else 0, int(h.group(2) or 0) if h else 0)
        except ValueError:
            continue
        titre_propre = titre.title() if len(titre) > 6 else titre
        categorie = categorie_du_titre(titre) or genre or "autre"
        est_film = bool(_FICHE_FILM.search(notice)) and categorie in ("cinema", "autre")
        if est_film or categorie == "cinema":
            titre_propre = titre_film(titre_propre)  # « Mercredis-Ciné Level Five » → « Level Five »
        titre_net = titre_precis(titre_propre, notice)
        if titre_net != titre_propre:  # « Tables Rondes » → « Entre deux rives » (le genre reste dans la catégorie)
            categorie = categorie if categorie != "autre" else (categorie_du_titre(titre_propre) or "autre")
        res.append(Evenement(titre=titre_net, debut=d, lien=lien, lieu=lieu,
                             categorie="cinema" if est_film else categorie,
                             film=est_film and not titre_generique(titre_net),
                             seances=[d] if est_film else [], description=resume(notice, 400)))
    return res


def depuis_texte(texte: str, mois: dt.date, lieu: str, lien: str) -> list[Evenement]:
    res = []
    for ville, bloc in _blocs(texte):
        cols = _colonnes(bloc)
        ici = f"Institut français de {ville}" if ville else lieu
        for i in range(0, len(cols) - 1, 2):
            (t0, t1), (c0, c1) = cols[i], cols[i + 1]
            res += _case([l[t0:t1] for l in bloc], [l[c0:c1] for l in bloc], mois, ici, lien)
    return res


def recuperer(source: dict) -> list[Evenement]:
    o = source.get("options") or {}
    res, lus = [], 0
    for url, mois in _pdfs(o["modele"]):
        try:
            texte = texte_pdf(url)
        except Exception as exc:  # noqa: BLE001 — ce mois n'est pas (encore) publié
            print(f"  {url} : {exc.__class__.__name__}")
            continue
        lus += 1
        evts = depuis_texte(texte, mois, o.get("lieu", source["nom"]), url)
        print(f"  {url} : {len(evts)} événement(s)")
        for e in evts:
            print(f"    {e.debut:%d/%m %H:%M} | {e.categorie} | {e.titre} | {e.lieu}")
        res += evts
    if not lus:
        raise RuntimeError("aucun PDF de programme trouvé")
    return res
