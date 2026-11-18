// Lit le titre, la date et le lieu d'une page d'événement (Facebook, billetterie, site de lieu…).
// Sources, dans l'ordre : schema.org (JSON-LD « Event »), puis balises Open Graph et <title>,
// puis balise <time datetime>. Fonction pure, sans réseau : testée hors ligne (worker/lecture.test.js).

const ENTITES = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " " };

export function decoder(texte) {
  return String(texte ?? "")
    .replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(parseInt(d, 10)))
    .replace(/&([a-z]+);/gi, (m, n) => ENTITES[n.toLowerCase()] ?? m)
    .replace(/\s+/g, " ")
    .trim();
}

function meta(html, nom) {
  for (const balise of html.match(/<meta\b[^>]*>/gi) ?? []) {
    const cle = /(?:property|name)\s*=\s*["']([^"']+)["']/i.exec(balise);
    if (!cle || cle[1].toLowerCase() !== nom) continue;
    const valeur = /content\s*=\s*"([^"]*)"|content\s*=\s*'([^']*)'/i.exec(balise);
    if (valeur) return decoder(valeur[1] ?? valeur[2]);
  }
  return "";
}

function evenementsJsonLd(html) {
  const trouves = [];
  const parcourir = (o) => {
    if (Array.isArray(o)) return o.forEach(parcourir);
    if (!o || typeof o !== "object") return;
    const types = [].concat(o["@type"] ?? []);
    if (types.some((t) => typeof t === "string" && t.endsWith("Event"))) trouves.push(o);
    for (const k of ["@graph", "itemListElement", "item", "subEvent"]) if (k in o) parcourir(o[k]);
  };
  for (const m of html.matchAll(/<script[^>]+application\/ld\+json[^>]*>([\s\S]*?)<\/script>/gi)) {
    try { parcourir(JSON.parse(m[1])); } catch { /* bloc illisible : on passe */ }
  }
  return trouves;
}

// « 2026-11-20T19:30:00+01:00 » → jour et heure telles qu'écrites (pas de conversion de fuseau :
// les sites tunisiens écrivent l'heure locale). Retourne { jour, heure } ou null.
export function dateIso(texte) {
  const m = /(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/.exec(String(texte ?? ""));
  if (!m) return null;
  const mois = Number(m[2]), jour = Number(m[3]);
  if (mois < 1 || mois > 12 || jour < 1 || jour > 31) return null;
  const heure = m[4] && !(m[4] === "00" && m[5] === "00") ? `${m[4]}:${m[5]}` : "";
  return { jour: `${m[1]}-${m[2]}-${m[3]}`, heure };
}

function lieu(l) {
  if (!l) return "";
  const o = Array.isArray(l) ? l[0] : l;
  if (typeof o === "string") return decoder(o);
  const nom = decoder(o.name ?? "");
  const a = o.address;
  const ville = typeof a === "string" ? decoder(a) : decoder(a?.streetAddress ?? a?.addressLocality ?? "");
  return [nom, ville].filter(Boolean).join(", ");
}

export function lire(html) {
  const res = { titre: "", jour: "", heure: "", fin: "", lieu: "", image: "" };
  const ev = evenementsJsonLd(html)[0];
  if (ev) {
    res.titre = decoder(ev.name ?? "");
    const debut = dateIso(ev.startDate);
    if (debut) { res.jour = debut.jour; res.heure = debut.heure; }
    const fin = dateIso(ev.endDate);
    if (fin && fin.jour !== res.jour) res.fin = fin.jour;
    res.lieu = lieu(ev.location);
    const img = Array.isArray(ev.image) ? ev.image[0] : ev.image;
    res.image = typeof img === "string" ? img : img?.url ?? "";
  }
  if (!res.titre) {
    res.titre = meta(html, "og:title") || meta(html, "twitter:title")
      || decoder((/<title[^>]*>([\s\S]*?)<\/title>/i.exec(html) ?? [])[1] ?? "");
  }
  if (!res.jour) {
    const d = dateIso(meta(html, "event:start_time"));
    const t = d ?? dateIso((/<time[^>]+datetime\s*=\s*["']([^"']+)["']/i.exec(html) ?? [])[1]);
    if (t) { res.jour = t.jour; res.heure = t.heure; }
  }
  if (!res.image) res.image = meta(html, "og:image");
  // « Titre | Nom du site » ou « Titre - Facebook » : on garde le titre seul
  res.titre = res.titre.replace(/\s*[|–—-]\s*(Facebook|Instagram|Eventbrite|Billetterie)\s*$/i, "").slice(0, 200);
  return res;
}
