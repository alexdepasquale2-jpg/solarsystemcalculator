import { getPlanet, type Planet } from './planets';
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
import {
  BASE_SLOTS,
  EQUIP_SLOTS,
  canMergeItems,
  createItem,
  equippedBonuses,
  findEmptySlot,
  getItemDef,
  itemPower,
  mergeItems,
  packUsed,
  rollLoot,
  starterLoot,
  type PackItem,
} from './backpack';
import { getNode, getPlanetNodes, getStarterNode, type WorldNode } from './locations';

const SAVE_KEY = 'soul_harvest_save';
const SAVE_VERSION = 2;

export type NotifyKind = 'tick' | 'state' | 'loot' | 'travel';

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
  packItems?: PackItem[];
  discoveredNodeIds?: string[];
  currentNodeId?: string;
  playerX?: number;
  playerY?: number;
  rummageCount?: number;
}

export interface TapResult {
  souls: number;
  isCritical: boolean;
  x: number;
  y: number;
  loot?: PackItem | null;
}

export interface TravelState {
  fromId: string;
  toId: string;
  startedAt: number;
  duration: number;
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
  packItems: PackItem[] = starterLoot();
  discoveredNodeIds: string[] = [getStarterNode('terra_mortis').id];
  currentNodeId = getStarterNode('terra_mortis').id;
  playerX = getStarterNode('terra_mortis').x;
  playerY = getStarterNode('terra_mortis').y;
  rummageCount = 0;
  travel: TravelState | null = null;
  lastLootDrop: PackItem | null = null;
  packFullWarned = false;

  simulatedWorld: SimulatedWorld;
  private lastTick = Date.now();
  private lootAcc = 0;
  private tickHandle: number | null = null;
  private listeners: Set<(kind: NotifyKind) => void> = new Set();
  floatingNumbers: TapResult[] = [];

  constructor() {
    this.simulatedWorld = new SimulatedWorld();
    this.load();
    this.simulatedWorld.setPlayerSouls(this.souls);
    this.simulatedWorld.startTicking();
  }

  subscribe(listener: (kind: NotifyKind) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private notify(kind: NotifyKind = 'state'): void {
    for (const l of this.listeners) l(kind);
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
      this.addSouls(idleRate * dt, false);
    }

    this.lootAcc += dt;
    if (this.lootAcc >= 4) {
      this.lootAcc = 0;
      this.tryIdleLoot();
    }

    if (this.travel) {
      const t = Math.min(1, (now - this.travel.startedAt) / this.travel.duration);
      const from = getNode(this.travel.fromId);
      const to = getNode(this.travel.toId);
      if (from && to) {
        this.playerX = from.x + (to.x - from.x) * t;
        this.playerY = from.y + (to.y - from.y) * t;
      }
      if (t >= 1 && to) {
        this.currentNodeId = to.id;
        this.playerX = to.x;
        this.playerY = to.y;
        if (!this.discoveredNodeIds.includes(to.id)) {
          this.discoveredNodeIds.push(to.id);
        }
        this.travel = null;
        this.notify('state');
        return;
      }
      this.notify('travel');
      return;
    }

    this.simulatedWorld.setPlayerSouls(this.souls);
    this.notify('tick');
  }

  getCurrentPlanet(): Planet {
    return getPlanet(this.currentPlanetId);
  }

  getCurrentNode(): WorldNode {
    return getNode(this.currentNodeId) ?? getStarterNode(this.currentPlanetId);
  }

  getPackCapacity(): number {
    return BASE_SLOTS + (this.upgradeLevels['pack_webbing'] ?? 0) * 5;
  }

  getEquippedBonuses(): { tap: number; idle: number; loot: number } {
    return equippedBonuses(this.packItems);
  }

