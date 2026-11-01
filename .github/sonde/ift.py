"""Sonde temporaire : en-têtes et contenu de l'API de l'agenda de l'IFT (à retirer avant la fusion)."""
import json, re, requests
from playwright.sync_api import sync_playwright
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
appels = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(user_agent=UA)
    def rep(resp):
        if "aec.app/api" in resp.url or "extranet-aec.com/api" in resp.url:
            try:
                d = resp.json()
            except Exception:
                d = None
            appels.append((resp.request.method, resp.url, resp.status, resp.request.all_headers(), d))
    pg.on("response", rep)
    pg.goto("https://www.institutfrancais-tunisie.com/list-agenda", wait_until="networkidle", timeout=90000)
    for i in range(6):  # « voir plus » / défilement
        pg.mouse.wheel(0, 20000)
        pg.wait_for_timeout(1500)
        for sel in ["text=Voir plus", "text=Charger plus", "text=Plus d'événements", "button.load-more", ".load-more"]:
            try:
                if pg.locator(sel).first.is_visible():
                    pg.locator(sel).first.click(); pg.wait_for_timeout(2500); print("clic", sel)
            except Exception:
                pass
    print("boutons:", pg.eval_on_selector_all("button, a.btn", "els => els.map(e => e.innerText.trim()).filter(t => t).slice(0,40)"))
    b.close()
for m, u, s, h, d in appels:
    print("\n==", m, s, u)
    print("   en-têtes:", {k: v[:80] for k, v in h.items() if k.lower() not in ("user-agent", "sec-ch-ua", "sec-ch-ua-platform", "sec-ch-ua-mobile", "accept-language", "referer")})
    if isinstance(d, list) and d and isinstance(d[0], dict) and "IDPRODUCT" in d[0]:
        print("   n =", len(d))
        for e in d:
            print("   ", e.get("IDPRODUCT"), e.get("event_date"), e.get("raw_unformatted_event_end_date"), e.get("event_location_name"),
                  "|", e.get("product_name"), "|", e.get("categoryForAnalytics"), "|", e.get("formated_price"), "| img", e.get("IDIMAGE"))
        print("   clés:", sorted(d[0].keys()))
        print("   extrait:", json.dumps({k: str(v)[:300] for k, v in d[0].items() if re.search(r"desc|image|img|summary|resume|text|comment", k, re.I)}, ensure_ascii=False))
    # rejouer sans navigateur avec les mêmes en-têtes
    if "aec.app/api/public" in u:
        hh = {k: v for k, v in h.items() if not k.startswith(":")}
        r = requests.get(u, headers=hh, timeout=30)
        print("   rejoué avec en-têtes :", r.status_code, len(r.text))
        r = requests.get(u, headers={"User-Agent": UA, "Referer": "https://www.institutfrancais-tunisie.com/", "Origin": "https://www.institutfrancais-tunisie.com"}, timeout=30)
        print("   rejoué avec Referer/Origin seuls :", r.status_code, len(r.text))
