"""Hygiène des tickets GitHub : balayage des issues inactives, contrôle des pull requests.

  python3 -m scrapers.tickets balayage              # affiche le plan, ne change rien
  python3 -m scrapers.tickets balayage --appliquer  # commente, étiquette, ferme
  python3 -m scrapers.tickets pr                    # signale une PR qui ne cite aucune issue à fermer

Règles du balayage (lancé chaque mois par le workflow « Tickets ») :
- une issue ouverte que une PR fusionnée ferme (« Closes #N ») encore ouverte est fermée : filet de sécurité
  si l'agent a oublié le mot-clé ou si la PR ne visait pas la branche principale ;
- une issue ouverte sans activité depuis AVERTIR_APRES jours reçoit un commentaire et l'étiquette « à-trier » ;
- une issue « à-trier » sans activité depuis FERMER_APRES jours est fermée « non planifiée » ;
- les issues « alerte » (tickets automatiques) ne sont jamais touchées ;
- les pull requests ne sont pas concernées.

Un commentaire ou une modification rouvre le délai : l'issue reste ouverte tant qu'on s'en occupe.
Dans GitHub Actions, le rapport est aussi écrit dans le résumé du workflow.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

DEPOT = "benjello/agenda-culturel-tunis"
AVERTIR_APRES = 60   # jours sans activité avant l'avertissement
FERMER_APRES = 14    # jours sans activité, après l'étiquette « à-trier », avant fermeture
SEUIL_OUVERTES = 10  # au-delà, on ferme ou on reporte avant d'en ouvrir une
ETIQUETTE_TRI = "à-trier"
ETIQUETTE_EXCLUE = "alerte"
FERMETURE = re.compile(r"\b(?:closes?|fixes?|resolves?)\s+#\d+", re.IGNORECASE)

AVERTISSEMENT = (
    "Ce ticket n'a plus d'activité depuis plus de {jours} jours. Il est étiqueté « à-trier ». "
    "Sans réponse ni action dans les {apres} jours qui suivent, il sera fermé comme « non planifié ». "
    "Il pourra être rouvert à tout moment. Pour le garder ouvert, il suffit de le commenter."
)
FERMETURE_TEXTE = (
    "Fermé comme « non planifié » : aucune activité depuis plus de {apres} jours après l'étiquette « à-trier ». "
    "Rouvrez-le si le sujet reste d'actualité."
)
RESOLUE_TEXTE = "Fermé : le travail est fusionné (PR fusionnée qui cite « Closes #N »). Rouvrez-le si ce n'est pas le cas."
LIBELLES = {
    "avertir": "avertissement et étiquette « à-trier »",
    "fermer": "fermeture « non planifiée »",
    "resolue": "fermeture, résolue par une PR fusionnée",
}


def age_en_jours(iso, maintenant):
    """Nombre de jours entre la dernière activité (format GitHub) et `maintenant`."""
    date = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (maintenant - date).days


def resolues(prs):
    """Numéros d'issues fermées par une PR fusionnée (« Closes #N », « Fixes #N », « Resolves #N »)."""
    trouvees = set()
    for pr in prs:
        if not pr.get("merged_at"):
            continue
        for trouve in FERMETURE.finditer(pr.get("body") or ""):
            trouvees.add(int(re.search(r"\d+", trouve.group(0)).group(0)))
    return trouvees


def plan(issues, maintenant, resolues_par_pr=frozenset()):
    """Liste des (numéro, action) à mener. Ne touche à rien : c'est `executer` qui agit."""
    actions = []
    for issue in issues:
        if "pull_request" in issue:
            continue
        etiquettes = {etiquette["name"] for etiquette in issue.get("labels", [])}
        if ETIQUETTE_EXCLUE in etiquettes:
            continue
        if issue["number"] in resolues_par_pr:
            actions.append((issue["number"], "resolue"))
            continue
        age = age_en_jours(issue["updated_at"], maintenant)
        if ETIQUETTE_TRI in etiquettes:
            if age >= FERMER_APRES:
                actions.append((issue["number"], "fermer"))
        elif age >= AVERTIR_APRES:
            actions.append((issue["number"], "avertir"))
    return actions


def pr_sans_fermeture(corps):
    """Vrai si la description de la PR ne contient aucun « Closes #N » (ou fixes, resolves)."""
    return not FERMETURE.search(corps or "")


def rapport(issues, actions, maintenant, appliquees):
    """Rapport en Markdown : nombre d'issues, actions menées ou prévues, liste des issues ouvertes."""
    ouvertes = [i for i in issues if "pull_request" not in i]
    lignes = [f"{len(ouvertes)} issue(s) ouverte(s), seuil conseillé : {SEUIL_OUVERTES}."]
    if len(ouvertes) > SEUIL_OUVERTES:
        lignes.append("Au-delà du seuil : fermer ou reporter une issue avant d'en ouvrir une nouvelle.")
    lignes.append("")
    if actions:
        titres = {i["number"]: i["title"] for i in ouvertes}
        statut = "appliquées" if appliquees else "à appliquer avec --appliquer"
        lignes.append(f"### Actions ({statut})\n")
        for numero, action in actions:
            lignes.append(f"- #{numero} {titres.get(numero, '')} : {LIBELLES[action]}")
    else:
        lignes.append("Aucune issue inactive à traiter.")
    lignes.append("\n### Issues ouvertes\n")
    for issue in sorted(ouvertes, key=lambda i: i["updated_at"]):
        age = age_en_jours(issue["updated_at"], maintenant)
        etiquettes = ", ".join(e["name"] for e in issue.get("labels", []))
        suffixe = f" [{etiquettes}]" if etiquettes else ""
        lignes.append(f"- #{issue['number']} {issue['title']} (inactive depuis {age} j){suffixe}")
    return "\n".join(lignes)


