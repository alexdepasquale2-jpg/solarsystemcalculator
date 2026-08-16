export interface Upgrade {
  id: string;
  name: string;
  description: string;
  icon: string;
  category: 'tap' | 'idle' | 'merge' | 'planet' | 'void';
  baseCost: number;
  costMultiplier: number;
  maxLevel: number;
  effectPerLevel: number;
}

export const UPGRADES: Upgrade[] = [
  {
    id: 'tap_mastery',
    name: 'Tap Mastery',
    description: '+10% souls per tap',
    icon: '👆',
    category: 'tap',
    baseCost: 25,
    costMultiplier: 1.5,
    maxLevel: 50,
    effectPerLevel: 0.1,
  },
  {
    id: 'soul_magnet',
    name: 'Soul Magnet',
    description: '+15% idle harvest rate',
    icon: '🧲',
    category: 'idle',
    baseCost: 100,
    costMultiplier: 1.6,
    maxLevel: 50,
    effectPerLevel: 0.15,
  },
  {
    id: 'merge_catalyst',
    name: 'Merge Catalyst',
    description: '+20% reaper merge efficiency',
    icon: '⚗️',
    category: 'merge',
    baseCost: 250,
    costMultiplier: 1.7,
    maxLevel: 30,
    effectPerLevel: 0.2,
  },
  {
    id: 'planet_scanner',
    name: 'Planet Scanner',
    description: '+5% souls from all planets',
    icon: '📡',
    category: 'planet',
    baseCost: 500,
    costMultiplier: 1.8,
    maxLevel: 40,
    effectPerLevel: 0.05,
  },
  {
    id: 'void_attunement',
    name: 'Void Attunement',
    description: '+25% prestige soul gain',
    icon: '🌀',
    category: 'void',
    baseCost: 1000,
    costMultiplier: 2.0,
    maxLevel: 20,
    effectPerLevel: 0.25,
  },
  {
    id: 'reaper_training',
    name: 'Reaper Training',
    description: 'Reapers start at +1 tier when summoned',
    icon: '📜',
    category: 'merge',
    baseCost: 2000,
    costMultiplier: 2.5,
    maxLevel: 5,
    effectPerLevel: 1,
  },
  {
    id: 'critical_harvest',
    name: 'Critical Harvest',
    description: '5% chance for 10x tap souls',
    icon: '💥',
    category: 'tap',
    baseCost: 750,
    costMultiplier: 1.9,
    maxLevel: 25,
    effectPerLevel: 0.05,
  },
  {
    id: 'auto_deploy',
    name: 'Auto-Deploy',
    description: 'Automatically assign reapers to planets',
    icon: '🤖',
    category: 'idle',
    baseCost: 1500,
    costMultiplier: 2.0,
    maxLevel: 1,
    effectPerLevel: 1,
  },
  {
    id: 'pack_webbing',
    name: 'Pack Webbing',
    description: '+5 backpack slots',
    icon: '🎒',
    category: 'idle',
    baseCost: 400,
    costMultiplier: 2.2,
    maxLevel: 4,
    effectPerLevel: 5,
  },
  {
    id: 'lucky_pockets',
    name: 'Lucky Pockets',
    description: '+8% loot find while exploring',
    icon: '🍀',
    category: 'idle',
    baseCost: 350,
    costMultiplier: 1.75,
    maxLevel: 20,
    effectPerLevel: 0.08,
  },
];

export function getUpgradeCost(upgrade: Upgrade, currentLevel: number): number {
  return Math.floor(upgrade.baseCost * Math.pow(upgrade.costMultiplier, currentLevel));
}

export function getUpgrade(id: string): Upgrade {
  return UPGRADES.find((u) => u.id === id)!;
}
