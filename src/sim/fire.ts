import { Field } from "./field";
import { Rng } from "./rng";

/**
 * Fire.
 *
 * This is the case's fastest process and its only violent one, and it is worth being careful
 * about what it is not: there is no ignition event, no fire season, nothing watching a dryness
 * meter waiting to fire a cutscene. A cell lights when it happens to be hot, dry and standing in
 * fuel, which after a run of summer weeks is many cells at once and after a wet spring is none.
 *
 * What makes it worth having is the aftermath rather than the flame. Burnt ground comes back
 * richer than it was, so a fire lays down a fertile scar that the herd finds two seasons later,
 * grazes hard, and wears a path to. The fire is over in fifty ticks. The path it caused is not.
 */
export interface FireParams {
  /** Heat above which dry fuel can catch at all. */
  ignitionHeat: number;
  /** Chance per cell per tick of a spark, once hot and dry enough. */
  sparkChance: number;
  /** Fuel needed before a spark takes. */
  fuelFloor: number;
  /** How fast flame spreads into neighbouring fuel. */
  spread: number;
  /** Fuel burnt per unit of flame per tick. */
  consume: number;
  /** Flame lost per tick with nothing left to eat. */
  decay: number;
  /** Heat added to the air by burning. Feeds back into the wind. */
  heatRelease: number;
  /** Damp fuel does not burn. Above this water depth, nothing catches. */
  wetProof: number;
  /** Fertility left behind, as a share of what was burnt. */
  ashYield: number;
  /** How fast ash is worked into the ground and stops being visible. */
  ashDecay: number;
}

export const defaultFire: FireParams = {
  ignitionHeat: 0.66,
  sparkChance: 0.000055,
  fuelFloor: 0.30,
  spread: 0.20,
  consume: 0.55,
  decay: 0.085,
  heatRelease: 0.55,
  wetProof: 0.145,
  ashYield: 0.65,
  ashDecay: 0.9993,
};

export class Fire {
  /** Currently burning, 0..1. */
  flame: Field;
  /** Burnt matter left on the ground. Raises carrying capacity while it lasts. */
  ash: Field;
  /** Ticks since this cell last burned, so the camera can point at an old burn. */
  lastBurn: Field;
  /** Set when the player raises heat far enough to light something themselves. */
  burnedThisTick = 0;

  private buf: Float32Array;

  constructor(w: number, h: number) {
    this.flame = new Field(w, h, 0);
    this.ash = new Field(w, h, 0);
    this.lastBurn = new Field(w, h, -1);
    this.buf = new Float32Array(w * h);
  }

  step(
    biomass: Field,
    heat: Field,
    water: Field,
    wind: { x: Field; y: Field },
    p: FireParams,
    rng: Rng,
    dt: number,
    tick: number,
  ): void {
    const { w, h } = biomass;
    const flame = this.flame.data, fuel = biomass.data, out = this.buf;
    this.burnedThisTick = 0;

    // Sparks. Rare per cell, common across a hot dry case — which is the whole difference
    // between a fire that is scheduled and a fire that is a consequence.
    let alight = 0;
    for (let i = 0; i < flame.length; i++) {
      if (flame[i] > 0.01) { alight++; continue; }
      if (fuel[i] < p.fuelFloor) continue;
      // Dryness is a matter of degree. The case is damp everywhere, so a hard "must be bone dry"
      // gate means it never catches at all; what actually matters is how much drier than usual
      // this patch is right now, which is a thing high summer does to a hillside.
      const dry = Math.max(0, 1 - water.data[i] / p.wetProof);
      if (dry <= 0) continue;
      const over = heat.data[i] - p.ignitionHeat;
      if (over <= 0) continue;
      if (rng.next() < p.sparkChance * over * over * dry * dry * fuel[i] * dt * 1e3) {
        flame[i] = 0.35;
        alight++;
      }
    }
    // Nothing is burning and nothing lit: the spread and consumption passes have no work.
    if (alight === 0) {
      this.ash.scale(Math.pow(p.ashDecay, dt));
      return;
    }

    // Spread. Flame leans downwind, so a burn runs as a front rather than a circle.
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const i = y * w + x;
        if (fuel[i] < 0.02 || water.data[i] > p.wetProof) { out[i] = 0; continue; }
        const xl = x > 0 ? x - 1 : 0, xr = x < w - 1 ? x + 1 : w - 1;
        const yl = y > 0 ? y - 1 : 0, yr = y < h - 1 ? y + 1 : h - 1;
        const lean = 1 + Math.hypot(wind.x.data[i], wind.y.data[i]) * 2.2;
        const near = flame[y * w + xl] + flame[y * w + xr] + flame[yl * w + x] + flame[yr * w + x];
        out[i] = near * p.spread * lean * Math.min(1, fuel[i] * 2.4) * dt;
      }
    }

    for (let i = 0; i < flame.length; i++) {
      flame[i] = Math.min(1.4, flame[i] + out[i]);
      if (flame[i] <= 0.004) { flame[i] = 0; continue; }
      const eaten = Math.min(fuel[i], flame[i] * p.consume * dt);
      fuel[i] -= eaten;
      this.ash.data[i] += eaten * p.ashYield;
      heat.data[i] += eaten * p.heatRelease;
      this.burnedThisTick += eaten;
      this.lastBurn.data[i] = tick;
      // Flame dies back as its fuel goes, and drowns outright in standing water.
      flame[i] -= (p.decay + (fuel[i] < p.fuelFloor ? 0.14 : 0)) * dt;
      if (water.data[i] > p.wetProof) flame[i] = 0;
      if (flame[i] < 0) flame[i] = 0;
    }

    this.ash.scale(Math.pow(p.ashDecay, dt));
    this.ash.clamp(0, 2);
  }

  /** Total flame in the case. Used only for readouts. */
  burning(): number {
    return this.flame.sum();
  }
}
