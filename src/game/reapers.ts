export type WoWClass = 'warlock' | 'necromancer' | 'deathknight' | 'soulpriest';

export interface ReaperClass {
  id: WoWClass;
  name: string;
  icon: string;
  description: string;
  tapMultiplier: number;
  idleMultiplier: number;
  mergeBonus: number;
  color: string;
}

export const REAPER_CLASSES: Record<WoWClass, ReaperClass> = {
  warlock: {
    id: 'warlock',
    name: 'Soul Warlock',
    icon: '🔥',
    description: '+50% tap harvest. Fel flames consume souls faster.',
    tapMultiplier: 1.5,
    idleMultiplier: 1.0,
    mergeBonus: 1.0,
    color: '#9b30ff',
  },
  necromancer: {
    id: 'necromancer',
    name: 'Necromancer',
    icon: '💀',
    description: '+40% idle harvest. Raise the dead to reap eternally.',
    tapMultiplier: 1.0,
    idleMultiplier: 1.4,
    mergeBonus: 1.1,
    color: '#4a9eff',
  },
  deathknight: {
    id: 'deathknight',
    name: 'Death Knight',
    icon: '⚔️',
    description: '+25% all harvest. Unholy presence empowers all reapers.',
    tapMultiplier: 1.25,
    idleMultiplier: 1.25,
    mergeBonus: 1.0,
    color: '#c41e3a',
  },
  soulpriest: {
    id: 'soulpriest',
    name: 'Soul Priest',
    icon: '✨',
    description: '+30% merge power. Shadow magic fuses souls efficiently.',
    tapMultiplier: 1.1,
    idleMultiplier: 1.1,
    mergeBonus: 1.3,
    color: '#ffd700',
  },
};

export interface ReaperTier {
  tier: number;
  name: string;
  basePower: number;
  icon: string;
}

export const REAPER_TIERS: ReaperTier[] = [
  { tier: 1, name: 'Wisp', basePower: 1, icon: '👻' },
  { tier: 2, name: 'Shade', basePower: 5, icon: '🌑' },
  { tier: 3, name: 'Phantom', basePower: 25, icon: '💨' },
  { tier: 4, name: 'Specter', basePower: 125, icon: '👁️' },
  { tier: 5, name: 'Wraith', basePower: 625, icon: '🦇' },
  { tier: 6, name: 'Banshee', basePower: 3125, icon: '😱' },
  { tier: 7, name: 'Lich', basePower: 15625, icon: '🧙' },
  { tier: 8, name: 'Archlich', basePower: 78125, icon: '👑' },
  { tier: 9, name: 'Soul Titan', basePower: 390625, icon: '🌟' },
  { tier: 10, name: 'Void Reaper', basePower: 1953125, icon: '☠️' },
];

export interface Reaper {
  id: string;
  tier: number;
  classId: WoWClass;
  assignedPlanetId: string | null;
}

export function getReaperTierInfo(tier: number): ReaperTier {
  return REAPER_TIERS[Math.min(tier - 1, REAPER_TIERS.length - 1)];
}

export function getReaperPower(reaper: Reaper): number {
  const tierInfo = getReaperTierInfo(reaper.tier);
  const classBonus = REAPER_CLASSES[reaper.classId];
  return tierInfo.basePower * classBonus.idleMultiplier;
}

export function canMergeReapers(a: Reaper, b: Reaper): boolean {
  return a.tier === b.tier && a.classId === b.classId && a.id !== b.id;
}

export function mergeReapers(a: Reaper, b: Reaper): Reaper {
  const classBonus = REAPER_CLASSES[a.classId];
  const newTier = Math.min(a.tier + 1, REAPER_TIERS.length);
  return {
    id: `reaper_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
    tier: newTier,
    classId: a.classId,
    assignedPlanetId: a.assignedPlanetId ?? b.assignedPlanetId,
  };
}
