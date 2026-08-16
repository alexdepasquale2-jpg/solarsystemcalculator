import { PLANETS, getPlanet, type Planet } from './planets';
import {
  REAPER_CLASSES,
  canMergeReapers,
  getReaperPower,
  mergeReapers,
  type Reaper,
  type WoWClass,
} from './reapers';
import { UPGRADES, getUpgrade, getUpgradeCost } from './upgrades';
import { SimulatedWorld } from './simulatedWorld';

const SAVE_KEY = 'soul_harvest_save';
const SAVE_VERSION = 1;

export interface GameSave {
  version: number;
  souls: number;
  totalSoulsEarned: number;
  currentPlanetId: string;
  unlockedPlanetIds: string[];
  reapers: Reaper[];
  upgradeLevels: Record<string, number>;
  playerClass: WoWClass;
  prestigeLevel: number;
  prestigeSouls: number;
  tapCount: number;
  lastSaveTime: number;
  reaperSummonCount: number;
}

export interface TapResult {
  souls: number;
  isCritical: boolean;
  x: number;
  y: number;
}

export class GameEngine {
  souls = 0;
  totalSoulsEarned = 0;
  currentPlanetId = 'terra_mortis';
  unlockedPlanetIds: string[] = ['terra_mortis'];
  reapers: Reaper[] = [];
  upgradeLevels: Record<string, number> = {};
  playerClass: WoWClass = 'warlock';
  prestigeLevel = 0;
  prestigeSouls = 0;
  tapCount = 0;
  reaperSummonCount = 0;

  simulatedWorld: SimulatedWorld;
  private lastTick = Date.now();
  private tickHandle: number | null = null;
  private listeners: Set<() => void> = new Set();
  floatingNumbers: TapResult[] = [];

  constructor() {
    this.simulatedWorld = new SimulatedWorld();
    this.load();
    this.simulatedWorld.setPlayerSouls(this.souls);
    this.simulatedWorld.startTicking();
  }

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private notify(): void {
    for (const l of this.listeners) l();
  }

  start(): void {
    if (this.tickHandle) return;
    this.lastTick = Date.now();
    this.tickHandle = window.setInterval(() => this.gameTick(), 100);
  }

  stop(): void {
    if (this.tickHandle) {
      clearInterval(this.tickHandle);
      this.tickHandle = null;
    }
    this.save();
  }

  private gameTick(): void {
    const now = Date.now();
    const dt = (now - this.lastTick) / 1000;
    this.lastTick = now;

    const idleRate = this.getIdleRate();
    if (idleRate > 0) {
      this.addSouls(idleRate * dt);
    }

    this.floatingNumbers = this.floatingNumbers.filter(
      (_, i) => i > this.floatingNumbers.length - 20
    );

    this.simulatedWorld.setPlayerSouls(this.souls);
    this.notify();
  }

  getCurrentPlanet(): Planet {
    return getPlanet(this.currentPlanetId);
  }

  getTapPower(): number {
    const planet = this.getCurrentPlanet();
    const classBonus = REAPER_CLASSES[this.playerClass];
    const tapUpgrade = this.getUpgradeEffect('tap_mastery');
    const planetUpgrade = this.getUpgradeEffect('planet_scanner');
    const prestigeBonus = 1 + this.prestigeLevel * 0.1;
    const eventBonus = this.getEventBonus('tap');

    return (
      planet.baseSoulValue *
      classBonus.tapMultiplier *
      (1 + tapUpgrade) *
      (1 + planetUpgrade) *
      prestigeBonus *
      eventBonus
    );
  }

  getIdleRate(): number {
    let total = 0;
    for (const reaper of this.reapers) {
      if (reaper.assignedPlanetId) {
        const planet = getPlanet(reaper.assignedPlanetId);
        const power = getReaperPower(reaper);
        const planetUpgrade = this.getUpgradeEffect('planet_scanner');
        const idleUpgrade = this.getUpgradeEffect('soul_magnet');
        const prestigeBonus = 1 + this.prestigeLevel * 0.1;
        const eventBonus = this.getEventBonus('idle');
        total +=
          power *
          planet.baseSoulValue *
          0.1 *
          (1 + planetUpgrade) *
          (1 + idleUpgrade) *
          prestigeBonus *
          eventBonus;
      }
    }
    return total;
  }

