import { describe, it, expect } from 'vitest';
import { formatNumber } from '../src/utils/format';
import { canMergeReapers, mergeReapers, getReaperPower } from '../src/game/reapers';
import { getUpgradeCost } from '../src/game/upgrades';
import type { Reaper } from '../src/game/reapers';
import {
  canMergeItems,
  createItem,
  findEmptySlot,
  mergeItems,
  packUsed,
} from '../src/game/backpack';
import { getPlanetNodes, getStarterNode } from '../src/game/locations';

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

describe('backpack', () => {
  it('finds empty slots and tracks used space', () => {
    const items = [createItem('soul_shard', 1, 0), createItem('ash_vial', 1, 2)];
    expect(findEmptySlot(items, 4)).toBe(1);
    expect(packUsed(items)).toBe(2);
  });

  it('merges matching relics to the next tier', () => {
    const a = createItem('bone_charm', 1, 0);
    const b = createItem('bone_charm', 1, 1);
    expect(canMergeItems(a, b)).toBe(true);
    expect(mergeItems(a, b).tier).toBe(2);
  });

  it('refuses to merge different relics', () => {
    const a = createItem('bone_charm', 1, 0);
    const b = createItem('soul_shard', 1, 1);
    expect(canMergeItems(a, b)).toBe(false);
  });
});

describe('world nodes', () => {
  it('gives every planet a walkable starting site', () => {
    const start = getStarterNode('terra_mortis');
    expect(start.unlockSouls).toBe(0);
    expect(getPlanetNodes('terra_mortis').length).toBeGreaterThanOrEqual(5);
  });
});
