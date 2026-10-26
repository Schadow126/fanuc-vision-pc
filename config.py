"""Configuration de la cellule vision PC -> FANUC LR Mate 200iD/4S."""

# --- Liaison socket avec le robot (PC = serveur, robot = client KAREL) ---
ROBOT_HOST = "0.0.0.0"   # ecoute sur toutes les interfaces
ROBOT_PORT = 59002       # = $HOSTC_CFG[2].$SERVER_PORT cote robot
SOCKET_TIMEOUT_S = 10.0  # delai max d'attente robot
TERMINATOR = b"\r"      # fin de ligne (ATR_EOL = 13 par defaut chez Fanuc)

# --- Camera (XC-56 analogique via carte d'acquisition / frame grabber) ---
CAMERA_INDEX = 0         # index VideoCapture du frame grabber
CAMERA_W = 640           # resolution utile NTSC
CAMERA_H = 480
CAPTURE_WARMUP = 5       # images a ignorer a l'allumage (signal analogique)

# --- Fichiers images ---
REFERENCE_IMAGE = "reference.bmp"   # image de reference ("parfaite")

# --- Etalonnage camera -> repere robot (UFRAME) ---
# Matrice 3x3 (px -> mm) obtenue lors du calibrage :
# [mm_x/px, 0, offset_x], [0, mm_y/px, offset_y], [0, 0, 1]
CALIB_MATRIX = [
    [0.05, 0.00, 0.0],   # exemple : 1 px = 0.05 mm
    [0.00, 0.05, 0.0],
    [0.00, 0.00, 1.0],
]

# --- Seuils de decision ---
MATCH_THRESHOLD = 0.85     # score minimal de correlation avec la reference
MAX_CORRECTION_MM = 20.0   # correction max envoyee au robot (garde-fou)
MAX_RETRIES = 3            # nombre max de cycles de correction

# --- Orientation envoyee (le PC ne voit pas la rotation en Z sauf si mesuree) ---
DEFAULT_WPR = (0.0, -90.0, 0.0)  # w, p, r par defaut (outil vers le bas, ex.)
Z_HEIGHT = -50.0                # hauteur de prise constante (mm, UFRAME)
