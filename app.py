import glob
import time
from collections import deque

from flask import Flask, render_template, jsonify
import serial
import serial.serialutil

# ==============================
#   CONFIGURACIÓN GENERAL
# ==============================

ROWS = 6
COLS = 12

# 0=N, 1=E, 2=S, 3=W
DIRS = [(-1, 0), (0, 1), (1, 0), (0, -1)]

goal_cells = [(0, 11)]  # puedes cambiar la meta

# Estado global
maze = []
robot_row = 5
robot_col = 0
robot_dir = 0
last_cmd = None
last_sensors = {"front": None, "left": None, "right": None}
log_lines = []

ser = None  # objeto serial


# ==============================
#   MODELO DE CELDA
# ==============================

class Cell:
    def __init__(self):
        # paredes [N, E, S, W]
        self.walls = [False, False, False, False]
        self.dist = 9999


def init_maze():
    global maze, robot_row, robot_col, robot_dir, last_cmd, last_sensors, log_lines
    maze = [[Cell() for _ in range(COLS)] for _ in range(ROWS)]
    robot_row = 5
    robot_col = 0
    robot_dir = 0
    last_cmd = None
    last_sensors = {"front": None, "left": None, "right": None}
    log_lines = []
    log("Maze reiniciado")


# ==============================
#   LOG Y UTILIDADES
# ==============================

def log(msg):
    print(msg)
    log_lines.append(msg)
    if len(log_lines) > 100:
        log_lines.pop(0)


def find_serial_port():
    ports = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
    if not ports:
        log("❌ No se encontró ningún puerto serial (ESP32)")
        return None
    log(f"🔌 Puerto detectado: {ports[0]}")
    return ports[0]


def init_serial():
    global ser
    port = find_serial_port()
    if port is None:
        return
    try:
        ser = serial.Serial(port, 115200, timeout=1)
        time.sleep(2)
        log("✅ Conectado al ESP32")
    except serial.serialutil.SerialException as e:
        log(f"❌ Error abriendo el puerto serial: {e}")
        ser = None


# ==============================
#   FLOOD FILL
# ==============================

def recompute_distances():
    for r in range(ROWS):
        for c in range(COLS):
            maze[r][c].dist = 9999

    q = deque()
    for gr, gc in goal_cells:
        maze[gr][gc].dist = 0
        q.append((gr, gc))

    while q:
        r, c = q.popleft()
        cd = maze[r][c].dist

        for d in range(4):
            if maze[r][c].walls[d]:
                continue

            dr, dc = DIRS[d]
            nr, nc = r + dr, c + dc
            if 0 <= nr < ROWS and 0 <= nc < COLS:
                if maze[nr][nc].dist > cd + 1:
                    maze[nr][nc].dist = cd + 1
                    q.append((nr, nc))


# ==============================
#   DECISIÓN DE MOVIMIENTO
# ==============================

def choose_next_move():
    global robot_row, robot_col, robot_dir

    r, c, d = robot_row, robot_col, robot_dir

    # 1 — si la celda actual tiene distancia 0 (meta real), detenerse
    if maze[r][c].dist == 0:
        return 'X'

    # 2 — revisar vecinos y buscar el MÁS SEGURO Y MENOR DIST
    best_dirs = []
    best_dist = 9999

    for ndir in range(4):
        # si hay pared en el mapa → prohibido
        if maze[r][c].walls[ndir]:
            continue

        dr, dc = DIRS[ndir]
        nr, nc = r + dr, c + dc

        # fuera del mapa → no
        if not (0 <= nr < ROWS and 0 <= nc < COLS):
            continue

        # si tiene mejor distancia → marcar como candidato
        if maze[nr][nc].dist < best_dist:
            best_dist = maze[nr][nc].dist
            best_dirs = [ndir]
        elif maze[nr][nc].dist == best_dist:
            best_dirs.append(ndir)

    # si no hay salida posible
    if not best_dirs:
        return 'X'

    # 3 — preferencia de giro mínima (procesamiento humano)
    # orden: F > L > R > B
    def cost(ndir):
        diff = (ndir - d) % 4
        if diff == 0: return 0  # forward
        if diff == 3: return 1  # left
        if diff == 1: return 2  # right
        return 3  # back

    best_dir = min(best_dirs, key=cost)
    diff = (best_dir - d) % 4

    if diff == 0: return 'F'
    if diff == 1: return 'R'
    if diff == 3: return 'L'
    return 'B'



