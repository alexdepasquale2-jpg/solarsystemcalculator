import { Field } from "./field";
import { Rng } from "./rng";
import { Climate, ClimateParams, defaultClimate } from "./climate";
import { Hydrology, HydroParams, defaultHydro } from "./hydrology";
import { Forage, ForageParams, defaultForage } from "./forage";
import { Population, BodyParams, defaultBodies, Kind } from "./bodies";
import { Fire, FireParams, defaultFire } from "./fire";
import { Aeolian, AeolianParams, defaultAeolian } from "./aeolian";
import { Mark, decayMarks, Traits, TRAIT_KEYS } from "./culture";

/**
 * The case.
 *
 * This file does exactly two things: it holds the media, and it runs the subsystems in an order
 * that lets each one's output land in the next one's input. There is no director in here. Nothing
 * watches a meter and fires an event. If something happens on a Tuesday it is because the water,
 * the heat, the grass and the bodies were all still running on Monday.
 */

export interface WorldParams {
  climate: ClimateParams;
  hydro: HydroParams;
  forage: ForageParams;
  bodies: BodyParams;
  fire: FireParams;
  aeolian: AeolianParams;
  /** How fast a path forgets it was walked on. */
  wearDecay: number;
  /** How much walking compacts and hollows the ground. Roads become gullies become barriers. */
  wearIncision: number;
  /** How fast a painted border loses its authority once nobody reinforces it. */
  borderDecay: number;
  /** How fast an unused shelter falls in. */
  shelterDecay: number;
  /** How fast ground forgets whose it was. Slower than a body lives, faster than a ridge. */
  claimDecay: number;
  markDecay: number;
  populationCap: number;
}

export const defaultParams: WorldParams = {
  climate: defaultClimate,
  hydro: defaultHydro,
  forage: defaultForage,
  bodies: defaultBodies,
  fire: defaultFire,
  aeolian: defaultAeolian,
  // A path has to outlast the feet that made it or the record grade is a lie: at the old rate
  // wear had a half-life of about 180 ticks, which is a fraction of a single body's life.
  wearDecay: 0.99865,
  wearIncision: 0.00055,
  borderDecay: 0.99965,
  shelterDecay: 0.99988,
  claimDecay: 0.99930,
  markDecay: 0.99955,
  populationCap: 900,
};

/** One thing the player did, kept forever so a landform can be traced back to a hand. */
export interface LedgerEntry {
  tick: number;
  tool: string;
  x: number;
  y: number;
  radius: number;
  note: string;
}

export interface WorldOptions {
  width?: number;
  height?: number;
  seed?: number;
  params?: WorldParams;
}

export class World {
  readonly w: number;
  readonly h: number;
  readonly rng: Rng;
  params: WorldParams;

  tick = 0;

  /** The dirt. Everything else is written into or read off this. */
  elev: Field;
  /** Footfall. Decays, but slower than a body lives. */
  wear: Field;
  /** Taught edges. Painted by the player, or inherited from a wear ridge nobody crosses. */
  border: Field;
  /** Where habits travel easily. */
  carry: Field;
  /** Built-up ground: burrows, windbreaks, whatever a body makes by sitting still. */
  shelter: Field;
  /** Whose ground this is, as a weighted running average of the habits laid down on it. */
  claimSum: Field;
  claimWeight: Field;

  climate: Climate;
  hydro: Hydrology;
  forage: Forage;
  fire: Fire;
  aeolian: Aeolian;
  pop: Population;

  marks: Mark[] = [];
  ledger: LedgerEntry[] = [];

