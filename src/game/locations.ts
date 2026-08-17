import { PLANETS } from './planets';

export type NodeKind = 'grove' | 'ruin' | 'rift' | 'camp' | 'cache' | 'shrine';

export interface WorldNode {
  id: string;
  planetId: string;
  name: string;
  icon: string;
  kind: NodeKind;
  x: number;
  y: number;
  soulMult: number;
  lootChance: number;
  unlockSouls: number;
  flavor: string;
}

const KIND_META: Record<NodeKind, { soulMult: number; lootChance: number }> = {
  grove: { soulMult: 1, lootChance: 0.18 },
  camp: { soulMult: 0.85, lootChance: 0.28 },
  ruin: { soulMult: 1.25, lootChance: 0.35 },
  shrine: { soulMult: 1.4, lootChance: 0.22 },
  cache: { soulMult: 0.6, lootChance: 0.55 },
  rift: { soulMult: 1.8, lootChance: 0.4 },
};

const PLANET_SITES: Record<string, { name: string; icon: string; kind: NodeKind; flavor: string }[]> = {
  terra_mortis: [
    { name: 'Cracked Fields', icon: '🌾', kind: 'grove', flavor: 'Souls seep from split soil.' },
    { name: 'Ash Camp', icon: '🏕️', kind: 'camp', flavor: 'Abandoned harvester tents still whisper.' },
    { name: 'Bone Well', icon: '🕳️', kind: 'ruin', flavor: 'A dry well stacked with nameless ribs.' },
    { name: 'Whisper Shrine', icon: '🕯️', kind: 'shrine', flavor: 'Prayers here are answered by silence.' },
    { name: 'Rift Scar', icon: '⚡', kind: 'rift', flavor: 'The first tear. Something looks back.' },
  ],
  gelatinous_moon: [
    { name: 'Wobble Shore', icon: '🟢', kind: 'grove', flavor: 'The ground breathes under your boots.' },
    { name: 'Bounce Dunes', icon: '🫧', kind: 'camp', flavor: 'Tents sink and resurface on a schedule.' },
    { name: 'Scream Pit', icon: '😱', kind: 'ruin', flavor: 'Jelly remembers every voice it ate.' },
    { name: 'Membrane Gate', icon: '🚪', kind: 'cache', flavor: 'Push through. It pushes back.' },
    { name: 'Jelly Core', icon: '💠', kind: 'rift', flavor: 'A heartbeat made of pudding and dread.' },
  ],
  screaming_nebula: [
    { name: 'Choir Drift', icon: '🎵', kind: 'grove', flavor: 'Harmonies of extinct languages.' },
    { name: 'Mute Camp', icon: '🔇', kind: 'camp', flavor: 'Harvesters stuff wax in their ears.' },
    { name: 'Regret Reef', icon: '🪸', kind: 'ruin', flavor: 'Coral grown from last words.' },
    { name: 'Echo Shrine', icon: '📡', kind: 'shrine', flavor: 'Say nothing. It still answers.' },
    { name: 'Howl Rift', icon: '🌪️', kind: 'rift', flavor: 'A scream that never finishes.' },
  ],
  inverted_ocean: [
    { name: 'Falling Tide', icon: '🌊', kind: 'grove', flavor: 'Water climbs the sky like ivy.' },
    { name: 'Memory Shoal', icon: '🐟', kind: 'camp', flavor: 'Fish recite your childhood.' },
    { name: 'Drowned Keep', icon: '🏯', kind: 'ruin', flavor: 'Banners wave downward forever.' },
    { name: 'Pearl Cache', icon: '🦪', kind: 'cache', flavor: 'Each pearl holds a stolen hour.' },
    { name: 'Abyss Mouth', icon: '🌀', kind: 'rift', flavor: 'Do not look at the teeth.' },
  ],
  bone_cathedral: [
    { name: 'Nave of Ribs', icon: '🦴', kind: 'grove', flavor: 'The pews are vertebrae.' },
    { name: 'Marrow Choir', icon: '🎶', kind: 'shrine', flavor: 'They never learned the last verse.' },
    { name: 'Ossuary Camp', icon: '⛺', kind: 'camp', flavor: 'Sleep among the faithful dead.' },
    { name: 'Reliquary', icon: '📦', kind: 'cache', flavor: 'Saints stored in labeled jars.' },
    { name: 'Heart Altar', icon: '❤️', kind: 'rift', flavor: 'It still beats. Do not help it.' },
  ],
  clockwork_hive: [
    { name: 'Tick Meadow', icon: '⏱️', kind: 'grove', flavor: 'Grass grows in second-increments.' },
    { name: 'Gear Camp', icon: '⚙️', kind: 'camp', flavor: 'Workers rewind their own memories.' },
    { name: 'Stopped Factory', icon: '🏭', kind: 'ruin', flavor: 'Yesterday is still being assembled.' },
    { name: 'Spring Cache', icon: '🧰', kind: 'cache', flavor: 'Time bottled in brass.' },
    { name: 'Pendulum Rift', icon: '🕰️', kind: 'rift', flavor: 'You arrive before you left.' },
  ],
  dream_maw: [
    { name: 'Soft Fields', icon: '☁️', kind: 'grove', flavor: 'The grass is someone else\'s pillow.' },
    { name: 'Lucid Camp', icon: '🛌', kind: 'camp', flavor: 'Pinch yourself. It pinches back.' },
    { name: 'Nightmare Ruin', icon: '👁️', kind: 'ruin', flavor: 'Doors open onto your worst week.' },
    { name: 'Tooth Shrine', icon: '🦷', kind: 'shrine', flavor: 'Offer a secret. Keep the tooth.' },
    { name: 'Uvula Rift', icon: '🕳️', kind: 'rift', flavor: 'The god swallows slowly.' },
  ],
  entropy_bloom: [
    { name: 'Wilt Gardens', icon: '🥀', kind: 'grove', flavor: 'Petals age you as they fall.' },
    { name: 'Compost Camp', icon: '🍂', kind: 'camp', flavor: 'Everything here is almost over.' },
    { name: 'Face Thicket', icon: '😶', kind: 'ruin', flavor: 'The roses have expressions.' },
    { name: 'Seed Vault', icon: '🌰', kind: 'cache', flavor: 'Each seed is a dead timeline.' },
    { name: 'Bloom Heart', icon: '🌺', kind: 'rift', flavor: 'Beauty that unmakes rooms.' },
  ],
  void_palace: [
    { name: 'Empty Courtyard', icon: '🌑', kind: 'grove', flavor: 'Footsteps echo before you take them.' },
    { name: 'Absent Court', icon: '👑', kind: 'camp', flavor: 'Courtiers who were never born.' },
    { name: 'Throne Ruin', icon: '🪑', kind: 'ruin', flavor: 'Sit and you stop existing slightly.' },
    { name: 'Tribute Vault', icon: '💎', kind: 'cache', flavor: 'Gifts for kings who are not.' },
    { name: 'Null Gate', icon: '🚪', kind: 'rift', flavor: 'The last door. It opens inward.' },
  ],
};

