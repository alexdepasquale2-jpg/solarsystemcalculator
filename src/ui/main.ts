import { World } from "../sim/world";
import { applyTool, ToolId, RuleKind } from "../sim/tools";
import { serialize, deserialize } from "../sim/persist";
import { Renderer, Overlay } from "../render/renderer";
import { Camera } from "../render/camera";
import { TRAIT_KEYS } from "../sim/culture";

const SAVE_KEY = "still-tank.case.v1";
/** Real seconds per tick while the window is closed. The case runs slow, not fast. */
const OFFLINE_SECONDS_PER_TICK = 9;

const canvas = document.getElementById("tank") as HTMLCanvasElement;
const ctx = canvas.getContext("2d")!;
const readout = document.getElementById("readout")!;
const statsEl = document.getElementById("stats")!;
const noticeEl = document.getElementById("notice")!;

let world: World;
let awayNotice = "";

/**
 * Booting a fresh case takes a couple of seconds of physics, because the case is supposed to be
 * already mid-sentence when you arrive rather than a flat tray waiting for you. Hand the browser
 * a frame first so it can say so, then do the work.
 */
function boot(): void {
  const saved = localStorage.getItem(SAVE_KEY);
  const loaded = saved ? deserialize(saved) : null;
  if (loaded) {
    world = loaded.world;
    const ticks = Math.floor(loaded.awaySeconds / OFFLINE_SECONDS_PER_TICK);
    if (ticks > 0) {
      const ran = world.runOffline(ticks);
      awayNotice = `The case ran ${ran} ticks without you.`;
    } else {
      awayNotice = "Where you left it.";
    }
  } else {
    world = new World({ seed: (Math.random() * 1e9) | 0 });
    world.init();
    awayNotice = "You inherited this case. It was already mid-sentence.";
  }
}

let cam: Camera;
let renderer: Renderer;

let tool: ToolId = "matter";
let rule: RuleKind = "border";
let sign = 1;
let radius = 6;
let overlay: Overlay = "none";
let running = true;
let speed = 1;
let probeAt: [number, number] | null = null;

// --- camera input: one volume, no second map ------------------------------------------------
let dragging = false;
let dragged = 0;
let lastPt = [0, 0];

canvas.addEventListener("pointerdown", (e) => {
  if (!world) return;
  dragging = true; dragged = 0; lastPt = [e.clientX, e.clientY];
  canvas.setPointerCapture(e.pointerId);
});

canvas.addEventListener("pointermove", (e) => {
  if (!dragging || !world) return;
  const dx = e.clientX - lastPt[0], dy = e.clientY - lastPt[1];
  dragged += Math.abs(dx) + Math.abs(dy);
  cam.x -= dx / cam.scale;
  cam.y -= dy / cam.scale;
  cam.clampTo(world.w, world.h);
  lastPt = [e.clientX, e.clientY];
});

canvas.addEventListener("pointerup", (e) => {
  if (!world) return;
  dragging = false;
  const rect = canvas.getBoundingClientRect();
  const [wx, wy] = cam.toWorld(e.clientX - rect.left, e.clientY - rect.top, canvas.width, canvas.height);
  if (dragged > 6) return;
  if (e.shiftKey || e.button === 2) { probeAt = [wx, wy]; return; }
  const note = applyTool(world, {
    tool, x: wx, y: wy, radius,
    strength: sign * 1.0,
    rule,
    shape: Math.random(),
  });
  probeAt = [wx, wy];
  flash(`${note} at ${wx.toFixed(0)}, ${wy.toFixed(0)} — now stop touching it`);
});

canvas.addEventListener("contextmenu", (e) => e.preventDefault());

canvas.addEventListener("wheel", (e) => {
  if (!cam) return;
  e.preventDefault();
  const rect = canvas.getBoundingClientRect();
  cam.zoomAt(e.clientX - rect.left, e.clientY - rect.top,
    Math.pow(0.999, e.deltaY), canvas.width, canvas.height, 0.9, 26);
}, { passive: false });

// --- the thin strip -------------------------------------------------------------------------
document.querySelectorAll<HTMLButtonElement>("[data-tool]").forEach((btn) => {
  btn.addEventListener("click", () => {
    tool = btn.dataset.tool as ToolId;
    document.querySelectorAll("[data-tool]").forEach((b) => b.classList.remove("on"));
    btn.classList.add("on");
    document.getElementById("rules")!.hidden = tool !== "rule";
    document.getElementById("signrow")!.hidden = !(tool === "matter" || tool === "heat");
  });
});

document.querySelectorAll<HTMLButtonElement>("[data-rule]").forEach((btn) => {
  btn.addEventListener("click", () => {
    rule = btn.dataset.rule as RuleKind;
    document.querySelectorAll("[data-rule]").forEach((b) => b.classList.remove("on"));
    btn.classList.add("on");
  });
});

