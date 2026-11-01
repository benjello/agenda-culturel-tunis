// Agenda culturel Tunis : ce qui marche sur toutes les pages.
// Langue, thème, affichage léger, favoris, « ajouter à mon agenda », partage, appli installable.
(function () {
  var d = document.documentElement;
  var I18N = window.I18N || {};
  function lire(cle, defaut) { try { return localStorage.getItem(cle) || defaut; } catch (e) { return defaut; } }
  function ecrire(cle, v) { try { localStorage.setItem(cle, v); } catch (e) {} }
  function iso(dt) { return dt.getFullYear() + '-' + ('0' + (dt.getMonth() + 1)).slice(-2) + '-' + ('0' + dt.getDate()).slice(-2); }
  function jour(decalage) { var x = new Date(); x.setDate(x.getDate() + (decalage || 0)); return iso(x); }

  // ---- Langue : français dans les pages, arabe et anglais par le dictionnaire _data/i18n.yml
  var langue = lire('langue', 'fr');
  var LOCALE = { fr: 'fr-FR', ar: 'ar-TN', en: 'en-GB' };
  function t(cle, defaut) {
    var e = I18N[cle];
    return (e && e[langue]) || (langue === 'fr' && e && e.fr) || defaut;
  }
  window.t = t;
  function traduire() {
    d.lang = langue; d.dir = langue === 'ar' ? 'rtl' : 'ltr';
    document.querySelectorAll('[data-t]').forEach(function (el) {
      if (el._fr === undefined) el._fr = el.textContent;
      el.textContent = langue === 'fr' ? el._fr : t(el.dataset.t, el._fr);
    });
    document.querySelectorAll('[data-t-title]').forEach(function (el) {
      var v = t(el.dataset.tTitle, el.title); el.title = v; el.setAttribute('aria-label', v);
    });
    document.querySelectorAll('[data-t-placeholder]').forEach(function (el) {
      el.placeholder = t(el.dataset.tPlaceholder, el.placeholder);
    });
    var loc = LOCALE[langue];
    document.querySelectorAll('time[datetime]').forEach(function (el) {
      if (el._fr === undefined) el._fr = el.textContent;
      if (langue === 'fr') { el.textContent = el._fr; return; }
      var v = el.getAttribute('datetime'), heure = v.length > 10;
      var x = new Date(v.length > 10 ? v : v + 'T12:00:00');
      var o = { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' };
      if (heure) { o.hour = '2-digit'; o.minute = '2-digit'; }
      el.textContent = x.toLocaleString(loc, o);
    });
    document.querySelectorAll('[data-mc]').forEach(function (el) {
      if (el._fr === undefined) el._fr = el.textContent;
      el.textContent = langue === 'fr' ? el._fr : new Date(2026, +el.dataset.mc - 1, 15).toLocaleString(loc, { month: 'short' });
    });
    document.querySelectorAll('[data-mois]').forEach(function (el) {
      if (el._fr === undefined) el._fr = el.textContent;
      var p = el.dataset.mois.split('-');
      el.textContent = langue === 'fr' ? el._fr : new Date(+p[0], +p[1] - 1, 15).toLocaleString(loc, { month: 'long', year: 'numeric' });
    });
    document.querySelectorAll('[data-langue]').forEach(function (b) { b.classList.toggle('active', b.dataset.langue === langue); });
    document.dispatchEvent(new CustomEvent('langue', { detail: langue }));
  }
  document.querySelectorAll('[data-langue]').forEach(function (b) {
    b.addEventListener('click', function () { langue = b.dataset.langue; ecrire('langue', langue); traduire(); });
  });

  // ---- Thème sombre ou clair (par défaut : celui du téléphone) et affichage léger
  var bt = document.getElementById('bouton-theme');
  if (bt) bt.addEventListener('click', function () {
    var sombre = d.dataset.theme ? d.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
    d.dataset.theme = sombre ? 'light' : 'dark';
    ecrire('theme', d.dataset.theme);
  });
  var bl = document.getElementById('bouton-leger');
  function marquerLeger() { if (bl) bl.classList.toggle('active', d.classList.contains('leger')); }
  if (bl) bl.addEventListener('click', function () {
    d.classList.toggle('leger');
    ecrire('leger', d.classList.contains('leger') ? '1' : '0');
    marquerLeger();
  });
  marquerLeger();
  // Affichage léger : les images ne sont pas téléchargées du tout.
  if (d.classList.contains('leger')) document.querySelectorAll('.vignette img, img.affiche-grande').forEach(function (i) { i.removeAttribute('src'); });

  // ---- Android : liens de carte vers l'appli du téléphone
  if (/Android/i.test(navigator.userAgent)) {
    document.querySelectorAll('a.carte[data-q]').forEach(function (a) { a.href = 'geo:0,0?q=' + encodeURIComponent(a.dataset.q); });
  }

  // ---- Listes des fiches (lieu, artiste, nouveautés) : masquer ce qui est passé
  var auj = jour(), ilya7 = jour(-7);
  document.querySelectorAll('[data-masquer-passes]').forEach(function (liste) {
    var nouveaux = liste.hasAttribute('data-nouveaux'), n = 0;
    liste.querySelectorAll('.event').forEach(function (el) {
      var ok = el.dataset.date >= auj && (!nouveaux || (el.dataset.ajoute || '') >= ilya7);
      el.hidden = !ok; if (ok) n++;
    });
    var vide = liste.parentNode.querySelector('[data-vide]');
    if (vide) vide.hidden = n > 0;
  });

  // ---- Favoris, gardés dans le navigateur (sans compte)
  var favoris = [];
  try { favoris = JSON.parse(lire('favoris', '[]')); } catch (e) {}
  window.lireFavoris = function () { return favoris; };
  function marquerFavoris() {
    document.querySelectorAll('.fav').forEach(function (b) {
      var c = b.closest('[data-id]'), on = c && favoris.indexOf(c.dataset.id) >= 0;
      b.classList.toggle('on', !!on); b.textContent = on ? '★' : '☆';
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
  }
  marquerFavoris();

  // ---- « Ajouter à mon agenda » : un fichier .ics que le téléphone ouvre dans son calendrier
  function utc(dateIso, heure, decalageH) {
    var p = dateIso.split('-'), h = heure ? heure.split(':') : [0, 0];
    // Tunis : UTC+1 toute l'année
    var x = new Date(Date.UTC(+p[0], +p[1] - 1, +p[2], +h[0] - 1 + (decalageH || 0), +h[1]));
    return x.toISOString().replace(/[-:]/g, '').slice(0, 15) + 'Z';
  }
  function echapper(s) { return (s || '').replace(/\\/g, '\\\\').replace(/[,;]/g, '\\$&').replace(/\n/g, '\\n'); }
  function ics(c) {
    var debut = c.dataset.debut, fin = c.dataset.date || debut, h = c.dataset.heure, l = [];
    l.push('BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Agenda culturel Tunis//FR', 'BEGIN:VEVENT');
    l.push('UID:' + c.dataset.id.replace(/\W+/g, '-') + '@agenda-culturel-tunis');
    l.push('DTSTAMP:' + new Date().toISOString().replace(/[-:]/g, '').slice(0, 15) + 'Z');
    if (h && fin === debut) {
      l.push('DTSTART:' + utc(debut, h), 'DTEND:' + utc(debut, h, 2));
    } else {
      var f = new Date(fin + 'T12:00:00'); f.setDate(f.getDate() + 1);
      l.push('DTSTART;VALUE=DATE:' + debut.replace(/-/g, ''), 'DTEND;VALUE=DATE:' + iso(f).replace(/-/g, ''));
    }
    l.push('SUMMARY:' + echapper(c.dataset.titre), 'LOCATION:' + echapper(c.dataset.lieu),
      'URL:' + c.dataset.lien, 'DESCRIPTION:' + echapper(c.dataset.lien), 'END:VEVENT', 'END:VCALENDAR');
    return l.join('\r\n');
  }
  function telecharger(blob, nom) {
    var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = nom;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 5000);
  }

  // ---- Partage : image au format story (1080×1920) et lien
  function lignes(ctx, texte, largeur) {
    var mots = texte.split(/\s+/), res = [], l = '';
    mots.forEach(function (m) {
      var essai = l ? l + ' ' + m : m;
      if (ctx.measureText(essai).width > largeur && l) { res.push(l); l = m; } else l = essai;
    });
    if (l) res.push(l);
    return res;
  }
  function quand(c) {
    var tm = c.querySelector('time');
    return tm ? tm.textContent.trim() : c.dataset.debut;
  }
  function image(c) {
    return new Promise(function (ok, ko) {
      var W = 1080, H = 1920, cv = document.createElement('canvas'); cv.width = W; cv.height = H;
      var x = cv.getContext('2d'), coul = c.dataset.couleur || '#b5442f';
      x.fillStyle = coul; x.fillRect(0, 0, W, H);
      x.fillStyle = 'rgba(0,0,0,.45)'; x.fillRect(0, 0, W, H);
      var ar = /[\u0600-\u06FF]/.test(c.dataset.titre);
      x.font = '700 38px system-ui, sans-serif';
      var cat = (c.dataset.categorie || '').toUpperCase(), lc = x.measureText(cat).width + 48;
      x.fillStyle = '#fff'; x.fillRect(80, 360, lc, 64);
      x.fillStyle = coul; x.fillText(cat, 104, 406);
      x.direction = ar ? 'rtl' : 'ltr'; x.textAlign = ar ? 'right' : 'left';
      var gauche = ar ? W - 80 : 80;
      x.fillStyle = '#fff';
      x.font = '800 92px system-ui, sans-serif';
      var y = 560;
      lignes(x, c.dataset.titre, W - 160).slice(0, 7).forEach(function (l) { x.fillText(l, gauche, y); y += 108; });
      y += 40; x.fillStyle = '#ffe2a8'; x.font = '700 52px system-ui, sans-serif';
      lignes(x, quand(c), W - 160).forEach(function (l) { x.fillText(l, gauche, y); y += 66; });
      y += 20; x.fillStyle = '#ddd'; x.font = '500 46px system-ui, sans-serif';
      lignes(x, '📍 ' + (c.dataset.lieu || ''), W - 160).slice(0, 4).forEach(function (l) { x.fillText(l, gauche, y); y += 60; });
      x.direction = 'ltr'; x.textAlign = 'left';
      x.fillStyle = '#fff'; x.font = '700 44px system-ui, sans-serif'; x.fillText('Agenda culturel Tunis', 80, H - 170);
      x.fillStyle = '#eee'; x.font = '400 34px system-ui, sans-serif';
      x.fillText(location.host + (window.BASE || '/'), 80, H - 110);
      cv.toBlob(function (b) { b ? ok(b) : ko(new Error('image')); }, 'image/png');
    });
  }
  function menu(c, blob) {
    var texte = c.dataset.titre + ' · ' + quand(c) + '\n' + c.dataset.lien;
    var m = document.createElement('div'); m.className = 'menu-partage'; m.setAttribute('role', 'dialog');
    function bouton(etiquette, f) { var b = document.createElement('button'); b.type = 'button'; b.textContent = etiquette; b.onclick = f; m.appendChild(b); return b; }
    var wa = document.createElement('a'); wa.href = 'https://wa.me/?text=' + encodeURIComponent(texte); wa.rel = 'noopener'; wa.target = '_blank'; wa.textContent = 'WhatsApp'; m.appendChild(wa);
    var tg = document.createElement('a'); tg.href = 'https://t.me/share/url?url=' + encodeURIComponent(c.dataset.lien) + '&text=' + encodeURIComponent(c.dataset.titre); tg.rel = 'noopener'; tg.target = '_blank'; tg.textContent = 'Telegram'; m.appendChild(tg);
    var fb = document.createElement('a'); fb.href = 'https://www.facebook.com/sharer/sharer.php?u=' + encodeURIComponent(c.dataset.lien); fb.rel = 'noopener'; fb.target = '_blank'; fb.textContent = 'Facebook'; m.appendChild(fb);
    var cp = bouton(t('copier', 'Copier le lien'), function () {
      (navigator.clipboard ? navigator.clipboard.writeText(c.dataset.lien) : Promise.reject()).then(function () { cp.textContent = t('copie', 'Lien copié'); }, function () {});
    });
    if (blob) bouton(t('image', "Télécharger l'image"), function () { telecharger(blob, 'agenda-tunis.png'); });
    bouton(t('fermer', 'Fermer'), function () { m.remove(); });
    document.querySelectorAll('.menu-partage').forEach(function (x) { x.remove(); });
    document.body.appendChild(m);
  }
  function partager(c) {
    var texte = c.dataset.titre + ' · ' + quand(c) + ' · ' + (c.dataset.lieu || '');
    image(c).then(function (blob) {
      var f = new File([blob], 'agenda-tunis.png', { type: 'image/png' });
      if (navigator.canShare && navigator.canShare({ files: [f] })) {
        return navigator.share({ files: [f], title: c.dataset.titre, text: texte + '\n' + c.dataset.lien }).catch(function (e) {
          if (e.name !== 'AbortError') menu(c, blob);
        });
      }
      if (navigator.share) {
        return navigator.share({ title: c.dataset.titre, text: texte, url: c.dataset.lien }).catch(function (e) {
          if (e.name !== 'AbortError') menu(c, blob);
        });
      }
      menu(c, blob);
    }, function () { menu(c, null); });
  }

  document.addEventListener('click', function (ev) {
    var b = ev.target.closest('.fav, .ajout-agenda, .partager');
    if (!b) return;
    var c = b.closest('[data-id]');
    if (!c) return;
    ev.preventDefault();
    if (b.classList.contains('fav')) {
      var i = favoris.indexOf(c.dataset.id);
      if (i >= 0) favoris.splice(i, 1); else favoris.push(c.dataset.id);
      ecrire('favoris', JSON.stringify(favoris));
      marquerFavoris();
      document.dispatchEvent(new CustomEvent('favoris'));
    } else if (b.classList.contains('ajout-agenda')) {
      telecharger(new Blob([ics(c)], { type: 'text/calendar;charset=utf-8' }), 'evenement.ics');
    } else {
      partager(c);
    }
  });

  if (langue !== 'fr') traduire(); else document.querySelectorAll('[data-langue="fr"]').forEach(function (b) { b.classList.add('active'); });

  // ---- Appli installable : le service worker garde les pages pour les consulter hors connexion
  if ('serviceWorker' in navigator && location.protocol === 'https:') {
    navigator.serviceWorker.register((window.BASE || '/') + 'sw.js').catch(function () {});
  }
})();