  getEventBonus(type: string): number {
    const event = this.simulatedWorld.globalEvent;
    if (!event || event.type !== type) return 1;
    return event.bonus;
  }

  getUpgradeEffect(id: string): number {
    const upgrade = getUpgrade(id);
    const level = this.upgradeLevels[id] ?? 0;
    return level * upgrade.effectPerLevel;
  }

  tap(x: number, y: number): TapResult {
    let power = this.getTapPower();
    const critChance = this.getUpgradeEffect('critical_harvest');
    const critBonus = this.getEventBonus('crit');
    const isCritical = Math.random() < critChance * critBonus;

    if (isCritical) power *= 10;

    this.addSouls(power);
    this.tapCount++;

    const result: TapResult = { souls: power, isCritical, x, y };
    this.floatingNumbers.push(result);
    this.notify();
    return result;
  }

  addSouls(amount: number): void {
    this.souls += amount;
    this.totalSoulsEarned += amount;
    this.notify();
  }

  spendSouls(amount: number): boolean {
    if (this.souls < amount) return false;
    this.souls -= amount;
    this.notify();
    return true;
  }

  unlockPlanet(planetId: string): boolean {
    const planet = getPlanet(planetId);
    if (this.unlockedPlanetIds.includes(planetId)) return false;
    if (!this.spendSouls(planet.unlockCost)) return false;
    this.unlockedPlanetIds.push(planetId);
    this.currentPlanetId = planetId;
    this.simulatedWorld.addSystemMessage(`🪐 You discovered ${planet.name}!`);
    this.notify();
    return true;
  }

  selectPlanet(planetId: string): void {
    if (!this.unlockedPlanetIds.includes(planetId)) return;
    this.currentPlanetId = planetId;
    this.notify();
  }

  buyUpgrade(upgradeId: string): boolean {
    const upgrade = getUpgrade(upgradeId);
    const level = this.upgradeLevels[upgradeId] ?? 0;
    if (level >= upgrade.maxLevel) return false;
    const cost = getUpgradeCost(upgrade, level);
    if (!this.spendSouls(cost)) return false;
    this.upgradeLevels[upgradeId] = level + 1;
    this.notify();
    return true;
  }

