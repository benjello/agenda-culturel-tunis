"""Sonde temporaire : API publique de l'agenda de l'IFT (à retirer avant la fusion)."""
import json, re, requests
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36"}
API = "https://tunisie.aec.app/api/public/core/v1/events/"
for js in ["https://tunisie.extranet-aec.com/js/aec-webapp.js",
           "https://www.institutfrancais-tunisie.com/wp-content/plugins/aec-kiosque/public/js/aec-public.js?ver=2.0.5"]:
    t = requests.get(js, headers=UA, timeout=30).text
    print(js, len(t))
    print("  routes events:", sorted(set(re.findall(r"events/([A-Za-z]+)", t))))
    print("  images:", sorted(set(re.findall(r"[\"'`][^\"'`]{0,60}(?:IDIMAGE|/images?/)[^\"'`]{0,60}[\"'`]", t)))[:15])
for nom in ["availableEventsToday", "availableEvents", "upcomingEvents", "futureEventsAvailable", "eventsAvailable",
            "availableEventsThisWeek", "availableEventsNextWeek", "availableEventsLater", "availableEventsThisMonth"]:
    for q in ["?eventType=&etablishmentBranchId=&CURRENT_LANG=fr_FR", "?eventType=&etablishmentBranchId=&page=0&CURRENT_LANG=fr_FR"]:
        try:
            r = requests.get(API + nom + q, headers=UA, timeout=30)
            d = r.json() if r.ok else None
        except Exception as e:
            print(nom, q, "ERR", e); continue
        n = len(d) if isinstance(d, list) else (list(d)[:10] if isinstance(d, dict) else None)
        print(nom, q[-20:], r.status_code, n)
        if isinstance(d, list) and d:
            for e in d:
                print("   ", e.get("IDPRODUCT"), e.get("event_date"), e.get("raw_unformatted_event_end_date"), e.get("event_location_name"),
                      "|", e.get("product_name"), "|", e.get("categoryForAnalytics"), "|", e.get("formated_price"), "| img", e.get("IDIMAGE"))
            print("    clés:", sorted(d[0].keys()))
            print("    extrait:", {k: (str(v)[:200]) for k, v in d[0].items() if re.search(r"desc|image|img|url|summary|resume|text|location", k, re.I)})
            break
