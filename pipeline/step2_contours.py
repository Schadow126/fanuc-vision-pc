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

L'INTERIEUR des formes peut etre remplit de hachures (FILL_SHAPES=1) :
zigzag de traits droits, une trajectoire "hachure" par trait ; le stylo
se leve entre deux traits (Z_TRAVEL_MM).

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


def _arc_points(cx, cy, r, a0, a1):
    """Points d'un arc de a0 a a1 (radians), corde max ARC_CHORD_MM."""
    r_px = max(r, 1.0)
    chord_px = max(config.ARC_CHORD_MM / config.SCALE_MM_PER_PX, 0.5)
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


def _segment_primitive(seg):
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
                                          float(angles[0]), float(angles[-1])))
    libre = cv2.approxPolyDP(seg.reshape(-1, 1, 2).astype(np.float32),
                             max(config.ARC_TOL_PX, 1.0), False)
    return ("angulaire", np.asarray(libre.reshape(-1, 2), np.float64))


def _greedy_primitives(pts):
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
                                               float(angles[0]), float(angles[-1])))
                    end = last
                    continue
            break  # plus rien ne s'ajuste : la primitive precedente est retenue
        if best is None:
            return None
        primitives.append(best)
        start = end
    return primitives


def _primitives(pts):
    """Contour ferme (px) -> primitives [(type, tableau de points px), ...]."""
    circle = _fit_circle(pts)

    # 1) CERCLE complet (ajustement propre + ouverture proche de 360 degres)
    if circle is not None:
        cx, cy, r, rms = circle
        if rms <= config.ARC_TOL_PX and _span(pts, cx, cy) >= np.radians(330.0):
            a0 = float(np.arctan2(pts[0, 1] - cy, pts[0, 0] - cx))
            return [("cercle", _arc_points(cx, cy, r, a0, a0 + 2.0 * np.pi))]

    # 2) ANGLES : decoupage du contour puis ligne / arc sur chaque portion
    corners = _corner_indices(pts)
    if len(corners) >= 2:
        return [_segment_primitive(seg) for seg in _segments(pts, corners)]

    # 3) Pas d'angle marque : suite gloutonne d'arcs/lignes, sinon polygone
    greedy = _greedy_primitives(pts)
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


def _hachures(outline_px):
    """Traits droits zigzag pour remplir l'INTERIEUR de la forme (px)."""
    if not config.FILL_SHAPES or len(outline_px) < 3:
        return []
    step_px = max(config.HATCH_SPACING_MM / config.SCALE_MM_PER_PX, 2.0)
    angle = np.radians(config.HATCH_ANGLE_DEG)
    rot = np.array([[np.cos(angle), -np.sin(angle)],
                    [np.sin(angle), np.cos(angle)]])
    centre = outline_px.mean(axis=0)
    poly = (outline_px - centre) @ rot.T  # hachures "horizontales" dans ce repere
    y_min = float(poly[:, 1].min())
    y_max = float(poly[:, 1].max())
    if y_max - y_min < 2.0 * step_px:
        return []  # forme trop plate pour etre hachuree
    strokes = []
    flip = 0
    y = y_min + 0.5 * step_px
    while y < y_max:
        crossings = []
        for i in range(len(poly)):
            a = poly[i]
            b = poly[(i + 1) % len(poly)]
            if (a[1] <= y < b[1]) or (b[1] <= y < a[1]):
                t = (y - a[1]) / (b[1] - a[1])
                crossings.append(a[0] + t * (b[0] - a[0]))
        crossings.sort()
        for m in range(0, len(crossings) - 1, 2):  # regle pair / impair
            x0 = crossings[m]
            x1 = crossings[m + 1]
            if x1 - x0 < 2.0:
                continue
            if flip % 2:
                x0, x1 = x1, x0  # zigzag : sens alterne d'un trait au suivant
            strokes.append(np.array([[x0, y], [x1, y]]) @ rot + centre)
            flip += 1
        y += step_px
    return strokes


def _to_traj(label, pts_px):
    """Points en pixels -> trajectoire en mm (dictionnaire)."""
    points = [{"x": round(float(x) * config.SCALE_MM_PER_PX, 2),
               "y": round(float(y) * config.SCALE_MM_PER_PX, 2),
               "z": config.Z_MM, "w": config.W_DEG,
               "p": config.P_DEG, "r": config.R_DEG}
              for x, y in np.asarray(pts_px, np.float64)]
    return {"type": label, "points": points}


def extract(bw):
    """Image binaire -> trajectoires [{"type": ..., "points": [...]}, ...] (mm)."""
    contours, _ = cv2.findContours(_formes(bw), cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    trajs = []
    for c in contours:
        if cv2.contourArea(c) < config.MIN_AREA_PX:
            continue  # trop petit : bruit
        pts = c.reshape(-1, 2).astype(np.float64)
        if len(pts) < 3:
            continue
        built = _assemble(_primitives(pts))
        if built is None:
            continue
        label, outline = built
        trajs.append(_to_traj(label, outline))   # contour de la forme
        for stroke in _hachures(outline):         # interieur (hachures)
            trajs.append(_to_traj("hachure", stroke))
    return trajs


# couleurs de l'apercu (BGR)
_COULEURS = {"cercle": (196, 128, 255), "arc": (196, 128, 255),
             "mixte": (255, 215, 94), "angulaire": (77, 163, 255),
             "ligne": (77, 163, 255), "hachure": (80, 220, 120)}


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
