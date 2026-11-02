# -*- coding: utf-8 -*-
"""
CODE 1 - Traitement d'image : conversion en noir et blanc.

Gris -> flou (reduit le bruit) -> seuil automatique d'Otsu.
"""
import cv2


def to_bw(bgr):
    """Image couleur BGR -> image binaire noir et blanc."""
    gray = cv2.GaussianBlur(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return bw