def api(methode, url, jeton, corps=None):
    """Appel à l'API REST GitHub. Sans jeton, seules les lectures d'un dépôt public marchent."""
    entetes = {"Accept": "application/vnd.github+json", "User-Agent": "agenda-culturel-tunis-tickets"}
    if jeton:
        entetes["Authorization"] = f"Bearer {jeton}"
    donnees = None
    if corps is not None:
        donnees = json.dumps(corps).encode("utf-8")
        entetes["Content-Type"] = "application/json"
    requete = urllib.request.Request(url, data=donnees, headers=entetes, method=methode)
    with urllib.request.urlopen(requete, timeout=30) as reponse:
        contenu = reponse.read()
    return json.loads(contenu) if contenu else None


def prs_fermees(depot, jeton, pages=3):
    """Pull requests fermées récentes (les plus récentes d'abord, 100 par page)."""
    tous = []
    for page in range(1, pages + 1):
        lot = api("GET", f"https://api.github.com/repos/{depot}/pulls?state=closed&per_page=100&page={page}", jeton)
        tous += lot
        if len(lot) < 100:
            break
    return tous


def issues_ouvertes(depot, jeton):
    """Toutes les issues et PR ouvertes du dépôt (pagination par 100)."""
    tous, page = [], 1
    while True:
        url = f"https://api.github.com/repos/{depot}/issues?state=open&per_page=100&page={page}"
        lot = api("GET", url, jeton)
        tous += lot
        if len(lot) < 100:
            return tous
        page += 1


def executer(depot, jeton, actions):
    """Commente, étiquette ou ferme les issues du plan."""
    base = f"https://api.github.com/repos/{depot}/issues"
    for numero, action in actions:
        if action == "resolue":
            api("POST", f"{base}/{numero}/comments", jeton, {"body": RESOLUE_TEXTE})
            api("PATCH", f"{base}/{numero}", jeton, {"state": "closed", "state_reason": "completed"})
        elif action == "avertir":
            texte = AVERTISSEMENT.format(jours=AVERTIR_APRES, apres=FERMER_APRES)
            api("POST", f"{base}/{numero}/comments", jeton, {"body": texte})
            api("POST", f"{base}/{numero}/labels", jeton, {"labels": [ETIQUETTE_TRI]})
        else:
            api("POST", f"{base}/{numero}/comments", jeton,
                {"body": FERMETURE_TEXTE.format(apres=FERMER_APRES)})
            api("PATCH", f"{base}/{numero}", jeton, {"state": "closed", "state_reason": "not_planned"})


def ecrire_resume(texte):
    """Ajoute le texte au résumé du workflow, s'il existe (GitHub Actions)."""
    resume = os.environ.get("GITHUB_STEP_SUMMARY")
    if resume:
        with open(resume, "a", encoding="utf-8") as f:
            f.write("## Tickets\n\n" + texte + "\n")


def controler_pr(chemin):
    """Avertit, sans bloquer, si la PR ne cite aucune issue à fermer à la fusion."""
    with open(chemin, encoding="utf-8") as f:
        evenement = json.load(f)
    corps = (evenement.get("pull_request") or {}).get("body")
    if pr_sans_fermeture(corps):
        texte = ("Cette PR ne cite aucune issue à fermer. Si elle en traite une, ajoutez « Closes #N » "
                 "dans la description pour qu'elle se ferme à la fusion. Sinon, rien à faire.")
    else:
        texte = "Cette PR ferme une issue à la fusion : rien à faire."
    print(f"::notice title=Tickets::{texte}")
    ecrire_resume(texte)
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["pr"]:
        return controler_pr(os.environ["GITHUB_EVENT_PATH"])
    if argv[:1] == ["balayage"]:
        appliquer = "--appliquer" in argv
        depot = os.environ.get("GITHUB_REPOSITORY", DEPOT)
        jeton = os.environ.get("GITHUB_TOKEN", "")
        if appliquer and not jeton:
            print("--appliquer demande un jeton GitHub (GITHUB_TOKEN).")
            return 1
        maintenant = datetime.now(timezone.utc)
        issues = issues_ouvertes(depot, jeton)
        actions = plan(issues, maintenant, resolues(prs_fermees(depot, jeton)))
        if appliquer:
            executer(depot, jeton, actions)
        texte = rapport(issues, actions, maintenant, appliquees=appliquer)
        print(texte)
        ecrire_resume(texte)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
