#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fanuc_vision_pc - Serveur web orchestrant le pipeline complet :

    CODE 1  page web : depot d'image  ->  noir et blanc        (pipeline/step1_process.py)
    CODE 2  image N&B -> points et trajectoires                (pipeline/step2_points.py)
    CODE 3  points -> trames ASCII -> R-30iB Mate (socket)    (pipeline/step3_ascii.py)
    CODE 4  photo camera XC-56 -> comparaison -> correction   (pipeline/step4_verify.py)
            (renvoi au CODE 3 uniquement si le S7-1500 autorise)

Usage :
    pip install -r requirements.txt   (opencv-python, numpy)
    ROBOT_IP=192.168.1.10 python app.py

Variables d'environnement :
    ROBOT_IP / ROBOT_PORT   controleur FANUC (defaut 192.168.1.10:59002)
    CAMERA_INDEX            index OpenCV de la XC-56 / frame grabber (defaut 0)
    SCALE_MM_PER_PX         etalonnage camera, mm par pixel (defaut 0.1)
    ERROR_LIMIT_PCT         seuil de correction (defaut 10)
    PLC_MODE                demo | file | socket  (autorisation S7-1500)
    WEB_PORT                port du serveur web (defaut 8080)

Points d'entree HTTP :
    GET  /                 page web (depot d'image + pipeline)
    GET  /api/config       configuration (JSON)
    GET  /api/plc          autorisation S7-1500 (JSON)
    GET  /files/<f>        images de travail (bw.png, traj.png, camera.png)
    POST /api/process      (upload multipart) CODE 1 : image -> N&B
    POST /api/generate     CODE 2 : N&B -> points/trajectoires
    POST /api/send         CODE 3 : points -> ASCII -> robot (si PLC OK)
    POST /api/verify       CODE 4 : photo XC-56 -> comparaison -> correction
"""

import json
import os
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import plc
from pipeline import step1_process, step2_points, step3_ascii, step4_verify

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
WORK_DIR = BASE_DIR / "work"
WORK_DIR.mkdir(exist_ok=True)

ROBOT_IP = os.environ.get("ROBOT_IP", "192.168.1.10")
ROBOT_PORT = int(os.environ.get("ROBOT_PORT", "59002"))
WEB_PORT = int(os.environ.get("WEB_PORT", "8080"))
CAMERA_INDEX = int(os.environ.get("CAMERA_INDEX", "0"))
SCALE_MM_PER_PX = float(os.environ.get("SCALE_MM_PER_PX", "0.1"))
ERROR_LIMIT_PCT = float(os.environ.get("ERROR_LIMIT_PCT", "10"))
SOCKET_TIMEOUT = float(os.environ.get("SOCKET_TIMEOUT", "5"))

UPLOADED = WORK_DIR / "uploaded.png"
BW_IMG = WORK_DIR / "bw.png"
TRAJ_PREVIEW = WORK_DIR / "traj.png"
POINTS_JSON = WORK_DIR / "points.json"
CAMERA_IMG = WORK_DIR / "camera.png"


def parse_multipart(body, content_type):
    """Extrait le premier fichier d'un corps multipart/form-data."""
    m = re.search(r"boundary=(.+)$", content_type or "")
    if not m:
        return None
    boundary = m.group(1).strip('"').encode("ascii")
    for part in body.split(b"--" + boundary):
        if b"filename=" not in part:
            continue
        header, _, content = part.partition(b"\r\n\r\n")
        content = content.rsplit(b"\r\n", 1)[0]
        if content.endswith(b"--"):
            content = content[:-1]
        fm = re.search(rb'filename="([^"]*)"', header)
        return {
            "filename": fm.group(1).decode("utf-8", "replace") if fm else "upload.png",
            "data": content,
        }
    return None


class Handler(BaseHTTPRequestHandler):
    server_version = "FanucVisionPC/1.0"

    # ---------- utilitaires ----------

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path, ctype):
        try:
            data = path.read_bytes()
        except OSError:
            return self._json(404, {"ok": False, "error": "fichier introuvable"})
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(length)

    # ---------- routes ----------

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            return self._file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
        if path == "/api/config":
            return self._json(200, {
                "robot_ip": ROBOT_IP, "robot_port": ROBOT_PORT,
                "web_port": WEB_PORT, "camera_index": CAMERA_INDEX,
                "scale_mm_per_px": SCALE_MM_PER_PX,
                "error_limit_pct": ERROR_LIMIT_PCT,
            })
        if path == "/api/plc":
            return self._json(200, {"ok": True, "plc": plc.status()})
        if path.startswith("/files/"):
            name = os.path.basename(path[len("/files/"):])
            ctype = "image/png" if name.endswith(".png") else "application/octet-stream"
            return self._file(WORK_DIR / name, ctype)
        return self._json(404, {"ok": False, "error": "introuvable"})

    def do_POST(self):
        path = urlparse(self.path).path

        # --- CODE 1 : depot d'image -> noir et blanc ---
        if path == "/api/process":
            up = parse_multipart(self._body(), self.headers.get("Content-Type", ""))
            if not up or not up["data"]:
                return self._json(400, {"ok": False, "error": "aucune image recue"})
            UPLOADED.write_bytes(up["data"])
            try:
                dims = step1_process.process_to_bw(UPLOADED, BW_IMG)
            except Exception as exc:
                return self._json(200, {"ok": False, "error": str(exc)})
            return self._json(200, {"ok": True, "code": 1,
                                     "bw_url": "files/bw.png", "dims": dims})

        # --- CODE 2 : N&B -> points et trajectoires ---
        if path == "/api/generate":
            if not BW_IMG.exists():
                return self._json(200, {"ok": False,
                                        "error": "deposez d'abord une image (code 1)"})
            try:
                stats = step2_points.extract_points(
                    BW_IMG, POINTS_JSON, TRAJ_PREVIEW,
                    scale_mm_per_px=SCALE_MM_PER_PX)
            except Exception as exc:
                return self._json(200, {"ok": False, "error": str(exc)})
            return self._json(200, {"ok": True, "code": 2, "stats": stats,
                                    "preview_url": "files/traj.png"})

        # --- CODE 3 : points -> ASCII -> robot (si S7-1500 autorise) ---
        if path == "/api/send":
            if not POINTS_JSON.exists():
                return self._json(200, {"ok": False,
                                        "error": "generer d'abord les points (code 2)"})
            if not plc.is_send_authorized():
                return self._json(200, {"ok": False, "blocked_by": "S7-1500",
                                        "error": "envoi refuse : le S7-1500 n'autorise pas"})
            points = json.loads(POINTS_JSON.read_text(encoding="utf-8"))
            try:
                send = step3_ascii.send_all(points, ROBOT_IP, ROBOT_PORT,
                                            timeout=SOCKET_TIMEOUT)
            except OSError as exc:
                return self._json(200, {"ok": False,
                                        "error": "connexion robot impossible : " + str(exc)})
            return self._json(200, {"ok": True, "code": 3,
                                    "sent": send["sent"], "acks": send["acks"]})

        # --- CODE 4 : photo XC-56 -> comparaison -> correction ---
        if path == "/api/verify":
            if not BW_IMG.exists():
                return self._json(200, {"ok": False,
                                        "error": "deposez d'abord une image (code 1)"})
            try:
                result = step4_verify.run(
                    BW_IMG, CAMERA_INDEX, WORK_DIR, POINTS_JSON,
                    ROBOT_IP, ROBOT_PORT, ERROR_LIMIT_PCT,
                    is_authorized=plc.is_send_authorized,
                    scale_mm_per_px=SCALE_MM_PER_PX,
                    timeout=SOCKET_TIMEOUT)
            except Exception as exc:
                return self._json(200, {"ok": False, "error": str(exc)})
            result["ok"] = True
            result["code"] = 4
            return self._json(200, result)

        return self._json(404, {"ok": False, "error": "introuvable"})

    def log_message(self, fmt, *args):
        print("[%s] %s" % (time.strftime("%H:%M:%S"), fmt % args))


def main():
    if not (STATIC_DIR / "index.html").exists():
        raise SystemExit("static/index.html introuvable a cote de app.py")
    print("=" * 66)
    print(" Serveur web       : http://0.0.0.0:" + str(WEB_PORT))
    print(" Controleur FANUC  : " + ROBOT_IP + ":" + str(ROBOT_PORT))
    print(" Camera XC-56      : index " + str(CAMERA_INDEX) +
          " | etalonnage " + str(SCALE_MM_PER_PX) + " mm/px")
    print(" Seuil correction  : " + str(ERROR_LIMIT_PCT) + " %")
    print(" PLC_MODE          : " + os.environ.get("PLC_MODE", "demo"))
    print("=" * 66)
    ThreadingHTTPServer(("0.0.0.0", WEB_PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
