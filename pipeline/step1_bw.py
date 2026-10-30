# -*- coding: utf-8 -*-
"""
CODE 1 - Traitement d'image : conversion en noir et blanc.

Recoit l'image deposee sur la page web, la convertit en niveaux de gris,
applique un flou pour reduire le bruit, puis une binarisation automatique
(seuil d'Otsu). Le resultat est l'image "de reference" utilisee par les
etapes suivantes.
"""
import cv2


def to_bw(bgr):
    """Image couleur BGR -> image binaire noir et blanc (blanc = fond)."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return bw
