#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Calcul du code 2 en direct (pour Visual Studio Code).

Usage :
    python pipeline/debug_step2.py [image.png]

Charge l'image, applique le code 1 (noir et blanc), extrait les formes
(code 2), sauvegarde les apercus (uploads/bw.png, uploads/preview.png)
et affiche la trame ASCII que le code 3 enverrait au robot.

Pour deboguer pas a pas dans VS Code : Run and Debug ->
"Code 2 : calcul des formes", placer des points d'arret dans
step2_contours.py (extract) ou step3_ascii.py (frame_for).
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "pipeline"))
Path(BASE_DIR / "uploads").mkdir(exist_ok=True)

import cv2  # noqa: E402

import step1_bw  # noqa: E402
import step2_contours  # noqa: E402
import step3_ascii  # noqa: E402


def main():
    img_path = sys.argv[1] if len(sys.argv) > 1 else str(BASE_DIR / "uploads/design.png")
    img = cv2.imread(img_path)
    if img is None:
        print("Image introuvable :", img_path)
        print("Deposez d'abord une image via la page web, ou donnez un chemin :")
        print("    python pipeline/debug_step2.py mon_image.png")
        return

    print("Image :", img_path, "(", img.shape[1], "x", img.shape[0], "px )")

    bw = step1_bw.to_bw(img)                       # CODE 1
    cv2.imwrite(str(BASE_DIR / "uploads/bw.png"), bw)

    trajs = step2_contours.extract(bw)             # CODE 2
    print("Trajectoires :", len(trajs),
          "   Points totaux :", sum(len(t["points"]) for t in trajs))
    for i, traj in enumerate(trajs):
        pts = traj["points"]
        print("  Traj", i + 1, "(", traj["type"], ") :", len(pts), "points ->",
              [(p["x"], p["y"]) for p in pts[:3]], "...")

    cv2.imwrite(str(BASE_DIR / "uploads/preview.png"),
                step2_contours.overlay(bw, trajs))
    print("Apercus sauvegardes : uploads/bw.png et uploads/preview.png")

    print("")                                      # CODE 3 (affichage seul)
    print("Trame ASCII qui serait envoyee au robot :")
    print(step3_ascii.frame_for(trajs).replace("\r\n", "\n"))


if __name__ == "__main__":
    main()
