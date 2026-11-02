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
import html
import re
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

from ..commun import Evenement, categorie_du_titre, prix_du_texte, propre, resume, telecharger, toutes_dates
from ..lecteurs import jours_sans_annee, periode
from .rss import _racine

MOTS = (r"festival|concert|spectacle|exposition|vernissage|projection|pi[èe]ce|repr[ée]sentation|soir[ée]e|"
        r"rencontre|conf[ée]rence|journ[ée]es|r[ée]cital|one man show|stand.?up|salon du livre|foire|"
        r"carnaval|biennale|mus[ée]e|th[ée][âa]tre|op[ée]ra|danse|cin[ée]-?club|"
        # en arabe : festival, spectacle, concert, exposition, colloque, soirée, rencontre, pièce, journées
        r"مهرجان|عرض|حفل|معرض|ندوة|أمسية|سهرة|تظاهرة|ملتقى|مسرحية|أيام|لقاء|ورشة")
# Articles sur un événement à l'étranger (« Paris : la Saison Méditerranée… ») : écartés.
_ETRANGER = re.compile(r"\b(?:Paris|Marseille|Lyon|Cannes|Venise|Rome|Berlin|Londres|Madrid|Bruxelles|Gen[èe]ve|"
                       r"New York|Montr[ée]al|Le Caire|Duba[ïi]|Doha|Rabat|Casablanca|Marrakech|Alger|Oran|Beyrouth|Amman)\b")
_CONTENU = "{http://purl.org/rss/1.0/modules/content/}encoded"
_LIEU = re.compile(r"\b(?:à|au|aux|à la|à l['’])\s*((?:Cité|Théâtre|Maison|Palais|Espace|Centre|Musée|Galerie|"
                   r"Institut|Salle|Cinéma|Cinémathèque|Dar|Bir|Club|Opéra|Bibliothèque|Médiathèque|Complexe|"
                   r"Amphithéâtre|Fondation|Rotonde|Acropolium|Colisée|Ksar|Fort)\b[^,.;:()\n«»\"]{2,60})")


def _lire(xml: str):
    try:
        return _racine(xml)
    except ET.ParseError:
        # « & » nu dans un titre (Tunisie Numérique) : on l'échappe et on réessaie
        # caractères de contrôle invisibles (Tunisie Numérique) aussi
        xml = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", xml)
        return _racine(re.sub(r"&(?!\w+;|#\d+;|#x[0-9a-fA-F]+;)", "&amp;", xml))


class _Item:
    """Élément d'un flux trop abîmé pour l'analyse XML, lu balise par balise."""
    def __init__(self, bloc: str):
        self.bloc = bloc

    def findtext(self, nom: str, defaut: str = "") -> str:
        nom = {_CONTENU: "content:encoded"}.get(nom, nom)
        m = re.search(rf"<{nom}[^>]*>(.*?)</{nom}>", self.bloc, re.S)
        if not m:
            return defaut
        v = m.group(1).strip()
        return v[9:-3] if v.startswith("<![CDATA[") and v.endswith("]]>") else html.unescape(v)


def _items(xml: str):
    try:
        return list(_lire(xml).iter("item"))
    except ET.ParseError:
        return [_Item(b) for b in re.findall(r"<item>(.*?)</item>", xml, re.S)]


def _articles(xml: str) -> list[dict]:
    res = []
    for it in _items(xml):
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
    limite = aujourd_hui + dt.timedelta(days=120)
    p = periode(texte)
    if p:
        debut, fin = dt.date.fromisoformat(p[0]), dt.date.fromisoformat(p[-1])
        if fin >= aujourd_hui and debut <= limite:
            return debut, fin
    jours = {d.date() for d in toutes_dates(texte)}
    jours |= {dt.date.fromisoformat(j) for j in jours_sans_annee(texte, ref)}
    a_venir = sorted(j for j in jours if aujourd_hui <= j <= limite)
    return (a_venir[0], None) if a_venir else (None, None)


