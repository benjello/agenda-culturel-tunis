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
| Teskerti | `teskerti` | ✅ marche | ~14 événements ; couvre aussi Théâtre municipal, 4ème Art, Le Rio, Zéphyr |
| El Teatro | `billetterie_sktech` | ✅ marche | ~7 événements ; doublons avec Teskerti masqués |
| Opéra de Tunis | `billetterie_sktech` | ⚠️ 0 événement | à vérifier : pas de date sur les fiches ? |
| Goethe-Institut | `rss` | ⚠️ 0 événement | flux lu, rien d'annoncé après le 1/11 |
| Beit al-Hikma | `rss` | 🆕 branché | dates en arabe dans le titre |
| IRMC | `rss` | 🆕 branché | `garder` écarte bourses et stages |
| Institut français | `liste_fiches` | ❌ en panne | agenda en JavaScript ; piste : PDF mensuel `CALENDRIER-MM-AAAA.pdf` |
| tunis.events (cinéma) | `tunis_events_cinema` | ✅ marche | ~40 films × salles : Colisée, Palace, CinéMadart, Agora, Pathé |
| Pathé Tunis City, Azur City | — | ✅ via tunis.events | pathe.tn refuse GitHub (403) |
| Alhambra Zéphyr, Ciné 350 | `facebook_programmes` + lecteur | ✅ marche | films lus dans les publications (texte + OCR) |
| Colisée, CinéMadart, Agora | `facebook_programmes` | ✅ programmes gardés | Agora : page pas publique |
| Amilcar, Cinévog (groupes) | `facebook` | ⚠️ 0 événement | rien d'annoncé à venir |
| tunis.events (agenda) | `tunis_events` | ✅ marche | ~15 événements : accueil, musique, vie nocturne, spectacles ; hors Grand Tunis écarté |
| Rachidia, Théâtre national, Club Tahar Haddad, Al Kitab, Cité de la Culture | `facebook_programmes` | à brancher | Facebook seulement (bilans dans `bilan-sources/`) |
| monticket, b7l9, IIC, Cervantes, Cinémathèque | — | à étudier | `actif: false` dans le registre |

## Fait

- Site Jekyll sur GitHub Pages, dates en français, événements passés masqués.
- Registre des sources et page Sources avec l'état de chacune (à jour, en panne, en attente).
- Scrapers génériques : `jsonld`, `rss`, `ical`, `liste_fiches` ; spécifiques : `teskerti`,
  `billetterie_sktech`, `pathe`, `facebook` (via Apify).
- Lancement automatique chaque jour (GitHub Actions), relance à la main d'une source choisie.
- Une source en panne garde ses anciens événements ; `tous_les_jours` pour les sources payantes.
- Détection des doublons entre sources.
- Données ouvertes : `agenda.ics` et `evenements.json`, licence CC BY 4.0.
- Thème Cinéma : une fiche par film (affiche, lien IMDb), puis les salles du jour choisi (`_data/films.json`).
- Clé Apify configurée (secret `APIFY_TOKEN`).

## À faire

- [ ] Cinéma : lire les horaires de chaque séance (fiches film de tunis.events).
- [ ] Page Festivals : calendrier annuel (JTC, JCC…) avec statut du programme.
- [ ] Institut français : lire le PDF mensuel du programme.
- [ ] Opéra de Tunis : comprendre pourquoi 0 événement.
- [ ] Contrôle de santé : ouvrir une alerte (issue GitHub) quand une source tombe en panne.
- [x] Formulaire « Proposer un événement » (issue GitHub, validée par l'étiquette « valide »).
- [ ] Version sans compte GitHub du formulaire.
- [ ] Critiques de films : ajouter d'autres liens (Letterboxd, AlloCiné…) à côté d'IMDb.
- [ ] Brancher les sources « à étudier ».

### Idées (1er novembre 2026)

Sources
- [ ] Comptes Instagram des clubs et bars (scraper `instagram`, recherche avec le workflow « Recherche de sources Instagram »).
- [ ] Suivre les **artistes et DJ** tunisiens sur Instagram plutôt que les lieux : ils annoncent toutes leurs dates.
- [ ] Bandsintown et Resident Advisor (tournées, scène électro).
- [ ] Agendas de presse (Tunisie Numérique, La Presse) comme filet de sécurité pour repérer des lieux non suivis.
- [ ] Une adresse où les organisateurs envoient leur affiche (e-mail ou formulaire), lue comme les affiches Instagram.
- [ ] Musées et expos : INP, galerie Selma Feriani (voir `bilan-sources/musees-expos.md`).

Usage
- [x] Page « Ce week-end » (`week-end.html`).
- [ ] Newsletter du jeudi générée depuis la page « Ce week-end ».
- [ ] Filtres « gratuit » et « en famille ».
- [ ] Carte des lieux (OpenStreetMap).
- [ ] Bouton « ajouter à mon agenda » par événement (.ics).
- [ ] Chaîne Telegram ou WhatsApp des événements du jour.

Fiabilité
- [ ] Alerte quand une source n'a rien publié depuis 30 jours (lieu fermé, compte changé).
- [ ] Bouton « signaler une erreur » sur chaque événement.
