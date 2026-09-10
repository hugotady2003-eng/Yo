"""
VISUEL — fabrique les images qui accompagnent les tweets.

⚠️ POURQUOI FABRIQUER PLUTÔT QUE REPRENDRE. La photo d'illustration d'un
   article de presse est souvent médiocre, filigranée, au mauvais format, et
   surtout : elle appartient à quelqu'un d'autre. Reprendre celle d'un
   concurrent, c'est faire sa promotion et prendre un risque juridique pour
   une image qu'on n'a pas choisie.

   Un visuel fabriqué est net, au bon format, cohérent d'un jour sur l'autre —
   et c'est cette cohérence qui fait qu'on reconnaît un compte au premier coup
   d'œil, avant même d'avoir lu le nom.

⚠️ LE PARTI PRIS EST LA SOBRIÉTÉ. Beaucoup de vide, une seule couleur d'accent,
   un chiffre qui domine, une typographie qui respire. Rien qui clignote, aucun
   dégradé criard, aucune icône décorative. Ce qui frappe, c'est ce qu'on
   enlève.

⚠️ HAUTE DÉFINITION. Tout est dessiné à l'échelle 2, puis réduit. Sans cela,
   les bords des lettres et des cercles bavent — c'est le premier signe d'une
   image faite à la va-vite.
"""

import io
import os
import re

# 1600×900 après réduction : le format qui s'affiche en pleine largeur sur X
# sans être rogné, et qui reste net sur un écran de téléphone récent.
LARGEUR, HAUTEUR = 1600, 900
ECHELLE = 2

# Deux ambiances, choisies selon le sujet. Le sombre pour les marchés et la
# finance, le clair pour le produit et le matériel — c'est la convention que
# le lecteur a déjà en tête.
THEMES = {
    "sombre": {
        "fond": (11, 11, 13), "voile": (22, 22, 26),
        "titre": (247, 247, 250), "texte": (150, 150, 160),
        "trait": (38, 38, 44),
    },
    "clair": {
        "fond": (250, 250, 252), "voile": (241, 241, 245),
        "titre": (16, 16, 20), "texte": (110, 110, 122),
        "trait": (224, 224, 230),
    },
}
VERT = (48, 209, 88)
ROUGE = (255, 69, 58)
ACCENT = (10, 132, 255)


def _polices():
    """Cherche une police sans empattement, du plus proche d'Apple au repli.

    ⚠️ Une police introuvable ne doit jamais faire échouer l'image : Pillow
    sait dessiner avec sa police par défaut, laide mais fonctionnelle."""
    from PIL import ImageFont
    pistes = [
        "/usr/share/fonts/truetype/inter/Inter-{}.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans{}.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-{}.ttf",
        "/usr/share/fonts/truetype/crosextra/Carlito-{}.ttf",
    ]
    variantes = {"gras": ["Bold", "-Bold", "Bold", "Bold"],
                 "normal": ["Regular", "", "Regular", "Regular"]}

    def charger(style, taille):
        for i, p in enumerate(pistes):
            chemin = p.format(variantes[style][i])
            if os.path.exists(chemin):
                try:
                    return ImageFont.truetype(chemin, taille)
                except Exception:
                    pass
        return ImageFont.load_default()

    return charger


def _couper(dessin, texte, police, largeur_max):
    """Découpe un texte en lignes qui tiennent dans la largeur donnée."""
    mots, lignes, courante = str(texte).split(), [], ""
    for m in mots:
        essai = (courante + " " + m).strip()
        if dessin.textlength(essai, font=police) <= largeur_max:
            courante = essai
        else:
            if courante:
                lignes.append(courante)
            courante = m
    if courante:
        lignes.append(courante)
    return lignes


