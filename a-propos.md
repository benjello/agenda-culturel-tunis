---
layout: default
title: À propos
permalink: /a-propos/
---

# À propos

Beaucoup d'événements culturels à Tunis ne sont annoncés que sur une page Facebook,
le site d'un cinéma ou une affiche. Cet agenda essaie de les rassembler au même endroit.

Pour l'instant, c'est un agenda entre amis. L'objectif est d'en faire un vrai site public.

## Proposer une source {#proposer}

L'agenda se remplit automatiquement à partir de [sources fiables](../sources/) : sites de lieux,
billetteries, festivals. Le plus utile est de nous signaler **un site qui annonce régulièrement
des événements**, plutôt qu'un événement isolé. Un formulaire de contribution arrive bientôt.

En attendant, si vous connaissez GitHub, vous pouvez ouvrir une issue sur le
[dépôt](https://github.com/benjello/agenda-culturel-tunis) avec l'adresse du site.

## Données ouvertes {#donnees}

Tout ce que contient l'agenda est réutilisable librement :

- **Calendrier** : abonnez-vous à [`agenda.ics`]({{ '/agenda.ics' | relative_url }}) dans Google Agenda,
  Apple Calendrier ou Outlook (« ajouter un calendrier par URL »). Il se met à jour tout seul.
- **JSON** : [`evenements.json`]({{ '/evenements.json' | relative_url }}) liste les événements à venir
  (titre, dates, lieu, catégorie, lien vers la source), pour vos sites, bots ou applis.
- **Registre des sources** et **code des scrapers** : sur le
  [dépôt GitHub](https://github.com/benjello/agenda-culturel-tunis), à réutiliser ou à améliorer.

Les données sont publiées sous licence [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.fr) :
réutilisation libre, y compris commerciale, en citant « Agenda culturel Tunis ».
Chaque événement garde le lien vers sa source d'origine.
