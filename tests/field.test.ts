import { describe, it, expect } from "vitest";
import { Field } from "../src/sim/field";

describe("Field", () => {
  it("samples bilinearly between cells", () => {
    const f = new Field(4, 4, 0);
    f.set(1, 1, 1);
    f.set(2, 1, 3);
    expect(f.sample(1, 1)).toBeCloseTo(1, 6);
    expect(f.sample(1.5, 1)).toBeCloseTo(2, 6);
  });

  it("splats a deposit across the cells it falls between", () => {
    const f = new Field(4, 4, 0);
    f.splat(1.5, 1.5, 1);
    expect(f.sum()).toBeCloseTo(1, 6);
    expect(f.at(1, 1)).toBeCloseTo(0.25, 6);
  });

  it("diffusion spreads without inventing or losing much", () => {
    const f = new Field(32, 32, 0);
    f.set(16, 16, 100);
    const before = f.sum();
    for (let i = 0; i < 40; i++) f.diffuse(0.2);
    expect(f.sum()).toBeCloseTo(before, 2);
    expect(f.at(16, 16)).toBeLessThan(100);
    expect(f.at(18, 16)).toBeGreaterThan(0);
  });

  it("gradient points uphill", () => {
    const f = new Field(8, 8, 0);
    for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) f.set(x, y, x);
    const g = { x: 0, y: 0 };
    f.grad(4, 4, g);
    expect(g.x).toBeCloseTo(1, 6);
    expect(g.y).toBeCloseTo(0, 6);
  });
});