document.querySelectorAll<HTMLButtonElement>("[data-overlay]").forEach((btn) => {
  btn.addEventListener("click", () => {
    overlay = btn.dataset.overlay as Overlay;
    document.querySelectorAll("[data-overlay]").forEach((b) => b.classList.remove("on"));
    btn.classList.add("on");
  });
});

document.getElementById("sign")!.addEventListener("click", (e) => {
  sign = -sign;
  (e.target as HTMLElement).textContent = sign > 0 ? "add" : "take away";
});

(document.getElementById("radius") as HTMLInputElement).addEventListener("input", (e) => {
  radius = Number((e.target as HTMLInputElement).value);
});

(document.getElementById("speed") as HTMLInputElement).addEventListener("input", (e) => {
  speed = Number((e.target as HTMLInputElement).value);
  running = speed > 0;
});

document.getElementById("reseed")!.addEventListener("click", () => {
  if (!confirm("Throw this case away and inherit a different one? The scars do not transfer.")) return;
  localStorage.removeItem(SAVE_KEY);
  location.reload();
});

function flash(msg: string): void {
  noticeEl.textContent = msg;
  noticeEl.classList.add("show");
  setTimeout(() => noticeEl.classList.remove("show"), 4200);
}

// --- loop -----------------------------------------------------------------------------------
function resize(): void {
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  canvas.width = canvas.clientWidth * dpr;
  canvas.height = canvas.clientHeight * dpr;
}
window.addEventListener("resize", resize);
resize();

// The sim runs on its own slow clock and the screen redraws at whatever rate it likes. A tank
// that ticked once per frame would race on a fast machine and crawl on a slow one, and the
// whole game is about what happens over time, so time has to mean the same thing everywhere.
const TICKS_PER_SECOND = 8;
let frame = 0;
let lastTime = performance.now();
let owed = 0;

function loop(now = performance.now()): void {
  const elapsed = Math.min(0.25, (now - lastTime) / 1000);
  lastTime = now;
  if (running) {
    owed += elapsed * TICKS_PER_SECOND * speed;
    const budget = Math.min(Math.floor(owed), 12);
    for (let i = 0; i < budget; i++) world.step(1);
    owed -= budget;
  }
  frame++;
  renderer.draw(ctx, cam, canvas.width, canvas.height, overlay, frame % 3 === 0);
  if (frame % 12 === 0) { drawStats(); drawProbe(); }
  requestAnimationFrame(loop);
}

function drawStats(): void {
  if (!world) return;
  const s = world.stats();
  const split = s.dialectSplit > 0.16
    ? `two habits, gap ${s.dialectSplit.toFixed(2)}`
    : "one habit pool";
  statsEl.textContent =
    `tick ${s.tick} · ${s.population} bodies · energy ${s.meanEnergy.toFixed(2)} · ` +
    `water ${s.water.toFixed(3)} · green ${s.biomass.toFixed(2)} · wear ${s.wear.toFixed(3)} · ` +
    `${s.marks} marks · ${split}`;
}

function drawProbe(): void {
  if (!world) return;
  if (!probeAt) { readout.textContent = "Shift-click, or click a tool then the ground."; return; }
  const p = world.probe(probeAt[0], probeAt[1]);
  const lines = [
    `at ${p.x.toFixed(0)}, ${p.y.toFixed(0)}`,
    `dirt ${p.elevation.toFixed(3)}  heat ${p.heat.toFixed(2)}  water ${p.water.toFixed(3)}`,
    `green ${p.biomass.toFixed(2)}  wear ${p.wear.toFixed(3)}  border ${p.border.toFixed(2)}`,
    `${p.bodiesNearby} bodies within nine cells`,
  ];
  if (p.localTraits) {
    lines.push("their habits: " + TRAIT_KEYS
      .map((k) => `${k} ${p.localTraits![k].toFixed(2)}`).join("  "));
  }
  if (p.history.length) {
    lines.push("—");
    for (const e of p.history) lines.push(`tick ${e.tick}: you ${e.note} here`);
  }
  readout.textContent = lines.join("\n");
}

// --- the case keeps running; the save has to keep up -----------------------------------------
function save(): void {
  if (!world) return;
  try { localStorage.setItem(SAVE_KEY, serialize(world)); } catch { /* case too big; skip */ }
}
setInterval(save, 20000);
window.addEventListener("beforeunload", save);
document.addEventListener("visibilitychange", () => { if (document.hidden) save(); });

noticeEl.textContent = "settling the case…";
noticeEl.classList.add("show");
requestAnimationFrame(() => setTimeout(() => {
  boot();
  // Open filling the frame: there is only one volume, so arriving letterboxed inside it
  // just makes the case look like a picture of a case.
  const fit = Math.min(canvas.width, canvas.height) * 0.94 / world.h;
  cam = new Camera(world.w / 2, world.h / 2, Math.max(1.2, Math.min(12, fit)));
  renderer = new Renderer(world);
  drawStats();
  flash(awayNotice);
  loop();
}, 30));
