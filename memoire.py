"""
MÉMOIRE DE VIE — l'état du personnage, conservé d'un jour sur l'autre.

C'est la pièce centrale. Sans elle, chaque mail repartirait de zéro et le
personnage n'aurait aucune épaisseur : il achèterait une action Tesla tous les
matins sans jamais en posséder.

⚠️ CONSERVÉE DANS LE DÉPÔT GITHUB, pas dans le cache d'exécution. Le cache
   d'une forge expire au bout de quelques jours ; un fichier versionné, non.
   « Pour toujours » demande un endroit qui ne s'efface pas — et le versionnement
   donne en prime l'historique complet de ce que le personnage a vécu.

⚠️ UNE SEULE SOURCE DE VÉRITÉ. Tout ce que le personnage possède, a dit ou a
   fait vit dans ce fichier. Rien n'est déduit ailleurs, rien n'est recalculé.
"""

import json
import os
import re
import base64
from datetime import datetime, timedelta, timezone

FICHIER = os.environ.get("MEMOIRE_FICHIER", "memoire/vie.json")
DEPOT = os.environ.get("GITHUB_REPOSITORY", "")
JETON = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""

# On garde le squelette ici : un fichier absent ou abîmé ne doit jamais
# empêcher un envoi. Le personnage repart alors de rien, ce qui est visible
# et réparable, plutôt que de planter.
VIDE = {
    "version": 1,
    "portefeuille": {},      # "TSLA": {"parts": 3, "pru": 412.5, "depuis": "…"}
    "positions_closes": [],  # ce qui a été vendu, pour pouvoir y faire allusion
    "veille": {},            # sujets suivis : {"sujet": {"depuis": "…", "vu": 4}}
    "habitudes": [],         # petits traits récurrents, écrits par le bot
    "journal": [],           # ce qui a été dit, jour par jour
    "tweets_envoyes": [],    # empreintes, pour ne jamais se répéter
    "compteurs": {"mails": 0, "tweets": 0, "jours": 0},
    "maj": "",
}


def _paris():
    """Heure de Paris sans dépendance externe (le fuseau suffit ici)."""
    n = datetime.now(timezone.utc)
    # France : UTC+2 d'avril à octobre, UTC+1 sinon. Approximation assumée —
    # aucune décision du bot ne dépend d'une heure à la minute près.
    return n + timedelta(hours=2 if 3 < n.month < 11 else 1)


def _api_github(chemin, methode="GET", corps=None):
    import requests
    if not (DEPOT and JETON):
        return None
    url = f"https://api.github.com/repos/{DEPOT}/contents/{chemin}"
    ent = {"Authorization": f"Bearer {JETON}",
           "Accept": "application/vnd.github+json"}
    try:
        if methode == "GET":
            r = requests.get(url, headers=ent, timeout=25)
            return r.json() if r.status_code == 200 else None
        r = requests.put(url, headers=ent, json=corps, timeout=30)
        return r.json() if r.status_code in (200, 201) else None
    except Exception as e:
        print(f"  ⚠️ Mémoire ({methode}) : {str(e)[:60]}", flush=True)
        return None


def charger():
    """Lit la mémoire. Renvoie (état, sha) — le sha sert à réécrire sans conflit."""
    # ① le dépôt fait foi
    d = _api_github(FICHIER)
    if d and d.get("content"):
        try:
            brut = base64.b64decode(d["content"]).decode("utf-8")
            etat = json.loads(brut)
            for k, v in VIDE.items():
                etat.setdefault(k, v if not isinstance(v, (dict, list))
                                else type(v)())
            print(f"  🧠 Mémoire : {len(etat.get('journal', []))} jour(s), "
                  f"{len(etat.get('portefeuille', {}))} ligne(s) en portefeuille",
                  flush=True)
            return etat, d.get("sha")
        except Exception as e:
            # ⚠️ Un fichier abîmé ne doit pas être écrasé en silence : on le
            #    signale bruyamment, et on repart du vide sans le supprimer.
            print(f"  ❌ Mémoire illisible ({str(e)[:60]}) — "
                  f"repart de zéro SANS écraser le fichier", flush=True)
            return json.loads(json.dumps(VIDE)), None
    # ② repli local, utile hors ligne et pour les essais
    if os.path.exists(FICHIER):
        try:
            with open(FICHIER, encoding="utf-8") as f:
                return json.load(f), None
        except Exception:
            pass
    print("  🧠 Mémoire vide — premier passage", flush=True)
    return json.loads(json.dumps(VIDE)), None


def enregistrer(etat, sha=None):
    """Écrit la mémoire dans le dépôt, et en local en secours."""
    etat["maj"] = _paris().strftime("%Y-%m-%d %H:%M")
    brut = json.dumps(etat, ensure_ascii=False, indent=1)
    os.makedirs(os.path.dirname(FICHIER) or ".", exist_ok=True)
    with open(FICHIER, "w", encoding="utf-8") as f:
        f.write(brut)
    corps = {
        "message": f"mémoire {etat['maj']} — {etat['compteurs']['tweets']} tweets",
        "content": base64.b64encode(brut.encode("utf-8")).decode("ascii"),
    }
    if sha:
        corps["sha"] = sha
    if _api_github(FICHIER, "PUT", corps) is not None:
        print(f"  💾 Mémoire enregistrée ({len(brut)} octets)", flush=True)
        return True
    print("  ⚠️ Mémoire non enregistrée sur GitHub — copie locale seule",
          flush=True)
    return False


