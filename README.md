# Agenda culturel Tunis

Un agenda simple des événements culturels à Tunis (concerts, cinéma, théâtre, expos…),
publié avec GitHub Pages : https://benjello.github.io/agenda-culturel-tunis/

## Ajouter un événement

Chaque événement est un petit fichier Markdown dans le dossier [`_events/`](_events/).

1. Sur GitHub, ouvrez le dossier `_events/` puis cliquez sur **Add file → Create new file**.
2. Nommez le fichier `AAAA-MM-JJ-nom-court.md`, par exemple `2026-11-07-concert-oud.md`.
3. Copiez ce modèle et remplissez-le :

```markdown
---
title: "Titre de l'événement"
date: 2026-11-07 20:30        # date et heure de début (AAAA-MM-JJ HH:MM)
end_date: 2026-11-30          # facultatif : date de fin (expos, festivals…)
venue: "Nom du lieu"
address: "Adresse, Tunis"     # facultatif
category: musique             # voir la liste ci-dessous
price: "20 DT"                # facultatif
link: "https://…"             # page d'origine : Facebook, site du lieu, billetterie…
---
Une courte description de l'événement (facultatif).
```

4. Cliquez sur **Commit changes**. Le site se met à jour en une ou deux minutes.

**Catégories disponibles** : `cinema`, `musique`, `theatre`, `expo`, `danse`,
`litterature`, `conference`, `autre`. Pour en ajouter une, modifiez
[`_data/categories.yml`](_data/categories.yml).

Les événements passés disparaissent automatiquement de la page d'accueil. Pas besoin de les supprimer.

Pensez d'abord à vérifier si le lieu peut devenir une **source** (voir plus bas) : c'est plus durable qu'une saisie à la main.

## Sources et scrapers (automatique)

L'agenda se remplit surtout tout seul : des **scrapers** relisent chaque jour des
**sources fiables** (sites de lieux, billetteries) et chaque événement renvoie vers sa source.

- La liste des sources est dans [`_data/sources.yml`](_data/sources.yml), visible sur la page
  [Sources](https://benjello.github.io/agenda-culturel-tunis/sources/) avec l'état de chacune.
- Chaque source indique quel scraper la lit (dossier [`scrapers/sources/`](scrapers/sources/)).
  Une source qui publie ses événements en schema.org s'ajoute avec `scraper: jsonld`, sans code.
- Les événements récupérés sont écrits en Markdown dans `_events/auto/<source>/`, comme ceux
  saisis à la main. Ne pas les modifier : le dossier est réécrit à chaque passage.
- Les films à l'affiche vont dans `_data/cinemas/`, affichés par la page Cinéma.
- L'état de chaque source (dernier passage, succès, erreur) est noté dans `_data/etat_sources.json`.
- Si une source tombe en panne, ses événements déjà récupérés restent en place.

### Lancer les scrapers

Sur GitHub : chaque jour à 6h, ou **Actions → Scrapers → Run workflow**.

Sur un ordinateur ou un serveur (par exemple dans un cron) :

```bash
pip install -r requirements.txt
python3 -m scrapers              # toutes les sources actives
python3 -m scrapers teskerti     # une seule source
python3 -m scrapers --debug      # garde les pages téléchargées dans debug/
git add _events/auto _data/cinemas _data/etat_sources.json && git commit -m "Scrapers" && git push
```

Exemple de ligne cron (tous les jours à 6h) :
`0 6 * * * cd ~/agenda-culturel-tunis && git pull -q && python3 -m scrapers && git add -A _events/auto _data && git commit -qm Scrapers && git push -q`

Certains sites (pathe.tn par exemple) refusent les requêtes venant des serveurs de GitHub.
Ces sources marchent mieux depuis un cron sur une machine ordinaire.

### Tests

`python3 -m unittest discover tests` vérifie les scrapers sur des pages d'exemple (`tests/fixtures/`).

## Organisation du dépôt

| Dossier / fichier | Rôle |
|---|---|
| `_events/` | un fichier par événement |
| `_events/auto/` | événements récupérés par les scrapers (généré) |
| `_data/sources.yml` | registre des sources |
| `_data/cinemas/`, `_data/etat_sources.json` | films à l'affiche et état des sources (générés) |
| `scrapers/` | les scrapers (Python) |
| `tests/` | tests des scrapers |
| `_data/categories.yml` | catégories (nom affiché, couleur) |
| `_data/fr.yml` | noms des jours et des mois en français |
| `_layouts/`, `_includes/` | gabarits HTML des pages |
| `assets/style.css` | apparence du site |
| `index.html` | page d'accueil (l'agenda) |
| `a-propos.md` | page « À propos » |

## Voir le site sur son ordinateur (facultatif)

```bash
bundle install
bundle exec jekyll serve
```

Puis ouvrez http://localhost:4000/agenda-culturel-tunis/

## Prochaines étapes

- Formulaire de contribution (issue GitHub préremplie, ou Google Form) pour signaler un événement.
- Autres sources : Goethe-Institut (flux RSS), Institut français…
- Contrôle de santé : alerte automatique quand une source meurt.
- Formulaire « Proposer une source ».
- Pages Facebook : saisie via le formulaire en attendant mieux.
