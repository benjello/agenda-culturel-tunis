# Consignes pour les agents (Claude et autres)

Agenda culturel de Tunis : site Jekyll sur GitHub Pages, scrapers Python lancés chaque jour par
GitHub Actions (`.github/workflows/scrapers.yml`). Voir `README.md` et `BACKLOG.md` (à tenir à jour).

## Données : d'abord les sources ouvertes

- **Chercher d'abord dans Wikidata** (CC0) et Wikipédia, puis les autres sources ouvertes
  (OpenStreetMap / Nominatim, flux RSS, iCal, schema.org des pages) avant toute API à clé
  ou tout site qui interdit la copie (IMDb, par exemple).
- Modules existants à réutiliser : `scrapers/wikidata.py` (films : IMDb, genres, âge, film tunisien),
  `scrapers/descriptifs.py` (Wikipédia via Wikidata pour lieux, festivals, musées, films),
  `scrapers/pages.py` (coordonnées OpenStreetMap).
- Garder les réponses en cache dans `_data/*.json` pour ne pas réinterroger chaque jour,
  et citer la source (lien) à l'affichage ; Wikipédia est sous CC BY-SA.
- Outils gratuits uniquement ; une clé payante ou une inscription lourde se décide avec Mahdi
  (noter la question dans `BACKLOG.md`).

## Façon de travailler

- Tout en français (code, commentaires, messages de commit, textes du site).
- Tout ce qui peut être scripté l'est (GitHub Actions), pour ne pas dépendre d'un agent.
- Tests hors ligne : `python3 -m unittest discover tests` (pages d'exemple dans `tests/fixtures/`).
- Tickets et backlog alignés : chaque point ouvert à traiter est une case non cochée dans `BACKLOG.md` **et**
  une issue GitHub (listée dans sa section « Tickets ouverts »). Une PR qui traite une issue écrit
  « Closes #N » ; une issue ne se ferme qu'une fois sa case cochée. Un chantier permanent, sans échéance
  (relecture, veille), reste seulement dans `BACKLOG.md`, sans case ni issue. Pas plus d'une dizaine d'issues
  ouvertes : au-delà, on ferme ou on reporte avant d'en ouvrir une. Le workflow « Synchro tickets »
  (chaque lundi) lance `scrapers/synchro_tickets.py` et signale les écarts dans son résumé.
- Tickets : un agent qui termine un travail ferme ce qu'il traite. Dans sa PR : « Closes #N » pour chaque issue
  résolue (GitHub la ferme à la fusion) et la case correspondante de `BACKLOG.md` cochée. Une issue obsolète
  ou en double se ferme avec un commentaire en français et `state_reason` (`not_planned` ou `duplicate`).
  Avant d'ouvrir une issue, lister les ouvertes : au-delà d'une dizaine, on ferme ou on reporte d'abord.
- Le workflow « Tickets » (`.github/workflows/tickets.yml`) fait le reste sans agent : le 1er de chaque mois,
  il avertit les issues inactives depuis 60 jours (étiquette « à-trier »), puis les ferme 14 jours plus tard
  (`scrapers/tickets.py`). Il n'agit pas sur les issues « alerte ». Sur chaque PR, il signale l'absence de
  « Closes #N ». Ne pas contourner ce garde-fou en rouvrant sans raison une issue fermée automatiquement.
