---
layout: null
permalink: /sw.js
---
// Service worker : le site s'ouvre comme une appli, et reste lisible sans connexion.
// Pages : réseau d'abord (l'agenda change chaque jour), copie gardée en secours.
// Style, script, icônes : copie gardée, mise à jour en arrière-plan.
var VERSION = 'agenda-{{ site.time | date: "%Y%m%d%H%M" }}';
var BASE = '{{ "/" | relative_url }}';
var DE_BASE = [BASE, BASE + 'week-end/', BASE + 'assets/style.css', BASE + 'assets/site.js', BASE + 'assets/icones/icone-192.png'];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(VERSION).then(function (c) { return c.addAll(DE_BASE); }).then(function () { return self.skipWaiting(); }));
});
self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (cles) {
    return Promise.all(cles.filter(function (k) { return k !== VERSION; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});
self.addEventListener('fetch', function (e) {
  var r = e.request, u = new URL(r.url);
  if (r.method !== 'GET' || u.origin !== location.origin || u.pathname.indexOf(BASE) !== 0) return;
  if (r.mode === 'navigate') {
    e.respondWith(fetch(r).then(function (rep) {
      var copie = rep.clone();
      caches.open(VERSION).then(function (c) { c.put(r, copie); });
      return rep;
    }).catch(function () {
      return caches.match(r).then(function (m) { return m || caches.match(BASE); });
    }));
    return;
  }
  e.respondWith(caches.match(r).then(function (m) {
    var reseau = fetch(r).then(function (rep) {
      if (rep.ok) { var copie = rep.clone(); caches.open(VERSION).then(function (c) { c.put(r, copie); }); }
      return rep;
    }).catch(function () { return m; });
    return m || reseau;
  }));
});