  constructor(opts: WorldOptions = {}) {
    this.w = opts.width ?? 180;
    this.h = opts.height ?? 180;
    this.rng = new Rng(opts.seed ?? 20260906);
    this.params = opts.params ?? defaultParams;

    this.elev = new Field(this.w, this.h, 0);
    this.wear = new Field(this.w, this.h, 0);
    this.border = new Field(this.w, this.h, 0);
    this.carry = new Field(this.w, this.h, 0);
    this.shelter = new Field(this.w, this.h, 0);
    this.claimSum = new Field(this.w, this.h, 0);
    this.claimWeight = new Field(this.w, this.h, 0);

    this.climate = new Climate(this.w, this.h);
    this.hydro = new Hydrology(this.w, this.h);
    this.forage = new Forage(this.w, this.h);
    this.fire = new Fire(this.w, this.h);
    this.aeolian = new Aeolian(this.w, this.h);
    this.pop = new Population(this.w, this.h);
  }

  /**
   * The case is already mid-sentence when you open it. So: lay down lumpy dirt, then run a few
   * hundred ticks of weather with nobody in it, so the water has already found somewhere to go.
   */
  init(settleTicks = 170, population = 240): void {
    this.layDirt();
    for (let i = 0; i < settleTicks; i++) this.stepPhysics(1);
    this.pop.seed(population, this.rng, this.elev);
    for (let i = 0; i < 70; i++) this.step(1);
    this.tick = 0;
    this.ledger.length = 0;
  }

