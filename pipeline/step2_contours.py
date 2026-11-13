# -*- coding: utf-8 -*-
"""
CODE 2 - Extraction des points et trajectoires.

Detecte les formes (claires OU sombres, detection automatique), puis
RECONNAIT les primitives geometriques de chaque contour :

  - "angulaire" : suite de lignes droites reliees par des angles (polygone) ;
  - "ligne"     : segment droit (primitive d'une forme composee) ;
  - "arc"       : portion de cercle ;
  - "cercle"    : contour circulaire complet ;
  - "mixte"     : combinaison de lignes et d'arcs (ex. rectangle arrondi).

L'INTERIEUR des formes suit LES TRAITS DE L'IMAGE (INNER_TRAJECTORIES=1) :
les contours internes (details reellement dessines a l'interieur des
formes) sont extraits et traces exactement comme le contour, avec le
moins de points possible. Aucun remplissage genere : si l'image ne
dessine rien a l'interieur, le robot n'y trace rien.

DESSINS AU TRAIT (mode SQUELETTE) : quand une composante de l'image est un
reseau de traits fins (demi-epaisseur <= SQUELETTE_MAX_PX, ex. deux cercles
entrelaces avec leurs rayons), les contours ne peuvent pas suivre les
traits (le contour longe les deux bords de chaque trait). On amincit alors
le trait en un SQUELETTE (Guo-Hall), on suit le graphe obtenu, puis on
FUSIONNE les chemins alignes qui se croisent : deux rayons opposes de la
meme droite deviennent UNE ligne de 2 points, les arcs d'un meme cercle
se recollent en un cercle complet. Les composantes épaisses (formes
pleines) gardent la logique des contours, inchangee.

Chaque trajectoire est un dictionnaire :
    {"type": "cercle",
     "points": [{"x": .., "y": .., "z": .., "w": .., "p": .., "r": ..}, ...]}
Les coordonnees sont en mm ; une trajectoire fermee se termine par une
copie de son premier point.
"""
import cv2
import numpy as np

import config


def _formes(bw):
    """Version de l'image ou les FORMES sont blanches.

    Les formes occupent en general moins de surface que le fond : on garde
    la version (image ou inverse) ou le blanc couvre le moins de pixels,
    ce qui marche aussi bien pour des formes sombres que claires.
    """
    inv = 255 - bw
    return inv if np.count_nonzero(inv) < np.count_nonzero(bw) else bw


# ------------------------------------------------------------------
# Ajustement des primitives (toutes les coordonnees sont en pixels)
# ------------------------------------------------------------------

def _fit_circle(pts):
    """Cercle ajuste aux moindres carres ; retourne (cx, cy, r, rms) ou None."""
    pts = np.asarray(pts, np.float64)
    if len(pts) < 3:
        return None
    x, y = pts[:, 0], pts[:, 1]
    mat = np.column_stack([2.0 * x, 2.0 * y, np.ones(len(x))])
    sol, *_ = np.linalg.lstsq(mat, x * x + y * y, rcond=None)
    cx, cy = float(sol[0]), float(sol[1])
    val = float(sol[2]) + cx * cx + cy * cy
    if val <= 0.0:
        return None
    r = float(np.sqrt(val))
    rms = float(np.sqrt(np.mean((np.hypot(x - cx, y - cy) - r) ** 2)))
    return cx, cy, r, rms


def _span(pts, cx, cy):
    """Ouverture angulaire (radians) du contour autour de son centre."""
    angles = np.sort(np.arctan2(pts[:, 1] - cy, pts[:, 0] - cx))
    gaps = np.diff(angles)
    wrap = 2.0 * np.pi - (angles[-1] - angles[0])
    hole = max(float(np.max(gaps)) if len(gaps) else 0.0, float(wrap))
    return 2.0 * np.pi - hole


