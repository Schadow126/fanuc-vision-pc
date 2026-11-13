# -*- coding: utf-8 -*-
"""
CODE 1 - Traitement d'image : conversion en noir et blanc.

Couleur -> carte "distance au blanc" (255 - canal le plus clair) : tout ce
qui n'est pas blanc/ivoire est de l'ENCRE, quelle que soit sa couleur. Un
passage en niveaux de gris perdrait les couleurs claires : le jaune vaut
~217 en gris et le rouge clair ~167, ils se fondent alors dans le fond
blanc (252). La carte rend l'histogramme nettement bimodal (papier ~0,
encre ~100-255), le seuil automatique d'Otsu tombe donc au bon endroit ;
le flou reduit le bruit et le median supprime les pixels isoles.

Resultat : blanc = fond, noir = objets.
"""
import cv2

import config


def to_bw(bgr):
    """Image couleur BGR -> image binaire noir et blanc."""
    if bgr.ndim == 2:
        carte = 255 - bgr
    else:
        carte = 255 - bgr.min(axis=2)   # distance au blanc (canal le plus clair)
    carte = cv2.GaussianBlur(carte, (5, 5), 0)
    _, bw = cv2.threshold(carte, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    if config.BW_MEDIAN_PX >= 3:
        bw = cv2.medianBlur(bw, config.BW_MEDIAN_PX)   # pixels isoles du seuillage
    return bw
