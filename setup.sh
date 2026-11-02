#!/usr/bin/env bash
# ============================================================
# setup.sh - Preparation du PC vision en une commande
#
#   bash setup.sh
#
# Cree un environnement virtuel Python (.venv), installe les
# dependances (opencv, numpy, snap7) et verifie que tout marche.
# ============================================================
set -e
cd "$(dirname "$0")"

echo "== 1/4 : Python =="
command -v python3 >/dev/null || {
    echo "ERREUR : Python 3 n'est pas installe."; exit 1;
}
python3 --version

echo "== 2/4 : environnement virtuel (.venv) =="
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "== 3/4 : dependances (opencv, numpy, snap7) =="
python3 -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt

echo "== 4/4 : verification =="
python3 - <<'PY'
import cv2
import numpy
print("OpenCV " + cv2.__version__ + " - numpy " + numpy.__version__ + " : OK")
PY

echo ""
echo "============================================================"
echo " Pret ! Lancement du serveur (hote) :"
echo "     source .venv/bin/activate && python app.py"
echo " Puis ouvrir http://localhost:8000"
echo ""
echo " Variables utiles (exemples) :"
echo "     Z_MM=-15 Z_TRAVEL_MM=-80 ROBOT_IP=192.168.1.10 python app.py"
echo "============================================================"
