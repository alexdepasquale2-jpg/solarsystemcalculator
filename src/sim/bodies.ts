import { Field } from "./field";
import { Rng } from "./rng";
import { Traits, Mark, imitate, inherit, randomTraits, dialectDistance } from "./culture";

/**
 * The small bodies.
 *
 * A body reads what is within a couple of body-lengths of itself — forage, heat, wear, water,
 * fire, shelter, whose ground this is, who else is here — and adds up the pulls. It has no
 * destination, no plan, and no knowledge that a herd exists. Herds exist anyway, because a body
 * that likes company steers toward company, and company is where the last body steered.
 *
 * There are two kinds. Grazers eat the field. Hunters eat grazers. Neither knows what it is; the
 * difference is which pulls it computes and what it can swallow.
 */
export const enum Kind {
  Grazer = 0,
  Hunter = 1,
}

export interface Body {
  id: number;
  kind: Kind;
  x: number;
  y: number;
  vx: number;
  vy: number;
  energy: number;
  age: number;
  traits: Traits;
  /** Founder this body descends from. Never changes, never merges. */
  lineage: number;
  bornTick: number;
  /** Tick this body last learned anything from anyone. Used only for readouts. */
  lastCopy: number;
  /** Ticks spent standing still somewhere it liked. Shelter is built out of this. */
  settled: number;
  /** Tick of this body's last kill. A hunter that just ate is busy with it. */
  lastKill: number;
}

export interface KindParams {
  speed: number;
  metabolism: number;
  breedEnergy: number;
  breedCost: number;
  maxAge: number;
  perception: number;
}

export interface BodyParams {
  drag: number;
  starveAt: number;
  crowding: number;
  copyRate: number;
  markCopyRate: number;
  markEmitChance: number;
  wearDeposit: number;

  grazer: KindParams;
  hunter: KindParams;

  /** Energy per unit of forage swallowed. The grazer budget hangs off this. */
  foodValue: number;
  /** Share of a caught body's energy the hunter actually gets. */
  killYield: number;
  /** How close a hunter must be to take something. */
  reach: number;
  /**
   * Ticks a hunter spends on a kill before it can take another.
   *
   * This is the single thing that keeps predation from being a spike: without it a hunter in a
   * dense herd eats continuously, the hunters multiply into the hundreds inside one season, the
   * herd is wiped out, and then the hunters starve with nothing left to recover from.
   */
  handling: number;
  /** How much built-up ground protects the bodies standing on it. */
  shelterRefuge: number;
  /**
   * Below this temperature a hunter is paying to stay warm, and pays hard.
   *
   * This is the refuge the whole predator-prey balance rests on. Given the run of the case, the
   * cold rim is somewhere a hunter cannot make a living and a grazer can — so the herd always
   * has somewhere to be that is not worth following it into, and a crash on the warm side has
   * something to recover from. Without it the hunters find every last grazer, eat them, and
   * starve; that is not a cycle, it is an ending.
   */
  hunterCold: number;
  hunterColdCost: number;
  /**
   * Chance a hunt in reach actually lands, before the crowd is counted.
   *
   * Most hunts fail. That is not flavour: an encounter rate this high with certain kills makes
   * the herd's birth rate irrelevant and the case ends every time.
   */
  catchChance: number;
  /**
   * How much each nearby herd-mate spoils a hunt.
   *
   * Many eyes. This is the one place where being in a crowd pays for itself, so gregariousness
   * stops being a preference the bodies happen to have and becomes a thing that survives.
   */
  vigilance: number;
  /** How hard a grazer runs from a hunter it can see. */
  fear: number;

  /** How fast a settled body builds up shelter under itself. */
  buildRate: number;
  /** Share of metabolism a full shelter saves. Why a cluster is worth returning to. */
  shelterSaving: number;
  /** Pull toward shelter, scaled by how tired the body is. */
  shelterDraw: number;

  /** How strongly a body marks ground as its own by using it. */
  claimRate: number;
  /** Habit distance past which claimed ground reads as somebody else's. */
  claimTolerance: number;

