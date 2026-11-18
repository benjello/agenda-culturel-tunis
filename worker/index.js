// Relais de contribution : reçoit une proposition depuis le site (sans compte GitHub), vérifie le
// captcha Cloudflare Turnstile, puis ouvre une issue dans le dépôt. L'équipe la valide ensuite avec
// l'étiquette « valide » (workflows « Proposition validée » et « Source validée »).
// Deux routes :
//   POST /proposer : { type: "evenement" | "source", champs…, jeton: <réponse Turnstile> }
//   GET  /lire?url=… : titre, date et lieu lus depuis le lien collé (aucun captcha, rien n'est écrit)
// Secrets (wrangler secret put) : GITHUB_TOKEN, TURNSTILE_SECRET. Variables (wrangler.toml) : DEPOT, ORIGINES.

import { lire } from "./lecture.js";

const MAX_PAGE = 1_500_000; // octets lus d'une page, pas plus
const LIMITES = { titre: 200, jour: 10, heure: 5, fin: 10, lieu: 200, categorie: 60, prix: 80, lien: 500,
  description: 3000, nom: 200, genre: 60, remarque: 1500 };
const CATEGORIES = ["Musique", "Théâtre", "Spectacle", "Danse", "Exposition", "Cinéma", "Conférence", "Littérature", "Autre"];

const reponse = (corps, statut, origine) => new Response(JSON.stringify(corps), {
  status: statut,
  headers: { "content-type": "application/json; charset=utf-8", ...entetesCors(origine) },
});

function entetesCors(origine) {
  return origine ? { "access-control-allow-origin": origine, "access-control-allow-methods": "GET, POST, OPTIONS",
    "access-control-allow-headers": "content-type", vary: "Origin" } : { vary: "Origin" };
}

export function origineAutorisee(requete, env) {
  const origine = requete.headers.get("Origin") ?? "";
  const permises = String(env.ORIGINES ?? "").split(",").map((s) => s.trim()).filter(Boolean);
  return permises.includes(origine) ? origine : "";
}

// Texte d'une proposition : sans retour à la ligne parasite, sans mention @ (pas de notification
// envoyée à un inconnu), sans balise.
export function nettoyer(valeur, max) {
  return String(valeur ?? "").replace(/[<>]/g, "").replace(/@/g, "@​").replace(/\r/g, "").trim().slice(0, max);
}

export function lienValide(texte) {
  try {
    const u = new URL(texte);
    return (u.protocol === "https:" || u.protocol === "http:") && u.hostname.includes(".");
  } catch { return false; }
}

// Le corps de l'issue suit les formulaires .github/ISSUE_TEMPLATE/*.yml : « ### Libellé » puis la valeur,
// pour que scrapers/propositions.py lise la proposition comme une issue remplie sur GitHub.
export function construire(donnees) {
  const c = {};
  for (const [k, max] of Object.entries(LIMITES)) c[k] = nettoyer(donnees[k], max);
  if (!lienValide(c.lien)) throw new Erreur("Le lien n'est pas une adresse valide (https://…).");
  const bloc = (libelle, valeur) => `### ${libelle}\n\n${valeur || "_No response_"}`;
  if (donnees.type === "source") {
    if (!c.nom) throw new Erreur("Il manque le nom du lieu ou de l'organisateur.");
    return { titre: `Source : ${c.nom}`, etiquettes: ["source", "sans-compte"], corps: [
      bloc("Lieu, collectif ou organisateur", c.nom), bloc("Adresse de la page", c.lien),
      bloc("Quelle sorte de page ? (facultatif)", c.genre), bloc("Source recherchée ou à réparer (facultatif)", ""),
      bloc("Remarque (facultatif)", c.remarque), bloc("Vérification", "- [x] La page est publique (on la voit sans se connecter) et annonce des événements culturels."),
    ].join("\n\n") };
  }
  if (!c.titre) throw new Erreur("Il manque le titre.");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(c.jour) || Number.isNaN(Date.parse(c.jour))) throw new Erreur("La date est illisible.");
  if (c.heure && !/^\d{2}:\d{2}$/.test(c.heure)) throw new Erreur("L'heure est illisible.");
  if (c.fin && !/^\d{4}-\d{2}-\d{2}$/.test(c.fin)) c.fin = "";
  const categorie = CATEGORIES.includes(c.categorie) ? c.categorie : "Autre";
  return { titre: `Événement : ${c.titre}`, etiquettes: ["proposition", "sans-compte"], corps: [
    bloc("Titre", c.titre), bloc("Date et heure", c.jour + (c.heure ? ` ${c.heure}` : "")),
    bloc("Date de fin (facultatif)", c.fin), bloc("Lieu", c.lieu || "À préciser (voir le lien)"),
    bloc("Catégorie", categorie), bloc("Prix (facultatif)", c.prix), bloc("Lien", c.lien),
    bloc("Description et affiche (facultatif)", c.description),
  ].join("\n\n") };
}

