#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fanuc_vision_pc - Serveur web de la cellule vision + robot FANUC.

Pipeline en 4 etapes (voir pipeline/) :
    1. depose d'une image -> traitement noir et blanc      (step1_bw)
    2. extraction des points et trajectoires des formes    (step2_contours)
    3. conversion ASCII + envoi au R-30iB Mate              (step3_ascii)
    4. photo camera Sony XC-56, comparaison, correction    (step4_verify)
       (envoi au robot seulement si la S7-1500 l'autorise)

Usage :
    pip install -r requirements.txt
    ROBOT_IP=192.168.1.10 python app.py
"""

import base64
import io
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
sys.path.insert(0, str(BASE_DIR))

import cv2  # noqa: E402
import config  # noqa: E402
import step1_bw  # noqa: E402
import step2_contours  # noqa: E402
import step3_ascii  # noqa: E402
import step4_verify  # noqa: E402
import plc  # noqa: E402

ORIG_PNG = UPLOAD_DIR / "design.png"
BW_PNG = UPLOAD_DIR / "bw.png"
STATE_FILE = UPLOAD_DIR / "state.json"

LOCK = threading.Lock()
STATE = {"trajs": [], "bw_ok": False}

MAX_BODY = 20 * 1024 * 1024  # 20 Mo max par image


def _b64_png(img):
    ok, buf = cv2.imencode(".png", img)
    return base64.b64encode(buf.tobytes()).decode("ascii") if ok else None


def _read_body_json(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    return json.loads(handler.rfile.read(length) or b"{}")


def do_upload(raw):
    img = cv2.imdecode(bytearray(raw), cv2.IMREAD_COLOR)
    if img is None:
        return {"ok": False, "error": "format d'image non supporte (PNG/JPG)"}
    cv2.imwrite(str(ORIG_PNG), img)
    STATE["bw_ok"] = False
    STATE["trajs"] = []
    return {"ok": True, "w": img.shape[1], "h": img.shape[0]}


def do_process():
    img = cv2.imread(str(ORIG_PNG))
    if img is None:
        return {"ok": False, "error": "aucune image deposee"}
    bw = step1_bw.to_bw(img)
    cv2.imwrite(str(BW_PNG), bw)
    STATE["bw_ok"] = True
    STATE["trajs"] = []
    return {"ok": True, "image": _b64_png(bw)}


def do_contours():
    bw = cv2.imread(str(BW_PNG), cv2.IMREAD_GRAYSCALE)
    if bw is None:
        return {"ok": False, "error": "etape 1 (noir et blanc) non faite"}
    trajs = step2_contours.extract(
        bw, config.SCALE_MM_PER_PX, config.Z_MM,
        config.W_DEG, config.P_DEG, config.R_DEG, config.MIN_AREA_PX)
    STATE["trajs"] = trajs
    vis = step2_contours.overlay(bw, trajs, config.SCALE_MM_PER_PX)
    STATE_FILE.write_text(json.dumps(
        {"trajs": trajs}), encoding="utf-8")
    return {"ok": True,
            "trajectories": len(trajs),
            "points": sum(len(t) for t in trajs),
            "image": _b64_png(vis)}


def do_send_path():
    trajs = STATE["trajs"]
    if not trajs:
        return {"ok": False, "error": "etape 2 (trajectoires) non faite"}
    if not plc.is_authorized():
        return {"ok": False, "error": "envoi refuse : la S7-1500 n'autorise pas"}
    try:
        replies = step3_ascii.send_path(trajs, config.ROBOT_IP, config.ROBOT_PORT)
        return {"ok": True, "sent": len(trajs), "robot": replies}
    except OSError as exc:
        return {"ok": False, "error": "connexion au robot impossible : " + str(exc)}


def do_verify():
    bw = cv2.imread(str(BW_PNG), cv2.IMREAD_GRAYSCALE)
    if bw is None:
        return {"ok": False, "error": "etape 1 (noir et blanc) non faite"}
    try:
        result = step4_verify.run(bw)
    except OSError as exc:
        return {"ok": False, "error": "erreur camera/reseau : " + str(exc)}
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = "FanucVisionPC/1.1"

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

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            page = (STATIC_DIR / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self._cors()
            self.end_headers()
            self.wfile.write(page)
        elif self.path == "/api/config":
            self._json(200, {
                "robot_ip": config.ROBOT_IP, "robot_port": config.ROBOT_PORT,
                "web_port": config.WEB_PORT,
                "scale_mm_per_px": config.SCALE_MM_PER_PX, "z_mm": config.Z_MM,
                "w": config.W_DEG, "p": config.P_DEG, "r": config.R_DEG,
                "cam_index": config.CAM_INDEX,
                "plc_ip": config.PLC_IP, "plc_db": config.PLC_DB,
                "plc_byte": config.PLC_BYTE, "plc_bit": config.PLC_BIT,
                "error_threshold_pct": config.ERROR_THRESHOLD_PCT,
                "demo": config.DEMO,
            })
        else:
            self._json(404, {"ok": False, "error": "introuvable"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BODY:
            return self._json(413, {"ok": False, "error": "image trop volumineuse"})
        with LOCK:
            if self.path == "/api/upload":
                raw = self.rfile.read(length)
                return self._json(200, do_upload(raw))
            if self.path == "/api/process":
                return self._json(200, do_process())
            if self.path == "/api/contours":
                return self._json(200, do_contours())
            if self.path == "/api/send_path":
                return self._json(200, do_send_path())
            if self.path == "/api/verify":
                return self._json(200, do_verify())
            if self.path == "/api/ping":
                try:
                    import socket
                    t0 = time.perf_counter()
                    with socket.create_connection(
                            (config.ROBOT_IP, config.ROBOT_PORT),
                            timeout=config.SOCKET_TIMEOUT):
                        pass
                    return self._json(200, {"ok": True, "latency_ms":
                        round((time.perf_counter() - t0) * 1000, 1)})
                except OSError as exc:
                    return self._json(200, {"ok": False, "error": str(exc)})
        self._json(404, {"ok": False, "error": "introuvable"})

    def log_message(self, fmt, *args):
        print("[%s] %s" % (time.strftime("%H:%M:%S"), fmt % args))


def main():
    if not (STATIC_DIR / "index.html").exists():
        raise SystemExit("static/index.html introuvable a cote de app.py")
    print("=" * 66)
    print(" Serveur web       : http://0.0.0.0:" + str(config.WEB_PORT))
    print(" Controleur FANUC  : " + config.ROBOT_IP + ":" + str(config.ROBOT_PORT))
    print(" Camera XC-56      : peripherique video index " + str(config.CAM_INDEX))
    print(" S7-1500           : " + config.PLC_IP + " (DB" + str(config.PLC_DB) +
          "." + str(config.PLC_BYTE) + "." + str(config.PLC_BIT) + ")")
    print(" Mode              : " + ("DEMO (sans robot/PLC)" if config.DEMO else "REEL"))
    print("=" * 66)
    ThreadingHTTPServer(("0.0.0.0", config.WEB_PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