  /** Flame this strong kills. Bodies flee well before it. */
  burnLethal: number;
}

export const defaultBodies: BodyParams = {
  drag: 0.80,
  starveAt: 0.0,
  crowding: 0.55,
  copyRate: 0.035,
  markCopyRate: 0.10,
  markEmitChance: 0.00022,
  wearDeposit: 0.030,

  grazer: {
    speed: 0.085,
    metabolism: 0.0042,
    breedEnergy: 1.22,
    breedCost: 0.78,
    maxAge: 5200,
    perception: 5.0,
  },
  hunter: {
    // Slow, long-lived and hard to breed: a predator that responds quickly to a good year eats
    // through the herd and then has nothing. Endurance through the lean years is what lets the
    // two populations cycle instead of ending.
    speed: 0.112,
    metabolism: 0.0035,
    breedEnergy: 2.30,
    breedCost: 1.30,
    maxAge: 9000,
    perception: 7.0,
  },

  foodValue: 0.42,
  killYield: 0.85,
  reach: 1.10,
  handling: 45,
  shelterRefuge: 0.85,
  hunterCold: 0.62,
  hunterColdCost: 7.5,
  catchChance: 0.55,
  vigilance: 0.40,
  fear: 58,

  buildRate: 0.090,
  shelterSaving: 0.45,
  shelterDraw: 11,

  claimRate: 0.020,
  claimTolerance: 0.16,

  burnLethal: 0.25,
};

/** Uniform-grid neighbour lookup. Keeps the body loop near-linear as the herd grows. */
export class SpatialHash {
  private cell: number;
  private cols: number;
  private rows: number;
  private buckets: number[][];

  constructor(w: number, h: number, cell: number) {
    this.cell = cell;
    this.cols = Math.ceil(w / cell);
    this.rows = Math.ceil(h / cell);
    this.buckets = Array.from({ length: this.cols * this.rows }, () => []);
  }

  rebuild(bodies: Body[]): void {
    for (const b of this.buckets) b.length = 0;
    for (let i = 0; i < bodies.length; i++) {
      const b = bodies[i];
      const cx = Math.min(this.cols - 1, Math.max(0, (b.x / this.cell) | 0));
      const cy = Math.min(this.rows - 1, Math.max(0, (b.y / this.cell) | 0));
      this.buckets[cy * this.cols + cx].push(i);
    }
  }

  /** Indices in the block of cells within `reach` of (x, y). */
  near(x: number, y: number, reach: number, out: number[]): number[] {
    out.length = 0;
    const r = Math.max(1, Math.ceil(reach / this.cell));
    const cx = Math.min(this.cols - 1, Math.max(0, (x / this.cell) | 0));
    const cy = Math.min(this.rows - 1, Math.max(0, (y / this.cell) | 0));
    for (let j = Math.max(0, cy - r); j <= Math.min(this.rows - 1, cy + r); j++) {
      for (let i = Math.max(0, cx - r); i <= Math.min(this.cols - 1, cx + r); i++) {
        const bucket = this.buckets[j * this.cols + i];
        for (let k = 0; k < bucket.length; k++) out.push(bucket[k]);
      }
    }
    return out;
  }
}

export interface BodyContext {
  elev: Field;
  heat: Field;
  water: Field;
  wear: Field;
  border: Field;
  carry: Field;
  biomass: Field;
  flame: Field;
  shelter: Field;
  /** Sum of (habit x weight) laid down on this ground, and the weight itself. */
  claimSum: Field;
  claimWeight: Field;
  eat(x: number, y: number, dt: number): number;
  marks: Mark[];
  tick: number;
}

export interface PopulationEvent {
  kind: "kill" | "starve" | "age" | "burn";
  x: number;
  y: number;
  lineage: number;
  tick: number;
}

export class Population {
  bodies: Body[] = [];
  /** Marks emitted by bodies this tick; the world folds them back in. */
  emitted: Mark[] = [];
  /** Deaths this tick, for the chronicle. Nothing in the sim reads these. */
  events: PopulationEvent[] = [];