def update_robot_pose_after_command(cmd):
    global robot_row, robot_col, robot_dir

    if cmd == 'L':
        robot_dir = (robot_dir + 3) % 4
    elif cmd == 'R':
        robot_dir = (robot_dir + 1) % 4
    elif cmd == 'B':
        robot_dir = (robot_dir + 2) % 4

    if cmd == 'F':
        dr, dc = DIRS[robot_dir]
        robot_row += dr
        robot_col += dc


def update_walls_from_sensors(front, left, right):
    global robot_row, robot_col, robot_dir

    r, c, d = robot_row, robot_col, robot_dir

    # direcciones
    left_d = (d + 3) % 4
    right_d = (d + 1) % 4

    # lista de paredes detectadas
    detected = [(front, d), (left, left_d), (right, right_d)]

    for wall_detected, direction in detected:
        if wall_detected == 1:
            maze[r][c].walls[direction] = True

            dr, dc = DIRS[direction]
            nr, nc = r + dr, c + dc

            if 0 <= nr < ROWS and 0 <= nc < COLS:
                # simetría obligatoria
                opposite = (direction + 2) % 4
                maze[nr][nc].walls[opposite] = True



# ==============================
#   COMUNICACIÓN CON ESP32
# ==============================

def send_command_and_get_walls(cmd):
    global ser
    if ser is None:
        log("⚠️ No hay conexión serial con el ESP32.")
        return None

    try:
        ser.write((cmd + "\n").encode())
        ser.flush()
    except serial.serialutil.SerialException as e:
        log(f"❌ Error enviando comando: {e}")
        return None

    # Esperar respuesta tipo: S f l r
    start = time.time()
    while time.time() - start < 2.0:  # timeout 2s
        try:
            line = ser.readline().decode(errors="ignore").strip()
        except serial.serialutil.SerialException as e:
            log(f"❌ Error leyendo serial: {e}")
            return None

        if not line:
            continue
        log(f"← {line}")
        if line.startswith("S"):
            parts = line.split()
            if len(parts) == 4:
                _, f, l, r = parts
                try:
                    return int(f), int(l), int(r)
                except ValueError:
                    continue
    log("⚠️ No se recibió respuesta válida del ESP32.")
    return None


# ==============================
#   SERIALIZACIÓN PARA FRONTEND
# ==============================

def get_state_json():
    cells = []
    for r in range(ROWS):
        row_cells = []
        for c in range(COLS):
            cell = maze[r][c]
            row_cells.append({
                "dist": cell.dist,
                "walls": {
                    "N": cell.walls[0],
                    "E": cell.walls[1],
                    "S": cell.walls[2],
                    "W": cell.walls[3],
                }
            })
        cells.append(row_cells)

    return {
        "rows": ROWS,
        "cols": COLS,
        "cells": cells,
        "robot": {
            "row": robot_row,
            "col": robot_col,
            "dir": robot_dir
        },
        "goalCells": [{"row": r, "col": c} for (r, c) in goal_cells],
        "lastCmd": last_cmd,
        "lastSensors": last_sensors,
        "logs": log_lines[-20:],  # últimas 20
        "atGoal": (robot_row, robot_col) in goal_cells
    }


# ==============================
#   FLASK APP
# ==============================

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def api_state():
    return jsonify(get_state_json())


@app.route("/api/reset", methods=["POST"])
def api_reset():
    init_maze()
    return jsonify({"ok": True})


@app.route("/api/step", methods=["POST"])
def api_step():
    global last_cmd, last_sensors

    # 1) Flood fill
    recompute_distances()

    # 2) Decidir movimiento
    cmd = choose_next_move()
    last_cmd = cmd
    log(f"CMD: {cmd}")

    if cmd == 'X':
        log("🏁 Meta alcanzada o sin movimientos.")
        return jsonify({"state": get_state_json(), "done": True})

    # 3) Enviar comando al ESP32 y leer sensores
    walls = send_command_and_get_walls(cmd)
    if walls is None:
        last_sensors = {"front": None, "left": None, "right": None}
    else:
        front, left, right = walls
        last_sensors = {"front": front, "left": left, "right": right}
        update_walls_from_sensors(front, left, right)

    # 4) Actualizar pose
    update_robot_pose_after_command(cmd)

    # 5) Devolver nuevo estado
    return jsonify({"state": get_state_json(), "done": False})


if __name__ == "__main__":
    init_maze()
    init_serial()
    # debug=False para que no cree dos procesos (importante por el serial)
    app.run(host="0.0.0.0", port=5000, debug=False)
