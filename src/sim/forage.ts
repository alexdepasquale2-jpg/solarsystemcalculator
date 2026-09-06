import { Field } from "./field";

/**
 * What the bodies eat.
 *
 * Growth is logistic against a local carrying capacity that depends on being damp enough, warm
 * enough, and not too steep. It also depends on there being something nearby to seed from, which
 * is why cleared ground stays bare for a while after the herd moves on, and why a river bank
 * becomes a green line without anybody drawing one.
 */
export interface ForageParams {
  growth: number;
  spread: number;
  heatOptimum: number;
  heatTolerance: number;
  wetOptimum: number;
  wetTolerance: number;
  slopePenalty: number;
  /** Share of the standing green a body can strip from one spot per tick. */
  grazeFraction: number;
  /** Ceiling on a single mouthful, so a lush cell cannot be emptied in one step. */
  maxBite: number;
  /** Seed blown in from elsewhere. Without it, ground stripped to zero can never come back:
   *  logistic growth multiplied by nothing stays nothing, and the herd eats itself a desert. */
  seedRain: number;
  /** How much burnt ground out-produces unburnt ground while the ash lasts. */
  ashBonus: number;
}

export const defaultForage: ForageParams = {
  growth: 0.055,
  spread: 0.09,
  heatOptimum: 0.62,
  heatTolerance: 0.30,
  wetOptimum: 0.30,
  wetTolerance: 0.34,
  slopePenalty: 2.2,
  grazeFraction: 0.060,
  maxBite: 0.030,
  seedRain: 0.0016,
  ashBonus: 0.55,
};

export class Forage {
  biomass: Field;
  capacity: Field;
  /** Player rule "nothing grows here": 0 = fertile, 1 = sterile. Erodes at the edges. */
  sterile: Field;

  private g = { x: 0, y: 0 };

  constructor(w: number, h: number) {
    this.biomass = new Field(w, h, 0.2);
    this.capacity = new Field(w, h, 0.5);
    this.sterile = new Field(w, h, 0);
  }

  step(
    elev: Field, heat: Field, water: Field, wear: Field, ash: Field,
    p: ForageParams, dt: number,
  ): void {
    const { w, h } = elev;
    const bio = this.biomass, cap = this.capacity;

    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const i = y * w + x;
        elev.gradAt(x, y, this.g);
        const slope = Math.hypot(this.g.x, this.g.y);
        const wet = water.data[i] * 3;
        const dh = (heat.data[i] - p.heatOptimum) / p.heatTolerance;
        const dw = (wet - p.wetOptimum) / p.wetTolerance;
        let k = Math.exp(-dh * dh) * Math.exp(-dw * dw);
        k /= 1 + slope * p.slopePenalty;
        // Trampled ground carries less. A road is a thing plants lose — but only where the feet
        // actually fall: once wear was made to persist, a heavy penalty here paved the case and
        // starved the herd that paved it.
        k /= 1 + wear.data[i] * 1.8;
        k *= 1 - Math.min(1, this.sterile.data[i]);
        // Burnt ground comes back better than it was. This is the reason a fire is worth having:
        // it lays down a fertile scar the herd will find two seasons later.
        k *= 1 + p.ashBonus * Math.min(1.5, ash.data[i]);
        cap.data[i] = k;
        const room = 1 - bio.data[i] / Math.max(1e-3, k);
        bio.data[i] += (p.growth * bio.data[i] + p.seedRain * k) * room * dt;
        if (bio.data[i] < 0) bio.data[i] = 0;
      }
    }

    bio.diffuse(p.spread * dt);
    bio.clamp(0, 1.5);
    this.sterile.scale(0.99978);
  }

  /**
   * Grazing takes a share of what is standing here, not a fixed ration. That one detail is what
   * makes the herd density-regulated instead of cap-regulated: thin grass feeds badly, badly fed
   * bodies stop breeding, and the grass comes back — or the herd moves and the bare patch stays
   * bare long enough to show up as a shape.
   */
  eat(x: number, y: number, dt: number, p: ForageParams): number {
    const have = this.biomass.sample(x, y);
    if (have <= 0) return 0;
    const took = Math.min(have * p.grazeFraction * dt, p.maxBite * dt);
    this.biomass.splat(x, y, -took);
    return took;
  }
}
