"""
PLUME — écrit les tweets du personnage.

⚠️ CE QUI FAIT LA DIFFÉRENCE entre un compte suivi et un fil d'actualité de
   plus : la continuité. Un lecteur ne revient pas pour apprendre que Nvidia a
   publié ses résultats — il l'a déjà lu ailleurs. Il revient pour savoir ce
   que TOI tu en fais.

   D'où la règle qui gouverne tout ce fichier : le rédacteur reçoit d'abord la
   mémoire — ce que le personnage possède, ce qu'il a dit hier, ce qu'il suit
   depuis des semaines — et seulement ensuite l'actualité du jour.

⚠️ LE GESTE RESTE PETIT. « +1 action Tesla » est crédible. « J'étais au
   lancement Apple » ne l'est pas : le personnage ne fait rien qu'un lecteur
   pourrait vérifier et démentir. Il commente, il investit un peu, il doute.
"""

import json
import re

MOMENTS = {
    "matin": ("Il est tôt. Le personnage ouvre ses écrans, regarde ce qui a "
              "bougé pendant la nuit américaine ou asiatique, et réagit."),
    "soir": ("La journée est passée. Le personnage fait le point : ce qu'il a "
             "retenu, ce qu'il a fait, ce qu'il surveille pour demain."),
}


def _consignes(moment):
    return f"""Tu écris les tweets d'un compte tech et finance en français.

QUI PARLE. Une personne réelle. Elle investit de petites sommes, suit
l'actualité de près, se trompe parfois et le dit. Elle écrit à la première
personne.

MOMENT. {MOMENTS.get(moment, MOMENTS['matin'])}

═══ CE QUI FAIT QU'ON RECONNAÎT UN TEXTE ÉCRIT PAR UNE MACHINE ═══

C'est le point le plus important de ces consignes. Un lecteur ne saurait pas
l'expliquer, mais il le sent en deux secondes et il se désabonne.

① TOUS LES TWEETS FONT LA MÊME LONGUEUR. C'est le signe le plus visible.
   Une personne écrit parfois six mots, parfois quatre lignes, selon ce
   qu'elle a à dire. Fais varier FRANCHEMENT : au moins un tweet très court
   (moins de 60 caractères) et un nettement plus long dans le lot.

② TOUS SUIVENT LA MÊME STRUCTURE : le fait, puis le commentaire, puis une
   petite conclusion qui boucle proprement. Une personne commence souvent
   par sa réaction, ou par le milieu de sa pensée. Elle ne conclut pas
   toujours. Elle laisse parfois la phrase en suspens.

③ TOUT EST EXPLIQUÉ. Une machine précise « Nvidia, le fabricant de puces ».
   Une personne écrit « Nvidia » : ceux qui la suivent savent. N'explique
   jamais ce que ton lecteur connaît déjà.

④ LE FRANÇAIS EST TROP PROPRE. Pas de phrase nominale, pas de « bon », pas
   de « franchement », jamais de parenthèse jetée, aucune phrase qui
   commence par « Et » ou « Sauf que ». C'est un français de rapport, pas
   de conversation.

⑤ AUCUNE ASPÉRITÉ. Une personne a des tics, des obsessions, des rancunes.
   Elle revient sur une erreur passée. Elle dit « je l'avais dit » ou
   « j'avais tort ». Une machine reste lisse et neutre.

⑥ LES FORMULES TOUTES FAITES : « à suivre de près », « ça va être
   intéressant », « le futur est déjà là », « game changer », « c'est
   fou », « on est qu'au début », « ça change la donne », « affaire à
   suivre », « le marché a parlé ». Aucune de ces expressions, jamais.

⑦ LES DEUX-POINTS QUI ANNONCENT, les tirets longs qui incisent, le
   « non pas X, mais Y ». Trois tournures de rédacteur, pas de tweetos.

═══ COMPARE ═══

MACHINE : « Tesla perd 6 % sur des livraisons plus faibles que prévu.
J'ajoute une part : c'est le niveau que j'attendais depuis trois semaines. »
PERSONNE : « 392 sur Tesla. J'attendais ce niveau depuis des semaines,
j'ai pris ma part. On verra bien. »

MACHINE : « Nvidia sort une puce d'inférence pensée pour le coût par token.
C'est là que la bataille se joue maintenant, plus sur l'entraînement. »
PERSONNE : « La bataille se déplace vers l'inférence et le coût par token.
Ça fait un moment que je le dis, mais là c'est écrit noir sur blanc dans
la fiche produit. »

MACHINE : « Le Nasdaq recule de 1,4 %. Rien de dramatique, mais je regarde
AMD qui prend -3,8 % sans nouvelle particulière. »
PERSONNE : « AMD -3,8 % sans rien pour l'expliquer. Bizarre. »

═══ CE QUE FAIT LE PERSONNAGE ═══

- une opinion nette, même discutable, assumée ;
- un chiffre précis pris dans les données fournies, jamais inventé ;
- un geste concret et modeste : renforcer, alléger, attendre, reconnaître
  une erreur ;
- un rappel de ce qu'il a dit avant : « je disais lundi », « ça fait trois
  semaines ». C'est ce qui donne une vie plutôt qu'un fil.

═══ CE QU'IL NE FAIT JAMAIS ═══

- conseiller d'acheter ou prédire un cours. Il dit ce qu'IL fait ;
- inventer un événement vécu invérifiable : une rencontre, un déplacement,
  un accès privilégié. Il commente de chez lui ;
- les fils numérotés, les émojis en rafale, les mots-dièse au milieu du
  texte.

FORME. Zéro ou un émoji, jamais plus. Pas de mot-dièse, sauf s'il tombe
vraiment naturellement, et alors un seul, à la fin."""