def _arc_points(cx, cy, r, a0, a1, chord_mm=None):
    """Points d'un arc de a0 a a1 (radians), corde max chord_mm."""
    r_px = max(r, 1.0)
    chord = chord_mm if chord_mm is not None else config.ARC_CHORD_MM
    chord_px = max(chord / config.SCALE_MM_PER_PX, 0.5)
    step = 2.0 * np.arccos(np.clip(1.0 - chord_px / r_px, -1.0, 1.0))
    step = float(np.clip(step, np.radians(2.0), np.radians(30.0)))
    count = max(int(np.ceil(abs(a1 - a0) / step)) + 1, 2)
    t_list = np.linspace(a0, a1, count)
    return np.column_stack([cx + r_px * np.cos(t_list), cy + r_px * np.sin(t_list)])


def _line_dev(pts, p0, p1):
    """Ecart maximal des points a la droite qui passe par p0 et p1."""
    direction = p1 - p0
    length = float(np.hypot(direction[0], direction[1]))
    if length < 1e-9:
        return float(np.max(np.linalg.norm(pts - p0, axis=1)))
    normal = np.array([-direction[1], direction[0]]) / length
    return float(np.max(np.abs((pts - p0) @ normal)))


def _turn_angles(vertices):
    """Deviation angulaire (degres) a chaque sommet d'un contour ferme."""
    count = len(vertices)
    turns = []
    for i in range(count):
        prev = vertices[(i - 1) % count]
        cur = vertices[i % count]
        nxt = vertices[(i + 1) % count]
        v1 = prev - cur
        v2 = nxt - cur
        n1 = float(np.hypot(v1[0], v1[1]))
        n2 = float(np.hypot(v2[0], v2[1]))
        if n1 < 1e-9 or n2 < 1e-9:
            turns.append(0.0)
            continue
        cos_angle = np.clip(float(v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2), -1.0, 1.0)
        turns.append(float(np.degrees(np.arccos(cos_angle))))
    return turns


def _corner_indices(pts):
    """Positions dans le contour des sommets qui sont des ANGLES."""
    approx = cv2.approxPolyDP(pts.reshape(-1, 1, 2).astype(np.float32),
                              config.LINE_TOL_PX, True).reshape(-1, 2)
    if len(approx) < 3:
        return []
    turns = _turn_angles(approx)
    found = []
    for i, angle in enumerate(turns):
        if angle >= config.CORNER_MIN_DEG:
            match = np.where((np.abs(pts - approx[i]) <= 0.5).all(axis=1))[0]
            if len(match):
                found.append(int(match[0]))
    return sorted(set(found))


def _segments(pts, corners):
    """Decoupe le contour aux angles -> sous-contours (px)."""
    segs = []
    for k in range(len(corners)):
        i0 = corners[k]
        i1 = corners[(k + 1) % len(corners)]
        if i1 > i0:
            segs.append(pts[i0:i1 + 1])
        else:  # dernier segment : passage par la fin du contour
            segs.append(np.vstack([pts[i0:], pts[:i1 + 1]]))
    return segs


def _segment_primitive(seg, chord_mm=None):
    """Sous-contour entre deux angles -> ligne, arc ou polygone libre."""
    seg = np.asarray(seg, np.float64)
    if len(seg) < 2:
        return ("angulaire", seg)
    if _line_dev(seg, seg[0], seg[-1]) <= config.LINE_TOL_PX:
        return ("ligne", np.asarray([seg[0], seg[-1]], np.float64))
    circle = _fit_circle(seg)
    if circle is not None:
        cx, cy, r, rms = circle
        if rms <= config.ARC_TOL_PX:
            angles = np.unwrap(np.arctan2(seg[:, 1] - cy, seg[:, 0] - cx))
            sweep = abs(float(angles[-1] - angles[0]))
            if np.radians(5.0) <= sweep <= np.radians(355.0):
                return ("arc", _arc_points(cx, cy, r,
                                          float(angles[0]), float(angles[-1]), chord_mm))
    libre = cv2.approxPolyDP(seg.reshape(-1, 1, 2).astype(np.float32),
                             max(config.ARC_TOL_PX, 1.0), False)
    return ("angulaire", np.asarray(libre.reshape(-1, 2), np.float64))


