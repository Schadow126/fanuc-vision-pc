# -*- coding: utf-8 -*-
"""
CODE 2 - Extraction des points et trajectoires.

Recoit l'image noire et blanche du code 1, detecte les contours des formes
(les formes sont supposees sombres sur fond clair), simplifie chaque contour
(approxPolyDP) et convertit les pixels en millimetres via l'etalonnage
(SCALE_MM_PER_PX). Produit une liste de trajectoires : chaque trajectoire est
une liste de points X Y Z W P R (Z et orientation constants, repere UFRAME
du programme TP).
"""
import cv2


def extract(bw, scale_mm_per_px, z_mm, w_deg, p_deg, r_deg, min_area_px):
    """Image binaire -> liste de trajectoires [[{x,y,z,w,p,r},...],...]."""
    # Les formes etant sombres : on cherche les contours sur l'inverse.
    contours, _ = cv2.findContours(255 - bw, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    trajs = []
    for c in contours:
        if cv2.contourArea(c) < min_area_px:
            continue  # ignore le bruit et les trop petites taches
        # Simplification du contour : 1 % du perimetre
        eps = 0.01 * cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, eps, True)
        traj = []
        for point in approx:
            px, py = int(point[0][0]), int(point[0][1])
            traj.append({
                "x": round(px * scale_mm_per_px, 2),
                "y": round(py * scale_mm_per_px, 2),
                "z": z_mm,
                "w": w_deg, "p": p_deg, "r": r_deg,
            })
        if len(traj) > 1:
            traj.append(dict(traj[0]))  # ferme la boucle : retour au depart
            trajs.append(traj)
    return trajs


def overlay(bw, trajs, scale_mm_per_px):
    """Dessine les trajectoires sur l'image pour la previsualisation web."""
    import numpy as np
    vis = cv2.cvtColor(bw, cv2.COLOR_GRAY2BGR)
    inv = 1.0 / max(scale_mm_per_px, 1e-6)
    for traj in trajs:
        pts = np.array(
            [[int(pt["x"] * inv), int(pt["y"] * inv)] for pt in traj],
            dtype=np.int32)
        cv2.polylines(vis, [pts], False, (77, 163, 255), 2)
        cv2.circle(vis, tuple(pts[0]), 4, (61, 220, 132), -1)
    return vis
