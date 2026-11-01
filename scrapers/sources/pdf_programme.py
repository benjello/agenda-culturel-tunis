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
import subprocess
import tempfile

from ..commun import _session


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


def recuperer(source: dict) -> list:
    o = source.get("options") or {}
    lus = 0
    for url, mois in _pdfs(o["modele"]):
        try:
            texte = texte_pdf(url)
        except Exception as exc:  # noqa: BLE001 — ce mois n'est pas (encore) publié
            print(f"  {url} : {exc.__class__.__name__}")
            continue
        lus += 1
        print(f"  {url} : {len(texte)} caractères")
        print(texte[:6000])
    if not lus:
        raise RuntimeError("aucun PDF de programme trouvé")
    return []