def _greedy_primitives(pts, chord_mm=None):
    """Contour lisse (sans angle) -> suite gloutonne de lignes et d'arcs.

    Part du premier point et etend chaque primitive tant qu'un ajustement
    ligne ou arc reste dans la tolerance ; gere les formes composees comme
    les rectangles arrondis (4 lignes + 4 arcs) ou les ellipses.
    """
    n = len(pts)
    cap = max(20, n // 8)
    primitives = []
    start = 0
    while start < n - 1:
        best = None
        end = start + 1
        for last in range(start + 1, min(start + cap, n)):
            seg = pts[start:last + 1]
            if _line_dev(seg, seg[0], seg[-1]) <= config.LINE_TOL_PX:
                best = ("ligne", np.asarray([seg[0], seg[-1]], np.float64))
                end = last
                continue
            circle = _fit_circle(seg)
            if circle is not None and circle[3] <= config.ARC_TOL_PX and circle[2] >= 3.0:
                cx, cy, r, _ = circle
                angles = np.unwrap(np.arctan2(seg[:, 1] - cy, seg[:, 0] - cx))
                sweep = abs(float(angles[-1] - angles[0]))
                if np.radians(8.0) <= sweep <= np.radians(355.0):
                    best = ("arc", _arc_points(cx, cy, r,
                                              float(angles[0]), float(angles[-1]), chord_mm))
                    end = last
                    continue
            break  # plus rien ne s'ajuste : la primitive precedente est retenue
        if best is None:
            return None
        primitives.append(best)
        start = end
    return primitives


def _primitives(pts, chord_mm=None):
    """Contour ferme (px) -> primitives [(type, tableau de points px), ...]."""
    circle = _fit_circle(pts)

    # 1) CERCLE complet (ajustement propre + ouverture proche de 360 degres)
    if circle is not None:
        cx, cy, r, rms = circle
        if rms <= config.ARC_TOL_PX and _span(pts, cx, cy) >= np.radians(330.0):
            a0 = float(np.arctan2(pts[0, 1] - cy, pts[0, 0] - cx))
            return [("cercle", _arc_points(cx, cy, r, a0, a0 + 2.0 * np.pi, chord_mm))]

    # 2) ANGLES : decoupage du contour puis ligne / arc sur chaque portion
    corners = _corner_indices(pts)
    if len(corners) >= 2:
        return [_segment_primitive(seg, chord_mm) for seg in _segments(pts, corners)]

    # 3) Pas d'angle marque : suite gloutonne d'arcs/lignes, sinon polygone
    greedy = _greedy_primitives(pts, chord_mm)
    if greedy:
        return greedy
    libre = cv2.approxPolyDP(pts.reshape(-1, 1, 2).astype(np.float32),
                             max(config.ARC_TOL_PX, 1.0), True)
    libre = np.asarray(libre.reshape(-1, 2), np.float64)
    return [("angulaire", libre)] if len(libre) >= 3 else []


def _assemble(primitives):
    """Assemble les primitives en une trajectoire fermee.

    Retourne (type, points px) ou None si rien a dessiner.
    """
    pieces = []
    for _, seg_pts in primitives:
        seg_pts = np.asarray(seg_pts, np.float64)
        if pieces and len(seg_pts):
            dx = float(seg_pts[0][0] - pieces[-1][-1][0])
            dy = float(seg_pts[0][1] - pieces[-1][-1][1])
            if np.hypot(dx, dy) < 0.75:
                seg_pts = seg_pts[1:]  # sommet partage avec la primitive precedente
        if len(seg_pts):
            pieces.append(seg_pts)
    if not pieces:
        return None
    outline = np.vstack(pieces)
    dx = float(outline[0][0] - outline[-1][0])
    dy = float(outline[0][1] - outline[-1][1])
    if np.hypot(dx, dy) > 0.75:
        outline = np.vstack([outline, outline[:1]])  # ferme la boucle
    kinds = set(kind for kind, _ in primitives)
    if kinds == {"cercle"}:
        label = "cercle"
    elif kinds <= {"arc"}:
        label = "arc"
    elif "arc" in kinds and ("ligne" in kinds or "angulaire" in kinds):
        label = "mixte"
    else:
        label = "angulaire"
    return label, outline


def _to_traj(label, pts_px):
    """Points en pixels -> trajectoire en mm (dictionnaire)."""
    points = [{"x": round(float(x) * config.SCALE_MM_PER_PX, 2),
               "y": round(float(y) * config.SCALE_MM_PER_PX, 2),
               "z": config.Z_MM, "w": config.W_DEG,
               "p": config.P_DEG, "r": config.R_DEG}
              for x, y in np.asarray(pts_px, np.float64)]
    return {"type": label, "points": points}


def _ajoute_contour(trajs, contour):
    """Analyse un contour (primitives) et ajoute sa trajectoire si valide."""
    pts = contour.reshape(-1, 2).astype(np.float64)
    if len(pts) < 3:
        return
    built = _assemble(_primitives(pts))
    if built is None:
        return
    label, outline = built
    trajs.append(_to_traj(label, outline))


def _distance_min(interieur, parent):
    """Distance minimale (px) entre un contour interne et son contour parent.

    Un contour interne colle a son parent (distance < INNER_MIN_GAP_PX)
    n'est pas un detail dessine : c'est l'interieur du trait lui-meme,
    on l'ignore pour ne pas tracer deux fois la meme ligne.
    """
    pts = interieur.reshape(-1, 2).astype(np.float64)
    pas = max(1, len(pts) // 100)  # echantillonnage (rapidite)
    mini = 1.0e9
    for x, y in pts[::pas]:
        d = abs(cv2.pointPolygonTest(parent, (float(x), float(y)), True))
        if d < mini:
            mini = d
    return mini


def _est_trait(contour):
    """Vrai si le contour est un petit TRAIT LINEAIRE fin, pas une forme.

    Un trait fin a une aire quasi nulle (longueur x epaisseur) : le filtre
    MIN_AREA_PX le rejetterait comme du bruit. On le reconnait par sa
    geometrie : rectangle minimal tres etroit (epaisseur <= TRAIT_MAX_W_PX)
    et longueur suffisante (>= MIN_TRAIT_PX).
    """
    rect = cv2.minAreaRect(contour)
    if min(rect[1]) > config.TRAIT_MAX_W_PX:
        return False
    return cv2.arcLength(contour, True) * 0.5 >= config.MIN_TRAIT_PX


def _axe_du_trait(contour):
    """Trait fin -> les 2 extremites de son axe median (px)."""
    pts = contour.reshape(-1, 2).astype(np.float64)
    if len(pts) < 2:
        return None
    centre = pts.mean(axis=0)
    _, _, vecteurs = np.linalg.svd(pts - centre, full_matrices=False)
    axe = vecteurs[0]                       # direction principale du trait
    t = (pts - centre) @ axe
    return np.asarray([centre + axe * float(t.min()),
                       centre + axe * float(t.max())], np.float64)


def _ajoute_trait(trajs, contour):
    """Petit trait lineaire : une seule trajectoire LIGNE, 2 points (son axe)."""
    axe = _axe_du_trait(contour)
    if axe is None:
        return
    trajs.append(_to_traj("ligne", axe))


# ------------------------------------------------------------------
# Mode SQUELETTE : dessins au trait (reseaux de traits fins entrelaces)
# ------------------------------------------------------------------

_DIRS8 = ((-1, -1), (0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0))


def _guo_hall(masque):
    """Amincissement Guo-Hall -> squelette large de 1 pixel (booleen 2D).

    Guo-Hall, contrairement a Zhang-Suen, ne laisse pas de doubles
    diagonales sur les courbes pixelisees : le squelette d'un cercle est
    une boucle fermee propre, sans faux croisements.
    """
    m = np.pad(np.asarray(masque, bool), 2)
    if not m.any():
        return m[2:-2, 2:-2]
    for _ in range(200):                    # garde-fou : convergence garantie
        change = False
        for phase in (0, 1):
            p2 = m[:-2, 1:-1]; p3 = m[:-2, 2:]; p4 = m[1:-1, 2:]
            p5 = m[2:, 2:];  p6 = m[2:, 1:-1]; p7 = m[2:, :-2]
            p8 = m[1:-1, :-2]; p9 = m[:-2, :-2]
            connexe = ((~p2 & (p3 | p4)).astype(np.int8) + (~p4 & (p5 | p6))
                       + (~p6 & (p7 | p8)) + (~p8 & (p9 | p2)))
            n1 = ((p9 | p2).astype(np.int8) + (p3 | p4)
                  + (p5 | p6) + (p7 | p8))
            n2 = ((p2 | p3).astype(np.int8) + (p4 | p5)
                  + (p6 | p7) + (p8 | p9))
            nb = np.minimum(n1, n2)
            if phase == 0:
                bloque = (p6 | p7 | ~p9) & p8
            else:
                bloque = (p2 | p3 | ~p5) & p4
            suppr = m[1:-1, 1:-1] & (connexe == 1) & (nb >= 2) & (nb <= 3) & ~bloque
            if suppr.any():
                m[1:-1, 1:-1][suppr] = False
                change = True
        if not change:
            break
    return m[2:-2, 2:-2]


def _voisins8(px, p):
    """Voisins 8-connexes du pixel p dans l'ensemble px."""
    return [(p[0] + dx, p[1] + dy)
            for dx, dy in _DIRS8 if (p[0] + dx, p[1] + dy) in px]


def _elague(px, taille_max):
    """Supprime les epines du squelette (branches mortes <= taille_max px).

    Les croisements de traits laissent de petites branches parasites qui
    casseraient la fusion des chemins alignes.
    """
    change = True
    while change:
        change = False
        degres = {p: len(_voisins8(px, p)) for p in px}
        for bout in [p for p, d in degres.items() if d == 1]:
            if bout not in px:
                continue
            prec, cur = None, bout
            branche = [bout]
            while True:
                suiv = [q for q in _voisins8(px, cur) if q != prec]
                if not suiv:
                    break
                prec, cur = cur, suiv[0]
                branche.append(cur)
                if len(_voisins8(px, cur)) != 2:   # jonction atteinte
                    break
            if len(branche) - 1 <= taille_max:
                for p in branche[:-1]:
                    px.discard(p)
                change = True
    return px


def _chemins_squelette(px, rayon):
    """Squelette (ensemble de pixels) -> chemins elementaires du graphe.

    Les noeuds (croisements) proches sont regroupes en CLUSTERS de rayon
    donne : une zone de croisement sale compte pour UNE seule jonction.
    Retourne (chemins, etiquettes) ; chaque etiquette est
    (cluster du 1er pixel, cluster du dernier pixel) - None si pas de
    noeud (boucle fermee pure).
    """
    degres = {p: len(_voisins8(px, p)) for p in px}
    noeuds = {p for p, d in degres.items() if d != 2}

    clusters = []
    restants = set(noeuds)
    while restants:
        depart = next(iter(restants))
        cluster = {depart}
        pile = [depart]
        while pile:
            p = pile.pop()
            for q in list(restants):
                if (q not in cluster and abs(q[0] - p[0]) <= rayon
                        and abs(q[1] - p[1]) <= rayon):
                    cluster.add(q)
                    pile.append(q)
        restants -= cluster
        clusters.append(cluster)
    cluster_de = {}
    for idx, cl in enumerate(clusters):
        for p in cl:
            cluster_de[p] = idx

    def suis(depart, vers):
        prec, cur = depart, vers
        chemin = [depart, cur]
        while cur not in noeuds:
            suivants = [q for q in _voisins8(px, cur) if q != prec]
            if not suivants:
                break
            prec, cur = cur, suivants[0]
            chemin.append(cur)
        return chemin

    chemins, etiquettes = [], []
    vus = set()
    for n in noeuds:
        for v in _voisins8(px, n):
            if frozenset((n, v)) in vus:
                continue
            chemin = suis(n, v)
            if len(chemin) >= 2:
                if frozenset((chemin[-2], chemin[-1])) in vus:
                    continue          # deja parcouru dans l'autre sens
                vus.add(frozenset((n, v)))
                vus.add(frozenset((chemin[-2], chemin[-1])))
                chemins.append(chemin)
                etiquettes.append((cluster_de[chemin[0]], cluster_de[chemin[-1]]))

    # boucles fermees pures, sans aucun noeud (ex. cercle isole)
    traces = {p for ch in chemins for p in ch}
    restants2 = px - traces
    while restants2:
        depart = next(iter(restants2))
        prec, cur = None, depart
        chemin = [depart]
        while True:
            suivants = [q for q in _voisins8(px, cur)
                        if q != prec and q in restants2]
            if not suivants:
                break
            prec, cur = cur, suivants[0]
            chemin.append(cur)
            if cur == depart:
                break
        for p in chemin:
            restants2.discard(p)
        if len(chemin) >= 3:
            chemins.append(chemin)
            etiquettes.append((None, None))
    return chemins, etiquettes


def _rms_ligne(pts):
    """RMS des ecarts a la droite aux moindres carres (px).

    Contrairement a l'ecart maximal, le RMS ignore les marches d'escalier
    symetriques du squelette : un rayon trace en diagonale reste une ligne.
    """
    pts = np.asarray(pts, np.float64)
    if len(pts) < 2:
        return 1.0e9
    d = pts - pts.mean(axis=0)
    sxx = float(np.mean(d[:, 0] ** 2))
    syy = float(np.mean(d[:, 1] ** 2))
    sxy = float(np.mean(d[:, 0] * d[:, 1]))
    trace = sxx + syy
    if trace < 1.0e-12:
        return 1.0e9
    disc = float(np.sqrt(max(0.0, (sxx - syy) ** 2 + 4.0 * sxy * sxy)))
    return float(np.sqrt(max(0.0, (trace - disc) * 0.5)))


def _dir_fin(a, saut=3, fen=5):
    """Direction a la fin du chemin, hors zone de jonction (px)."""
    i1 = len(a) - 1 - saut
    i0 = max(0, i1 - fen)
    if i1 <= i0:
        i1, i0 = len(a) - 1, 0
    return (a[i1][0] - a[i0][0], a[i1][1] - a[i0][1])


def _dir_debut(b, saut=3, fen=5):
    """Direction au debut du chemin, hors zone de jonction (px)."""
    i0 = min(len(b) - 1, saut)
    i1 = min(len(b) - 1, i0 + fen)
    if i1 <= i0:
        i1, i0 = len(b) - 1, 0
    return (b[i1][0] - b[i0][0], b[i1][1] - b[i0][1])


def _virage(a, b):
    """Angle (degres) entre la fin de a et le debut de b."""
    ta, tb = _dir_fin(a), _dir_debut(b)
    na = float(np.hypot(ta[0], ta[1]))
    nb = float(np.hypot(tb[0], tb[1]))
    if na < 1.0e-9 or nb < 1.0e-9:
        return 180.0
    cosv = float(np.clip((ta[0] * tb[0] + ta[1] * tb[1]) / (na * nb), -1.0, 1.0))
    return float(np.degrees(np.arccos(cosv)))


def _virage_entre(a, b, k):
    """Virage selon la configuration k (0: fin-debut, 1: fin-fin,
    2: debut-debut, 3: debut-fin)."""
    if k == 0:
        return _virage(a, b)
    if k == 1:
        return _virage(a, b[::-1])
    if k == 2:
        return _virage(a[::-1], b)
    return _virage(a[::-1], b[::-1])


def _aligne(chemin):
    """Vrai si le chemin reste une DROITE ou un CERCLE (tolerances squelette)."""
    if _rms_ligne(chemin) <= config.SQUELETTE_LIGNE_RMS_PX:
        return True
    cercle = _fit_circle(chemin)
    return cercle is not None and cercle[3] <= config.ARC_TOL_PX


def _fusionne(chemins, etiquettes):
    """Fusionne les chemins alignes qui se touchent a une meme jonction.

    Deux rayons opposes d'une meme droite deviennent une seule LIGNE de
    2 points ; les arcs d'un meme cercle se recollent en un CERCLE complet.
    """
    chemins = [list(c) for c in chemins]
    bouts = [list(e) for e in etiquettes]
    virage_max = config.SQUELETTE_VIRAGE_DEG
    fusion = True
    while fusion:
        fusion = False
        for i in range(len(chemins)):
            j = i + 1
            while j < len(chemins):
                a, b = chemins[i], chemins[j]
                ca0, ca1 = bouts[i]
                cb0, cb1 = bouts[j]
                if None in (ca0, ca1, cb0, cb1):
                    j += 1
                    continue
                # k : 0 = fin a -> debut b ; 1 = fin a -> fin b ;
                #     2 = debut a -> debut b ; 3 = debut a -> fin b
                candidats = []
                if ca1 == cb0:
                    candidats.append((0, a + b[1:], ca0, cb1))
                if ca1 == cb1:
                    candidats.append((1, a + b[::-1][1:], ca0, cb0))
                if ca0 == cb0:
                    candidats.append((2, a[::-1] + b[1:], ca1, cb1))
                if ca0 == cb1:
                    candidats.append((3, a[::-1] + b[::-1][1:], ca1, cb0))
                ok = False
                for k, chemin, n0, n1 in candidats:
                    if _virage_entre(a, b, k) <= virage_max and _aligne(chemin):
                        chemins[i] = chemin
                        bouts[i] = [n0, n1]
                        chemins.pop(j)
                        bouts.pop(j)
                        fusion = True
                        ok = True
                        break
                if ok:
                    break
                j += 1
            if fusion:
                break
    return chemins


def _longueur(chemin):
    """Longueur developpee d'un chemin (px)."""
    pts = np.asarray(chemin, np.float64)
    if len(pts) < 2:
        return 0.0
    d = np.diff(pts, axis=0)
    return float(np.sum(np.hypot(d[:, 0], d[:, 1])))


def _primitive_squelette(chemin):
    """Chemin fusionne -> trajectoire : ligne 2 pts, cercle, arc ou angulaire."""
    pts = np.asarray(chemin, np.float64)
    if len(pts) < 2:
        return None
    ferme = float(np.hypot(pts[0][0] - pts[-1][0],
                           pts[0][1] - pts[-1][1])) <= 3.0
    if not ferme and _rms_ligne(pts) <= config.SQUELETTE_LIGNE_RMS_PX:
        return _to_traj("ligne", np.asarray([pts[0], pts[-1]], np.float64))
    cercle = _fit_circle(pts)
    if (cercle is not None and cercle[3] <= config.ARC_TOL_PX
            and cercle[2] >= config.MIN_TRAIT_PX * 0.5):
        cx, cy, r, _ = cercle
        angles = np.unwrap(np.arctan2(pts[:, 1] - cy, pts[:, 0] - cx))
        a0 = float(angles[0])
        sweep = float(angles[-1]) - a0
        if abs(sweep) < 0.1:
            sweep = 2.0 * np.pi
        if abs(sweep) >= np.radians(330.0):       # tour complet -> cercle
            a1 = a0 + 2.0 * np.pi * (1.0 if sweep >= 0 else -1.0)
            return _to_traj("cercle", _arc_points(cx, cy, r, a0, a1))
        if abs(sweep) >= np.radians(10.0):        # portion de cercle
            return _to_traj("arc", _arc_points(cx, cy, r, a0, a0 + sweep))
    libre = cv2.approxPolyDP(pts.reshape(-1, 1, 2).astype(np.float32),
                             1.0, False)
    libre = np.asarray(libre.reshape(-1, 2), np.float64)
    if len(libre) < 2:
        return None
    return _to_traj("angulaire", libre)


def _trajectoires_squelette(masque):
    """Composante 'dessin au trait' -> trajectoires des axes des traits (mm).

    Squelette -> epines elaguees -> chemins du graphe -> fusion des traits
    alignes -> primitive minimale par trait (ligne 2 points, cercle, arc).
    """
    squelette = _guo_hall(masque)
    px = {(int(x), int(y)) for y, x in np.argwhere(squelette)}
    if not px:
        return []
    px = _elague(px, config.SQUELETTE_ELAGUE_PX)
    chemins, etiquettes = _chemins_squelette(px, config.SQUELETTE_JONCTION_PX)
    # les chemins internes a une zone de jonction (deux bouts dans le meme
    # cluster) ne sont pas des traits : ce sont les debris du croisement
    garde = [(ch, et) for ch, et in zip(chemins, etiquettes)
             if not (et[0] is not None and et[0] == et[1])]
    chemins = _fusionne([g[0] for g in garde], [g[1] for g in garde])
    trajs = []
    for chemin in chemins:
        if _longueur(chemin) < config.MIN_TRAIT_PX:
            continue
        traj = _primitive_squelette(chemin)
        if traj is not None:
            trajs.append(traj)
    return trajs


def extract(bw):
    """Image binaire -> trajectoires [{"type": ..., "points": [...]}, ...] (mm).

    Les composantes FINES (dessin au trait : demi-epaisseur <=
    SQUELETTE_MAX_PX, ex. cercles entrelaces et leurs rayons) passent par le
    mode SQUELETTE : leurs traits sont suivis sur leur axe median et
    reduits aux primitives minimales. Les composantes EPAISSES gardent la
    logique des contours : forme, puis traits interieurs reellement
    dessines dans l'image (INNER_TRAJECTORIES), jamais de remplissage.
    """
    formes = _formes(bw)
    trajs = []
    etiquetes = set()
    labels = None
    if config.SQUELETTE_MAX_PX > 0:
        nb, labels = cv2.connectedComponents(formes)
        for lab in range(1, nb):
            masque = labels == lab
            if not masque.any():
                continue
            dist = cv2.distanceTransform(masque.astype(np.uint8),
                                         cv2.DIST_L2, 3)
            if float(dist.max()) <= config.SQUELETTE_MAX_PX:
                trajs.extend(_trajectoires_squelette(masque))
                etiquetes.add(int(lab))

    contours, hierarchy = cv2.findContours(formes, cv2.RETR_CCOMP,
                                           cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None or not len(contours):
        return trajs
    hier = hierarchy[0]
    for i, c in enumerate(contours):
        if hier[i][3] != -1:
            continue  # contour interne : trace juste apres son parent
        if labels is not None:
            x0, y0 = int(c[0][0][0]), int(c[0][0][1])
            if int(labels[y0, x0]) in etiquetes:
                continue  # composant squelettise : deja trace par son axe
        if _est_trait(c):
            _ajoute_trait(trajs, c)        # petit trait lineaire -> axe (2 points)
        else:
            _ajoute_contour(trajs, c)      # contour de la forme
        if not config.INNER_TRAJECTORIES:
            continue
        j = hier[i][2]                     # premier trait interieur
        while j != -1:
            trou = contours[j]
            if _distance_min(trou, c) >= config.INNER_MIN_GAP_PX:
                if _est_trait(trou):
                    _ajoute_trait(trajs, trou)     # petit trait lineaire interieur
                elif cv2.contourArea(trou) >= config.MIN_AREA_PX:
                    _ajoute_contour(trajs, trou)   # trait interieur de l'image
            j = hier[j][0]                          # trait interieur suivant
    return trajs


# couleurs de l'apercu (BGR)
_COULEURS = {"cercle": (196, 128, 255), "arc": (196, 128, 255),
             "mixte": (255, 215, 94), "angulaire": (77, 163, 255),
             "ligne": (77, 163, 255)}


def overlay(bw, trajs):
    """Dessine les trajectoires sur l'image (pour la page web)."""
    vis = cv2.cvtColor(bw, cv2.COLOR_GRAY2BGR)
    for traj in trajs:
        pts = np.array([[int(p["x"] / config.SCALE_MM_PER_PX),
                         int(p["y"] / config.SCALE_MM_PER_PX)]
                        for p in traj["points"]], np.int32)
        if len(pts) < 2:
            continue
        cv2.polylines(vis, [pts], False,
                      _COULEURS.get(traj["type"], (77, 163, 255)), 2)
        cv2.circle(vis, (int(pts[0][0]), int(pts[0][1])), 4, (61, 220, 132), -1)
    return vis