const NODE_LAYOUTS: [number, number][] = [
  [28, 62],
  [68, 58],
  [22, 28],
  [78, 26],
  [50, 42],
];

function buildNodes(): WorldNode[] {
  const nodes: WorldNode[] = [];
  for (const planet of PLANETS) {
    const sites = PLANET_SITES[planet.id] ?? [];
    sites.forEach((site, index) => {
      const [x, y] = NODE_LAYOUTS[index] ?? [50, 50];
      const meta = KIND_META[site.kind];
      nodes.push({
        id: `${planet.id}_${index}`,
        planetId: planet.id,
        name: site.name,
        icon: site.icon,
        kind: site.kind,
        x,
        y,
        soulMult: meta.soulMult,
        lootChance: meta.lootChance,
        unlockSouls: index === 0 ? 0 : Math.floor(planet.unlockCost * 0.15 * index + 20 * index),
        flavor: site.flavor,
      });
    });
  }
  return nodes;
}

export const WORLD_NODES: WorldNode[] = buildNodes();

export function getPlanetNodes(planetId: string): WorldNode[] {
  return WORLD_NODES.filter((n) => n.planetId === planetId);
}

export function getNode(id: string): WorldNode | undefined {
  return WORLD_NODES.find((n) => n.id === id);
}

export function getStarterNode(planetId: string): WorldNode {
  return getPlanetNodes(planetId)[0] ?? WORLD_NODES[0];
}

export function nodeDistance(a: WorldNode, b: WorldNode): number {
  const dx = a.x - b.x;
  const dy = a.y - b.y;
  return Math.hypot(dx, dy);
}