  getTapPower(): number {
    const planet = this.getCurrentPlanet();
    const node = this.getCurrentNode();
    const classBonus = REAPER_CLASSES[this.playerClass];
    const tapUpgrade = this.getUpgradeEffect('tap_mastery');
    const planetUpgrade = this.getUpgradeEffect('planet_scanner');
    const prestigeBonus = 1 + this.prestigeLevel * 0.1;
    const eventBonus = this.getEventBonus('tap');
    const packBonus = 1 + this.getEquippedBonuses().tap;

    return (
      planet.baseSoulValue *
      node.soulMult *
      classBonus.tapMultiplier *
      (1 + tapUpgrade) *
      (1 + planetUpgrade) *
      prestigeBonus *
      eventBonus *
      packBonus
    );
  }

  getIdleRate(): number {
    let total = 0;
    const packBonus = 1 + this.getEquippedBonuses().idle;
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
          eventBonus *
          packBonus;
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

    this.addSouls(power, false);
    this.tapCount++;

    const loot = this.rollNodeLoot(isCritical ? 0.35 : 0);
    const result: TapResult = { souls: power, isCritical, x, y, loot };
    this.floatingNumbers.push(result);
    this.notify('tick');
    if (loot) this.notify('loot');
    return result;
  }

  rummage(): { souls: number; loot: PackItem | null } {
    const node = this.getCurrentNode();
    const souls = this.getTapPower() * (2.5 + node.soulMult);
    this.addSouls(souls, false);
    this.rummageCount++;
    const loot = this.rollNodeLoot(0.45 + node.lootChance);
    this.notify(loot ? 'loot' : 'tick');
    return { souls, loot };
  }

  private rollNodeLoot(extraChance: number): PackItem | null {
    const node = this.getCurrentNode();
    const lucky = this.getUpgradeEffect('lucky_pockets');
    const packLoot = this.getEquippedBonuses().loot;
    const chance = Math.min(0.85, node.lootChance + extraChance + lucky + packLoot);
    if (Math.random() > chance) return null;
    return this.addLoot(0.15 + extraChance + packLoot);
  }

  private tryIdleLoot(): void {
    if (this.reapers.length === 0) return;
    this.addLoot(this.getEquippedBonuses().loot);
  }

  addLoot(rarityBonus = 0): PackItem | null {
    const slot = findEmptySlot(this.packItems, this.getPackCapacity());
    if (slot < 0) {
      if (!this.packFullWarned) {
        this.packFullWarned = true;
        this.simulatedWorld.addSystemMessage('🎒 Backpack is full. Crush or merge loot to keep finding relics.');
        this.notify('state');
      }
      return null;
    }
    this.packFullWarned = false;
    const def = rollLoot(rarityBonus);
    const item = createItem(def.id, 1, slot);
    this.packItems.push(item);
    this.lastLootDrop = item;
    this.notify('loot');
    return item;
  }

  crushItem(uid: string): number {
    const item = this.packItems.find((i) => i.uid === uid);
    if (!item) return 0;
    const planet = this.getCurrentPlanet();
    const value = itemPower(item).crush * Math.max(1, planet.baseSoulValue * 0.35);
    this.packItems = this.packItems.filter((i) => i.uid !== uid);
    this.addSouls(value, false);
    this.notify('state');
    return value;
  }

  crushAllShards(): number {
    const shards = this.packItems.filter((i) => i.defId === 'soul_shard' && i.slot >= 0);
    let total = 0;
    for (const shard of shards) {
      total += this.crushItem(shard.uid);
    }
    return total;
  }

  moveItem(uid: string, targetSlot: number): boolean {
    const item = this.packItems.find((i) => i.uid === uid);
    if (!item) return false;
    if (targetSlot >= this.getPackCapacity()) return false;

    const occupant = this.packItems.find((i) => i.uid !== uid && i.slot === targetSlot);
    if (occupant && canMergeItems(item, occupant)) {
      const merged = mergeItems(item, occupant);
      merged.slot = targetSlot;
      this.packItems = this.packItems.filter((i) => i.uid !== uid && i.uid !== occupant.uid);
      this.packItems.push(merged);
      this.notify('state');
      return true;
    }
    if (occupant) {
      occupant.slot = item.slot;
    }
    item.slot = targetSlot;
    this.notify('state');
    return true;
  }

