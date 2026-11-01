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

## Organisation du dépôt

| Dossier / fichier | Rôle |
|---|---|
| `_events/` | un fichier par événement |
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
- Récupération automatique des programmes des cinémas.
- Pages Facebook : saisie via le formulaire en attendant mieux.
