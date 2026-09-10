"""
MARCHÉS — cours du jour et variations, pour ancrer le personnage dans le réel.

⚠️ POURQUOI C'EST NÉCESSAIRE. « +1 action Tesla parce qu'elle a chuté » n'a de
   valeur que si Tesla a VRAIMENT chuté ce jour-là. Un geste inventé sur un
   mouvement inventé se démonte en dix secondes, et c'est précisément ce qui
   ferait passer le compte pour ce qu'il ne doit pas être.

⚠️ AUCUNE CLÉ D'API. Les points d'accès publics de Yahoo Finance suffisent et
   couvrent actions, indices, matières premières et cryptomonnaies. Une panne
   ne bloque rien : sans cours, le bot écrit sur l'actualité seule et ne
   propose aucun geste d'investissement — plutôt que d'en inventer un faux.
"""

import json
import os
import time

# Ce que le personnage suit. Volontairement court : un portefeuille crédible
# se construit sur quelques convictions, pas sur cinquante lignes.
SUIVI = [s.strip().upper() for s in os.environ.get(
    "SUIVI",
    "TSLA,NVDA,AAPL,MSFT,GOOGL,AMZN,META,AMD,PLTR,COIN,"
    "BTC-USD,ETH-USD,SOL-USD,^GSPC,^IXIC"
).split(",") if s.strip()]

# Un mouvement en dessous de ce seuil n'est pas une nouvelle : le signaler
# reviendrait à commenter du bruit.
SEUIL_MOUVEMENT = float(os.environ.get("SEUIL_MOUVEMENT", "3.0"))

_ENTETE = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/122.0 Safari/537.36"}

NOMS = {
    "TSLA": "Tesla", "NVDA": "Nvidia", "AAPL": "Apple", "MSFT": "Microsoft",
    "GOOGL": "Alphabet", "AMZN": "Amazon", "META": "Meta", "AMD": "AMD",
    "PLTR": "Palantir", "COIN": "Coinbase", "BTC-USD": "Bitcoin",
    "ETH-USD": "Ethereum", "SOL-USD": "Solana", "^GSPC": "S&P 500",
    "^IXIC": "Nasdaq",
}


def nom(symbole):
    return NOMS.get(str(symbole).upper(), str(symbole).upper())


def cours_du_jour(symboles=None):
    """Cours et variation du jour pour chaque valeur suivie.

    Renvoie {symbole: {"cours": float, "var": float, "nom": str}}.
    Une valeur absente est simplement absente : jamais de zéro par défaut,
    qui serait pris pour un vrai cours."""
    import requests
    symboles = symboles or SUIVI
    out = {}
    # Yahoo accepte une liste, mais un symbole fautif fait échouer tout le lot :
    # on découpe en petits paquets pour qu'un seul mauvais ne coûte pas le reste.
    for i in range(0, len(symboles), 5):
        lot = symboles[i:i + 5]
        try:
            r = requests.get(
                "https://query1.finance.yahoo.com/v7/finance/quote",
                params={"symbols": ",".join(lot)},
                headers=_ENTETE, timeout=15)
            if getattr(r, "status_code", 500) != 200:
                continue
            for q in (r.json().get("quoteResponse", {}).get("result") or []):
                s = str(q.get("symbol") or "").upper()
                px = q.get("regularMarketPrice")
                var = q.get("regularMarketChangePercent")
                if s and px is not None:
                    out[s] = {"cours": round(float(px), 2),
                              "var": round(float(var or 0), 2),
                              "nom": nom(s)}
        except Exception as e:
            print(f"  ⚠️ Cours ({', '.join(lot)}) : {str(e)[:50]}", flush=True)
        time.sleep(0.3)          # on ne martèle pas un service gratuit
    if out:
        print(f"  📈 {len(out)}/{len(symboles)} cours relevés", flush=True)
    else:
        print("  ⚠️ Aucun cours disponible — aucun geste d'investissement "
              "ne sera proposé", flush=True)
    return out


def mouvements_notables(cours, seuil=None):
    """Les valeurs qui ont vraiment bougé, du plus fort au plus faible."""
    seuil = SEUIL_MOUVEMENT if seuil is None else seuil
    m = [{"symbole": s, "nom": v["nom"], "cours": v["cours"], "var": v["var"]}
         for s, v in cours.items() if abs(v["var"]) >= seuil]
    m.sort(key=lambda x: -abs(x["var"]))
    for x in m[:6]:
        print(f"     {x['nom']} {x['var']:+.1f} % → {x['cours']}", flush=True)
    return m


def occasion_dachat(mouvements, portefeuille, cours):
    """Une baisse franche sur une valeur que le personnage suit ou détient.

    ⚠️ On ne propose JAMAIS d'acheter sur une hausse : « j'ai renforcé parce
    que ça montait » ne ressemble à rien. Et on ne renforce pas une ligne déjà
    lourde — un personnage qui met tout sur une valeur n'est pas crédible."""
    for m in mouvements:
        if m["var"] > -3.0:
            continue
        if m["symbole"].startswith("^"):      # un indice ne s'achète pas ainsi
            continue
        p = portefeuille.get(m["symbole"])
        if p and p.get("parts", 0) >= 8:
            continue
        return {**m, "detenu": bool(p),
                "parts_actuelles": (p or {}).get("parts", 0),
                "pru": (p or {}).get("pru")}
    return None


def occasion_de_vente(portefeuille, cours, seuil_gain=25.0):
    """Une ligne largement gagnante : de quoi raconter une prise de bénéfice."""
    for s, p in (portefeuille or {}).items():
        c = (cours.get(s) or {}).get("cours")
        if not c or not p.get("pru"):
            continue
        gain = (c - p["pru"]) / p["pru"] * 100
        if gain >= seuil_gain and p.get("parts", 0) >= 2:
            return {"symbole": s, "nom": nom(s), "cours": c, "pru": p["pru"],
                    "gain": round(gain, 1), "parts": p["parts"]}
    return None