def carte_marche(valeur, cours, variation, contexte="", theme="sombre"):
    """Carte d'une valeur : le chiffre domine, le reste s'efface.

    C'est la composition la plus utile : elle marche pour une action, un
    indice, une cryptomonnaie, et se lit en une demi-seconde dans un fil."""
    from PIL import Image, ImageDraw
    t = THEMES.get(theme, THEMES["sombre"])
    L, H = LARGEUR * ECHELLE, HAUTEUR * ECHELLE
    img = Image.new("RGB", (L, H), t["fond"])
    d = ImageDraw.Draw(img)
    f = _polices()
    marge = 130 * ECHELLE

    couleur = VERT if variation >= 0 else ROUGE

    # ① le nom de la valeur, discret, tout en haut
    p_nom = f("gras", 34 * ECHELLE)
    d.text((marge, marge), str(valeur).upper(), font=p_nom, fill=t["texte"])

    # ② le cours, énorme — c'est lui qu'on doit voir de loin
    #    ⚠️ Écriture FRANÇAISE : espace pour les milliers, virgule pour les
    #       décimales. « 392.1 » sur un compte français fait traduction ratée.
    p_cours = f("gras", 190 * ECHELLE)
    entier, _, dec = f"{cours:,.2f}".partition(".")
    entier = entier.replace(",", "\u202f")          # espace fine insécable
    txt = entier if dec == "00" else f"{entier},{dec}"
    d.text((marge, marge + 60 * ECHELLE), txt, font=p_cours, fill=t["titre"])

    # ③ la variation, dans une pastille colorée posée à côté
    p_var = f("gras", 46 * ECHELLE)
    v = f"{variation:+.2f} %"
    lv = d.textlength(v, font=p_var)
    haut = marge + 300 * ECHELLE
    pad = 26 * ECHELLE
    d.rounded_rectangle(
        [marge, haut, marge + lv + pad * 2, haut + 84 * ECHELLE],
        radius=42 * ECHELLE, fill=couleur)
    d.text((marge + pad, haut + 18 * ECHELLE), v, font=p_var,
           fill=(255, 255, 255) if variation < 0 else (0, 40, 12))

    # ④ le contexte, en bas, séparé par un filet fin
    #    ⚠️ Le bloc était calé trop haut et laissait un vide mort sous lui.
    #       On l'ancre sur le BAS de la carte : le texte descend, la marge
    #       inférieure devient égale à la marge latérale, et la composition
    #       retrouve son équilibre.
    if contexte:
        p_ctx = f("normal", 40 * ECHELLE)
        lignes = _couper(d, contexte, p_ctx, L - marge * 2)[:2]
        interligne = 56 * ECHELLE
        bas = H - marge
        y = bas - len(lignes) * interligne
        d.line([marge, y - 46 * ECHELLE, L - marge, y - 46 * ECHELLE],
               fill=t["trait"], width=2 * ECHELLE)
        for i, ligne in enumerate(lignes):
            d.text((marge, y + i * interligne), ligne, font=p_ctx,
                   fill=t["texte"])

    return _sortir(img)


def carte_citation(phrase, source="", theme="clair"):
    """Une phrase seule, centrée, sur beaucoup de vide.

    ⚠️ Aucun guillemet décoratif géant, aucune icône. La phrase se suffit :
    tout ce qu'on ajoute autour la rend moins forte."""
    from PIL import Image, ImageDraw
    t = THEMES.get(theme, THEMES["clair"])
    L, H = LARGEUR * ECHELLE, HAUTEUR * ECHELLE
    img = Image.new("RGB", (L, H), t["fond"])
    d = ImageDraw.Draw(img)
    f = _polices()
    marge = 150 * ECHELLE

    # la taille s'adapte à la longueur : une phrase courte mérite d'être grande
    n = len(str(phrase))
    taille = 96 if n < 70 else (76 if n < 130 else 58)
    p = f("gras", taille * ECHELLE)
    lignes = _couper(d, phrase, p, L - marge * 2)[:5]
    interligne = int(taille * 1.34) * ECHELLE
    y = (H - len(lignes) * interligne) // 2 - 30 * ECHELLE
    for i, ligne in enumerate(lignes):
        d.text((marge, y + i * interligne), ligne, font=p, fill=t["titre"])

    if source:
        p_s = f("normal", 34 * ECHELLE)
        d.text((marge, y + len(lignes) * interligne + 40 * ECHELLE),
               str(source), font=p_s, fill=t["texte"])
    return _sortir(img)