  /** Value noise, several octaves. A floor with opinions but no features. */
  layDirt(): void {
    const octaves = [
      { s: 6, a: 1.0 }, { s: 12, a: 0.5 }, { s: 24, a: 0.26 },
      { s: 48, a: 0.13 }, { s: 96, a: 0.07 },
    ];
    for (const oct of octaves) {
      const gw = Math.ceil(this.w / oct.s) + 2;
      const gh = Math.ceil(this.h / oct.s) + 2;
      const g = new Float32Array(gw * gh);
      for (let i = 0; i < g.length; i++) g[i] = this.rng.next();
      for (let y = 0; y < this.h; y++) {
        for (let x = 0; x < this.w; x++) {
          const fx = x / oct.s, fy = y / oct.s;
          const x0 = fx | 0, y0 = fy | 0;
          const tx = smooth(fx - x0), ty = smooth(fy - y0);
          const a = g[y0 * gw + x0], b = g[y0 * gw + x0 + 1];
          const c = g[(y0 + 1) * gw + x0], d = g[(y0 + 1) * gw + x0 + 1];
          const v = (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty;
          this.elev.data[y * this.w + x] += v * oct.a;
        }
      }
    }
    // Tilt the whole case slightly, and dish the rim, so water has somewhere to be going.
    for (let y = 0; y < this.h; y++) {
      for (let x = 0; x < this.w; x++) {
        const i = y * this.w + x;
        const rx = (x / (this.w - 1)) * 2 - 1;
        const ry = (y / (this.h - 1)) * 2 - 1;
        this.elev.data[i] = this.elev.data[i] * 0.85 + ry * 0.22 + (rx * rx + ry * ry) * 0.45;
      }
    }
  }

  /** Media only. Used for settling, and for the slow tick while you are away. */
  stepPhysics(dt: number): void {
    const p = this.params;
    this.climate.step(this.elev, this.hydro.water, p.climate, dt, this.tick);
    this.hydro.step(this.elev, this.climate.moisture, p.hydro, dt);
    // Wind-blown grit is the slowest thing in the case by an order of magnitude, so it runs on
    // every other tick at double weight rather than costing a full grid pass every time.
    if ((this.tick & 1) === 0) {
      this.aeolian.step(
        this.elev, this.hydro.water, this.forage.biomass, this.hydro.hardness,
        this.climate.windX, this.climate.windY, p.aeolian, dt * 2,
      );
    }
    this.forage.step(
      this.elev, this.climate.heat, this.hydro.water, this.wear, this.fire.ash, p.forage, dt,
    );
    this.fire.step(
      this.forage.biomass, this.climate.heat, this.hydro.water,
      { x: this.climate.windX, y: this.climate.windY }, p.fire, this.rng, dt, this.tick,
    );
  }

  /**
   * One tick.
   *
   * `dt` above 1 is not a shortcut: diffusion, advection and erosion here are explicit schemes
   * with a stability limit, and a big step does not fast-forward the case, it detonates it. So
   * the step is capped, and anything that wants more time takes more steps.
   */
  step(dt = 1): void {
    if (dt > 1) dt = 1;
    const p = this.params;
    this.stepPhysics(dt);

    this.pop.step(
      {
        elev: this.elev,
        heat: this.climate.heat,
        water: this.hydro.water,
        wear: this.wear,
        border: this.border,
        carry: this.carry,
        biomass: this.forage.biomass,
        flame: this.fire.flame,
        shelter: this.shelter,
        claimSum: this.claimSum,
        claimWeight: this.claimWeight,
        eat: (x, y, d) => this.forage.eat(x, y, d, p.forage),
        marks: this.marks,
        tick: this.tick,
      },
      p.bodies, this.rng, dt, p.populationCap,
    );

    if (this.pop.emitted.length) {
      for (const m of this.pop.emitted) this.marks.push(m);
      if (this.marks.length > 400) this.marks.splice(0, this.marks.length - 400);
    }

    // The record grade, mechanically: footfall compacts the dirt into a hollow, the hollow
    // takes the water, the water finishes the job. Nobody built a road.
    const wear = this.wear.data, elev = this.elev.data, hard = this.hydro.hardness.data;
    for (let i = 0; i < wear.length; i++) {
      const wv = wear[i];
      if (wv > 0.05) {
        // Trampled dirt is not destroyed, it is loosened: it goes into suspension and the water
        // takes it somewhere. Subtracting it outright planed the whole case down over 10k ticks.
        const cut = p.wearIncision * wv * dt;
        elev[i] -= cut;
        this.hydro.sediment.data[i] += cut;
        hard[i] += 0.00018 * wv * dt;
      }
    }
    this.wear.scale(Math.pow(p.wearDecay, dt));
    // Barely any smearing: wear that diffuses turns every path into a halo around wherever the
    // herd stood, and a halo never becomes a road no matter how deep it gets.
    this.wear.diffuse(0.0035 * dt);
    this.wear.clamp(0, 2.5);
    this.border.scale(Math.pow(p.borderDecay, dt));
    this.carry.scale(0.99975);
    this.shelter.scale(Math.pow(p.shelterDecay, dt));
    this.shelter.clamp(0, 6);
    // Ground forgets whose it was at the same rate in both terms, so the average it stores stays
    // an average and does not drift as it fades.
    const cd = Math.pow(p.claimDecay, dt);
    this.claimSum.scale(cd);
    this.claimWeight.scale(cd);
    this.marks = decayMarks(this.marks, Math.pow(p.markDecay, dt));

    this.tick += dt;
  }

  /**
   * Catch-up for time the case ran while the window was closed.
   *
   * Capped, and the cap is honest: if you leave for a month you do not come back to a month of
   * history, you come back to `budget` ticks of it. The alternative is either a long freeze on
   * load or a coarser step, and a coarser step is not the same case.
   */
  runOffline(ticks: number, budget = 3000): number {
    const n = Math.min(Math.floor(ticks), budget);
    for (let i = 0; i < n; i++) this.step(1);
    return n;
  }

  record(entry: LedgerEntry): void {
    this.ledger.push(entry);
    if (this.ledger.length > 500) this.ledger.shift();
  }

  /** What the camera says when you point it somewhere. Description, never narration. */
  probe(x: number, y: number): Probe {
    const near = this.ledger
      .map((e) => ({ e, d: Math.hypot(e.x - x, e.y - y) }))
      .filter((r) => r.d < r.e.radius + 6)
      .sort((a, b) => a.e.tick - b.e.tick)
      .map((r) => r.e);

    let n = 0, grazers = 0, hunters = 0;
    const mean: Traits = { warmth: 0, gregarious: 0, roadLove: 0, borderFear: 0, venture: 0, shape: 0 };
    for (const b of this.pop.bodies) {
      if (Math.hypot(b.x - x, b.y - y) > 9) continue;
      n++;
      if (b.kind === Kind.Hunter) hunters++; else grazers++;
      for (const k of TRAIT_KEYS) mean[k] += b.traits[k];
    }
    if (n) for (const k of TRAIT_KEYS) mean[k] /= n;

    const claimW = this.claimWeight.sample(x, y);
    const lastBurn = this.fire.lastBurn.sample(x, y);
    return {
      x, y,
      elevation: this.elev.sample(x, y),
      heat: this.climate.heat.sample(x, y),
      water: this.hydro.water.sample(x, y),
      biomass: this.forage.biomass.sample(x, y),
      wear: this.wear.sample(x, y),
      border: this.border.sample(x, y),
      sterile: this.forage.sterile.sample(x, y),
      carry: this.carry.sample(x, y),
      shelter: this.shelter.sample(x, y),
      flame: this.fire.flame.sample(x, y),
      ash: this.fire.ash.sample(x, y),
      dust: this.aeolian.dust.sample(x, y),
      claimStrength: claimW,
      claimShape: claimW > 1e-4 ? this.claimSum.sample(x, y) / claimW : null,
      ticksSinceBurn: lastBurn >= 0 ? this.tick - lastBurn : null,
      grazersNearby: grazers,
      huntersNearby: hunters,
      bodiesNearby: n,
      localTraits: n ? mean : null,
      history: near,
    };
  }

  stats(): Stats {
    const bodies = this.pop.bodies;
    let energy = 0, grazers = 0, hunters = 0;
    const shapes: number[] = [];
    const lineages = new Set<number>();
    let oldest = Infinity;
    for (const b of bodies) {
      energy += b.energy;
      shapes.push(b.traits.shape);
      lineages.add(b.lineage);
      if (b.kind === Kind.Hunter) hunters++; else grazers++;
      if (b.lineage < oldest) oldest = b.lineage;
    }
    shapes.sort((a, b) => a - b);
    // Rough read on whether the habit pool has split in two. Not a win condition; a readout.
    let biggestGap = 0, gapAt = 0;
    for (let i = 1; i < shapes.length; i++) {
      const g = shapes[i] - shapes[i - 1];
      if (g > biggestGap) { biggestGap = g; gapAt = (shapes[i] + shapes[i - 1]) / 2; }
    }
    return {
      tick: this.tick,
      year: this.tick / this.params.climate.seasonPeriod,
      season: this.climate.season,
      population: bodies.length,
      grazers,
      hunters,
      lineages: lineages.size,
      eldestLineage: Number.isFinite(oldest) ? oldest : 0,
      meanEnergy: bodies.length ? energy / bodies.length : 0,
      water: this.hydro.water.sum() / (this.w * this.h),
      biomass: this.forage.biomass.mean(),
      wear: this.wear.mean(),
      shelter: this.shelter.mean(),
      burning: this.fire.burning(),
      ash: this.fire.ash.mean(),
      haze: this.aeolian.haze(),
      marks: this.marks.length,
      dialectSplit: biggestGap,
      dialectSplitAt: gapAt,
    };
  }
}

export interface Probe {
  x: number;
  y: number;
  elevation: number;
  heat: number;
  water: number;
  biomass: number;
  wear: number;
  border: number;
  sterile: number;
  carry: number;
  shelter: number;
  flame: number;
  ash: number;
  dust: number;
  claimStrength: number;
  claimShape: number | null;
  ticksSinceBurn: number | null;
  grazersNearby: number;
  huntersNearby: number;
  bodiesNearby: number;
  localTraits: Traits | null;
  history: LedgerEntry[];
}

export interface Stats {
  tick: number;
  year: number;
  season: number;
  population: number;
  grazers: number;
  hunters: number;
  lineages: number;
  eldestLineage: number;
  meanEnergy: number;
  water: number;
  biomass: number;
  wear: number;
  shelter: number;
  burning: number;
  ash: number;
  haze: number;
  marks: number;
  dialectSplit: number;
  dialectSplitAt: number;
}

function smooth(t: number): number {
  return t * t * (3 - 2 * t);
}