  equipItem(uid: string, equipIndex: number): boolean {
    if (equipIndex < 0 || equipIndex >= EQUIP_SLOTS) return false;
    const item = this.packItems.find((i) => i.uid === uid);
    if (!item) return false;
    const dest = -(equipIndex + 1);
    const occupant = this.packItems.find((i) => i.slot === dest);
    if (occupant) {
      const empty = findEmptySlot(this.packItems.filter((i) => i.uid !== item.uid), this.getPackCapacity());
      occupant.slot = empty >= 0 ? empty : item.slot;
    }
    item.slot = dest;
    this.notify('state');
    return true;
  }

  unequipItem(uid: string): boolean {
    const item = this.packItems.find((i) => i.uid === uid);
    if (!item || item.slot >= 0) return false;
    const empty = findEmptySlot(this.packItems, this.getPackCapacity());
    if (empty < 0) return false;
    item.slot = empty;
    this.notify('state');
    return true;
  }

  addSouls(amount: number, ping = true): void {
    this.souls += amount;
    this.totalSoulsEarned += amount;
    if (ping) this.notify('tick');
  }

  spendSouls(amount: number): boolean {
    if (this.souls < amount) return false;
    this.souls -= amount;
    this.notify('tick');
    return true;
  }

  travelTo(nodeId: string): boolean {
    if (this.travel) return false;
    const dest = getNode(nodeId);
    if (!dest || dest.planetId !== this.currentPlanetId) return false;
    if (dest.id === this.currentNodeId) return false;
    const discovered = this.discoveredNodeIds.includes(dest.id);
    if (!discovered && this.souls < dest.unlockSouls) return false;
    if (!discovered) {
      if (dest.unlockSouls > 0 && !this.spendSouls(dest.unlockSouls)) return false;
    }
    const from = this.getCurrentNode();
    const dist = Math.hypot(dest.x - from.x, dest.y - from.y);
    this.travel = {
      fromId: from.id,
      toId: dest.id,
      startedAt: Date.now(),
      duration: Math.max(700, dist * 28),
    };
    this.notify('travel');
    return true;
  }

  unlockPlanet(planetId: string): boolean {
    const planet = getPlanet(planetId);
    if (this.unlockedPlanetIds.includes(planetId)) return false;
    if (!this.spendSouls(planet.unlockCost)) return false;
    this.unlockedPlanetIds.push(planetId);
    this.selectPlanet(planetId);
    this.simulatedWorld.addSystemMessage(`🪐 You discovered ${planet.name}!`);
    this.notify('state');
    return true;
  }

  selectPlanet(planetId: string): void {
    if (!this.unlockedPlanetIds.includes(planetId)) return;
    this.currentPlanetId = planetId;
    const start = getStarterNode(planetId);
    this.currentNodeId = start.id;
    this.playerX = start.x;
    this.playerY = start.y;
    this.travel = null;
    if (!this.discoveredNodeIds.includes(start.id)) {
      this.discoveredNodeIds.push(start.id);
    }
    this.notify('state');
  }

  buyUpgrade(upgradeId: string): boolean {
    const upgrade = getUpgrade(upgradeId);
    const level = this.upgradeLevels[upgradeId] ?? 0;
    if (level >= upgrade.maxLevel) return false;
    const cost = getUpgradeCost(upgrade, level);
    if (!this.spendSouls(cost)) return false;
    this.upgradeLevels[upgradeId] = level + 1;
    this.notify('state');
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
    this.notify('state');
    return true;
  }

  getReaperSummonCost(): number {
    return Math.floor(50 * Math.pow(1.15, this.reaperSummonCount));
  }