  private hash: SpatialHash;
  private nextId = 1;
  private nextLineage = 1;
  private scratch: number[] = [];
  private watchScratch: number[] = [];
  private g = { x: 0, y: 0 };

  constructor(private w: number, private h: number, cell = 6) {
    this.hash = new SpatialHash(w, h, cell);
  }

  seed(n: number, rng: Rng, elev: Field, hunterShare = 0.030): void {
    for (let i = 0; i < n; i++) {
      // Start low, where water and forage already are. No formation, just a plausible puddle.
      let bx = 0, by = 0, best = Infinity;
      for (let k = 0; k < 6; k++) {
        const x = rng.range(2, this.w - 3);
        const y = rng.range(2, this.h - 3);
        const e = elev.sample(x, y);
        if (e < best) { best = e; bx = x; by = y; }
      }
      const hunter = rng.next() < hunterShare;
      this.bodies.push({
        id: this.nextId++,
        kind: hunter ? Kind.Hunter : Kind.Grazer,
        x: bx, y: by, vx: 0, vy: 0,
        energy: rng.range(0.5, 0.9) * (hunter ? 2 : 1),
        age: rng.int(400),
        traits: randomTraits(rng),
        lineage: this.nextLineage++,
        bornTick: 0,
        lastCopy: 0,
        settled: 0,
        lastKill: -9999,
      });
    }
  }

