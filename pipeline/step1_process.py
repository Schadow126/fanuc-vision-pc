# -*- coding: utf-8 -*-
"""
CODE 1 - step1_process.py
Traite l'image deposee sur la page web et la met en noir et blanc
(carte "distance au blanc" -> seuillage automatique d'Otsu -> nettoyage).

Entree : work/uploaded.png (image deposee)
Sortie : work/bw.png        (image binaire noir et blanc)
"""

import cv2

import step1_bw


def process_to_bw(input_path, output_path):
    """Couleur -> carte distance au blanc -> Otsu : blanc = fond, noir = objets."""
    img = cv2.imread(str(input_path))
    if img is None:
        raise RuntimeError("image introuvable : " + str(input_path))
    bw = step1_bw.to_bw(img)
    cv2.imwrite(str(output_path), bw)
    return {"width": int(bw.shape[1]), "height": int(bw.shape[0])}
