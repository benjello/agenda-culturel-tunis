"""Sonde temporaire : comment l'agenda de l'IFT se charge (à retirer avant la fusion)."""
import json, re, requests
from playwright.sync_api import sync_playwright

BASE = "https://www.institutfrancais-tunisie.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
for u in ["/list-agenda", "/wp-json/", "/wp-json/wp/v2/types", "/agenda", "/feed/"]:
    try:
        r = requests.get(BASE + u, headers={"User-Agent": UA}, timeout=30)
        print("GET", u, r.status_code, r.headers.get("content-type"), len(r.text))
        print("   liens details:", sorted(set(re.findall(r'href="([^"]*detail[^"]*)"', r.text)))[:10])
        print("   scripts:", re.findall(r'<script[^>]+src="([^"]+)"', r.text)[:25])
        if "json" in (r.headers.get("content-type") or ""):
            print("   ", r.text[:1500])
    except Exception as e:
        print("GET", u, "ERREUR", e)

xhr = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(user_agent=UA)
    def rep(resp):
        rq = resp.request
        if rq.resource_type in ("xhr", "fetch") or "api" in rq.url or "json" in (resp.headers.get("content-type") or ""):
            try:
                corps = resp.text()[:3000]
            except Exception as e:
                corps = f"<{e}>"
            xhr.append((rq.method, rq.url, resp.status, rq.post_data, corps))
    pg.on("response", rep)
    pg.goto(BASE + "/list-agenda", wait_until="networkidle", timeout=90000)
    pg.wait_for_timeout(5000)
    html = pg.content()
    liens = pg.eval_on_selector_all("a[href]", "els => els.map(e => [e.href, e.innerText.trim().slice(0,80)])")
    print("\n=== XHR ===")
    for m, u, s, d, c in xhr:
        print(m, s, u, "POST:", (d or "")[:300])
        print("   ", c.replace("\n", " ")[:2500])
    print("\n=== liens après rendu ===")
    for h, t in liens:
        if "agenda" in h.lower() or "event" in h.lower():
            print(h, "|", t)
    fiche = next((h for h, t in liens if "detail" in h.lower()), None)
    print("\n=== fiche", fiche)
    if fiche:
        r = requests.get(fiche, headers={"User-Agent": UA}, timeout=30)
        txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<(script|style).*?</\1>", "", r.text)))
        print("brut:", r.status_code, txt[:2500])
        pg.goto(fiche, wait_until="networkidle", timeout=90000)
        print("rendu:", re.sub(r"\s+", " ", pg.inner_text("body"))[:2500])
    open("ift-rendu.html", "w").write(html)
    b.close()