def _bloc_memoire(etat, cours, contexte):
    l = ["CE QUE TU ES ET CE QUE TU AS DÉJÀ DIT", ""]
    from memoire import resume_portefeuille
    pf = resume_portefeuille(etat, {s: v["cours"] for s, v in cours.items()})
    if pf:
        l.append("Ton portefeuille aujourd'hui :")
        l += [f"  {x}" for x in pf]
    else:
        l.append("Tu n'as encore aucune position ouverte.")
    fermes = etat.get("positions_closes", [])[-3:]
    if fermes:
        l.append("")
        l.append("Tes dernières sorties :")
        for f in fermes:
            l.append(f"  {f['symbole']} : {f['parts']} part(s) à {f['sortie']} "
                     f"(PRU {f['pru']}), soit {f['gain']:+.0f}")
    if contexte:
        l.append("")
        l.append("Ce que tu as publié ces derniers jours :")
        l += [f"  {x}" for x in contexte]
    hab = etat.get("habitudes", [])
    if hab:
        l.append("")
        l.append("Tes habitudes : " + " · ".join(hab[:6]))
    return "\n".join(l)


def _bloc_actu(articles, mouvements, occasion, vente):
    l = ["L'ACTUALITÉ DU MOMENT", ""]
    if mouvements:
        l.append("Marchés :")
        for m in mouvements[:6]:
            l.append(f"  {m['nom']} {m['var']:+.1f} % → {m['cours']}")
    if articles:
        l.append("")
        l.append("Ce qui se dit :")
        for a in articles[:10]:
            t = re.sub(r"\s+", " ", str(a.get("titre") or "")).strip()
            l.append(f"  [{a.get('source', '?')}] {t[:130]}")
    if occasion:
        l.append("")
        l.append(
            f"POINT D'ENTRÉE POSSIBLE : {occasion['nom']} recule de "
            f"{abs(occasion['var']):.1f} % à {occasion['cours']}."
            + (f" Tu en détiens déjà {occasion['parts_actuelles']} "
               f"(PRU {occasion['pru']})." if occasion.get("detenu")
               else " Tu n'en as pas encore.")
            + " Si tu le juges pertinent, tu peux renforcer d'UNE seule part "
              "et le dire simplement. Rien ne t'y oblige : ne pas acheter et "
              "expliquer pourquoi est un tweet tout aussi bon.")
    if vente:
        l.append("")
        l.append(
            f"PRISE DE BÉNÉFICE POSSIBLE : {vente['nom']} est à "
            f"{vente['gain']:+.1f} % de ton prix de revient "
            f"({vente['pru']} → {vente['cours']}), tu en as {vente['parts']}. "
            "Tu peux en alléger une part, ou assumer de tout garder.")
    return "\n".join(l)