  step(ctx: BodyContext, p: BodyParams, rng: Rng, dt: number, cap: number): void {
    this.emitted.length = 0;
    this.events.length = 0;
    this.hash.rebuild(this.bodies);
    const born: Body[] = [];
    const eaten = new Set<number>();

    for (let i = 0; i < this.bodies.length; i++) {
      const b = this.bodies[i];
      if (eaten.has(i)) continue;
      const t = b.traits;
      const kp = b.kind === Kind.Hunter ? p.hunter : p.grazer;
      let ax = 0, ay = 0;
      const hunger = Math.max(0, (b.kind === Kind.Hunter ? 2.1 : 1.25) - b.energy);

      // --- pull: food. A grazer smells grass. A hunter does not.
      if (b.kind === Kind.Grazer) {
        ctx.biomass.grad(b.x, b.y, this.g);
        ax += this.g.x * 44 * hunger;
        ay += this.g.y * 44 * hunger;
      }

      // --- pull: comfort. Not "go warm" — go toward this body's own idea of warm.
      ctx.heat.grad(b.x, b.y, this.g);
      const err = ctx.heat.sample(b.x, b.y) - t.warmth;
      ax -= this.g.x * err * 30;
      ay -= this.g.y * err * 30;

      // --- pull: the road. Wear attracts, which deepens wear, which attracts.
      // Sharpening the wear field made these gradients much steeper, so the weight has to come
      // down to compensate: a body that follows the path harder than it looks for food starves
      // on a beautifully maintained road.
      ctx.wear.grad(b.x, b.y, this.g);
      ax += this.g.x * 13 * t.roadLove;
      ay += this.g.y * 13 * t.roadLove;

      // --- pull: shelter, and it is worth more the more tired you are
      ctx.shelter.grad(b.x, b.y, this.g);
      const tired = 0.4 + hunger * 0.5;
      ax += this.g.x * p.shelterDraw * tired;
      ay += this.g.y * p.shelterDraw * tired;

      // --- pull: away from fire. Nothing here has to be taught this; the ones that were not
      //     pulled away are not in the list any more.
      const flame = ctx.flame.sample(b.x, b.y);
      if (flame > 0.01) {
        ctx.flame.grad(b.x, b.y, this.g);
        ax -= this.g.x * 300;
        ay -= this.g.y * 300;
      }

      // --- pull: water is drinkable at the edge and lethal in the middle
      const depth = ctx.water.sample(b.x, b.y);
      if (depth > 0.12) {
        ctx.water.grad(b.x, b.y, this.g);
        ax -= this.g.x * 40;
        ay -= this.g.y * 40;
        b.energy -= 0.004 * dt;
      } else if (depth < 0.02) {
        ctx.water.grad(b.x, b.y, this.g);
        ax += this.g.x * 4;
        ay += this.g.y * 4;
      }

      // --- pull: borders. Painted ones, and ones that are just somebody else's ground.
      ctx.border.grad(b.x, b.y, this.g);
      const bstr = ctx.border.sample(b.x, b.y);
      ax -= this.g.x * 55 * t.borderFear * (0.2 + bstr);
      ay -= this.g.y * 55 * t.borderFear * (0.2 + bstr);

      const foreign = this.foreignness(ctx, b.x, b.y, t.shape, p);
      if (foreign > 0) {
        // Read the gradient of foreignness by sampling, not by being told where the line is.
        const fx = this.foreignness(ctx, b.x + 1.5, b.y, t.shape, p)
          - this.foreignness(ctx, b.x - 1.5, b.y, t.shape, p);
        const fy = this.foreignness(ctx, b.x, b.y + 1.5, t.shape, p)
          - this.foreignness(ctx, b.x, b.y - 1.5, t.shape, p);
        ax -= fx * 46 * t.borderFear;
        ay -= fy * 46 * t.borderFear;
      }

      // --- pull: each other. Familiar company, personal space, prey, and predators.
      const near = this.hash.near(b.x, b.y, kp.perception, this.scratch);
      let kinX = 0, kinY = 0, kinW = 0, crowdX = 0, crowdY = 0;
      let teacher = -1, teacherScore = -Infinity;
      let prey = -1, preyD2 = Infinity;
      for (let n = 0; n < near.length; n++) {
        const j = near[n];
        if (j === i || eaten.has(j)) continue;
        const o = this.bodies[j];
        const dx = o.x - b.x, dy = o.y - b.y;
        const d2 = dx * dx + dy * dy;
        if (d2 > kp.perception * kp.perception || d2 < 1e-6) continue;
        const d = Math.sqrt(d2);

        if (b.kind === Kind.Hunter && o.kind === Kind.Grazer) {
          if (d2 < preyD2) { preyD2 = d2; prey = j; }
          continue;
        }
        if (b.kind === Kind.Grazer && o.kind === Kind.Hunter) {
          const urgency = p.fear / (1 + d2);
          ax -= (dx / d) * urgency;
          ay -= (dy / d) * urgency;
          continue;
        }
        if (o.kind !== b.kind) continue;

        const strange = dialectDistance(t, o.traits);
        const familiarity = 1 / (1 + strange * 2.5);
        kinX += (dx / d) * familiarity; kinY += (dy / d) * familiarity; kinW += familiarity;
        if (d < 1.6) { crowdX -= dx / d2; crowdY -= dy / d2; }
        // Prestige: fed, alive a while, and not too foreign to parse.
        const score = o.energy * 1.4 + Math.min(o.age, 1500) / 1500 - strange * 1.1;
        if (score > teacherScore) { teacherScore = score; teacher = j; }
      }

      if (kinW > 0) {
        ax += (kinX / kinW) * 9 * t.gregarious;
        ay += (kinY / kinW) * 9 * t.gregarious;
      }
      ax += crowdX * p.crowding * 9;
      ay += crowdY * p.crowding * 9;

      if (prey >= 0) {
        const o = this.bodies[prey];
        const d = Math.sqrt(preyD2);
        const keen = 14 + hunger * 26;
        ax += ((o.x - b.x) / d) * keen;
        ay += ((o.y - b.y) / d) * keen;
        // A kill needs the hunter free, the prey in reach, and the prey not standing on ground
        // its own kind has built up: a camp is worth something beyond warmth.
        const busy = ctx.tick - b.lastKill < p.handling;
        if (!busy && d < p.reach) {
          const cover = Math.min(1, ctx.shelter.sample(o.x, o.y) * p.shelterRefuge);
          const watched = this.grazersAround(o.x, o.y, 3.2, prey);
          const lands = p.catchChance / (1 + p.vigilance * watched);
          if (rng.next() > cover && rng.next() < lands) {
            eaten.add(prey);
            b.energy += Math.max(0.25, o.energy) * p.killYield;
            b.lastKill = ctx.tick;
            this.events.push({ kind: "kill", x: o.x, y: o.y, lineage: o.lineage, tick: ctx.tick });
          }
        }
      }

      // --- the noise floor. Without it the tank freezes into whatever it found first. A hungry
      // body wanders wider, which is the only reason a stripped patch ever gets left behind.
      const restless = t.venture * (1 + hunger * 1.6);
      ax += rng.normal(1) * 9 * restless;
      ay += rng.normal(1) * 9 * restless;

      // --- terrain cost: uphill is expensive
      ctx.elev.gradAt(b.x | 0, b.y | 0, this.g);
      ax -= this.g.x * 26;
      ay -= this.g.y * 26;

      b.vx = (b.vx + ax * kp.speed * dt) * p.drag;
      b.vy = (b.vy + ay * kp.speed * dt) * p.drag;
      const sp = Math.hypot(b.vx, b.vy);
      const maxSp = b.kind === Kind.Hunter ? 1.05 : 0.9;
      if (sp > maxSp) { b.vx *= maxSp / sp; b.vy *= maxSp / sp; }

      b.x = Math.max(0.5, Math.min(this.w - 1.5, b.x + b.vx * dt));
      b.y = Math.max(0.5, Math.min(this.h - 1.5, b.y + b.vy * dt));

      // Travel wears the ground; standing about does not. Squaring the speed is what separates
      // a trail from a trampled meadow — a body going somewhere lays down far more than one
      // grazing in circles, so lines survive the threshold where halos do not.
      const moved = Math.min(sp, maxSp);
      ctx.wear.splat(b.x, b.y, p.wearDeposit * moved * moved * dt);

      // Using ground makes it yours, in the only sense the case knows: the habits laid down here
      // are mostly yours, so the next body to arrive can tell whether it is somewhere familiar.
      const claimed = p.claimRate * dt;
      ctx.claimSum.splat(b.x, b.y, t.shape * claimed);
      ctx.claimWeight.splat(b.x, b.y, claimed);

      // Standing still somewhere good builds shelter. Nobody decides to found a settlement.
      // "Settled" cannot mean motionless: the noise floor guarantees every body twitches. It
      // means moving less than a body with somewhere to be.
      if (moved < 0.24 && b.energy > 0.62) {
        b.settled += dt;
        ctx.shelter.splat(b.x, b.y, p.buildRate * dt * Math.min(3, b.settled / 12));
      } else {
        b.settled = Math.max(0, b.settled - dt * 0.6);
      }

      // --- eat, burn, learn
      if (b.kind === Kind.Grazer) b.energy += ctx.eat(b.x, b.y, dt) * p.foodValue;
      const sheltered = 1 - p.shelterSaving * Math.min(1, ctx.shelter.sample(b.x, b.y));
      let burn = kp.metabolism * sheltered;
      if (b.kind === Kind.Hunter) {
        const cold = Math.max(0, p.hunterCold - ctx.heat.sample(b.x, b.y));
        burn *= 1 + p.hunterColdCost * cold;
      }
      b.energy -= (burn + moved * 0.0032) * dt;
      b.age += dt;

      const carry = 1 + ctx.carry.sample(b.x, b.y) * 3;
      if (teacher >= 0 && rng.next() < p.copyRate * carry * dt) {
        const o = this.bodies[teacher];
        // Weight by how much better off the teacher looks. Copying down happens too, weakly.
        // Scaled by how well you parse them. Without this, every body copies the single
        // best-fed body in earshot regardless of how foreign it sounds, and the whole case
        // converges to one habit inside a few thousand ticks — no dialects, so no borders.
        const familiar = 1 / (1 + dialectDistance(t, o.traits) * 3.5);
        const wgt = Math.max(0.03, Math.min(0.5, ((o.energy - b.energy) * 0.5 + 0.12) * familiar));
        imitate(t, o.traits, wgt, rng);
        b.lastCopy = ctx.tick;
      }

      // --- marks: copy the shape off the ground, get it wrong, occasionally leave your version
      for (let m = 0; m < ctx.marks.length; m++) {
        const mk = ctx.marks[m];
        const dx = mk.x - b.x, dy = mk.y - b.y;
        if (dx * dx + dy * dy > 9) continue;
        if (rng.next() < p.markCopyRate * mk.strength * carry * dt) {
          t.shape += (mk.shape - t.shape) * 0.4 + rng.normal(0.05);
          b.lastCopy = ctx.tick;
        }
      }
      if (rng.next() < p.markEmitChance * dt && ctx.wear.sample(b.x, b.y) > 0.35) {
        let gen = 1;
        for (const mk of ctx.marks) {
          if ((mk.x - b.x) ** 2 + (mk.y - b.y) ** 2 < 36) gen = Math.max(gen, mk.generation + 1);
        }
        this.emitted.push({
          x: b.x, y: b.y,
          shape: t.shape + rng.normal(0.04),
          strength: 0.6,
          generation: gen,
          bornTick: ctx.tick,
        });
      }

      if (b.energy > kp.breedEnergy && this.bodies.length + born.length < cap) {
        b.energy -= kp.breedCost;
        born.push({
          id: this.nextId++,
          kind: b.kind,
          x: b.x + rng.range(-1, 1),
          y: b.y + rng.range(-1, 1),
          vx: 0, vy: 0,
          energy: kp.breedCost * 0.75,
          age: 0,
          traits: inherit(t, rng),
          lineage: b.lineage,
          bornTick: ctx.tick,
          lastCopy: ctx.tick,
          settled: 0,
          lastKill: -9999,
        });
      }
    }

    // Death returns matter. A herd that starves in one place fertilises that place.
    const alive: Body[] = [];
    for (let i = 0; i < this.bodies.length; i++) {
      const b = this.bodies[i];
      const kp = b.kind === Kind.Hunter ? p.hunter : p.grazer;
      const burnt = ctx.flame.sample(b.x, b.y) > p.burnLethal;
      if (eaten.has(i)) continue;
      if (burnt || b.energy <= p.starveAt || b.age > kp.maxAge) {
        ctx.biomass.splat(b.x, b.y, 0.05);
        ctx.elev.splat(b.x, b.y, 0.0015);
        this.events.push({
          kind: burnt ? "burn" : b.energy <= p.starveAt ? "starve" : "age",
          x: b.x, y: b.y, lineage: b.lineage, tick: ctx.tick,
        });
      } else {
        alive.push(b);
      }
    }
    this.bodies = alive.concat(born);
  }

  /** How many grazers are close enough to this one to spoil a hunt on it. */
  private grazersAround(x: number, y: number, radius: number, skip: number): number {
    const near = this.hash.near(x, y, radius, this.watchScratch);
    const r2 = radius * radius;
    let n = 0;
    for (let k = 0; k < near.length; k++) {
      const j = near[k];
      if (j === skip) continue;
      const o = this.bodies[j];
      if (o.kind !== Kind.Grazer) continue;
      const dx = o.x - x, dy = o.y - y;
      if (dx * dx + dy * dy <= r2) n++;
    }
    return n;
  }

  /** How much this ground reads as somebody else's, to a body with this habit. */
  private foreignness(ctx: BodyContext, x: number, y: number, shape: number, p: BodyParams): number {
    const weight = ctx.claimWeight.sample(x, y);
    if (weight < 1e-4) return 0;
    const theirs = ctx.claimSum.sample(x, y) / weight;
    const gap = Math.abs(theirs - shape) - p.claimTolerance;
    return gap > 0 ? gap * Math.min(1, weight * 6) : 0;
  }

  count(kind: Kind): number {
    let n = 0;
    for (const b of this.bodies) if (b.kind === kind) n++;
    return n;
  }
}
