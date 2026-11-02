# -*- coding: utf-8 -*-
"""
CODE 2 - Extraction des points et trajectoires.

Contours des formes sombres, simplification, conversion px -> mm.
Chaque trajectoire est fermee (retour au point de depart).
"""
import cv2
import numpy as np

import config


def extract(bw):
    """Image binaire -> liste de trajectoires [[{x,y,z,w,p,r},...],...]."""
    contours, _ = cv2.findContours(255 - bw, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    trajs = []
    for c in contours:
        if cv2.contourArea(c) < config.MIN_AREA_PX:
            continue  # trop petit : bruit
        poly = cv2.approxPolyDP(c, 0.01 * cv2.arcLength(c, True), True)
        traj = [{"x": round(int(x) * config.SCALE_MM_PER_PX, 2),
                 "y": round(int(y) * config.SCALE_MM_PER_PX, 2),
                 "z": config.Z_MM, "w": config.W_DEG,
                 "p": config.P_DEG, "r": config.R_DEG}
                for x, y in poly.reshape(-1, 2)]
        if len(traj) > 1:
            trajs.append(traj + [dict(traj[0])])  # ferme la boucle
    return trajs


def overlay(bw, trajs):
    """Dessine les trajectoires sur l'image (pour la page web)."""
    vis = cv2.cvtColor(bw, cv2.COLOR_GRAY2BGR)
    for traj in trajs:
        pts = np.array([[int(pt["x"] / config.SCALE_MM_PER_PX),
                         int(pt["y"] / config.SCALE_MM_PER_PX)]
                        for pt in traj], np.int32)
        cv2.polylines(vis, [pts], False, (77, 163, 255), 2)
        cv2.circle(vis, tuple(pts[0]), 4, (61, 220, 132), -1)
    return vis