  assignReaper(reaperId: string, planetId: string): void {
    const reaper = this.reapers.find((r) => r.id === reaperId);
    if (!reaper || !this.unlockedPlanetIds.includes(planetId)) return;
    reaper.assignedPlanetId = planetId;
    this.notify('state');
  }

  mergeReaperPair(idA: string, idB: string): boolean {
    const a = this.reapers.find((r) => r.id === idA);
    const b = this.reapers.find((r) => r.id === idB);
    if (!a || !b || !canMergeReapers(a, b)) return false;

    const merged = mergeReapers(a, b);
    this.reapers = this.reapers.filter((r) => r.id !== idA && r.id !== idB);
    this.reapers.push(merged);
    this.notify('state');
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
    if (mergeCount > 0) this.notify('state');
    return mergeCount;
  }

  canPrestige(): boolean {
    return this.totalSoulsEarned >= 1_000_000;
  }

  getPrestigeReward(): number {
    const voidBonus = 1 + this.getUpgradeEffect('void_attunement');
    return Math.floor(Math.sqrt(this.totalSoulsEarned / 1_000_000) * voidBonus);
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
    this.packItems = starterLoot();
    this.discoveredNodeIds = [getStarterNode('terra_mortis').id];
    this.currentNodeId = getStarterNode('terra_mortis').id;
    this.playerX = getStarterNode('terra_mortis').x;
    this.playerY = getStarterNode('terra_mortis').y;
    this.rummageCount = 0;
    this.travel = null;

    this.simulatedWorld.addSystemMessage(
      `🌀 You ascended to the Void! +${reward} Prestige Souls (Total: ${this.prestigeSouls})`
    );
    this.notify('state');
    return true;
  }

  setPlayerClass(classId: WoWClass): void {
    this.playerClass = classId;
    this.notify('state');
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
      packItems: this.packItems,
      discoveredNodeIds: this.discoveredNodeIds,
      currentNodeId: this.currentNodeId,
      playerX: this.playerX,
      playerY: this.playerY,
      rummageCount: this.rummageCount,
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
      if (save.version > SAVE_VERSION) return;

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
      this.packItems = save.packItems?.length ? save.packItems : starterLoot();
      this.discoveredNodeIds = save.discoveredNodeIds?.length
        ? save.discoveredNodeIds
        : [getStarterNode(this.currentPlanetId).id];
      const start = getStarterNode(this.currentPlanetId);
      this.currentNodeId = save.currentNodeId ?? start.id;
      this.playerX = save.playerX ?? start.x;
      this.playerY = save.playerY ?? start.y;
      this.rummageCount = save.rummageCount ?? 0;

      const offlineSeconds = (Date.now() - save.lastSaveTime) / 1000;
      if (offlineSeconds > 5) {
        const offlineSouls = this.getIdleRate() * Math.min(offlineSeconds, 3600 * 8);
        if (offlineSouls > 0) {
          this.addSouls(offlineSouls, false);
        }
        const lootTicks = Math.floor(Math.min(offlineSeconds, 3600 * 2) / 8);
        for (let i = 0; i < lootTicks; i++) {
          if (!this.addLoot(0.05)) break;
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
    this.packItems = starterLoot();
    this.discoveredNodeIds = [getStarterNode('terra_mortis').id];
    this.currentNodeId = getStarterNode('terra_mortis').id;
    this.playerX = getStarterNode('terra_mortis').x;
    this.playerY = getStarterNode('terra_mortis').y;
    this.rummageCount = 0;
    this.travel = null;
    this.notify('state');
  }
}

let engineInstance: GameEngine | null = null;

export function getGameEngine(): GameEngine {
  if (!engineInstance) {
    engineInstance = new GameEngine();
  }
  return engineInstance;
}

export function resetEngineForTests(): GameEngine {
  engineInstance = new GameEngine();
  return engineInstance;
}

export { getPlanetNodes, packUsed, getItemDef, EQUIP_SLOTS };