# ── PORTEFEUILLE ──────────────────────────────────────────────────────────
def acheter(etat, symbole, parts, prix, motif=""):
    """Ajoute des parts et recalcule le prix de revient moyen.

    ⚠️ Le prix de revient est ce qui donne sa cohérence au personnage : c'est
    lui qui permet de dire « je suis à +18 % sur Tesla » des semaines plus
    tard sans se contredire."""
    symbole = str(symbole).upper().strip()
    p = etat["portefeuille"].get(symbole)
    if p:
        total = p["parts"] + parts
        p["pru"] = round((p["pru"] * p["parts"] + prix * parts) / total, 2)
        p["parts"] = total
    else:
        etat["portefeuille"][symbole] = {
            "parts": parts, "pru": round(prix, 2),
            "depuis": _paris().strftime("%Y-%m-%d"), "motif": motif[:120],
        }
    return etat["portefeuille"][symbole]


def vendre(etat, symbole, parts, prix):
    """Retire des parts. Une ligne vidée passe dans l'historique."""
    symbole = str(symbole).upper().strip()
    p = etat["portefeuille"].get(symbole)
    if not p:
        return None
    parts = min(parts, p["parts"])
    gain = round((prix - p["pru"]) * parts, 2)
    p["parts"] -= parts
    etat["positions_closes"].append({
        "symbole": symbole, "parts": parts, "pru": p["pru"],
        "sortie": round(prix, 2), "gain": gain,
        "date": _paris().strftime("%Y-%m-%d"),
    })
    if p["parts"] <= 0:
        etat["portefeuille"].pop(symbole, None)
    return gain


def resume_portefeuille(etat, cours=None):
    """Une ligne par position, telle que le rédacteur la lira."""
    cours = cours or {}
    out = []
    for s, p in sorted(etat.get("portefeuille", {}).items()):
        l = f"{s} : {p['parts']} part(s), PRU {p['pru']}"
        c = cours.get(s)
        if c:
            var = round((c - p["pru"]) / p["pru"] * 100, 1)
            l += f", cours {c} ({var:+.1f} %)"
        out.append(l)
    return out


# ── JOURNAL ET ANTI-RÉPÉTITION ────────────────────────────────────────────
def _empreinte(texte):
    """Signature d'un tweet, insensible à la ponctuation et à la casse."""
    m = re.findall(r"[0-9a-zà-ÿ]{4,}", str(texte).lower())
    return " ".join(sorted(set(m))[:12])


def deja_dit(etat, texte, jours=45):
    """Ce tweet, ou presque, a-t-il déjà été envoyé ?

    ⚠️ Se répéter est ce qui trahit le plus sûrement un compte automatisé.
    On compare sur les mots significatifs, pas sur la chaîne exacte : une
    reformulation reste une répétition."""
    e = _empreinte(texte)
    if not e:
        return False
    mots = set(e.split())
    limite = (_paris() - timedelta(days=jours)).strftime("%Y-%m-%d")
    for t in etat.get("tweets_envoyes", []):
        if t.get("date", "") < limite:
            continue
        autres = set(str(t.get("emp", "")).split())
        if not autres:
            continue
        commun = len(mots & autres) / max(1, min(len(mots), len(autres)))
        if commun >= 0.7:
            return True
    return False


def noter_tweets(etat, tweets, moment):
    """Consigne les tweets proposés : ils ne seront jamais reproposés."""
    j = _paris().strftime("%Y-%m-%d")
    for t in tweets:
        etat["tweets_envoyes"].append({
            "date": j, "moment": moment, "emp": _empreinte(t.get("texte", "")),
            "texte": str(t.get("texte", ""))[:400],
            "angle": t.get("angle", ""),
        })
    # on garde une année : au-delà, une répétition ne se voit plus
    limite = (_paris() - timedelta(days=365)).strftime("%Y-%m-%d")
    etat["tweets_envoyes"] = [t for t in etat["tweets_envoyes"]
                              if t.get("date", "") >= limite][-900:]
    etat["compteurs"]["tweets"] += len(tweets)
    etat["compteurs"]["mails"] += 1


def noter_journee(etat, moment, resume, gestes):
    """Ce que le personnage a vécu aujourd'hui, pour pouvoir y revenir demain."""
    j = _paris().strftime("%Y-%m-%d")
    entree = next((x for x in etat["journal"] if x.get("date") == j), None)
    if entree is None:
        entree = {"date": j, "moments": []}
        etat["journal"].append(entree)
        etat["compteurs"]["jours"] += 1
    entree["moments"].append({
        "moment": moment, "resume": str(resume)[:300],
        "gestes": [str(g)[:160] for g in (gestes or [])][:5],
    })
    etat["journal"] = etat["journal"][-180:]      # six mois de continuité


def contexte_recent(etat, jours=7):
    """Ce que le rédacteur doit avoir en tête : les derniers jours vécus."""
    limite = (_paris() - timedelta(days=jours)).strftime("%Y-%m-%d")
    out = []
    for e in etat.get("journal", []):
        if e.get("date", "") < limite:
            continue
        for m in e.get("moments", []):
            out.append(f"{e['date']} ({m['moment']}) : {m['resume']}")
    return out[-14:]