_RUBRIQUE = re.compile(r"^\s*(?:Tunisie|Culture|Cin[ée]ma|Th[ée][âa]tre|Musique|Expo(?:sition)?|Livres?|Agenda|Sortie|"
                       r"Critique|Festival|Danse|Arts?)\s*[:|–-]\s+", re.I)
_EVENEMENT = re.compile(r"festival|foire|salon|journ[ée]es|biennale|rencontres|semaine|mois|nuit|f[êe]te|"
                        r"\b20\d{2}\b|مهرجان|أيام|معرض", re.I)


def titre_evenement(titre: str) -> str:
    """Le nom de l'événement dans un titre d'article :
    « Cinéma : Le Temps suspendu, un film hongrois à ne pas rater » → « Le Temps suspendu » ;
    « « Saveurs et amertume » à la Galerie TGM : Lorsque l'art… » → « Saveurs et amertume » ;
    « Foire nationale du livre tunisien: Traduire, transmettre… » → « Foire nationale du livre tunisien »."""
    t = _RUBRIQUE.sub("", titre, count=1).strip()
    m = re.search(r"[«“\"]\s*([^»”\"]{3,80}?)\s*[»”\"]", t)
    if m:
        return propre(m.group(1))
    avant, sep, apres = t.partition(":")
    if sep and 2 <= len(avant.split()) <= 8 and len(apres.split()) >= 3 and _EVENEMENT.search(avant):
        return propre(avant)
    t = re.split(r",\s+(?:un|une|le|la|les|des|ce|cette)\s", t, maxsplit=1)[0]
    return propre(t) or titre


# Un article sur un film (critique, sortie en salles) n'est pas un événement : ses séances viennent des
# cinémas (doublon sinon). On garde seulement un film montré lors d'un événement précis.
_FILM = re.compile(r"\bfilms?\b|cin[ée]ma|en salles?|[àa] l.affiche|\bsortie\b|long.m[ée]trage|documentaire|فيلم|سينما", re.I)
_SEANCE_UNIQUE = re.compile(r"festival|cin[ée].?club|projection|avant.premi[èe]re|journ[ée]es|r[ée]trospective|cycle|"
                            r"semaine du|nuit du|rencontre|d[ée]bat|مهرجان|نادي السينما|عرض خاص", re.I)


def est_sortie_de_film(titre: str, texte: str = "") -> bool:
    return bool(_FILM.search(titre)) and not _SEANCE_UNIQUE.search(f"{titre} {texte[:300]}")


def depuis_flux(xml: str, source: dict) -> list[Evenement]:
    o = source.get("options") or {}
    mots = re.compile(o.get("garder", MOTS), re.I)
    res = []
    for a in _articles(xml):
        tout = f"{a['titre']}. {a['texte']}"
        if not a["titre"] or not mots.search(a["titre"] + " " + a["texte"][:400]):
            continue
        if _ETRANGER.search(a["titre"]):
            continue
        if est_sortie_de_film(a["titre"], a["texte"]):
            continue
        debut, fin = _dates(tout, a["date"])
        if not debut:
            continue
        m = _LIEU.search(tout)
        lieu = propre(m.group(1)).rstrip(" .") if m else o.get("lieu", "Tunisie, voir l'article")
        categorie = categorie_du_titre(a["titre"]) or (
            "expo" if re.search(r"\bgalerie\b|exposition|معرض", a["titre"], re.I) else source.get("categorie", "autre"))
        res.append(Evenement(titre=titre_evenement(a["titre"]), debut=dt.datetime(debut.year, debut.month, debut.day),
                             fin=dt.datetime(fin.year, fin.month, fin.day) if fin else None, lien=a["lien"] or source["url"],
                             lieu=lieu, categorie=categorie,
                             prix=prix_du_texte(tout), description=resume(a["texte"], 400)))
    return res


def recuperer(source: dict) -> list[Evenement]:
    xml = telecharger(source["url"])
    if not _items(xml):
        raise RuntimeError("flux vide ou illisible")
    return depuis_flux(xml, source)
