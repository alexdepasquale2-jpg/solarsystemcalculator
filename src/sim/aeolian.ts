import { Field } from "./field";

/**
 * Wind moving loose dry grit.
 *
 * This is the design doc's own example, put in on purpose: nobody writes "dune". Wind lifts
 * grains where the ground is dry, bare and unarmoured; it carries them; it drops them where it
 * slows down or where something is standing in the way. A grain that lands makes the ground
 * slightly rougher there, which slows the wind slightly more, which catches the next grain.
 *
 * The result is that the dry side of the case grows ripples that migrate downwind, that plants
 * anchor them into hummocks, and that anything the player builds on the dry side eventually
 * grows a tail of drift behind it. None of those three sentences exists as a rule.
 */
export interface AeolianParams {
  /** Wind speed below which nothing moves at all. Sand has a threshold; that matters. */
  threshold: number;
  /** How readily bare dry ground gives up grains. */
  lift: number;
  /** How readily airborne grit comes back down. */
  settle: number;
  /** How much standing vegetation traps passing grit. */
  trap: number;
  /** Water content above which the ground is too heavy to lift. */
  dampProof: number;
  /** Ceiling on how much one cell may lose or gain per tick. */
  maxMove: number;
  /** Airborne grit smears out as it travels. */
  diffuse: number;
}

export const defaultAeolian: AeolianParams = {
  threshold: 0.055,
  lift: 0.055,
  settle: 0.11,
  trap: 2.6,
  dampProof: 0.030,
  maxMove: 0.0022,
  diffuse: 0.05,
};

export class Aeolian {
  /** Grit currently in the air. Visible as haze when the case is dry and windy. */
  dust: Field;

  constructor(w: number, h: number) {
    this.dust = new Field(w, h, 0);
  }

  step(
    elev: Field,
    water: Field,
    biomass: Field,
    hardness: Field,
    windX: Field,
    windY: Field,
    p: AeolianParams,
    dt: number,
  ): void {
    const dust = this.dust;
    const n = elev.data.length;

    for (let i = 0; i < n; i++) {
      const speed = Math.hypot(windX.data[i], windY.data[i]);
      const damp = water.data[i];
      const cover = biomass.data[i];

      // Lift: only bare, dry, loose ground, and only above the threshold speed.
      if (speed > p.threshold && damp < p.dampProof) {
        const bare = 1 / (1 + cover * p.trap);
        const loose = 1 / (1 + hardness.data[i] * 3);
        const excess = speed - p.threshold;
        const up = Math.min(p.maxMove * dt, excess * excess * p.lift * bare * loose * dt * 40);
        elev.data[i] -= up;
        dust.data[i] += up;
      }

      // Settle: slow air drops its load, and so does air that runs into something growing.
      const slow = Math.max(0, 1 - speed / Math.max(1e-6, p.threshold * 3));
      const caught = Math.min(1, cover * p.trap);
      const rate = p.settle * (0.25 + slow + caught) * dt;
      const down = Math.min(dust.data[i], Math.min(p.maxMove * dt, dust.data[i] * rate));
      dust.data[i] -= down;
      elev.data[i] += down;
    }

    dust.advect(windX, windY, dt);
    dust.diffuse(p.diffuse * dt);
    dust.clamp(0, 1);
  }

  haze(): number {
    return this.dust.mean();
  }
}
