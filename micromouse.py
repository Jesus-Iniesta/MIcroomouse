import serial
import time
import tkinter as tk
import glob
from collections import deque

##############################################
#          AUTO-DETECCIÓN DEL PUERTO
##############################################

def find_serial_port():
    print("Buscando ESP32 en puertos seriales...")

    ports = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")

    if len(ports) == 0:
        print("❌ No se encontró ningún ESP32 conectado.")
        print("Prueba ejecutar:   dmesg | grep tty")
        return None

    print("🔌 Puerto detectado:", ports[0])
    return ports[0]

SERIAL_PORT = find_serial_port()
BAUDRATE = 115200

if SERIAL_PORT is None:
    exit("No hay puerto serial disponible.")


##############################################
#         CONFIGURACIÓN DEL LABERINTO
##############################################

ROWS = 6
COLS = 12
CELL_SIZE = 45

# Direcciones absolutas
# 0 = norte, 1 = este, 2 = sur, 3 = oeste
DIRS = [(-1, 0), (0, 1), (1, 0), (0, -1)]


##############################################
#               CLASE CELDA
##############################################

class Cell:
    def __init__(self):
        # paredes: [N, E, S, W]
        self.walls = [False, False, False, False]
        self.dist = 9999


##############################################
#      LABERINTO Y ESTADO DEL ROBOT
##############################################

maze = [[Cell() for _ in range(COLS)] for _ in range(ROWS)]

robot_row = 5
robot_col = 0
robot_dir = 0  # mirando al norte

goal_cells = [(0, 11)]  # objetivo final


##############################################
#                 FLOOD FILL
##############################################

def recompute_distances():
    for r in range(ROWS):
        for c in range(COLS):
            maze[r][c].dist = 9999

    q = deque()

    for (gr, gc) in goal_cells:
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


##############################################
#     ELEGIR SIGUIENTE MOVIMIENTO (PC)
##############################################

def choose_next_move():
    global robot_row, robot_col, robot_dir

    r, c, d = robot_row, robot_col, robot_dir
    best_dir = None
    best_dist = 9999

    for ndir in range(4):
        if maze[r][c].walls[ndir]:
            continue

        dr, dc = DIRS[ndir]
        nr, nc = r + dr, c + dc

        if 0 <= nr < ROWS and 0 <= nc < COLS:
            if maze[nr][nc].dist < best_dist:
                best_dist = maze[nr][nc].dist
                best_dir = ndir

    if best_dir is None:
        return 'X'

    diff = (best_dir - d) % 4

    if diff == 0:
        return 'F'
    elif diff == 1:
        return 'R'
    elif diff == 3:
        return 'L'
    else:
        return 'B'


##############################################
#   ACTUALIZAR POSE DEL ROBOT DESPUÉS DEL MOV
##############################################

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


##############################################
#       ACTUALIZAR MUROS DESDE ESP32
##############################################

def update_walls_from_sensors(front, left, right):
    global robot_row, robot_col, robot_dir

    r, c, d = robot_row, robot_col, robot_dir

    if front == 1:
        maze[r][c].walls[d] = True

    if left == 1:
        maze[r][c].walls[(d + 3) % 4] = True

    if right == 1:
        maze[r][c].walls[(d + 1) % 4] = True


##############################################
#         ENVIAR COMANDO Y RECIBIR MUROS
##############################################

def send_command_and_get_walls(ser, cmd):
    ser.write((cmd + "\n").encode())
    ser.flush()

    while True:
        line = ser.readline().decode().strip()
        if line.startswith("S"):
            try:
                _, f, l, r = line.split()
                return int(f), int(l), int(r)
            except:
                continue


##############################################
#                 GUI TKINTER
##############################################

def draw_maze(canvas):
    canvas.delete("all")

    for r in range(ROWS):
        for c in range(COLS):
            x1 = c * CELL_SIZE
            y1 = r * CELL_SIZE
            x2 = x1 + CELL_SIZE
            y2 = y1 + CELL_SIZE

            d = maze[r][c].dist
            if d >= 9999:
                color = "#ffffff"
            else:
                shade = max(0, 255 - d * 20)
                color = f"#{shade:02x}{shade:02x}ff"

            canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="black")
            canvas.create_text((x1+x2)//2, (y1+y2)//2, text=str(d), font=("Arial", 8))

    rx = robot_col * CELL_SIZE + CELL_SIZE // 2
    ry = robot_row * CELL_SIZE + CELL_SIZE // 2
    canvas.create_oval(rx-12, ry-12, rx+12, ry+12, fill="red")


##############################################
#               MAIN LOOP
##############################################

def main():
    ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1)
    time.sleep(2)

    root = tk.Tk()
    root.title("Micromouse Flood Fill – Hadita")

    canvas = tk.Canvas(root, width=COLS * CELL_SIZE, height=ROWS * CELL_SIZE)
    canvas.pack()

    def step():
        # 1 — Flood Fill
        recompute_distances()

        # 2 — Movimiento
        cmd = choose_next_move()
        print("CMD:", cmd)

        if cmd == "X":
            print("No hay movimientos posibles")
            return

        # 3 — Enviar comando al ESP32 y obtener paredes
        front, left, right = send_command_and_get_walls(ser, cmd)

        # 4 — Actualizar pose local
        update_robot_pose_after_command(cmd)

        # 5 — Actualizar paredes en el mapa
        update_walls_from_sensors(front, left, right)

        # 6 — Redibujar GUI
        draw_maze(canvas)

        root.after(300, step)  # velocidad del algoritmo

    step()
    root.mainloop()


if __name__ == "__main__":
    main()