def carte_portefeuille(lignes, theme="sombre"):
    """Le portefeuille du personnage, aligné comme un relevé.

    Sa force est la répétition : publiée régulièrement, elle devient un
    rendez-vous, et les lecteurs suivent la progression."""
    from PIL import Image, ImageDraw
    t = THEMES.get(theme, THEMES["sombre"])
    L, H = LARGEUR * ECHELLE, HAUTEUR * ECHELLE
    img = Image.new("RGB", (L, H), t["fond"])
    d = ImageDraw.Draw(img)
    f = _polices()
    marge = 130 * ECHELLE

    p_t = f("gras", 44 * ECHELLE)
    d.text((marge, marge - 20 * ECHELLE), "PORTEFEUILLE", font=p_t,
           fill=t["texte"])

    p_s = f("gras", 60 * ECHELLE)
    p_v = f("gras", 52 * ECHELLE)
    y = marge + 90 * ECHELLE
    for l in (lignes or [])[:6]:
        sym = str(l).split(":")[0].strip()
        m = re.search(r"\(([-+][\d.]+) %\)", str(l))
        var = float(m.group(1)) if m else None
        parts = re.search(r"(\d+) part", str(l))
        d.text((marge, y), sym, font=p_s, fill=t["titre"])
        if parts:
            p_p = f("normal", 40 * ECHELLE)
            d.text((marge + 340 * ECHELLE, y + 14 * ECHELLE),
                   f"{parts.group(1)} part" + ("s" if parts.group(1) != "1" else ""),
                   font=p_p, fill=t["texte"])
        if var is not None:
            v = f"{var:+.1f} %"
            lv = d.textlength(v, font=p_v)
            d.text((L - marge - lv, y + 6 * ECHELLE), v, font=p_v,
                   fill=VERT if var >= 0 else ROUGE)
        y += 96 * ECHELLE
        d.line([marge, y - 22 * ECHELLE, L - marge, y - 22 * ECHELLE],
               fill=t["trait"], width=2 * ECHELLE)
    return _sortir(img)


def _sortir(img):
    """Réduit à la taille finale et encode. Le rééchantillonnage Lanczos est
    ce qui donne des bords nets plutôt que crénelés."""
    from PIL import Image
    img = img.resize((LARGEUR, HAUTEUR), Image.LANCZOS)
    tampon = io.BytesIO()
    img.save(tampon, format="PNG", optimize=True)
    return tampon.getvalue()


def choisir(tweet, cours, portefeuille):
    """Quelle carte pour ce tweet, s'il en mérite une.

    ⚠️ Tous les tweets n'ont pas besoin d'image. Une remarque courte se suffit,
    et un compte où chaque message porte un visuel finit par ressembler à une
    publicité."""
    txt = tweet.get("texte", "")
    # ① une valeur nommée dont on a le cours
    for sym, v in (cours or {}).items():
        nom = v.get("nom", sym)
        if re.search(rf"\b{re.escape(nom)}\b", txt, re.I) or \
           re.search(rf"\b{re.escape(sym.split('-')[0])}\b", txt):
            theme = "clair" if any(k in txt.lower() for k in
                                   ("apple", "iphone", "mac", "design",
                                    "produit", "écran")) else "sombre"
            ctx = re.sub(r"\s+", " ", txt)[:150]
            return ("marche", carte_marche(nom, v["cours"], v["var"], ctx, theme))
    # ② un tweet qui fait le point sur les positions
    if portefeuille and re.search(r"portefeuille|mes lignes|mes positions", txt, re.I):
        return ("portefeuille", carte_portefeuille(portefeuille))
    # ③ une phrase forte et courte : elle porte bien en citation
    if 40 <= len(txt) <= 150 and not re.search(r"\d+\s*%", txt):
        return ("citation", carte_citation(txt))
    return (None, None)
