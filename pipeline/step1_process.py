# -*- coding: utf-8 -*-
"""
CODE 1 - step1_process.py
Traite l'image deposee sur la page web et la met en noir et blanc
(niveaux de gris -> seuillage automatique d'Otsu -> image binaire N&B).

Entree : work/uploaded.png (image deposee)
Sortie : work/bw.png        (image binaire noir et blanc)
"""

import cv2
import numpy as np
from pathlib import Path


def process_to_bw(input_path, output_path):
    """Gris -> flou -> seuillage Otsu : blanc = fond, noir = objets."""
    img = cv2.imread(str(input_path))
    if img is None:
        raise RuntimeError("image introuvable : " + str(input_path))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, bw = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    cv2.imwrite(str(output_path), bw)
    return {"width": int(bw.shape[1]), "height": int(bw.shape[0])}