  summonReaper(): boolean {
    const cost = this.getReaperSummonCost();
    if (!this.spendSouls(cost)) return false;

    const trainingLevel = this.upgradeLevels['reaper_training'] ?? 0;
    const startTier = 1 + Math.min(trainingLevel, 3);

    const reaper: Reaper = {
      id: `reaper_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      tier: startTier,
      classId: this.playerClass,
      assignedPlanetId: this.currentPlanetId,
    };
    this.reapers.push(reaper);
    this.reaperSummonCount++;
    this.notify();
    return true;
  }

  getReaperSummonCost(): number {
    return Math.floor(50 * Math.pow(1.15, this.reaperSummonCount));
  }

  assignReaper(reaperId: string, planetId: string): void {
    const reaper = this.reapers.find((r) => r.id === reaperId);
    if (!reaper || !this.unlockedPlanetIds.includes(planetId)) return;
    reaper.assignedPlanetId = planetId;
    this.notify();
  }

  mergeReaperPair(idA: string, idB: string): boolean {
    const a = this.reapers.find((r) => r.id === idA);
    const b = this.reapers.find((r) => r.id === idB);
    if (!a || !b || !canMergeReapers(a, b)) return false;

    const merged = mergeReapers(a, b);
    this.reapers = this.reapers.filter((r) => r.id !== idA && r.id !== idB);
    this.reapers.push(merged);
    this.notify();
    return true;
  }

  autoMerge(): number {
    let mergeCount = 0;
    const byKey = new Map<string, Reaper[]>();
    for (const r of this.reapers) {
      const key = `${r.tier}_${r.classId}`;
      if (!byKey.has(key)) byKey.set(key, []);
      byKey.get(key)!.push(r);
    }
    for (const [, group] of byKey) {
      while (group.length >= 2) {
        const a = group.pop()!;
        const b = group.pop()!;
        const mergedReaper = mergeReapers(a, b);
        this.reapers = this.reapers.filter((r) => r.id !== a.id && r.id !== b.id);
        this.reapers.push(mergedReaper);
        group.push(mergedReaper);
        mergeCount++;
      }
    }
    if (mergeCount > 0) this.notify();
    return mergeCount;
  }

  canPrestige(): boolean {
    return this.totalSoulsEarned >= 1_000_000;
  }

  getPrestigeReward(): number {
    return Math.floor(Math.sqrt(this.totalSoulsEarned / 1_000_000));
  }

  prestige(): boolean {
    if (!this.canPrestige()) return false;
    const reward = this.getPrestigeReward();
    this.prestigeSouls += reward;
    this.prestigeLevel++;

    this.souls = 0;
    this.totalSoulsEarned = 0;
    this.currentPlanetId = 'terra_mortis';
    this.unlockedPlanetIds = ['terra_mortis'];
    this.reapers = [];
    this.reaperSummonCount = 0;
    this.tapCount = 0;

    this.simulatedWorld.addSystemMessage(
      `🌀 You ascended to the Void! +${reward} Prestige Souls (Total: ${this.prestigeSouls})`
    );
    this.notify();
    return true;
  }

  setPlayerClass(classId: WoWClass): void {
    this.playerClass = classId;
    this.notify();
  }

  save(): void {
    const save: GameSave = {
      version: SAVE_VERSION,
      souls: this.souls,
      totalSoulsEarned: this.totalSoulsEarned,
      currentPlanetId: this.currentPlanetId,
      unlockedPlanetIds: this.unlockedPlanetIds,
      reapers: this.reapers,
      upgradeLevels: this.upgradeLevels,
      playerClass: this.playerClass,
      prestigeLevel: this.prestigeLevel,
      prestigeSouls: this.prestigeSouls,
      tapCount: this.tapCount,
      lastSaveTime: Date.now(),
      reaperSummonCount: this.reaperSummonCount,
    };
    try {
      localStorage.setItem(SAVE_KEY, JSON.stringify(save));
    } catch {
      // Storage full or unavailable
    }
  }

  load(): void {
    try {
      const raw = localStorage.getItem(SAVE_KEY);
      if (!raw) return;
      const save: GameSave = JSON.parse(raw);
      if (save.version !== SAVE_VERSION) return;

      this.souls = save.souls;
      this.totalSoulsEarned = save.totalSoulsEarned;
      this.currentPlanetId = save.currentPlanetId;
      this.unlockedPlanetIds = save.unlockedPlanetIds;
      this.reapers = save.reapers;
      this.upgradeLevels = save.upgradeLevels;
      this.playerClass = save.playerClass;
      this.prestigeLevel = save.prestigeLevel;
      this.prestigeSouls = save.prestigeSouls;
      this.tapCount = save.tapCount;
      this.reaperSummonCount = save.reaperSummonCount ?? 0;

      const offlineSeconds = (Date.now() - save.lastSaveTime) / 1000;
      if (offlineSeconds > 5) {
        const offlineSouls = this.getIdleRate() * Math.min(offlineSeconds, 3600 * 8);
        if (offlineSouls > 0) {
          this.addSouls(offlineSouls);
        }
      }
    } catch {
      // Corrupt save
    }
  }

  reset(): void {
    localStorage.removeItem(SAVE_KEY);
    this.souls = 0;
    this.totalSoulsEarned = 0;
    this.currentPlanetId = 'terra_mortis';
    this.unlockedPlanetIds = ['terra_mortis'];
    this.reapers = [];
    this.upgradeLevels = {};
    this.playerClass = 'warlock';
    this.prestigeLevel = 0;
    this.prestigeSouls = 0;
    this.tapCount = 0;
    this.reaperSummonCount = 0;
    this.notify();
  }
}

let engineInstance: GameEngine | null = null;

export function getGameEngine(): GameEngine {
  if (!engineInstance) {
    engineInstance = new GameEngine();
  }
  return engineInstance;
}
