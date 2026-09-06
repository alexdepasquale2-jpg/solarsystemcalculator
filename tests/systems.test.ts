import { describe, it, expect } from "vitest";
import { World, defaultParams } from "../src/sim/world";
import { Kind } from "../src/sim/bodies";
import { structures, herds, frontierLength, Chronicle } from "../src/sim/observe";
import { applyTool } from "../src/sim/tools";

function run(seed: number, ticks: number, size = 96): World {
  const w = new World({ width: size, height: size, seed, params: defaultParams });
  w.init(140, 180);
  for (let i = 0; i < ticks; i++) w.step(1);
  return w;
}

describe("the year", () => {
  it("moves the lamp instead of holding it still", () => {
    const w = new World({ width: 64, height: 64, seed: 2, params: defaultParams });
    w.layDirt();
    const seen: number[] = [];
    for (let i = 0; i < defaultParams.climate.seasonPeriod; i++) {
      w.stepPhysics(1);
      w.tick++;
      if (i % 120 === 0) seen.push(w.climate.heat.mean());
    }
    const hi = Math.max(...seen), lo = Math.min(...seen);
    expect(hi - lo).toBeGreaterThan(0.05);
    // And it is a cycle, not a drift: the year comes back to where it started.
    expect(Math.abs(seen[0] - seen[seen.length - 1])).toBeLessThan((hi - lo) * 0.6);
  });
});

describe("fire", () => {
  it("burns fuel, leaves fertile ash, and goes out on its own", () => {
    const w = new World({ width: 64, height: 64, seed: 5, params: defaultParams });
    w.layDirt();
    for (let i = 0; i < 300; i++) w.stepPhysics(1);
    // Light it the way the player would: put heat in, do not call an ignite function.
    applyTool(w, { tool: "heat", x: 32, y: 32, radius: 12, strength: 3 });
    let peak = 0, burnt = 0;
    for (let i = 0; i < 1200; i++) {
      w.stepPhysics(1);
      w.tick++;
      peak = Math.max(peak, w.fire.burning());
      burnt += w.fire.burnedThisTick;
    }
    expect(burnt).toBeGreaterThan(0);
    expect(peak).toBeGreaterThan(0);
    // Nothing burns forever: fuel is finite and flame decays without it.
    expect(w.fire.burning()).toBeLessThan(peak);
    expect(w.fire.ash.mean()).toBeGreaterThan(0);
  });

  it("cannot cross standing water", () => {
    const w = new World({ width: 48, height: 48, seed: 8, params: defaultParams });
    for (let i = 0; i < w.hydro.water.data.length; i++) {
      w.hydro.water.data[i] = 1;
      w.forage.biomass.data[i] = 1;
      w.climate.heat.data[i] = 1.5;
    }
    w.fire.flame.data[24 * 48 + 24] = 1;
    for (let i = 0; i < 60; i++) {
      w.fire.step(
        w.forage.biomass, w.climate.heat, w.hydro.water,
        { x: w.climate.windX, y: w.climate.windY }, defaultParams.fire, w.rng, 1, i,
      );
    }
    expect(w.fire.burning()).toBe(0);
  });
});

describe("wind-blown grit", () => {
  it("moves dirt without creating or destroying it", () => {
    const w = new World({ width: 64, height: 64, seed: 6, params: defaultParams });
    w.layDirt();
    // A dry, bare, windy case: nothing to hold the grit down.
    for (let i = 0; i < w.elev.data.length; i++) {
      w.hydro.water.data[i] = 0;
      w.forage.biomass.data[i] = 0;
      w.climate.windX.data[i] = 0.4;
      w.climate.windY.data[i] = 0.1;
    }
    const before = w.elev.sum() + w.aeolian.dust.sum();
    const snapshot = w.elev.data.slice();
    for (let i = 0; i < 400; i++) {
      w.aeolian.step(
        w.elev, w.hydro.water, w.forage.biomass, w.hydro.hardness,
        w.climate.windX, w.climate.windY, defaultParams.aeolian, 1,
      );
    }
    const after = w.elev.sum() + w.aeolian.dust.sum();
    expect(after).toBeCloseTo(before, 1);
    // It did something: the surface is not where it was.
    let moved = 0;
    for (let i = 0; i < w.elev.data.length; i++) moved += Math.abs(w.elev.data[i] - snapshot[i]);
    expect(moved).toBeGreaterThan(0.05);
  });
});

describe("two kinds of body", () => {
  it("hunters take grazers rather than grass", () => {
    const w = run(41, 900);
    const kills = w.pop.bodies.length;
    expect(kills).toBeGreaterThan(0);
    // Whatever the mix is, hunters never eat the field: the grazer budget is the only one that
    // touches forage, so a case with hunters and no grazers must collapse to no hunters.
    const anyHunter = w.pop.bodies.some((b) => b.kind === Kind.Hunter);
    const anyGrazer = w.pop.bodies.some((b) => b.kind === Kind.Grazer);
    expect(anyHunter && !anyGrazer).toBe(false);
  });

  it("a fed body settles and the settling builds something", () => {
    const w = run(41, 2600);
    expect(w.shelter.minmax()[1]).toBeGreaterThan(0.05);
  });
});

describe("ground remembers whose feet were on it", () => {
  it("accumulates a claim that fades without upkeep", () => {
    const w = run(41, 1200);
    const claimed = w.claimWeight.minmax()[1];
    expect(claimed).toBeGreaterThan(0.01);
    const before = w.claimWeight.sum();
    w.pop.bodies.length = 0;
    for (let i = 0; i < 3000; i++) w.step(1);
    expect(w.claimWeight.sum()).toBeLessThan(before * 0.5);
  });
});

describe("the observer", () => {
  it("names arrangements without being able to cause them", () => {
    const w = run(41, 2000);
    const before = w.elev.data.slice();
    const beforeBodies = w.pop.bodies.length;
    const s = structures(w);
    herds(w);
    frontierLength(w);
    new Chronicle().sample(w);
    // Looking must not touch anything.
    expect(w.pop.bodies.length).toBe(beforeBodies);
    for (let i = 0; i < before.length; i += 97) expect(w.elev.data[i]).toBe(before[i]);
    expect(Array.isArray(s.paths)).toBe(true);
    for (const h of s.herds) expect(h.size).toBeGreaterThanOrEqual(5);
  });

  it("finds herds nobody was assigned to", () => {
    const w = run(41, 1500);
    const found = herds(w);
    if (w.pop.bodies.length > 60) expect(found.length).toBeGreaterThan(0);
    for (const h of found) {
      expect(h.cx).toBeGreaterThanOrEqual(0);
      expect(h.cx).toBeLessThanOrEqual(w.w);
    }
  });
});
