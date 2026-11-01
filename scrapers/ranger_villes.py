"""Ajoute (ou corrige) le champ « ville » de tous les événements : python3 -m scrapers.ranger_villes"""
from __future__ import annotations

import re

from .commun import RACINE
from .villes import ville


def main() -> int:
    n = 0
    for f in sorted((RACINE / "_events").rglob("*.md")):
        t = f.read_text()
        m = re.match(r"^---\n(.*?)\n---", t, re.S)
        if not m:
            continue
        tete = m.group(1)
        champ = lambda k: (re.search(rf'^{k}: "?(.*?)"?$', tete, re.M) or [None, ""])[1]  # noqa: E731
        v = ville(champ("venue"), champ("address"))
        if re.search(r"^ville: ", tete, re.M):
            nouvelle = re.sub(r'^ville: .*$', f'ville: "{v}"', tete, flags=re.M)
        else:
            nouvelle = re.sub(r'^(venue: .*)$', rf'\1\nville: "{v}"', tete, count=1, flags=re.M)
            if nouvelle == tete:
                nouvelle = tete + f'\nville: "{v}"'
        if nouvelle != tete:
            f.write_text(t.replace(tete, nouvelle, 1))
            n += 1
    print(f"{n} événement(s) rangé(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
