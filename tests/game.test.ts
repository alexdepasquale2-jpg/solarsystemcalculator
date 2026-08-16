import { describe, it, expect, beforeEach } from 'vitest';
import { formatNumber } from '../src/utils/format';
import { canMergeReapers, mergeReapers, getReaperPower } from '../src/game/reapers';
import { getUpgradeCost } from '../src/game/upgrades';
import type { Reaper } from '../src/game/reapers';

describe('formatNumber', () => {
  it('formats small numbers', () => {
    expect(formatNumber(0)).toBe('0');
    expect(formatNumber(999)).toBe('999');
  });

  it('formats thousands', () => {
    expect(formatNumber(1500)).toBe('1.50K');
    expect(formatNumber(10000)).toBe('10.0K');
  });

  it('formats millions', () => {
    expect(formatNumber(1500000)).toBe('1.50M');
  });
});

describe('reaper merge', () => {
  const base: Reaper = {
    id: 'a',
    tier: 2,
    classId: 'warlock',
    assignedPlanetId: 'terra_mortis',
  };

  it('can merge same tier and class', () => {
    const b = { ...base, id: 'b' };
    expect(canMergeReapers(base, b)).toBe(true);
  });

  it('cannot merge different tiers', () => {
    const b = { ...base, id: 'b', tier: 3 };
    expect(canMergeReapers(base, b)).toBe(false);
  });

  it('merges to next tier', () => {
    const b = { ...base, id: 'b' };
    const merged = mergeReapers(base, b);
    expect(merged.tier).toBe(3);
    expect(merged.classId).toBe('warlock');
  });
});

describe('reaper power', () => {
  it('scales with tier', () => {
    const low: Reaper = { id: '1', tier: 1, classId: 'warlock', assignedPlanetId: null };
    const high: Reaper = { id: '2', tier: 5, classId: 'warlock', assignedPlanetId: null };
    expect(getReaperPower(high)).toBeGreaterThan(getReaperPower(low));
  });
});

describe('upgrade costs', () => {
  it('increases with level', () => {
    const upgrade = {
      id: 'test',
      name: 'Test',
      description: '',
      icon: '',
      category: 'tap' as const,
      baseCost: 100,
      costMultiplier: 1.5,
      maxLevel: 10,
      effectPerLevel: 0.1,
    };
    expect(getUpgradeCost(upgrade, 0)).toBe(100);
    expect(getUpgradeCost(upgrade, 1)).toBe(150);
    expect(getUpgradeCost(upgrade, 5)).toBeGreaterThan(150);
  });
});
