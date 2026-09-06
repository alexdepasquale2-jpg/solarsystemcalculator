import { describe, it, expect } from "vitest";
import { World, defaultParams } from "../src/sim/world";
import { applyTool } from "../src/sim/tools";

/**
 * Every one of these guards a feedback loop that actually detonated during development. They are
 * slow tests on purpose: all three failures took thousands of ticks to show up, and a case that
 * is only stable for two hundred ticks is not stable.
 */

function bare(seed: number): World {
  const w = new World({ width: 64, height: 64, seed, params: defaultParams });
  w.layDirt();
  return w;
}

describe("the media stay bounded", () => {
  it("does not boil: heat gradient drives wind drives heat", () => {
    const w = bare(3);
    for (let i = 0; i < 2500; i++) w.stepPhysics(1);
    const [hlo, hhi] = w.climate.heat.minmax();
    expect(hhi).toBeLessThan(1.8);
    expect(hlo).toBeGreaterThan(-0.6);
    let fastest = 0;
    for (let i = 0; i < w.climate.windX.data.length; i++) {
      fastest = Math.max(fastest, Math.hypot(w.climate.windX.data[i], w.climate.windY.data[i]));
    }
    expect(fastest).toBeLessThanOrEqual(defaultParams.climate.maxWind + 1e-6);
  });

  it("does not tear the dirt into spikes, and keeps relief while doing it", () => {
    const w = bare(3);
    for (let i = 0; i < 300; i++) w.stepPhysics(1);
    const early = w.elev.minmax();
    for (let i = 0; i < 2500; i++) w.stepPhysics(1);
    const [lo, hi] = w.elev.minmax();
    expect(Number.isFinite(hi)).toBe(true);
    expect(hi).toBeLessThan(early[1] * 2);
    // Still a landscape, not a planed tray.
    expect(hi - lo).toBeGreaterThan(0.3);
  });

  it("does not silt up into one growing sink, and does not flood", () => {
    const w = bare(3);
    for (let i = 0; i < 2500; i++) w.stepPhysics(1);
    expect(w.hydro.sediment.minmax()[1]).toBeLessThan(1);
    expect(w.hydro.water.mean()).toBeLessThan(0.25);
    expect(w.hydro.water.mean()).toBeGreaterThan(0.01);
  });

  it("survives its own tools: loose fill must not invert the erosion term", () => {
    const w = bare(9);
    for (let i = 0; i < 200; i++) w.stepPhysics(1);
    const meanBefore = w.elev.mean();
    applyTool(w, { tool: "matter", x: 32, y: 32, radius: 9, strength: 1 });
    applyTool(w, { tool: "open", x: 16, y: 32, radius: 6, strength: 1 });
    applyTool(w, { tool: "block", x: 48, y: 32, radius: 6, strength: 1 });
    for (let i = 0; i < 2000; i++) w.stepPhysics(1);
    expect(w.hydro.hardness.minmax()[0]).toBeGreaterThanOrEqual(0);
    // The floor may drift, but it must not inflate: this ran away to 30x before it was fixed.
    expect(w.elev.mean()).toBeLessThan(meanBefore * 1.5 + 0.5);
  });

  it("refuses to take a step big enough to break its own integrators", () => {
    const a = bare(12);
    const b = bare(12);
    for (let i = 0; i < 30; i++) a.step(1);
    for (let i = 0; i < 30; i++) b.step(9); // asked for nine, gets one
    expect(a.elev.mean()).toBeCloseTo(b.elev.mean(), 10);
    expect(a.tick).toBe(b.tick);
  });
});
