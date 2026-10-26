#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fanuc_socket_web - Serveur web + client TCP "Socket Messaging" pour robot FANUC R-30iB Mate.

Architecture :
    [Navigateur] --HTTP--> [PC (ce script, port 8080)] --TCP--> [R-30iB Mate (tag C2, port 59002)]

Aucune dépendance externe : Python 3.8+ (bibliothèque standard uniquement).

Usage :
    python app.py                       # utilise ROBOT_IP / ROBOT_PORT par défaut
    ROBOT_IP=10.0.0.5 python app.py     # variables d'environnement acceptées
    DEMO=1 python app.py                # mode démonstration (sans robot)

Points d'entrée HTTP :
    GET  /              -> page web (static/index.html)
    GET  /api/config    -> configuration courante (JSON)
    POST /api/ping      -> test de connexion TCP au contrôleur
    POST /api/send      -> envoi d'un point X Y Z W P R au robot (JSON)
"""

import json
import os
import socket
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

ROBOT_IP = os.environ.get("ROBOT_IP", "192.168.1.10")
ROBOT_PORT = int(os.environ.get("ROBOT_PORT", "59002"))
WEB_PORT = int(os.environ.get("WEB_PORT", "8080"))
SOCKET_TIMEOUT = float(os.environ.get("SOCKET_TIMEOUT", "5"))
DEMO = os.environ.get("DEMO", "0") == "1"


def ping_robot():
    """Teste la connexion TCP vers le contrôleur FANUC."""
    if DEMO:
        time.sleep(0.05)
        return {"ok": True, "demo": True, "latency_ms": 1.0}
    t0 = time.perf_counter()
    with socket.create_connection((ROBOT_IP, ROBOT_PORT), timeout=SOCKET_TIMEOUT):
        pass
    return {"ok": True, "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}


def send_point_to_robot(x, y, z, w, p, r):
    """
    Envoie une trame 'X Y Z W P R' terminée par CR au contrôleur,
    puis lit l'accusé renvoyé par le programme KAREL (ex. 'ACK').
    """
    if DEMO:
        time.sleep(0.12)
        return {"ok": True, "demo": True, "reply": "ACK (mode démo)"}
    frame = "{:.3f} {:.3f} {:.3f} {:.3f} {:.3f} {:.3f}\r".format(x, y, z, w, p, r)
    with socket.create_connection((ROBOT_IP, ROBOT_PORT), timeout=SOCKET_TIMEOUT) as s:
        s.settimeout(SOCKET_TIMEOUT)
        s.sendall(frame.encode("ascii"))
        reply = s.recv(64).decode("ascii", errors="replace").strip()
    return {"ok": True, "reply": reply or "(aucune réponse)"}


class Handler(BaseHTTPRequestHandler):
    server_version = "FanucSocketWeb/1.0"

    def _cors(self):
        # Autorise la page hébergée sur GitHub Pages à piloter ce serveur local.
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
                "robot_ip": ROBOT_IP,
                "robot_port": ROBOT_PORT,
                "web_port": WEB_PORT,
                "demo": DEMO,
            })
        else:
            self._json(404, {"ok": False, "error": "introuvable"})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {"ok": False, "error": "JSON invalide"})

        if self.path == "/api/ping":
            try:
                return self._json(200, ping_robot())
            except OSError as exc:
                return self._json(200, {"ok": False, "error": str(exc)})

        if self.path == "/api/send":
            try:
                x = float(data["x"]); y = float(data["y"]); z = float(data["z"])
                w = float(data["w"]); p = float(data["p"]); r = float(data["r"])
            except (KeyError, TypeError, ValueError):
                return self._json(400, {"ok": False,
                                        "error": "champs x,y,z,w,p,r numériques requis"})
            try:
                return self._json(200, send_point_to_robot(x, y, z, w, p, r))
            except OSError as exc:
                return self._json(200, {"ok": False,
                                        "error": "connexion au robot impossible : " + str(exc)})

        return self._json(404, {"ok": False, "error": "introuvable"})

    def log_message(self, fmt, *args):
        print("[%s] %s" % (time.strftime("%H:%M:%S"), fmt % args))


def main():
    if not (STATIC_DIR / "index.html").exists():
        raise SystemExit("static/index.html introuvable à côté de app.py")
    print("=" * 62)
    print(" Serveur web       : http://0.0.0.0:" + str(WEB_PORT))
    print(" Contrôleur FANUC  : " + ROBOT_IP + ":" + str(ROBOT_PORT) + ("  (DÉMO)" if DEMO else ""))
    print("=" * 62)
    ThreadingHTTPServer(("0.0.0.0", WEB_PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
