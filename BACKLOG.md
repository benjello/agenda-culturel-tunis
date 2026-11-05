# Backlog de l'agenda culturel

Ce fichier garde la trace de ce qui est fait, de ce qui reste à faire, et de la marche à suivre
pour vérifier chaque nouvelle source. À mettre à jour à chaque changement.

État en direct de chaque source : page [Sources](https://benjello.github.io/agenda-culturel-tunis/sources/).

Principe : chercher d'abord dans Wikidata et les autres sources ouvertes (voir `AGENTS.md`).

## Tickets ouverts

Les points restants sont suivis en issues GitHub : [liste des issues](https://github.com/benjello/agenda-culturel-tunis/issues).
Chaque lundi, le workflow « Synchro tickets » compare les cases non cochées de ce fichier aux issues ouvertes
(`scrapers/synchro_tickets.py`) et signale les écarts dans son résumé.

- Étiquette **décision** (choix de conception) : [#107 Page « Presse »](https://github.com/benjello/agenda-culturel-tunis/issues/107).
- Étiquette **vérification humaine** (contrôles ouverts à tous) :
  [#106 festivals et séries manquants](https://github.com/benjello/agenda-culturel-tunis/issues/106),
  [#108 sources proposées à trier](https://github.com/benjello/agenda-culturel-tunis/issues/108),
  [#109 fiches de l'Institut français](https://github.com/benjello/agenda-culturel-tunis/issues/109).
- Étiquette **amélioration** : [#110 relecture par catégorie](https://github.com/benjello/agenda-culturel-tunis/issues/110),
  [#111 rapport après les scrapers](https://github.com/benjello/agenda-culturel-tunis/issues/111),
  [#112 accès Facebook](https://github.com/benjello/agenda-culturel-tunis/issues/112),
  [#113 version anglaise ou arabe](https://github.com/benjello/agenda-culturel-tunis/issues/113),
  [#114 test du formulaire de contribution](https://github.com/benjello/agenda-culturel-tunis/issues/114).

## Horaires

Chaque événement porte son heure de début (`date: AAAA-MM-JJ HH:MM`) et, si on la connaît, son heure de fin
(`end_time: "HH:MM"`). Si la source ne donne pas l'heure, `scrapers/commun.py: horaire_du_texte` la cherche dans le
titre et la notice (« de 19h à 21h », « à 20h30 », « doors 9pm ») ; un texte ambigu (plusieurs heures) ne donne rien.
Les films ont leurs séances, les expos leurs jours d'ouverture : pas d'heure unique. Le nombre d'événements
sans heure par source apparaît sur la page Sources et dans `_data/etat_sources.json` (`sans_heure`).
À vérifier au prochain passage des scrapers : lire le journal (`heures : N/M`) et repérer les sources à 0.

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
| Opéra de Tunis | `billetterie_sktech` | ⚠️ 0 événement | liste lue, fiches sans date reconnue ; dates ISO et balises `time` lues depuis, raison de chaque fiche rejetée dans le journal : à vérifier au prochain passage |
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

- Référencement : plan du site (`sitemap.xml`), balises canonique, Open Graph et Twitter, données structurées `Event` (fiches) et `WebSite` (accueil).
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
- Abonnements : calendriers `.ics` par catégorie et par ville (`calendriers/`), fil RSS `feed.xml`, page S'abonner.
- Page « Cette semaine » avec message WhatsApp prêt à partager.
- Carte : filtre Aujourd'hui / 7 jours / Tout, liste des événements dans chaque lieu.
- Métadonnées schema.org (Event) sur chaque fiche, pour Google.
- Descriptifs (`scrapers/descriptifs.py`) : notice lue sur la page de l'annonce, synopsis des films (salle, Wikipédia, TMDb si `TMDB_API_KEY`), courte présentation des lieux, festivals et musées (Wikipédia) ; textes à la main dans `_data/descriptifs_manuels.yml`.
- Artistes et conférenciers séparés sur la page Artistes (`role` deviné d'après les dates — conférences, rencontres, débats —, ou fixé dans `_data/artistes.yml`).
- Types de lieux (cinéma, théâtre, galerie, musée, médiathèque, club, centre culturel) : lus dans le nom, sinon dans OpenStreetMap, corrections dans `_data/types_lieux.yml` ; intertitres et filtre sur la page Lieux.
- Formulaire « Ajouter ou corriger une fiche » (lieu, artiste, conférencier, organisateur) : page Proposer et lien sur chaque fiche (issue GitHub, étiquette « fiche »).
- Archives : `scrapers/archives.py` garde les événements passés (`archives/donnees/AAAA.json`), page de recherche `/archives/`.

## Contributions extérieures (sources)

- Page **Contribuer** (`/contribuer/`) : sources recherchées (`_data/sources_recherchees.yml`, à tenir à jour :
  retirer une entrée quand elle est branchée) et sources à réparer (calculées depuis le registre).
- Formulaire `source.yml`, issues vides désactivées, modèle de PR, `CODEOWNERS`, guide `.github/CONTRIBUTING.md`.
- Chaque PR : tests (dont `tests/test_registre.py`, qui vérifie le registre) et résumé « Contribution »
  (contribution extérieure ? fichiers de code ou de workflows touchés ?). Aucun workflow en `pull_request_target`.
- **Réglages GitHub à faire par Mahdi** (pas scriptables) :
  - [x] Settings → Actions → General → « Approval for running fork pull request workflows » :
        **Require approval for all external contributors**.
  - [x] Settings → Actions → General → « Workflow permissions » : **Read repository contents** par défaut
        (les workflows qui écrivent le demandent déjà eux-mêmes).
  - [ ] Settings → Rules → règle sur `main` : PR obligatoire avec relecture des Code Owners, vérification « Tests »
        obligatoire, avec Mahdi et GitHub Actions dans la liste de contournement (les scrapers poussent sur `main`).
        Facultatif : seul Mahdi peut fusionner, ce qui protège déjà de l'extérieur.
  - [ ] En cas de vague de spam : Settings → Moderation → **Interaction limits** (24 h à 6 mois).
- [ ] Formulaire sans compte GitHub : seulement avec un captcha (Cloudflare Turnstile, gratuit) et un relais
      (ex. Formspree, Google Form) ; tant que tout passe par GitHub, le compte sert de protection.
- Décision (2 nov. 2026) : les propositions de sources par IA restent **à la demande** (conversation avec Claude, validation par Mahdi) ;
  pas de workflow hebdomadaire ni de clé d'API payante pour l'instant.
- [ ] Traiter automatiquement une issue « source » validée (étiquette `valide`) comme pour les événements.

## À faire

- [ ] Référencement : déclarer le site dans Google Search Console et Bing Webmaster, puis soumettre `sitemap.xml` (action de Mahdi, #127).

- [x] Cinéma : lire les horaires de chaque séance (fiches film de tunis.events).
- [x] Page Festivals : calendrier annuel (JTC, JCC…) avec statut du programme.
- [x] Institut français : lire le PDF mensuel du programme.
- [x] Grand écran : filtres en colonne fixe à gauche, cartes sur 2-3 colonnes avec début de notice,
  fiche ouverte dans un panneau à droite sans changer de page (le téléphone garde une colonne).
- [x] Données : certaines notices contiennent « rn » à la place des retours à la ligne (\r\n mal décodé
  par un scraper, ex. El Teatro « FUITE ») : corrigé dans les textes partagés (`retours_ligne_casses`).
- [ ] Opéra de Tunis : 0 événement. Liste trouvée, mais aucune fiche n'a donné de date reconnue. Dates ISO ajoutées ; à confirmer dans le journal du prochain passage (les fiches rejetées y sont listées avec la raison).
- [ ] Contrôle de santé : ouvrir une alerte (issue GitHub) quand une source tombe en panne.
- [x] Formulaire « Proposer un événement » : **prêt mais masqué** (issue GitHub + étiquette « valide »). À remettre dans le pied de page et la page À propos après les retours des premiers testeurs.
- [ ] Version sans compte GitHub du formulaire.
- [ ] Issues « fiche » : traitées à la main pour l'instant (`_data/artistes.yml`, `_data/types_lieux.yml`, `_data/lieux_alias.yml`) ; à automatiser si elles sont nombreuses.
- [x] Critiques de films : lien Letterboxd à côté d'IMDb (identifiant Wikidata P6127, jamais de lien vide). À faire : AlloCiné.
- [ ] Brancher les sources « à étudier ».
- [ ] Synopsis des films : après le prochain passage des scrapers, compter les films sans synopsis
  (`_data/films.json`, champ `synopsis`). S'il en manque beaucoup, choisir une clé :
  **TMDb** (synopsis riches en français, inscription plus longue, conditions « usage personnel »)
  ou **OMDb** (simple e-mail, synopsis courts en anglais, à brancher dans `scrapers/descriptifs.py`).
  Secret à ajouter : `TMDB_API_KEY` (déjà lu par le workflow) ou `OMDB_API_KEY`.
  Si TMDb : garder la mention obligatoire « ce site utilise l'API TMDb sans être approuvé ni certifié
  par TMDb » (déjà dans `a-propos.md`) et ajouter le logo TMDb à côté.

### Idées (1er novembre 2026)

Sources
- [ ] Comptes Instagram des clubs et bars (scraper `instagram`, recherche avec le workflow « Recherche de sources Instagram »).
- [ ] Suivre les **artistes et DJ** tunisiens sur Instagram plutôt que les lieux : ils annoncent toutes leurs dates.
- [x] Bandsintown et Resident Advisor (tournées, scène électro). RA branché (API GraphQL, zone 196) ; Bandsintown inutile pour Tunis.
- [ ] Agendas de presse (Tunisie Numérique, La Presse) comme filet de sécurité pour repérer des lieux non suivis.
- [ ] Une adresse où les organisateurs envoient leur affiche (e-mail ou formulaire), lue comme les affiches Instagram.
- [ ] Musées et expos : INP, galerie Selma Feriani (voir `bilan-sources/musees-expos.md`).
- [ ] Ambassades et centres culturels étrangers (Italie, Espagne, Japon, Corée…) : projections et concerts souvent gratuits.
- [ ] Clubs étudiants et ciné-clubs universitaires (ENS, ISAM, ISAD, Manouba).
- [ ] Associations de la médina (L'Art Rue / Dream City) et festivals de quartier.
- [x] Calendrier spécial des soirées de Ramadan.

Usage
- [x] Page « Ce week-end » (`week-end.html`).
- [ ] Newsletter du jeudi générée depuis la page « Ce week-end ». Reportée : Buttondown proposé (gratuit jusqu'à 100 abonnés), il faudra le secret BUTTONDOWN_API_KEY.
- [x] Filtres « gratuit » et « en famille ».
- [x] Carte des lieux (OpenStreetMap).
- [x] Carte : placer à la main (lat/lon) les lieux que Nominatim ne trouve pas (valeur null dans `_data/geo.json`).
- [x] Bouton « ajouter à mon agenda » par événement (.ics).
- [ ] Chaîne Telegram ou WhatsApp des événements du jour. Reportée : bot @BotFather + secrets TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID ; WhatsApp sans API, texte à copier-coller.
- [x] Site installable comme une appli (PWA, hors ligne, sans store). Complété : icônes maskable, méta iOS, page hors ligne, encart « Installer l’application » (a-propos), test `tests/test_pwa.py`.
- [x] Favoris sans compte, gardés dans le téléphone.
- [x] Image prête à partager (WhatsApp, story) pour chaque événement.
- [x] Liste « Nouveau cette semaine ».

- [x] Barre de recherche (artiste, lieu, film) sur l'accueil.
- [x] Filtre par moment : ce soir, cet après-midi, en semaine, le week-end.
- [x] Prix : « Gratuit » ou une fourchette lus dans les légendes et la presse, case « seulement gratuits ». À faire : lire le prix sur la page de chaque événement.
- [x] Presse : dates collées ou abrégées (« jusqu'au27nov. »), nom de l'événement cité dans le texte plutôt que le lieu du titre, catégorie lue dans le texte ; un article qui recoupe un événement officiel (même lieu, dates qui se chevauchent, titre proche) est masqué et lié dans la section « Dans la presse » de la fiche.
- [x] Presse : un article d'un journal (genre « presse ») ne devient jamais une entrée « Autre » ni sans lieu : il faut une catégorie reconnue et un lieu précis. Sinon il est gardé dans `_data/presse.json` et rattaché à la manifestation officielle qui recoupe ses dates et son titre (section « Dans la presse »). Un article sur un festival ou une manifestation multi-jours (Jaou Tunis, Saisons de la création…) devient une entrée de festival (champ `festival`, catégorie de sa discipline, « spectacle » à défaut), listée sur la page Festivals (« Repérés dans la presse »). À faire : page « Presse » listant les articles non rattachés.
- [x] Presse : le lieu est d'abord cherché parmi les lieux du registre (`_data/lieux.json`) cités dans le corps de l'article (« la salle du Quatrième Art » → Théâtre Le 4ème Art), avant les expressions « à la/au… ».
- [x] Fiche lieu : adresse, carte, liens et tous ses événements à venir.
- [x] Fiche artiste ou collectif : ses dates à venir (aide les petits à être visibles).
- [x] Page Santé des sources (`/sante/`) : état, nombre d'événements, dernière nouveauté, sources silencieuses (rien depuis 30 jours), en panne, en pause.
- [x] Affichage léger pour les petits forfaits mobiles (images à la demande). Le mode sombre suit déjà le réglage du téléphone.
- [x] Choix de la ville (Grand Tunis par défaut) et lien carte 📍 des lieux.

Ouverture
- [x] API publique documentée (JSON des événements) pour médias, applis, chercheurs.
- [x] Langue de l'événement (français, arabe, anglais, VO sous-titrée) : étiquette sur les cartes et les fiches.
- [ ] Accessibilité des lieux (fauteuil) : basse priorité, difficile à collecter.

Présentation (demandé le 1er novembre)
- [x] Récupérer les **notices et visuels** de chaque événement : texte et image de la page d'origine (balises `og:description` / `og:image`, champ `description` du schema.org), affiche Instagram déjà enregistrée.
- [ ] Fiche artiste : photo et courte bio depuis Wikidata / Wikipédia (licence libre), lien Instagram.
- [ ] Image des lieux depuis Wikimedia Commons (Théâtre municipal, Cité de la culture…).
- [x] Billets : afficher « Complet » ou « Gratuit » quand la billetterie le dit (`offers.availability`, prix 0).
- [ ] Catégories : affiner au fil des remarques (règles par mots du titre dans `commun.categorie_du_titre`).

Couverture et langues (demandé le 1er novembre)
- [ ] À terme, **toute la Tunisie** : on garde tous les événements (la Manouba, Carthage…) avec leur lieu réel ; plus tard, un filtre par ville ou gouvernorat. Le filtre « hors Grand Tunis » de tunis.events sera alors retiré.
- [x] Site **multilingue** : français, arabe (sens de lecture droite-gauche), peut-être anglais. Textes de l'interface dans `_data/fr.yml` → un fichier par langue. Fait pour l'interface (`_data/i18n.yml`) ; les titres restent dans la langue de la source.

- [ ] Événements commerciaux (yoga, fitness, brunchs…) : pour l'instant **gardés en bas de liste et en plus discret** (`commun.est_discret`). Décider plus tard s'il faut une rubrique à part ou les retirer.

Fiabilité
- [x] Alerte quand une source n'a rien publié depuis 30 jours (lieu fermé, compte changé).
- [x] Bouton « signaler une erreur » sur chaque événement.

- [ ] Délégations régionales de la culture : leurs sites cultureregions-*.gov.tn ne répondent pas depuis GitHub (en pause). 8 pages Facebook branchées ; trouver les 16 autres.
- [x] FTCC (ciné-clubs) : page Facebook FTCCTunisie, plus le Ciné-club de Tunis et la FTCA sur Instagram.
- [ ] Formulaire sans compte GitHub : renseigner `contact_email` dans `_config.yml`.

- [ ] L'Agora Djerba : vérifier au premier passage que `www.lagoradjerba.tn` expose bien l'API WooCommerce (`/wp-json/wc/store/v1/products`, attribut « Séances ») ; sinon écrire un lecteur dédié (le site n'était pas joignable depuis l'environnement de développement).

Comprendre sans cliquer (demandé le 2 novembre)
- [x] Aperçu au survol (ordinateur) et bouton 👁 en feuille du bas (téléphone) : affiche, heure, lieu, prix, notice.
- [x] « Ce soir à Tunis » en tête de l'accueil : événements du jour classés par heure, avec « dans 40 min ».
- [x] Heure de début en évidence sous la date de chaque carte.
- [ ] Heure de fin et durée : aucune source ne la donne pour l'instant (seulement les films). À chercher dans les scrapers (schema.org `endDate`).
- [ ] Frise horaire de la soirée, « Ma soirée » (favoris en plan avec chevauchements), « autour de ce lieu », sélection éditoriale, regroupement par quartier.

Entrées « Autre » à réduire (relevé du 2 novembre) : une entrée « Autre » devrait rester rare.
- [ ] `ift-pdf` en produit 19 (programme PDF de l'Institut français : trouver la vraie catégorie dans le texte), puis `tunis-events` et `ig-lart-rue` (3 chacun), les sources de presse et `fb-cr-sidibouzid` (2 chacune).
- [x] Annonces hors culture (santé, prévention, caritatif…) : mots-clés dans `_data/hors_culture.yml`, appliqués à toutes les sources sur le titre.

## Téléphone : suite de l'audit d'ergonomie (3 nov. 2026)
- [x] Vues rapides « Ce soir / Demain / Ce week-end » avec compteurs, et bande de dates défilante collée en haut (téléphone seulement).
- [x] Filtre « Quartier » (liste déroulante du tiroir), rangé d'après le lieu et l'adresse (`_data/quartiers.yml`).
- [x] Formulaire « Proposer » : lien, titre, date d'abord ; le reste sous « Plus de détails » sur téléphone.
- [ ] Tri par distance (géolocalisation demandée au clic) ; alléger la page d'accueil (30 premiers jours puis « Voir la suite »).
- [ ] Contribution : lire titre et date depuis le lien collé.
