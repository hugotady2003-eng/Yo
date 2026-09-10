"""
COURRIER — met en forme et envoie le mail du matin ou du soir.

⚠️ CE MAIL EST L'UNIQUE INTERFACE. Le bot ne publie rien : il propose, tu
   choisis. C'est ce qui met le compte hors d'atteinte des règles sur
   l'automatisation, et c'est aussi ce qui garantit qu'aucun tweet maladroit
   ne part sans qu'un humain l'ait lu.

⚠️ CHAQUE TWEET DOIT ÊTRE COPIABLE EN UN GESTE. Un mail joli mais dont on ne
   peut pas extraire le texte proprement ne sert à rien : on lit ça sur un
   téléphone, le pouce sur l'écran.
"""

import os
import re
import smtplib
from email.message import EmailMessage
from email.utils import formatdate

ADRESSE = os.environ.get("GMAIL_ADDRESS", "")
MOT_DE_PASSE = os.environ.get("GMAIL_APP_PASS", "")
DESTINATAIRE = os.environ.get("EMAIL_TO", "") or ADRESSE

_CSS = """
body{margin:0;background:#0E0B16;color:#E8E4F0;
     font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.wrap{max-width:620px;margin:0 auto;padding:22px 16px 40px}
h1{font-size:20px;margin:0 0 4px;color:#fff;letter-spacing:-.01em}
.sub{color:#9B93AE;font-size:13px;margin:0 0 22px}
.tw{background:#1A1526;border:1px solid #2E2740;border-radius:16px;
    padding:16px 18px;margin:0 0 14px}
.tw .angle{font-size:11px;text-transform:uppercase;letter-spacing:.09em;
           color:#A78BFA;margin:0 0 8px}
.tw .txt{font-size:16px;color:#F3F0FA;white-space:pre-wrap;margin:0}
.tw .n{font-size:11px;color:#6F677F;margin:10px 0 0}
.img{width:100%;border-radius:12px;margin:12px 0 0;display:block}
.pf{background:#151021;border:1px solid #2A2340;border-radius:14px;
    padding:14px 16px;margin:22px 0 0;font-size:14px}
.pf h2{font-size:12px;text-transform:uppercase;letter-spacing:.09em;
       color:#9B93AE;margin:0 0 9px}
.pf .l{display:flex;justify-content:space-between;gap:10px;padding:3px 0;
       border-bottom:1px solid #221C33}
.pf .l:last-child{border:0}
.vert{color:#4ADE80}.rouge{color:#F87171}.gris{color:#9B93AE}
.pied{color:#6F677F;font-size:12px;margin:26px 0 0;line-height:1.5}
"""


def _ligne_pf(txt):
    m = re.search(r"\(([-+][\d.]+) %\)", txt)
    cls = "gris"
    if m:
        cls = "vert" if float(m.group(1)) >= 0 else "rouge"
    gauche = txt.split(",")[0]
    droite = ", ".join(txt.split(",")[1:]).strip()
    return f'<div class="l"><span>{gauche}</span><span class="{cls}">{droite}</span></div>'


def composer(tweets, portefeuille, gestes, moment, date_lisible, images=None):
    """Le corps HTML du mail."""
    images = images or {}
    h = [f'<html><head><meta charset="utf-8"><style>{_CSS}</style></head><body>',
         '<div class="wrap">',
         f'<h1>{"Bonjour" if moment == "matin" else "Bonsoir"} — '
         f'{len(tweets)} tweet{"s" if len(tweets) > 1 else ""}</h1>',
         f'<p class="sub">{date_lisible} · {moment}</p>']
    for i, t in enumerate(tweets, 1):
        h.append('<div class="tw">')
        if t.get("angle"):
            h.append(f'<p class="angle">{t["angle"]}</p>')
        h.append(f'<p class="txt">{t["texte"]}</p>')
        img = images.get(i)
        if img:
            h.append(f'<img class="img" src="cid:img{i}" alt="">')
        h.append(f'<p class="n">{len(t["texte"])} caractères</p>')
        h.append('</div>')
    if portefeuille:
        h.append('<div class="pf"><h2>Ton portefeuille</h2>')
        h += [_ligne_pf(x) for x in portefeuille]
        h.append('</div>')
    if gestes:
        h.append('<div class="pf"><h2>Inscrit en mémoire aujourd\'hui</h2>')
        for g in gestes:
            v = "vert" if g["type"] == "achat" else "rouge"
            h.append(f'<div class="l"><span>{g["type"].capitalize()} '
                     f'{g["parts"]} × {g["symbole"]}</span>'
                     f'<span class="{v}">{g["prix"]}</span></div>')
        h.append('</div>')
    h.append('<p class="pied">Ces tweets ne sont pas publiés : à toi de choisir '
             'ceux que tu gardes.<br>Les gestes ci-dessus sont déjà enregistrés '
             'dans la mémoire du personnage — il s\'en souviendra demain.</p>')
    h.append('</div></body></html>')
    return "\n".join(h)


def texte_brut(tweets):
    """⚠️ Indispensable : certains clients n'affichent pas le HTML, et une
    version texte se copie mieux au pouce."""
    l = []
    for i, t in enumerate(tweets, 1):
        l.append(f"--- {i} — {t.get('angle', '')} ---")
        l.append(t["texte"])
        l.append("")
    return "\n".join(l)


def envoyer(sujet, html, brut, images=None):
    """Envoi par Gmail. Renvoie True si le message est parti."""
    if not (ADRESSE and MOT_DE_PASSE and DESTINATAIRE):
        print("  ❌ Mail non envoyé : GMAIL_ADDRESS, GMAIL_APP_PASS ou "
              "EMAIL_TO manque", flush=True)
        return False
    msg = EmailMessage()
    msg["Subject"] = sujet
    msg["From"] = ADRESSE
    msg["To"] = DESTINATAIRE
    msg["Date"] = formatdate(localtime=True)
    msg.set_content(brut)
    msg.add_alternative(html, subtype="html")
    # les images sont attachées à la partie HTML, pas au message : sans quoi
    # elles apparaissent en pièces jointes au lieu de s'afficher dans le corps
    if images:
        partie = msg.get_payload()[-1]
        for i, data in (images or {}).items():
            if data:
                partie.add_related(data, maintype="image", subtype="jpeg",
                                   cid=f"<img{i}>")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
            s.login(ADRESSE, MOT_DE_PASSE)
            s.send_message(msg)
        print(f"  📧 Mail envoyé à {DESTINATAIRE}", flush=True)
        return True
    except Exception as e:
        print(f"  ❌ Envoi impossible : {str(e)[:90]}", flush=True)
        return False
