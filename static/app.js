let running = false;
let stepInterval = null;

const canvas = document.getElementById("maze-canvas");
const ctx = canvas.getContext("2d");

const logsEl = document.getElementById("logs");
const lastCmdEl = document.getElementById("last-cmd");
const sensorFrontEl = document.getElementById("sensor-front");
const sensorLeftEl = document.getElementById("sensor-left");
const sensorRightEl = document.getElementById("sensor-right");

const btnStart = document.getElementById("btn-start");
const btnStep = document.getElementById("btn-step");
const btnStop = document.getElementById("btn-stop");
const btnReset = document.getElementById("btn-reset");

const CELL_SIZE = 45;  // debe coincidir con backend


async function fetchState() {
  const res = await fetch("/api/state");
  const data = await res.json();
  renderState(data);
}

async function stepOnce() {
  const res = await fetch("/api/step", { method: "POST" });
  const data = await res.json();
  renderState(data.state);
  if (data.done) {
    addLog("🏁 Meta alcanzada o sin movimientos.");
    stopLoop();
  }
}

async function resetMaze() {
  await fetch("/api/reset", { method: "POST" });
  await fetchState();
  addLog("🔁 Maze reiniciado");
}

function startLoop() {
  if (running) return;
  running = true;
  addLog("▶️ Start");
  stepInterval = setInterval(stepOnce, 400);
}

function stopLoop() {
  running = false;
  if (stepInterval) {
    clearInterval(stepInterval);
    stepInterval = null;
  }
  addLog("⏸ Stop");
}

function addLog(msg) {
  const timestamp = new Date().toLocaleTimeString();
  logsEl.textContent += `[${timestamp}] ${msg}\n`;
  logsEl.scrollTop = logsEl.scrollHeight;
}

function renderState(state) {
  const { rows, cols, cells, robot, goalCells, lastCmd, lastSensors, logs } = state;

  // Logs desde backend (últimas 20 líneas)
  logsEl.textContent = "";
  logs.forEach(line => {
    logsEl.textContent += line + "\n";
  });
  logsEl.scrollTop = logsEl.scrollHeight;

  // Último comando y sensores
  lastCmdEl.textContent = lastCmd || "-";
  sensorFrontEl.textContent = lastSensors.front !== null ? lastSensors.front : "-";
  sensorLeftEl.textContent  = lastSensors.left !== null ? lastSensors.left : "-";
  sensorRightEl.textContent = lastSensors.right !== null ? lastSensors.right : "-";

  // Dibujo grid
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const cell = cells[r][c];
      const d = cell.dist;
      const x = c * CELL_SIZE;
      const y = r * CELL_SIZE;

      let color;
      if (d >= 9999) {
        color = "#ffffff";
      } else {
        const shade = Math.max(0, 255 - d * 20);
        color = `rgb(${shade}, ${shade}, 255)`;
      }

      ctx.fillStyle = color;
      ctx.fillRect(x, y, CELL_SIZE, CELL_SIZE);

      ctx.strokeStyle = "#0f172a";
      ctx.strokeRect(x, y, CELL_SIZE, CELL_SIZE);

      // Paredes
      ctx.strokeStyle = "#111827";
      ctx.lineWidth = 3;

      if (cell.walls.N) {
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x + CELL_SIZE, y);
        ctx.stroke();
      }
      if (cell.walls.E) {
        ctx.beginPath();
        ctx.moveTo(x + CELL_SIZE, y);
        ctx.lineTo(x + CELL_SIZE, y + CELL_SIZE);
        ctx.stroke();
      }
      if (cell.walls.S) {
        ctx.beginPath();
        ctx.moveTo(x, y + CELL_SIZE);
        ctx.lineTo(x + CELL_SIZE, y + CELL_SIZE);
        ctx.stroke();
      }
      if (cell.walls.W) {
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x, y + CELL_SIZE);
        ctx.stroke();
      }

      // Distancia
      ctx.fillStyle = "#0f172a";
      ctx.font = "10px 'Segoe UI'";
      const text = d >= 9999 ? "-" : d.toString();
      ctx.fillText(text, x + 4, y + 12);
    }
  }

  // Dibujar meta(s)
  goalCells.forEach(g => {
    const gx = g.col * CELL_SIZE;
    const gy = g.row * CELL_SIZE;
    ctx.fillStyle = "rgba(16, 185, 129, 0.3)";
    ctx.fillRect(gx, gy, CELL_SIZE, CELL_SIZE);
  });

  // Dibujar robot
  const rr = robot.row;
  const rc = robot.col;
  const rdir = robot.dir;
  const cx = rc * CELL_SIZE + CELL_SIZE / 2;
  const cy = rr * CELL_SIZE + CELL_SIZE / 2;

  ctx.fillStyle = "#ef4444";
  ctx.beginPath();
  ctx.arc(cx, cy, CELL_SIZE * 0.3, 0, Math.PI * 2);
  ctx.fill();

  // Flecha de dirección
  const len = CELL_SIZE * 0.3;
  let dx = 0, dy = 0;
  if (rdir === 0) dy = -len;
  else if (rdir === 1) dx = len;
  else if (rdir === 2) dy = len;
  else if (rdir === 3) dx = -len;

  ctx.strokeStyle = "#111827";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(cx, cy);
  ctx.lineTo(cx + dx, cy + dy);
  ctx.stroke();
}

// Eventos
btnStart.addEventListener("click", startLoop);
btnStep.addEventListener("click", () => {
  stopLoop();
  stepOnce();
});
btnStop.addEventListener("click", stopLoop);
btnReset.addEventListener("click", () => {
  stopLoop();
  resetMaze();
});

// Cargar estado inicial
fetchState().catch(err => console.error(err));
