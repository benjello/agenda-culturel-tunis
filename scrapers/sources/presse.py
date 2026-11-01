"""Articles culturels de la presse (La Presse, Tunisie Numérique, Kapitalis, Webdo…), via RSS.

La presse annonce beaucoup d'événements que nous ne suivons pas directement (régions, maisons
de la culture, festivals). Un article devient un événement s'il :
  - parle d'un événement (festival, concert, spectacle, exposition…, voir MOTS) ;
  - donne une date à venir (« du 5 au 9 novembre », « le 12 novembre », « 12 novembre 2026 »).
Le lieu est cherché dans le texte (« à la Cité de la culture », « au Théâtre municipal »…).

Options :
  garder   expression régulière qui remplace MOTS
  lieu     lieu par défaut quand le texte n'en donne pas (défaut : « Tunisie, voir l'article »)
"""
from __future__ import annotations

import datetime as dt
import email.utils
import re
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

from ..commun import Evenement, categorie_du_titre, propre, telecharger, toutes_dates
from ..lecteurs import jours_sans_annee, periode
from .rss import _racine

MOTS = (r"festival|concert|spectacle|exposition|vernissage|projection|pi[èe]ce|repr[ée]sentation|soir[ée]e|"
        r"rencontre|conf[ée]rence|journ[ée]es|r[ée]cital|one man show|stand.?up|salon du livre|foire|"
        r"carnaval|biennale|mus[ée]e|th[ée][âa]tre|op[ée]ra|danse|cin[ée]-?club")
_CONTENU = "{http://purl.org/rss/1.0/modules/content/}encoded"
_LIEU = re.compile(r"\b(?:à|au|aux|à la|à l['’])\s*((?:Cité|Théâtre|Maison|Palais|Espace|Centre|Musée|Galerie|"
                   r"Institut|Salle|Cinéma|Cinémathèque|Dar|Bir|Club|Opéra|Bibliothèque|Médiathèque|Complexe|"
                   r"Amphithéâtre|Fondation|Rotonde|Acropolium|Colisée|Ksar|Fort)\b[^,.;:()\n«»\"]{2,60})")


def _articles(xml: str) -> list[dict]:
    res = []
    for it in _racine(xml).iter("item"):
        html = it.findtext(_CONTENU, "") or it.findtext("description", "")
        try:
            pub = email.utils.parsedate_to_datetime(it.findtext("pubDate", "")).date()
        except (TypeError, ValueError):
            pub = dt.date.today()
        res.append({"titre": propre(it.findtext("title", "")), "lien": propre(it.findtext("link", "")),
                    "texte": propre(BeautifulSoup(html, "html.parser").get_text(" ")), "date": pub})
    return res


def _dates(texte: str, ref: dt.date) -> tuple[dt.date | None, dt.date | None]:
    """Première date à venir (ou période) citée dans le texte."""
    aujourd_hui = dt.date.today()
    limite = aujourd_hui + dt.timedelta(days=180)
    p = periode(texte)
    if p:
        debut, fin = dt.date.fromisoformat(p[0]), dt.date.fromisoformat(p[-1])
        if fin >= aujourd_hui and debut <= limite:
            return debut, fin
    jours = {d.date() for d in toutes_dates(texte)}
    jours |= {dt.date.fromisoformat(j) for j in jours_sans_annee(texte, ref)}
    a_venir = sorted(j for j in jours if aujourd_hui <= j <= limite)
    return (a_venir[0], None) if a_venir else (None, None)


def depuis_flux(xml: str, source: dict) -> list[Evenement]:
    o = source.get("options") or {}
    mots = re.compile(o.get("garder", MOTS), re.I)
    res = []
    for a in _articles(xml):
        tout = f"{a['titre']}. {a['texte']}"
        if not a["titre"] or not mots.search(a["titre"] + " " + a["texte"][:400]):
            continue
        debut, fin = _dates(tout, a["date"])
        if not debut:
            continue
        m = _LIEU.search(tout)
        lieu = propre(m.group(1)).rstrip(" .") if m else o.get("lieu", "Tunisie, voir l'article")
        res.append(Evenement(titre=a["titre"], debut=dt.datetime(debut.year, debut.month, debut.day),
                             fin=dt.datetime(fin.year, fin.month, fin.day) if fin else None, lien=a["lien"] or source["url"],
                             lieu=lieu, categorie=categorie_du_titre(a["titre"]) or source.get("categorie", "autre")))
    return res


def recuperer(source: dict) -> list[Evenement]:
    xml = telecharger(source["url"])
    try:
        _racine(xml)
    except ET.ParseError as exc:
        raise RuntimeError(f"flux illisible ({exc})") from exc
    return depuis_flux(xml, source)