# ⚠️ Expressions qui trahissent immédiatement un texte de modèle. La consigne
#    les interdit — une consigne n'étant pas une garantie, on vérifie.
_TICS = [
    r"à suivre de près", r"ça va être intéressant", r"le futur est déjà là",
    r"game.?changer", r"on (?:n')?est qu'au début", r"ça change la donne",
    r"affaire à suivre", r"le marché a parlé", r"ça promet",
    r"reste à voir", r"une chose est sûre", r"force est de constater",
    r"il n'en fallait pas plus", r"autant dire que", r"inutile de dire",
    r"la question se pose", r"l'avenir nous le dira", r"wait and see",
    r"c'est tout sauf anodin", r"loin d'être anodin", r"ce n'est pas rien",
    r"\bnon pas .{3,40}, mais\b", r"plus que jamais", r"véritable révolution",
]
_TICS_RX = [re.compile(t, re.IGNORECASE) for t in _TICS]


def diagnostic_robot(tweets):
    """Ce qui, dans ce lot, sonne encore artificiel.

    ⚠️ On mesure le LOT, pas chaque tweet isolément : le signe le plus visible
    d'une écriture de machine n'est pas une phrase en particulier, c'est
    l'uniformité de l'ensemble — même longueur, même forme, même rythme."""
    ennuis = []
    # les formules toutes faites se jugent tweet par tweet, dès le premier
    for t in tweets:
        for rx in _TICS_RX:
            m = rx.search(t["texte"])
            if m:
                ennuis.append(f"formule toute faite : « {m.group(0)} »")
                break
    # ⚠️ L'uniformité ne se mesure qu'à partir de trois : sur deux tweets,
    #    une longueur proche est un hasard, pas un symptôme.
    if len(tweets) < 3:
        return ennuis
    longueurs = [len(t["texte"]) for t in tweets]
    ecart = max(longueurs) - min(longueurs)
    if ecart < 70:
        ennuis.append(f"toutes les longueurs se ressemblent ({min(longueurs)}"
                      f"-{max(longueurs)} caractères)")
    if min(longueurs) > 95:
        ennuis.append("aucun tweet court dans le lot")
    # toutes les phrases qui démarrent par un nom propre = structure figée
    debuts = [re.match(r"[A-ZÀ-Ý][\wÀ-ÿ'-]*", t["texte"]) for t in tweets]
    debuts = [d.group(0).lower() for d in debuts if d]
    if len(tweets) >= 3 and len(set(debuts)) == len(debuts) and all(
            re.match(r"^[A-ZÀ-Ý]", t["texte"]) and
            re.search(r"^[\wÀ-ÿ'-]+ (?:perd|gagne|recule|progresse|monte|"
                      r"baisse|chute|sort|annonce|publie|dévoile)", t["texte"])
            for t in tweets):
        ennuis.append("tous les tweets démarrent par « sujet + verbe d'actu »")
    # un lot où chaque tweet finit par un point net, sans aucune variation
    if len(tweets) >= 4 and all(t["texte"].rstrip().endswith(".")
                                for t in tweets):
        ennuis.append("tous les tweets finissent par un point")
    return ennuis


