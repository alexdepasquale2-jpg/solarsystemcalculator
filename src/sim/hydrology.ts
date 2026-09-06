import { Field } from "./field";

/**
 * Shallow water over erodible dirt.
 *
 * No rule here says "river". Water moves down the gradient of (dirt + water), carries as much
 * sediment as its speed allows, and drops the rest. Channels are what that does after a while:
 * a slightly wetter line moves slightly faster, cuts slightly deeper, and therefore collects
 * the next drop. That is the amplification the design doc is about, and it is the first place a
 * player-poured wall turns into a landform nobody drew.
 */
export interface HydroParams {
  gravity: number;       // how hard the surface slope pushes water
  friction: number;      // velocity retained per tick
  seep: number;          // groundwater welling up, the case's only external source
  drain: number;         // water lost into the dirt and out under the glass
  /** Depth at which the ground stops accepting more groundwater. Sets the water table. */
  seepChoke: number;
  /** Fine silt that leaves with the draining water instead of piling up forever. */
  siltExport: number;
  /** Share of exported silt that comes back up with the groundwater. 1 = closed budget. */
  wellUp: number;
  capacity: number;      // sediment a unit of fast water can hold
  erodeRate: number;     // how fast excess capacity bites into dirt
  depositRate: number;   // how fast surplus sediment settles
  minSlopeSpeed: number; // floor on effective speed, keeps flats from freezing solid
  maxSpeed: number;      // ceiling on flow, in cells per tick
  maxCut: number;        // most dirt a single cell may gain or lose in one tick
  creep: number;         // hillslope slumping rate
}

export const defaultHydro: HydroParams = {
  gravity: 9.0,
  friction: 0.82,
  seep: 0.00075,
  drain: 0.0032,
  seepChoke: 0.34,
  siltExport: 0.9,
  wellUp: 1.0,
  capacity: 0.28,
  erodeRate: 0.22,
  depositRate: 0.14,
  minSlopeSpeed: 0.02,
  maxSpeed: 0.55,
  maxCut: 0.004,
  creep: 0.005,
};

export class Hydrology {
  water: Field;
  sediment: Field;
  vx: Field;
  vy: Field;
  /** Set by the "block a path" tool: dirt that resists being cut. Decays very slowly. */
  hardness: Field;

  private surface: Field;
  private creepBuf: Float32Array;
  private g = { x: 0, y: 0 };

  constructor(w: number, h: number) {
    this.water = new Field(w, h, 0);
    this.sediment = new Field(w, h, 0);
    this.vx = new Field(w, h, 0);
    this.vy = new Field(w, h, 0);
    this.hardness = new Field(w, h, 0);
    this.surface = new Field(w, h, 0);
    this.creepBuf = new Float32Array(w * h);
  }

  step(elev: Field, moisture: Field, p: HydroParams, dt: number): void {
    const { w, h } = elev;
    const water = this.water, sed = this.sediment, vx = this.vx, vy = this.vy;
    let exported = 0;

    // Groundwater seeps in wherever the air above is already damp, and leaks away everywhere at
    // a fixed fraction. Neither term picks a spot; the balance between them is what makes some
    // hollows permanent and others a thing that happens after rain.
    for (let i = 0; i < water.data.length; i++) {
      // Seep backs off as the ground saturates, which is what gives the case a water table
      // instead of a slowly rising flood.
      const room = Math.max(0, 1 - water.data[i] / p.seepChoke);
      const inflow = p.seep * (0.4 + moisture.data[i]) * room * dt;
      const outflow = water.data[i] * p.drain * dt;
      water.data[i] += inflow - outflow;
      // Draining water takes its silt with it, and brings a little mineral back up. Without the
      // export, every grain the case ever moved ends up in one sink, and the sink grows forever.
      const lost = sed.data[i] * p.drain * p.siltExport * dt;
      sed.data[i] -= lost;
      exported += lost;
    }
    // What went out under the glass comes back up through the floor, spread evenly. The case
    // keeps its total dirt; what it does not keep is where that dirt was.
    if (exported > 0) {
      const back = (exported * p.wellUp) / elev.data.length;
      for (let i = 0; i < elev.data.length; i++) elev.data[i] += back;
    }

    // Surface = dirt + standing water. Water accelerates down its gradient, not the dirt's.
    const surf = this.surface;
    for (let i = 0; i < surf.data.length; i++) surf.data[i] = elev.data[i] + water.data[i];

    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const i = y * w + x;
        surf.gradAt(x, y, this.g);
        vx.data[i] = (vx.data[i] - this.g.x * p.gravity * dt) * p.friction;
        vy.data[i] = (vy.data[i] - this.g.y * p.gravity * dt) * p.friction;
        // Same trap as the wind: a steep cell drives fast water, fast water cuts it steeper.
        // Without a ceiling the dirt tears itself into a checkerboard in about four hundred ticks.
        const sp = Math.hypot(vx.data[i], vy.data[i]);
        if (sp > p.maxSpeed) {
          const k = p.maxSpeed / sp;
          vx.data[i] *= k;
          vy.data[i] *= k;
        }
      }
    }

    water.advect(vx, vy, dt);
    sed.advect(vx, vy, dt);

    // Erosion/deposition. Capacity rises with speed and depth; the difference cuts or fills.
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const i = y * w + x;
        const speed = Math.max(p.minSlopeSpeed, Math.hypot(vx.data[i], vy.data[i]));
        const depth = water.data[i];
        if (depth < 1e-5) continue;
        const cap = p.capacity * speed * Math.min(depth, 0.5);
        const diff = cap - sed.data[i];
        if (diff > 0) {
          // Hardness is clamped non-negative on purpose: this reciprocal changes sign below
          // -1/6, which turns erosion into unbounded deposition and inflates the whole floor.
          const resist = 1 / (1 + this.hardness.data[i] * 6);
          const bite = Math.min(p.maxCut * dt, diff * p.erodeRate * resist);
          elev.data[i] -= bite;
          sed.data[i] += bite;
        } else {
          // Silt cannot stack higher than the water carrying it. This is the difference between
          // a delta and a spike.
          const drop = Math.min(p.maxCut * dt, -diff * p.depositRate, depth * 0.2);
          elev.data[i] += drop;
          sed.data[i] -= drop;
        }
      }
    }

    water.clamp(0, 4);
    sed.clamp(0, 4);
    this.hardness.scale(0.99985);
    this.hardness.clamp(0, 4);

    // Slumping: dirt does not stand at any angle you like. This is what turns a poured wall
    // into a ridge with shoulders instead of a permanent vertical fence.
    this.creep(elev, p.creep);
  }

  /** Diffusive hillslope creep, weighted by slope so flats stay put. */
  private creep(elev: Field, rate: number): void {
    const { w, h, data } = elev;
    const out = this.creepBuf;
    for (let y = 0; y < h; y++) {
      const yl = y > 0 ? y - 1 : 0;
      const yr = y < h - 1 ? y + 1 : h - 1;
      for (let x = 0; x < w; x++) {
        const i = y * w + x;
        const xl = x > 0 ? x - 1 : 0;
        const xr = x < w - 1 ? x + 1 : w - 1;
        const lap = data[y * w + xl] + data[y * w + xr] + data[yl * w + x] + data[yr * w + x] - 4 * data[i];
        const hard = 1 / (1 + this.hardness.data[i] * 3);
        out[i] = data[i] + rate * lap * hard;
      }
    }
    data.set(out);
  }
}
