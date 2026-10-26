"""
vision_processing.py - capture XC-56, comparaison a la reference, calcul du point.

Etapes :
1. capture d'une image depuis le frame grabber ;
2. comparaison avec l'image de reference (template matching) ;
3. conversion de l'ecart pixels -> mm via la matrice d'etalonnage ;
4. composition du point X,Y,Z,W,P,R dans l'UFRAME.
"""
import logging

import cv2
import numpy as np

import config

log = logging.getLogger("vision")


class Vision:
    def __init__(self) -> None:
        self.cap = cv2.VideoCapture(config.CAMERA_INDEX)
        if not self.cap.isOpened():
            raise RuntimeError("Impossible d'ouvrir la camera (index %d)" % config.CAMERA_INDEX)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_W)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_H)
        self.reference = cv2.imread(config.REFERENCE_IMAGE, cv2.IMREAD_GRAYSCALE)
        if self.reference is None:
            raise FileNotFoundError(
                "Image de reference absente : %s "
                "(placez le robot en position parfaite et lancez 'python main.py --save-ref')"
                % config.REFERENCE_IMAGE
            )
        self.calib = np.array(config.CALIB_MATRIX, dtype=np.float64)

    # ------------------------------------------------------------ capture
    def grab(self):
        """Capture en niveaux de gris, apres stabilisation du signal analogique."""
        for _ in range(config.CAPTURE_WARMUP):
            self.cap.grab()
        ret, frame = self.cap.read()
        if not ret or frame is None:
            raise RuntimeError("Echec de capture camera")
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    def save_reference(self, path=None) -> None:
        """Enregistre l'image courante comme reference (position 'parfaite')."""
        if path is None:
            path = config.REFERENCE_IMAGE
        cv2.imwrite(path, self.grab())
        log.info("Nouvelle image de reference enregistree : %s", path)

    # ---------------------------------------------------------- analyse
    def compute_offset(self, frame):
        """
        Correle la piece avec la reference et retourne l'ecart (dx, dy, dtheta) :
        dx/dy en mm (UFRAME), dtheta en degres autour de Z.
        Retourne None si la correlation est trop faible.
        """
        best = (-1.0, 0, 0, 0.0)  # score, dx_px, dy_px, angle
        for angle in np.arange(-15, 15.1, 1.0):  # rotation supposee petite
            rot = self._rotate(self.reference, angle)
            res = cv2.matchTemplate(frame, rot, cv2.TM_CCOEFF_NORMED)
            _, score, _, loc = cv2.minMaxLoc(res)
            if score > best[0]:
                best = (score, loc[0], loc[1], angle)

        score, x_px, y_px, theta = best
        log.info("Correlation=%.3f  dx_px=%d  dy_px=%d  theta=%.1f deg",
                 score, x_px, y_px, theta)
        if score < config.MATCH_THRESHOLD:
            return None

        # pixels -> mm (matrice d'etalonnage : [u v 1] * Calib)
        vec = np.array([x_px, y_px, 1.0]) @ self.calib.T
        return vec[0], vec[1], float(theta)

    @staticmethod
    def _rotate(img, angle):
        h, w = img.shape[:2]
        m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_LINEAR,
                              borderValue=0)

    # ------------------------------------------------------------- point
    def build_point(self, offset):
        """Compose le point X,Y,Z,W,P,R dans l'UFRAME, avec garde-fou."""
        dx, dy, dtheta = offset
        if abs(dx) > config.MAX_CORRECTION_MM or abs(dy) > config.MAX_CORRECTION_MM:
            raise ValueError("Correction hors limite (%.1f, %.1f mm)" % (dx, dy))
        w, p, r = config.DEFAULT_WPR
        return (dx, dy, config.Z_HEIGHT, w, p, r + dtheta)
