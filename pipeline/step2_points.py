# -*- coding: utf-8 -*-
"""
CODE 2 - step2_points.py
Recupere l'image traitee (noir et blanc) et cree les points et trajectoires.

Methode : les objets sont les zones sombres de l'image binaire. Pour chaque
contour, on echantillonne des points tous les ~step_px pixels, on convertit
pixels -> millimetres avec l'etalonnage SCALE_MM_PER_PX, et on referme la
boucle (le dernier point = le premier).

Entree : work/bw.png
Sortie : work/points.json (trajectoires {x,y,z,w,p,r}) + work/traj.png (apercu)
"""

import json
import cv2
import numpy as np
from pathlib import Path


def extract_points(bw_path, out_json, out_preview,
                   scale_mm_per_px=0.1, z_mm=10.0, step_px=40,
                   w=180.0, p=0.0, r=0.0, min_area_px=50):
    bw = cv2.imread(str(bw_path), cv2.IMREAD_GRAYSCALE)
    if bw is None:
        raise RuntimeError("image N&B introuvable : " + str(bw_path))

    # Objets sombres -> contours externes
    _, inv = cv2.threshold(bw, 127, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    h, wpx = bw.shape[:2]
    cx_img, cy_img = wpx / 2.0, h / 2.0   # origine au centre de l'image

    trajectories = []
    preview = cv2.cvtColor(bw, cv2.COLOR_GRAY2BGR)
    n_points = 0

    for tid, cnt in enumerate(contours, start=1):
        if cv2.contourArea(cnt) < min_area_px:
            continue
        total = len(cnt)
        n = max(2, total // max(1, step_px))
        idxs = [int(i * total / n) % total for i in range(n)]

        pts = []
        for i in idxs:
            px, py = cnt[i][0]
            x = (px - cx_img) * scale_mm_per_px
            y = (cy_img - py) * scale_mm_per_px   # axe image y vers le bas
            pts.append([round(x, 3), round(y, 3), z_mm, w, p, r])
        pts.append(list(pts[0]))                  # boucle fermee
        n_points += len(pts)
        trajectories.append({"id": tid, "points": pts})

        cv2.drawContours(preview, [cnt], -1, (0, 200, 255), 2)
        for i in idxs:
            px, py = cnt[i][0]
            cv2.circle(preview, (px, py), 3, (0, 140, 255), -1)

    data = {
        "trajectories": trajectories,
        "scale_mm_per_px": scale_mm_per_px,
        "z_mm": z_mm,
        "source_image": str(Path(bw_path).name),
    }
    Path(out_json).write_text(json.dumps(data, indent=2), encoding="utf-8")
    cv2.imwrite(str(out_preview), preview)
    return {"n_trajectories": len(trajectories), "n_points": n_points}


def load_points(points_json):
    return json.loads(Path(points_json).read_text(encoding="utf-8"))
