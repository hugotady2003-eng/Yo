#!/usr/bin/env python3
"""
VEILLE — bot de tweets tech et finance, à personnage suivi.

Deux fois par jour : lit l'actualité, relève les marchés, écrit 3 à 5 tweets à
la première personne, les envoie par mail, et inscrit en mémoire ce que le
personnage a fait — pour que demain découle d'aujourd'hui.

⚠️ IL NE PUBLIE RIEN. Il propose ; tu choisis. C'est la différence entre un
   compte automatisé, désormais interdit à la monétisation, et un compte tenu
   par une personne qui s'aide d'un outil.

Lancement :  python3 veille.py            (le moment se déduit de l'heure)
             python3 veille.py soir       (moment imposé)
"""

import os
import re
import sys
import json
import time
from datetime import datetime

import memoire as M
import marches as MK
import plume as PL
import courrier as CO

VERSION = "1.0.0"

# Flux tech et finance. Volontairement resserré : mieux vaut dix sources lues
# qu'une centaine survolée.
FLUX = [f.strip() for f in os.environ.get("FLUX", ",".join([
    "https://feeds.reuters.com/reuters/technologyNews",
    "https://feeds.reuters.com/reuters/businessNews",
    "https://www.cnbc.com/id/19854910/device/rss/rss.html",
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://arstechnica.com/feed/",
    "https://feeds.bloomberg.com/technology/news.rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://www.ft.com/technology?format=rss",
    "https://openai.com/blog/rss.xml",
    "https://www.anthropic.com/news/rss.xml",
])).split(",") if f.strip()]

NB_TWEETS = int(os.environ.get("NB_TWEETS", "4"))
HEURES_ACTU = int(os.environ.get("HEURES_ACTU", "14"))


def moment_du_jour():
    """Matin ou soir, d'après l'heure de Paris."""
    if len(sys.argv) > 1 and sys.argv[1] in ("matin", "soir"):
        return sys.argv[1]
    return "matin" if M._paris().hour < 14 else "soir"


def lire_actualite():
    """Les articles récents des flux suivis, les plus frais d'abord."""
    import feedparser
    arts, vus = [], set()
    limite = time.time() - HEURES_ACTU * 3600
    for url in FLUX:
        try:
            f = feedparser.parse(url)
        except Exception as e:
            print(f"  ⚠️ Flux illisible ({url.split('/')[2]}) : {str(e)[:40]}",
                  flush=True)
            continue
        src = (getattr(f, "feed", {}) or {}).get("title", "") or url.split("/")[2]
        for e in (getattr(f, "entries", []) or [])[:12]:
            titre = re.sub(r"\s+", " ", str(e.get("title") or "")).strip()
            if not titre or titre.lower() in vus:
                continue
            ts = None
            for champ in ("published_parsed", "updated_parsed"):
                v = e.get(champ)
                if v:
                    try:
                        ts = time.mktime(v)
                        break
                    except Exception:
                        pass
            if ts and ts < limite:
                continue
            vus.add(titre.lower())
            arts.append({"titre": titre, "source": src[:28],
                         "url": e.get("link", ""), "ts": ts or time.time(),
                         "resume": re.sub(r"<[^>]+>", " ",
                                          str(e.get("summary") or ""))[:280]})
    arts.sort(key=lambda a: -a["ts"])
    print(f"  📰 {len(arts)} article(s) de moins de {HEURES_ACTU} h", flush=True)
    return arts[:30]


def _llm(prompt, max_tokens=1600):
    """Rédaction. Gemini d'abord, Claude en secours — comme sur Pulse."""
    cles = [os.environ.get(k) for k in
            ("GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3",
             "GEMINI_API_KEY_4", "GEMINI_API_KEY_5")]
    cles = [c for c in cles if c]
    modeles = [m.strip() for m in os.environ.get(
        "MODELES", "gemini-3.5-flash-lite,gemini-3.1-flash-lite,"
                   "gemini-2.5-flash-lite").split(",") if m.strip()]
    import requests
    # ⚠️ Chaque CLÉ, tous ses modèles : le quota se compte par projet ET par
    #    modèle, épuiser l'un ne dit rien de l'autre.
    for cle in cles:
        for mod in modeles:
            try:
                r = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{mod}:generateContent",
                    headers={"x-goog-api-key": cle,
                             "Content-Type": "application/json"},
                    json={"contents": [{"parts": [{"text": prompt}]}],
                          "generationConfig": {
                              "temperature": 0.9,
                              "maxOutputTokens": max_tokens,
                              "responseMimeType": "application/json"}},
                    timeout=90)
                if r.status_code != 200:
                    continue
                t = (r.json()["candidates"][0]["content"]["parts"][0]["text"])
                return json.loads(re.sub(r"^```(?:json)?|```$", "",
                                         t.strip(), flags=re.M).strip())
            except Exception:
                continue
    # secours payant
    ck = os.environ.get("ANTHROPIC_API_KEY")
    if ck:
        try:
            import anthropic
            c = anthropic.Anthropic(api_key=ck)
            m = c.messages.create(
                model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}])
            t = m.content[0].text
            return json.loads(re.sub(r"^```(?:json)?|```$", "", t.strip(),
                                     flags=re.M).strip())
        except Exception as e:
            print(f"  ❌ Claude : {str(e)[:60]}", flush=True)
    raise RuntimeError("aucun modèle disponible")


