# Backlog de l'agenda culturel

Ce fichier garde la trace de ce qui est fait, de ce qui reste à faire, et de la marche à suivre
pour vérifier chaque nouvelle source. À mettre à jour à chaque changement.

État en direct de chaque source : page [Sources](https://benjello.github.io/agenda-culturel-tunis/sources/).

## Vérifier une nouvelle source (à refaire pour chaque entrée)

0. **Chercher aussi la page Facebook** (et Instagram) du lieu : à Tunis, c'est souvent là que
   l'information à jour se trouve. Une page Facebook se branche avec `scraper: facebook_programmes`
   (dernières publications avec image + OCR), et un lecteur si le programme a un format récurrent.
1. **Ajouter la source** dans [`_data/sources.yml`](_data/sources.yml) : `id`, `nom`, `url`, `type`,
   `scraper`, `categorie`, `actif: true`. Un scraper générique suffit souvent (voir le README).
2. **La lancer seule** : GitHub → Actions → Scrapers → Run workflow, et mettre son `id` dans
   le champ « sources ». Sur un ordinateur : `python3 -m scrapers <id> --debug`.
3. **Lire le journal** de l'exécution : la ligne `✓ <id> : N` donne le nombre d'événements,
   `✗ <id> : …` l'erreur.
4. **Contrôler 2 ou 3 événements** sur le site : titre, date et heure, lieu, lien vers la source.
5. **Vérifier les doublons** : un événement déjà vu ailleurs (même lieu, même heure) doit
   apparaître une seule fois, avec « Aussi sur : … ».
6. **Ajouter un test** avec une page d'exemple dans `tests/fixtures/` si le scraper est nouveau.
7. **Noter le résultat** dans le tableau ci-dessous.

## Sources

| Source | Scraper | État | Remarque |
|---|---|---|---|
| Teskerti | `teskerti` | ✅ marche | ~14 événements ; lieu et adresse corrects depuis la fiche |
| El Teatro | `billetterie_sktech` | ✅ marche | ~7 événements ; doublons avec Teskerti masqués |
| Opéra de Tunis | `billetterie_sktech` | ⚠️ 0 événement | à vérifier : pas de date sur les fiches ? |
| Goethe-Institut | `rss` | ⚠️ 0 événement | flux lu, rien à venir pour l'instant |
| Institut français | `liste_fiches` | ❌ en panne | liste chargée en JavaScript : chercher l'API cachée |
| Pathé Tunis City, Azur City | `pathe` | ❌ bloqué | pathe.tn refuse GitHub (403) : lancer depuis un cron perso |
| Agora, Alhambra Zéphyr, Colisée, CinéMadart | `facebook` | ❌ rien | Apify : « page d'événements invalide », ces pages ne publient pas d'événements Facebook |
| Amilcar, Cinévog (groupes) | `facebook` | ⚠️ 0 événement | Apify lit le groupe, mais seulement 3 événements passés : rien d'annoncé à venir |
| tunis.events, monticket, b7l9, IIC, Cervantes, Cinémathèque, Ciné 360 | — | à étudier | `actif: false` dans le registre |

## Fait

- Site Jekyll sur GitHub Pages, dates en français, événements passés masqués.
- Registre des sources et page Sources avec l'état de chacune (à jour, en panne, en attente).
- Scrapers génériques : `jsonld`, `rss`, `ical`, `liste_fiches` ; spécifiques : `teskerti`,
  `billetterie_sktech`, `pathe`, `facebook` (via Apify).
- Lancement automatique chaque jour (GitHub Actions), relance à la main d'une source choisie.
- Une source en panne garde ses anciens événements ; `tous_les_jours` pour les sources payantes.
- Détection des doublons entre sources.
- Données ouvertes : `agenda.ics` et `evenements.json`, licence CC BY 4.0.
- Page Cinéma : films des cinémas, projections de l'agenda, liens IMDb.
- Clé Apify configurée (secret `APIFY_TOKEN`).

## À faire

- [ ] Pathé : lancer le scraper depuis un cron sur une machine perso (ligne dans le README).
- [ ] Facebook : les cinémas publient leur programme en **affiches**, pas en événements.
      Piste : lire les publications et extraire les séances de l'image (IA). Mis de côté pour l'instant.
- [ ] Institut français : trouver l'API qui charge la liste en JavaScript.
- [ ] Opéra de Tunis : comprendre pourquoi 0 événement.
- [ ] Contrôle de santé : ouvrir une alerte (issue GitHub) quand une source tombe en panne.
- [ ] Formulaire « Proposer une source » / « Signaler un événement ».
- [ ] Critiques de films : ajouter d'autres liens (Letterboxd, AlloCiné…) à côté d'IMDb.
- [ ] Brancher les sources « à étudier ».