export class Erreur extends Error {}

async function turnstileValide(jeton, env, ip) {
  if (!jeton) return false;
  const r = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
    method: "POST",
    body: new URLSearchParams({ secret: env.TURNSTILE_SECRET, response: jeton, remoteip: ip ?? "" }),
  });
  return Boolean((await r.json()).success);
}

async function ouvrirIssue(env, proposition) {
  const r = await fetch(`https://api.github.com/repos/${env.DEPOT}/issues`, {
    method: "POST",
    headers: { authorization: `Bearer ${env.GITHUB_TOKEN}`, accept: "application/vnd.github+json",
      "user-agent": "agenda-culturel-relais", "content-type": "application/json" },
    body: JSON.stringify({ title: proposition.titre, body: proposition.corps, labels: proposition.etiquettes }),
  });
  if (!r.ok) throw new Error(`GitHub ${r.status}`);
  return (await r.json()).number;
}

async function lirePage(adresse) {
  if (!lienValide(adresse)) throw new Erreur("Adresse invalide.");
  const r = await fetch(adresse, { redirect: "follow", signal: AbortSignal.timeout(8000),
    headers: { "user-agent": "Mozilla/5.0 (compatible; AgendaCulturelTunis; +https://benjello.github.io/agenda-culturel-tunis/)",
      "accept-language": "fr,ar;q=0.8,en;q=0.5" } });
  const lecteur = r.body.getReader();
  const morceaux = []; let total = 0;
  while (total < MAX_PAGE) {
    const { done, value } = await lecteur.read();
    if (done) break;
    morceaux.push(value); total += value.length;
  }
  await lecteur.cancel().catch(() => {});
  return lire(new TextDecoder().decode(await new Blob(morceaux).arrayBuffer()));
}

export default {
  async fetch(requete, env) {
    const origine = origineAutorisee(requete, env);
    if (requete.method === "OPTIONS") return new Response(null, { status: 204, headers: entetesCors(origine) });
    if (!origine) return reponse({ erreur: "origine refusée" }, 403, "");
    const { pathname, searchParams } = new URL(requete.url);
    try {
      if (requete.method === "GET" && pathname === "/lire") {
        try { return reponse(await lirePage(searchParams.get("url") ?? ""), 200, origine); }
        catch (e) { if (e instanceof Erreur) throw e; return reponse({}, 200, origine); } // page illisible : formulaire vide, sans erreur
      }
      if (requete.method === "POST" && pathname === "/proposer") {
        const donnees = await requete.json();
        if (donnees.piege) return reponse({ ok: true }, 200, origine); // champ caché rempli : un robot, on fait semblant
        if (!(await turnstileValide(donnees.jeton, env, requete.headers.get("CF-Connecting-IP")))) {
          throw new Erreur("Vérification anti-robot échouée : rechargez la page et réessayez.");
        }
        const numero = await ouvrirIssue(env, construire(donnees));
        return reponse({ ok: true, numero }, 200, origine);
      }
      return reponse({ erreur: "introuvable" }, 404, origine);
    } catch (e) {
      if (e instanceof Erreur) return reponse({ erreur: e.message }, 400, origine);
      return reponse({ erreur: "Le service est indisponible, réessayez plus tard." }, 502, origine);
    }
  },
};
