# Relais de contribution (sans compte GitHub)

Petit programme Cloudflare Workers (offre gratuite, 100 000 appels par jour) qui permet de proposer un
événement ou une source depuis le site, sans compte GitHub.

```
formulaire du site ──► relais (Worker) ──► issue GitHub ──► étiquette « valide » ──► ajout automatique
   (captcha Turnstile)    vérifie le captcha     étiquettes « proposition » ou « source » + « sans-compte »
```

- `POST /proposer` : vérifie le captcha [Cloudflare Turnstile](https://developers.cloudflare.com/turnstile/) (gratuit),
  nettoie les champs (longueurs, balises, mentions `@`), puis ouvre l'issue avec le même texte que les formulaires
  GitHub : `scrapers/propositions.py` (événements) et `scrapers/propositions_source.py` (sources) la lisent donc pareil.
- `GET /lire?url=…` : lit le titre, la date, l'heure et le lieu du lien collé (schema.org, Open Graph, balise `time`)
  pour préremplir le formulaire. Rien n'est enregistré. Facebook et Instagram ne donnent souvent que le titre.
- Seul le site (`ORIGINES` dans `wrangler.toml`) peut appeler le relais.

## Mise en route (une seule fois, environ 10 minutes)

1. Compte gratuit sur <https://dash.cloudflare.com> ; noter l'identifiant de compte (« Account ID »).
2. **Turnstile** : Turnstile → Add widget, nom de domaine `benjello.github.io`, mode « Managed ».
   Noter la **clé de site** (publique) et la **clé secrète**.
3. **Jeton GitHub** : Settings → Developer settings → Fine-grained tokens, limité au dépôt
   `benjello/agenda-culturel-tunis`, permission *Issues : Read and write* (rien d'autre).
4. **Jeton Cloudflare** : My Profile → API Tokens → modèle « Edit Cloudflare Workers ».
5. Dans le dépôt, Settings → Secrets and variables → Actions, créer : `CLOUDFLARE_API_TOKEN`,
   `CLOUDFLARE_ACCOUNT_ID`, `RELAIS_GITHUB_TOKEN` (jeton de l'étape 3), `TURNSTILE_SECRET` (clé secrète).
6. Actions → « Relais de contribution » → Run workflow : le relais est déployé et affiche son adresse
   (`https://agenda-culturel-relais.<compte>.workers.dev`).
7. Dans `_config.yml`, renseigner `proposition_api` (adresse du relais, sans `/` final) et `turnstile_cle`
   (clé de site). La page Proposer montre alors le bouton « Envoyer » direct et le formulaire « Proposer une source ».

À la main : `cd worker && npx wrangler deploy`, puis `npx wrangler secret put GITHUB_TOKEN` et
`npx wrangler secret put TURNSTILE_SECRET`.

## Après l'envoi

L'issue arrive avec l'étiquette `sans-compte`. Poser l'étiquette **valide** : le workflow « Proposition validée »
(événement) ou « Source validée » (source, ajoutée à `_data/sources.yml`) fait le reste et ferme l'issue.
Spam : fermer l'issue ; en cas de vague, mettre `proposition_api` à `""` dans `_config.yml` coupe le formulaire direct.

## Tests

`node --test worker/lecture.test.js` (hors ligne, lancé par le workflow « Tests »).
