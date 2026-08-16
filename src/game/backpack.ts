import { pickRandom, weightedPick } from '../utils/format';

export type ItemRarity = 'common' | 'uncommon' | 'rare' | 'epic' | 'legendary';
export type ItemKind = 'shard' | 'essence' | 'charm' | 'relic' | 'artifact';

export interface ItemDef {
  id: string;
  name: string;
  icon: string;
  kind: ItemKind;
  rarity: ItemRarity;
  crushSouls: number;
  tapBonus: number;
  idleBonus: number;
  lootBonus: number;
  maxTier: number;
}

export interface PackItem {
  uid: string;
  defId: string;
  tier: number;
  slot: number;
}

export const GRID_COLS = 5;
export const GRID_ROWS = 4;
export const BASE_SLOTS = GRID_COLS * GRID_ROWS;
export const EQUIP_SLOTS = 3;

export const ITEM_DEFS: ItemDef[] = [
  { id: 'soul_shard', name: 'Soul Shard', icon: '💎', kind: 'shard', rarity: 'common', crushSouls: 8, tapBonus: 0, idleBonus: 0, lootBonus: 0, maxTier: 6 },
  { id: 'ash_vial', name: 'Ash Vial', icon: '🧪', kind: 'essence', rarity: 'common', crushSouls: 12, tapBonus: 0.02, idleBonus: 0.04, lootBonus: 0, maxTier: 5 },
  { id: 'bone_charm', name: 'Bone Charm', icon: '🦴', kind: 'charm', rarity: 'uncommon', crushSouls: 20, tapBonus: 0.08, idleBonus: 0, lootBonus: 0.02, maxTier: 5 },
  { id: 'wisp_lantern', name: 'Wisp Lantern', icon: '🏮', kind: 'charm', rarity: 'uncommon', crushSouls: 28, tapBonus: 0.04, idleBonus: 0.06, lootBonus: 0.04, maxTier: 5 },
  { id: 'void_splinter', name: 'Void Splinter', icon: '✴️', kind: 'relic', rarity: 'rare', crushSouls: 60, tapBonus: 0.06, idleBonus: 0.08, lootBonus: 0.06, maxTier: 4 },
  { id: 'scream_pearl', name: 'Scream Pearl', icon: '🔮', kind: 'relic', rarity: 'rare', crushSouls: 80, tapBonus: 0.1, idleBonus: 0.04, lootBonus: 0.08, maxTier: 4 },
  { id: 'dream_tooth', name: 'Dream Tooth', icon: '🦷', kind: 'artifact', rarity: 'epic', crushSouls: 180, tapBonus: 0.12, idleBonus: 0.12, lootBonus: 0.1, maxTier: 3 },
  { id: 'entropy_petal', name: 'Entropy Petal', icon: '🥀', kind: 'artifact', rarity: 'epic', crushSouls: 220, tapBonus: 0.08, idleBonus: 0.16, lootBonus: 0.12, maxTier: 3 },
  { id: 'null_crown', name: 'Null Crown', icon: '👑', kind: 'artifact', rarity: 'legendary', crushSouls: 600, tapBonus: 0.2, idleBonus: 0.2, lootBonus: 0.2, maxTier: 2 },
];

const RARITY_WEIGHT: Record<ItemRarity, number> = {
  common: 48,
  uncommon: 28,
  rare: 14,
  epic: 8,
  legendary: 2,
};

export const RARITY_COLOR: Record<ItemRarity, string> = {
  common: '#9a8ab0',
  uncommon: '#2ecc71',
  rare: '#4a9eff',
  epic: '#9b30ff',
  legendary: '#ffd700',
};

export function getItemDef(id: string): ItemDef {
  return ITEM_DEFS.find((d) => d.id === id) ?? ITEM_DEFS[0];
}

export function createItem(defId: string, tier = 1, slot = -1): PackItem {
  return {
    uid: `item_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    defId,
    tier,
    slot,
  };
}

export function rollLoot(rarityBonus = 0): ItemDef {
  const items = ITEM_DEFS.map((def) => ({
    item: def,
    weight: Math.max(0.4, RARITY_WEIGHT[def.rarity] * (def.rarity === 'common' ? 1 : 1 + rarityBonus)),
  }));
  return weightedPick(items);
}

export function itemPower(item: PackItem): { crush: number; tap: number; idle: number; loot: number } {
  const def = getItemDef(item.defId);
  const scale = Math.pow(2.2, item.tier - 1);
  return {
    crush: Math.floor(def.crushSouls * scale),
    tap: def.tapBonus * scale,
    idle: def.idleBonus * scale,
    loot: def.lootBonus * scale,
  };
}

export function canMergeItems(a: PackItem, b: PackItem): boolean {
  if (a.uid === b.uid) return false;
  if (a.defId !== b.defId || a.tier !== b.tier) return false;
  return a.tier < getItemDef(a.defId).maxTier;
}

export function mergeItems(a: PackItem, b: PackItem): PackItem {
  return {
    uid: `item_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    defId: a.defId,
    tier: a.tier + 1,
    slot: a.slot >= 0 ? a.slot : b.slot,
  };
}

export function findEmptySlot(items: PackItem[], capacity: number): number {
  const used = new Set(items.filter((i) => i.slot >= 0).map((i) => i.slot));
  for (let i = 0; i < capacity; i++) {
    if (!used.has(i)) return i;
  }
  return -1;
}

export function packUsed(items: PackItem[]): number {
  return items.filter((i) => i.slot >= 0).length;
}

export function equippedItems(items: PackItem[]): PackItem[] {
  return items.filter((i) => i.slot < 0 && i.slot >= -EQUIP_SLOTS);
}

export function equippedBonuses(items: PackItem[]): { tap: number; idle: number; loot: number } {
  return equippedItems(items).reduce(
    (acc, item) => {
      const p = itemPower(item);
      acc.tap += p.tap;
      acc.idle += p.idle;
      acc.loot += p.loot;
      return acc;
    },
    { tap: 0, idle: 0, loot: 0 }
  );
}

export function starterLoot(): PackItem[] {
  return [createItem('soul_shard', 1, 0), createItem('ash_vial', 1, 1)];
}

export function randomFlavorDrop(): string {
  return pickRandom([
    'Something cold dropped into your pack.',
    'A relic squirms, then goes still.',
    'You pocket a screaming little thing.',
    'The backpack grows heavier.',
    'Idle reapers mailed you loot.',
  ]);
}