def image_pour(tweet, articles):
    """Illustration : la photo de l'article le plus proche du tweet.

    ⚠️ On ne fabrique rien et on ne va rien chercher ailleurs : soit l'article
    a une image, soit le tweet part sans. Une illustration hors sujet ferait
    plus de mal que pas d'illustration."""
    import requests
    mots = set(re.findall(r"[0-9a-zà-ÿ]{4,}", tweet["texte"].lower()))
    best, score = None, 0
    for a in articles:
        m = set(re.findall(r"[0-9a-zà-ÿ]{4,}", a["titre"].lower()))
        if not m:
            continue
        r = len(mots & m) / len(m)
        if r > score:
            score, best = r, a
    if not best or score < 0.25 or not best.get("url"):
        return None
    try:
        p = requests.get(best["url"], timeout=12, headers={
            "User-Agent": "Mozilla/5.0"}).text[:120000]
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+'
                      r'content=["\']([^"\']+)', p, re.I)
        if not m:
            return None
        img = requests.get(m.group(1), timeout=12,
                           headers={"User-Agent": "Mozilla/5.0"})
        if img.status_code == 200 and len(img.content) > 8000:
            return img.content[:900000]
    except Exception:
        pass
    return None


def main():
    moment = moment_du_jour()
    print(f"\n🕐 Veille {VERSION} — {M._paris():%d/%m/%Y %H:%M} · {moment}\n",
          flush=True)

    etat, sha = M.charger()
    articles = lire_actualite()
    cours = MK.cours_du_jour()
    mouvements = MK.mouvements_notables(cours)
    occasion = MK.occasion_dachat(mouvements, etat.get("portefeuille", {}), cours)
    vente = MK.occasion_de_vente(etat.get("portefeuille", {}), cours)

    if not articles and not mouvements:
        print("  💤 Ni actualité ni mouvement — aucun mail", flush=True)
        return

    tweets, gestes, resume = PL.ecrire(
        _llm, etat, articles, cours, mouvements, occasion, vente,
        moment=moment, combien=NB_TWEETS,
        contexte=M.contexte_recent(etat))
    if not tweets:
        print("  ❌ Aucun tweet produit — rien envoyé", flush=True)
        return

    # ⚠️ On écarte ce qui a déjà été dit AVANT d'envoyer : recevoir deux fois
    #    le même tweet à quinze jours d'écart ruine la confiance dans l'outil.
    neufs = [t for t in tweets if not M.deja_dit(etat, t["texte"])]
    if len(neufs) < len(tweets):
        print(f"  ♻️ {len(tweets) - len(neufs)} tweet(s) déjà dit(s), écarté(s)",
              flush=True)
    if not neufs:
        print("  ❌ Tous les tweets étaient des redites — rien envoyé", flush=True)
        return

    # les gestes sont inscrits AVANT l'envoi : le mail annonce ce qui est en
    # mémoire, pas ce qui pourrait y entrer
    for g in gestes:
        if g["type"] == "achat":
            M.acheter(etat, g["symbole"], g["parts"], g["prix"], g["motif"])
            print(f"  💰 Achat {g['parts']} × {g['symbole']} à {g['prix']} "
                  f"— {g['motif']}", flush=True)
        else:
            gain = M.vendre(etat, g["symbole"], g["parts"], g["prix"])
            print(f"  💰 Vente {g['parts']} × {g['symbole']} à {g['prix']} "
                  f"({gain:+.0f})", flush=True)

    images = {}
    for i, t in enumerate(neufs, 1):
        if t.get("illustration"):
            img = image_pour(t, articles)
            if img:
                images[i] = img
    if images:
        print(f"  🖼️ {len(images)} illustration(s)", flush=True)

    pf = M.resume_portefeuille(etat, {s: v["cours"] for s, v in cours.items()})
    jour = M._paris()
    html = CO.composer(neufs, pf, gestes, moment,
                       f"{jour:%d/%m/%Y}", images)
    sujet = (f"{'☀️' if moment == 'matin' else '🌙'} {len(neufs)} tweets — "
             f"{jour:%d/%m}")
    envoye = CO.envoyer(sujet, html, CO.texte_brut(neufs), images)

    # ⚠️ On n'inscrit les tweets que si le mail est PARTI. Sinon ils seraient
    #    marqués « déjà dits » sans avoir jamais été lus, et perdus à jamais.
    if envoye:
        M.noter_tweets(etat, neufs, moment)
        M.noter_journee(etat, moment, resume or "", [g["motif"] for g in gestes])
        M.enregistrer(etat, sha)
    else:
        print("  ⚠️ Mémoire NON mise à jour : le mail n'est pas parti",
              flush=True)

    print(f"\n✅ {len(neufs)} tweet(s) · {len(gestes)} geste(s) · "
          f"{len(images)} image(s)\n", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n❌ Cycle interrompu : {e}\n", flush=True)
        sys.exit(1)
