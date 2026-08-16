export interface Planet {
  id: string;
  name: string;
  description: string;
  icon: string;
  soulType: string;
  baseSoulValue: number;
  unlockCost: number;
  bizarreFactor: number;
  ambientColor: string;
  flavorText: string;
}

export const PLANETS: Planet[] = [
  {
    id: 'terra_mortis',
    name: 'Terra Mortis',
    description: 'A dying world where souls leak through cracked bedrock.',
    icon: '🌍',
    soulType: 'Earthbound',
    baseSoulValue: 1,
    unlockCost: 0,
    bizarreFactor: 1,
    ambientColor: '#2d5016',
    flavorText: 'The first harvest. Mundane by cosmic standards.',
  },
  {
    id: 'gelatinous_moon',
    name: 'Gelatinous Moon',
    description: 'A quivering satellite of sentient jelly that absorbs screams.',
    icon: '🟢',
    soulType: 'Squishy',
    baseSoulValue: 5,
    unlockCost: 500,
    bizarreFactor: 1.5,
    ambientColor: '#1a6644',
    flavorText: 'Souls bounce. Harvesters report existential wobble.',
  },
  {
    id: 'screaming_nebula',
    name: 'Screaming Nebula',
    description: 'Gas clouds that vocalize the regrets of extinct civilizations.',
    icon: '🌌',
    soulType: 'Vocal',
    baseSoulValue: 25,
    unlockCost: 5000,
    bizarreFactor: 2,
    ambientColor: '#4a1a6b',
    flavorText: 'Earplugs recommended. Souls arrive pre-traumatized.',
  },
  {
    id: 'inverted_ocean',
    name: 'Inverted Ocean',
    description: 'Water falls upward. Fish swim through your memories.',
    icon: '🌊',
    soulType: 'Aqueous',
    baseSoulValue: 150,
    unlockCost: 50000,
    bizarreFactor: 2.5,
    ambientColor: '#0a3d5c',
    flavorText: 'Drowning is optional. Regret is mandatory.',
  },
  {
    id: 'bone_cathedral',
    name: 'Bone Cathedral',
    description: 'A planet-sized ribcage orbiting a pulsing marrow sun.',
    icon: '🦴',
    soulType: 'Calcified',
    baseSoulValue: 1000,
    unlockCost: 500000,
    bizarreFactor: 3,
    ambientColor: '#3d2817',
    flavorText: 'The choir never stops. Neither do the harvests.',
  },
  {
    id: 'clockwork_hive',
    name: 'Clockwork Hive',
    description: 'Mechanical bees harvest time itself. Souls tick backward.',
    icon: '⚙️',
    soulType: 'Temporal',
    baseSoulValue: 7500,
    unlockCost: 5000000,
    bizarreFactor: 3.5,
    ambientColor: '#5c4a1a',
    flavorText: 'You were here yesterday. You will be here tomorrow.',
  },
  {
    id: 'dream_maw',
    name: 'Dream Maw',
    description: 'A sleeping god\'s open mouth. Nightmares are currency.',
    icon: '😴',
    soulType: 'Oneiric',
    baseSoulValue: 50000,
    unlockCost: 50000000,
    bizarreFactor: 4,
    ambientColor: '#1a1a4a',
    flavorText: 'Do not wake it. The souls are dreaming of you.',
  },
  {
    id: 'entropy_bloom',
    name: 'Entropy Bloom',
    description: 'Flowers that wilt universes. Petals are screaming faces.',
    icon: '🥀',
    soulType: 'Entropic',
    baseSoulValue: 400000,
    unlockCost: 500000000,
    bizarreFactor: 5,
    ambientColor: '#4a0a2d',
    flavorText: 'Beauty and decay are the same thing here.',
  },
  {
    id: 'void_palace',
    name: 'Void Palace',
    description: 'An infinite throne room where absent kings demand tribute.',
    icon: '🏰',
    soulType: 'Void-Touched',
    baseSoulValue: 3000000,
    unlockCost: 5000000000,
    bizarreFactor: 6,
    ambientColor: '#0a0612',
    flavorText: 'The final frontier of bizarre. Souls taste like nothing.',
  },
];

export function getPlanet(id: string): Planet {
  return PLANETS.find((p) => p.id === id) ?? PLANETS[0];
}