def ecrire(llm_json, etat, articles, cours, mouvements, occasion, vente,
           moment="matin", combien=4, contexte=None):
    """Produit les tweets du moment.

    Renvoie (tweets, gestes) où un geste est une opération réellement décidée
    par le rédacteur — c'est elle qui sera inscrite en mémoire."""
    prompt = (
        _consignes(moment) + "\n\n"
        + _bloc_memoire(etat, cours, contexte or []) + "\n\n"
        + _bloc_actu(articles, mouvements, occasion, vente) + "\n\n"
        f"Écris {combien} tweets différents, du plus fort au plus faible.\n"
        "Varie les angles : une réaction à une actualité, un point de vue sur "
        "une valeur, un geste sur ton portefeuille, une remarque sur ce que tu "
        "suis depuis longtemps. N'écris PAS quatre fois la même chose sous "
        "quatre formes.\n\n"
        "Si tu décides d'un achat ou d'une vente, DÉCLARE-LE dans « gestes » "
        "avec le symbole exact, le nombre de parts et le prix indiqué "
        "ci-dessus. N'invente aucun prix. Un geste non déclaré ne sera pas "
        "retenu en mémoire et le personnage se contredira demain.\n\n"
        'JSON strict : {"tweets":[{"texte":"...","angle":"<3 mots>",'
        '"illustration":"<ce qu\'une image devrait montrer, ou vide>"}],'
        '"gestes":[{"type":"achat|vente","symbole":"TSLA","parts":1,'
        '"prix":392.1,"motif":"<8 mots>"}],'
        '"resume_journee":"<en une phrase, ce que le personnage a vécu>"}'
    )
    try:
        rep = llm_json(prompt, max_tokens=1600)
    except Exception as e:
        print(f"  ❌ Rédaction impossible : {str(e)[:70]}", flush=True)
        return [], [], ""
    if not isinstance(rep, dict):
        return [], [], ""

    def _extraire(r):
        out = []
        for t in (r.get("tweets") or []):
            txt = re.sub(r"[ \t]+", " ", str(t.get("texte") or "")).strip()
            # ⚠️ on descend à 25 caractères : un tweet court est justement ce
            #    qui manquait. « AMD -3,8 % sans rien pour l'expliquer. » en
            #    fait 38 et c'est le meilleur du lot.
            if not (25 <= len(txt) <= 280):
                continue
            out.append({"texte": txt,
                        "angle": str(t.get("angle") or "")[:40],
                        "illustration": str(t.get("illustration") or "")[:160]})
        return out

    tweets = _extraire(rep)
    # ⚠️ UNE SEULE REPRISE. Le modèle corrige presque toujours du premier coup
    #    quand on lui dit précisément ce qui cloche ; insister coûterait un
    #    appel de plus pour un gain nul.
    ennuis = diagnostic_robot(tweets)
    if ennuis:
        print(f"  🤖 Écriture trop mécanique : {' · '.join(ennuis[:3])}",
              flush=True)
        try:
            rep2 = llm_json(
                prompt + "\n\n═══ TU AS DÉJÀ ESSAYÉ, VOICI CE QUI CLOCHE ═══\n"
                + "\n".join(f"• {e}" for e in ennuis)
                + "\n\nTes brouillons :\n"
                + "\n".join(f"  — {t['texte']}" for t in tweets)
                + "\n\nRécris-les. Garde les idées, change la FORME : coupe "
                  "court là où c'est possible, commence au moins un tweet par "
                  "ta réaction plutôt que par le fait, laisses-en un sans "
                  "conclusion. Au moins un tweet doit faire moins de 60 "
                  "caractères.",
                max_tokens=1600)
            neufs = _extraire(rep2) if isinstance(rep2, dict) else []
            if neufs and len(diagnostic_robot(neufs)) < len(ennuis):
                print(f"  ✅ Reprise retenue ({len(neufs)} tweets)", flush=True)
                tweets = neufs
                rep = {**rep, "tweets": rep2.get("tweets") or []}
            else:
                print("  ↩️ Reprise pas meilleure — brouillons conservés",
                      flush=True)
        except Exception as e:
            print(f"  ⚠️ Reprise impossible ({str(e)[:40]})", flush=True)

    # ⚠️ Un geste n'est retenu que s'il porte sur une valeur RÉELLEMENT cotée
    #    aujourd'hui, à son prix réel. Sinon le portefeuille dériverait du monde.
    gestes = []
    for g in (rep.get("gestes") or []):
        s = str(g.get("symbole") or "").upper().strip()
        if s not in cours:
            print(f"  ⚠️ Geste ignoré : {s} n'a pas de cours aujourd'hui",
                  flush=True)
            continue
        try:
            parts = max(1, min(3, int(g.get("parts") or 1)))
        except Exception:
            parts = 1
        reel = cours[s]["cours"]
        prix = g.get("prix")
        try:
            prix = float(prix)
        except Exception:
            prix = reel
        # un prix qui s'écarte du marché est remplacé, pas refusé
        if abs(prix - reel) / max(1e-9, reel) > 0.05:
            print(f"  ⚠️ Prix corrigé pour {s} : {prix} → {reel}", flush=True)
            prix = reel
        gestes.append({"type": ("vente" if str(g.get("type", "")).startswith("v")
                                else "achat"),
                       "symbole": s, "parts": parts, "prix": prix,
                       "motif": str(g.get("motif") or "")[:120]})
    return tweets, gestes[:2], str(rep.get("resume_journee") or "")[:300]
