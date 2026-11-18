// node --test worker/
import test from "node:test";
import assert from "node:assert/strict";
import { lire, dateIso } from "./lecture.js";
import { construire, nettoyer, lienValide, Erreur } from "./index.js";

test("JSON-LD : titre, date, heure, lieu", () => {
  const html = `<script type="application/ld+json">{"@type":"MusicEvent","name":"Concert de oud &amp; nay",
    "startDate":"2026-11-20T19:30:00+01:00","endDate":"2026-11-20T22:00:00+01:00",
    "location":{"@type":"Place","name":"Dar Lasram","address":{"streetAddress":"Médina de Tunis"}}}</script>`;
  const r = lire(html);
  assert.deepEqual([r.titre, r.jour, r.heure, r.fin, r.lieu],
    ["Concert de oud & nay", "2026-11-20", "19:30", "", "Dar Lasram, Médina de Tunis"]);
});

test("Open Graph et titre Facebook sans date", () => {
  const r = lire(`<meta property="og:title" content="Soirée jazz | Facebook"><meta property="og:image" content="https://x.tn/a.jpg">`);
  assert.equal(r.titre, "Soirée jazz");
  assert.equal(r.jour, "");
  assert.equal(r.image, "https://x.tn/a.jpg");
});

test("balise time et <title>", () => {
  const r = lire(`<title>Expo Medina</title><time datetime="2026-12-02">2 déc.</time>`);
  assert.deepEqual([r.titre, r.jour, r.heure], ["Expo Medina", "2026-12-02", ""]);
});

test("dates absurdes refusées", () => {
  assert.equal(dateIso("2026-13-40"), null);
  assert.equal(lire("<html></html>").titre, "");
});

test("construire une issue d'événement", () => {
  const p = construire({ type: "evenement", titre: "Concert @mahdi", jour: "2026-11-20", heure: "20:00",
    lien: "https://facebook.com/events/1", categorie: "Musique", description: "<b>x</b>" });
  assert.deepEqual(p.etiquettes, ["proposition", "sans-compte"]);
  assert.match(p.corps, /### Date et heure\n\n2026-11-20 20:00/);
  assert.match(p.corps, /### Titre\n\nConcert @​mahdi/);
  assert.doesNotMatch(p.corps, /<b>/);
});

test("construire une issue de source", () => {
  const p = construire({ type: "source", nom: "Dar Lasram", lien: "https://instagram.com/darlasram" });
  assert.deepEqual(p.etiquettes, ["source", "sans-compte"]);
  assert.match(p.corps, /### Adresse de la page\n\nhttps:\/\/instagram.com\/darlasram/);
});

test("entrées refusées", () => {
  assert.throws(() => construire({ type: "evenement", titre: "x", jour: "demain", lien: "https://a.tn" }), Erreur);
  assert.throws(() => construire({ type: "evenement", titre: "x", jour: "2026-11-20", lien: "javascript:alert(1)" }), Erreur);
  assert.throws(() => construire({ type: "source", nom: "", lien: "https://a.tn" }), Erreur);
  assert.equal(lienValide("ftp://a.tn"), false);
  assert.equal(nettoyer("a".repeat(500), 10).length, 10);
});
