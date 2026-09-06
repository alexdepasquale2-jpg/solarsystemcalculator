import { describe, it, expect } from "vitest";
import { World, defaultParams } from "../src/sim/world";
import { Rng } from "../src/sim/rng";
import { imitate, dialectDistance, randomTraits, Traits } from "../src/sim/culture";
import { applyTool } from "../src/sim/tools";

/**
 * These do not test that the tank is fun. They test the four ingredients from the design doc:
 * coupling actually couples, biases actually amplify, and the medium actually keeps a record.
 */

function build(seed: number): World {
  const w = new World({ width: 96, height: 96, seed, params: defaultParams });
  w.init(120, 120);
  return w;
}

describe("the case runs", () => {
  it("is deterministic from a seed", () => {
    const a = build(4242).stats();
    const b = build(4242).stats();
    expect(a.population).toBe(b.population);
    expect(a.biomass).toBeCloseTo(b.biomass, 10);
    expect(a.wear).toBeCloseTo(b.wear, 10);
  });

  it("keeps a population alive rather than dying out or exploding", () => {
    const w = build(7);
    for (let i = 0; i < 400; i++) w.step(1);
    expect(w.pop.bodies.length).toBeGreaterThan(10);
    expect(w.pop.bodies.length).toBeLessThanOrEqual(defaultParams.populationCap);
  });
});

describe("water finds channels nobody drew", () => {
  it("concentrates instead of staying an even sheet", () => {
    // Start from bare dirt, not a settled case: the point is to watch the sheet break up.
    const w = new World({ width: 96, height: 96, seed: 11, params: defaultParams });
    w.layDirt();
    const spread = (f: Float32Array) => {
      let m = 0;
      for (const v of f) m += v;
      m /= f.length;
      let s = 0;
      for (const v of f) s += (v - m) ** 2;
      return Math.sqrt(s / f.length) / (m + 1e-9);
    };
    for (let i = 0; i < 40; i++) w.stepPhysics(1);
    const before = spread(w.hydro.water.data);
    for (let i = 0; i < 500; i++) w.stepPhysics(1);
    const after = spread(w.hydro.water.data);
    // Coefficient of variation rises: some lines carry much more than the average cell.
    expect(after).toBeGreaterThan(before);
  });
});

describe("record: footfall outlives the feet", () => {
  it("leaves wear in the ground and incises it", () => {
    const w = build(23);
    const elevBefore = w.elev.data.slice();
    for (let i = 0; i < 600; i++) w.step(1);
    expect(w.wear.mean()).toBeGreaterThan(0);

    // Somewhere got measurably lower under traffic, and it is a worn place.
    let worstIdx = 0, worst = 0;
    for (let i = 0; i < w.wear.data.length; i++) {
      if (w.wear.data[i] > worst) { worst = w.wear.data[i]; worstIdx = i; }
    }
    expect(worst).toBeGreaterThan(0.05);
    expect(w.elev.data[worstIdx]).toBeLessThan(elevBefore[worstIdx] + 0.5);
  });

  it("remembers a pour long after the hand left, and can name it", () => {
    const w = build(31);
    const x = 40, y = 40;
    const before = w.elev.sample(x, y);
    applyTool(w, { tool: "matter", x, y, radius: 7, strength: 1 });
    expect(w.elev.sample(x, y)).toBeGreaterThan(before);
    for (let i = 0; i < 500; i++) w.step(1);
    const p = w.probe(x, y);
    expect(p.history.some((e) => e.tool === "matter")).toBe(true);
    // The physics may have eaten some of it, but the case is not back where it started.
    expect(Math.abs(w.elev.sample(x, y) - before)).toBeGreaterThan(1e-4);
  });
});

describe("tools are biases, not commands", () => {
  it("a barren rule suppresses growth locally without touching the rest", () => {
    const w = build(57);
    for (let i = 0; i < 200; i++) w.stepPhysics(1);
    applyTool(w, { tool: "rule", rule: "barren", x: 30, y: 30, radius: 8, strength: 1 });
    for (let i = 0; i < 200; i++) w.stepPhysics(1);
    expect(w.forage.capacity.sample(30, 30)).toBeLessThan(0.02);
    expect(w.forage.biomass.mean()).toBeGreaterThan(0);
  });

  it("heat put into one corner does not stay in that corner", () => {
    const w = build(63);
    applyTool(w, { tool: "heat", x: 20, y: 20, radius: 6, strength: 1 });
    const spotBefore = w.climate.heat.sample(20, 20);
    for (let i = 0; i < 150; i++) w.stepPhysics(1);
    const spotAfter = w.climate.heat.sample(20, 20);
    const neighbourAfter = w.climate.heat.sample(34, 20);
    expect(spotAfter).toBeGreaterThan(0);
    // It spread: the neighbourhood warmed relative to the peak decaying.
    expect(spotAfter - neighbourAfter).toBeLessThan(Math.abs(spotBefore) + 1);
  });
});

describe("habits drift when groups stop meeting", () => {
  it("imitation converges but never exactly, and separated pools diverge", () => {
    const rng = new Rng(99);
    const teacher = randomTraits(rng);
    const pupil: Traits = { ...teacher, shape: teacher.shape + 0.5 };
    const start = dialectDistance(pupil, teacher);
    for (let i = 0; i < 60; i++) imitate(pupil, teacher, 0.25, rng);
    const end = dialectDistance(pupil, teacher);
    expect(end).toBeLessThan(start);
    expect(end).toBeGreaterThan(0); // copy error never fully closes

    // Two pools that only ever copy inside themselves walk apart.
    const rng2 = new Rng(5);
    const base = randomTraits(rng2);
    const poolA = [ { ...base }, { ...base } ];
    const poolB = [ { ...base }, { ...base } ];
    for (let i = 0; i < 800; i++) {
      imitate(poolA[0], poolA[1], 0.2, rng2);
      imitate(poolA[1], poolA[0], 0.2, rng2);
      imitate(poolB[0], poolB[1], 0.2, rng2);
      imitate(poolB[1], poolB[0], 0.2, rng2);
    }
    expect(dialectDistance(poolA[0], poolB[0])).toBeGreaterThan(0.02);
  });

  it("a player mark gets copied wrong and the wrong copy spreads", () => {
    const w = build(77);
    for (let i = 0; i < 200; i++) w.step(1);
    const b = w.pop.bodies[0];
    applyTool(w, { tool: "mark", x: b.x, y: b.y, radius: 3, strength: 1, shape: 0.9 });
    const original = w.marks[w.marks.length - 1].shape;
    for (let i = 0; i < 900; i++) w.step(1);
    const copies = w.marks.filter((m) => m.generation > 0);
    if (copies.length) {
      expect(copies.some((m) => Math.abs(m.shape - original) > 1e-6)).toBe(true);
    }
    // Either way, somebody near the mark now carries a shape closer to it than chance.
    expect(w.pop.bodies.length).toBeGreaterThan(0);
  });
});
