"""Films à l'affiche de tunis.events : un seul site pour plusieurs salles de Tunis.

tunis.events (billetterie) publie sur https://tunis.events/cinema les films de
plusieurs salles (Colisée, Palace, CinéMadart, Agora, Pathé…) en schema.org :
un objet par film, par salle et par jour, avec le lien vers la réservation.
C'est aussi le seul moyen de lire Pathé, dont le site bloque GitHub.

Résultat : un événement par film et par salle (catégorie cinéma), avec un jour
de séance par jour de projection. Les salles hors Grand Tunis sont écartées.

Options :
  exclure   mots qui écartent une salle (défaut : Sousse, Sfax, Nabeul, Bizerte…)
"""
from __future__ import annotations

from ..commun import Evenement, film, json_ld_evenements, page, propre, slug
from .jsonld import _date, _lieu

EXCLURE = ("sousse", "sfax", "nabeul", "hammamet", "bizerte", "monastir", "djerba", "kairouan", "gabes")


def _image(v):
    if isinstance(v, list):
        v = v[0] if v else None
    if isinstance(v, dict):
        v = v.get("url")
    return v if isinstance(v, str) else ""


def recuperer(source: dict) -> list[Evenement]:
    exclure = tuple(m.lower() for m in source.get("options", {}).get("exclure", EXCLURE))
    films: dict[tuple, dict] = {}
    for o in json_ld_evenements(page(source["url"])):
        debut, titre = _date(o.get("startDate")), propre(o.get("name"))
        lieu, adresse = _lieu(o.get("location") or {})
        if not (debut and titre and lieu) or any(m in f"{lieu} {adresse}".lower() for m in exclure):
            continue
        # « WEEKEND » et « Weekend » dans la même salle : un seul film.
        f = films.setdefault((slug(lieu), slug(titre)), {
            "titre": titre, "lien": o.get("url") or source["url"], "lieu": lieu,
            "adresse": adresse, "image": _image(o.get("image")), "jours": set()})
        f["jours"].add(debut.date().isoformat())  # un objet par jour : on garde le jour
    if source.get("options", {}).get("explorer"):
        _explorer(source)
    if not films:
        raise RuntimeError("aucun film en schema.org sur la page (site modifié ?)")
    return [film(f["titre"], f["lien"], f["lieu"], f["jours"], f["adresse"], image=f["image"])
            for f in films.values()]


def _explorer(source: dict) -> None:
    """Journal pour régler la lecture des horaires (temporaire)."""
    import re
    objets = json_ld_evenements(page(source["url"]))
    print("  startDate :", sorted({str(o.get("startDate")) for o in objets})[:15])
    url = next((o.get("url") for o in objets if o.get("url")), None)
    print("  fiche :", url)
    if not url:
        return
    s = page(url)
    for a in s.find_all("a", href=True):
        if re.search(r"\b\d{1,2}:\d{2}\b", a.get_text()):
            print("   lien", a.get_text(" ", strip=True)[:40], "->", a["href"][:160])
    for el in s.find_all(string=re.compile(r"^\s*\d{1,2}:\d{2}\s*$"))[:10]:
        print("   texte", el.strip(), "| parent", el.parent.name, el.parent.get("class"))
    for b in s.find_all(["button", "a"], string=re.compile(r"Demain|Aujourd")):
        print("   jour", b.name, b.get("href"), b.attrs)
    for sc in s.find_all("script"):
        txt = sc.string or ""
        if "startDate" in txt or "showtime" in txt.lower() or "seance" in txt.lower():
            print("   script", txt[:1500])
