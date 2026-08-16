import { formatNumber, pickRandom, randomBetween, weightedPick } from '../utils/format';
import type { WoWClass } from './reapers';

export interface SimulatedPlayer {
  id: string;
  name: string;
  avatar: string;
  souls: number;
  prestige: number;
  planet: string;
  classId: WoWClass;
  isOnline: boolean;
  lastAction: string;
  lastActionTime: number;
  rank: number;
  guild: string;
  activityPattern: 'grinder' | 'casual' | 'whale' | 'lurker';
}

const AVATARS = ['💀', '👻', '🦇', '🔥', '⚔️', '✨', '🌑', '☠️', '🧙', '👑', '🐉', '🦴'];
const GUILDS = [
  'Void Legion', 'Soul Syndicate', 'Necro Nexus', 'Death Dealers',
  'Harvest Moon', 'Entropy Cult', 'Bone Brigade', 'Dream Eaters',
  'Fel Harvesters', 'Shadow Council', 'Reaper\'s Rest', 'Chaos Collective',
];

const NAME_PREFIXES = [
  'Dark', 'Shadow', 'Void', 'Soul', 'Death', 'Bone', 'Night', 'Blood',
  'Grim', 'Crypt', 'Ash', 'Doom', 'Raven', 'Hex', 'Wraith', 'Necro',
];
const NAME_SUFFIXES = [
  'Reaper', 'Slayer', 'Hunter', 'Walker', 'Bringer', 'Collector',
  'Harvester', 'Devourer', 'Bane', 'Fang', 'Claw', 'Shade', 'Lord',
  'King', 'Mage', 'Priest', 'Knight', 'Warlock', 'Lich', 'Titan',
];
const NAME_MIDDLES = ['', 'the', 'of', 'xX', ''];

const PLANET_NAMES = [
  'Terra Mortis', 'Gelatinous Moon', 'Screaming Nebula', 'Inverted Ocean',
  'Bone Cathedral', 'Clockwork Hive', 'Dream Maw', 'Entropy Bloom', 'Void Palace',
];

const ACTIONS = [
  'harvested {n} souls',
  'merged reapers',
  'unlocked a new planet',
  'ascended to the Void',
  'joined a raid',
  'found a rare soul',
  'upgraded Tap Mastery',
  'deployed reapers',
  'crit for massive harvest',
  'completed daily quest',
];

const CLASSES: WoWClass[] = ['warlock', 'necromancer', 'deathknight', 'soulpriest'];

function generateName(): string {
  const prefix = pickRandom(NAME_PREFIXES);
  const suffix = pickRandom(NAME_SUFFIXES);
  const middle = pickRandom(NAME_MIDDLES);
  if (middle === 'xX') return `xX${prefix}${suffix}Xx`;
  if (middle) return `${prefix}${middle}${suffix}`;
  return `${prefix}${suffix}`;
}

function generatePlayer(index: number, playerSouls: number): SimulatedPlayer {
  const activity = weightedPick([
    { item: 'grinder' as const, weight: 30 },
    { item: 'casual' as const, weight: 45 },
    { item: 'whale' as const, weight: 15 },
    { item: 'lurker' as const, weight: 10 },
  ]);

  const soulMultiplier = {
    grinder: randomBetween(0.8, 2.5),
    casual: randomBetween(0.3, 1.2),
    whale: randomBetween(2.0, 8.0),
    lurker: randomBetween(0.1, 0.5),
  }[activity];

  const souls = Math.floor(playerSouls * soulMultiplier * randomBetween(0.5, 1.5));
  const prestige = souls > 1e9 ? Math.floor(Math.log10(souls) - 6) : 0;

  return {
    id: `sim_${index}`,
    name: generateName(),
    avatar: pickRandom(AVATARS),
    souls: Math.max(souls, Math.floor(randomBetween(10, 1000))),
    prestige,
    planet: pickRandom(PLANET_NAMES),
    classId: pickRandom(CLASSES),
    isOnline: Math.random() > 0.35,
    lastAction: '',
    lastActionTime: Date.now(),
    rank: index + 1,
    guild: pickRandom(GUILDS),
    activityPattern: activity,
  };
}

export class SimulatedWorld {
  players: SimulatedPlayer[] = [];
  globalEvent: GlobalEvent | null = null;
  chatMessages: ChatMessage[] = [];
  private tickInterval: number | null = null;
  private playerSouls = 0;

  constructor() {
    this.regeneratePlayers(0);
    this.startGlobalEvent();
    this.addSystemMessage('Welcome to the Soul Harvest network. 847 harvesters online.');
  }

  setPlayerSouls(souls: number): void {
    this.playerSouls = souls;
    this.updateRanks();
  }

  regeneratePlayers(playerSouls: number): void {
    const count = 50;
    this.players = Array.from({ length: count }, (_, i) => generatePlayer(i, playerSouls));
    this.updateRanks();
  }

  private updateRanks(): void {
    const all = [
      ...this.players,
      { id: 'player', souls: this.playerSouls, name: 'You' },
    ];
    all.sort((a, b) => b.souls - a.souls);
    const rankMap = new Map(all.map((p, i) => [p.id, i + 1]));
    for (const p of this.players) {
      p.rank = rankMap.get(p.id) ?? 99;
    }
  }

  getPlayerRank(): number {
    const all = [...this.players.map((p) => p.souls), this.playerSouls];
    all.sort((a, b) => b - a);
    return all.indexOf(this.playerSouls) + 1;
  }

  startTicking(): void {
    if (this.tickInterval) return;
    this.tickInterval = window.setInterval(() => this.tick(), 3000);
  }

  stopTicking(): void {
    if (this.tickInterval) {
      clearInterval(this.tickInterval);
      this.tickInterval = null;
    }
  }

  private tick(): void {
    for (const player of this.players) {
      if (!player.isOnline && Math.random() < 0.1) {
        player.isOnline = true;
      } else if (player.isOnline && Math.random() < 0.05) {
        player.isOnline = false;
      }

      if (player.isOnline) {
        const growth = {
          grinder: randomBetween(1.01, 1.08),
          casual: randomBetween(1.005, 1.03),
          whale: randomBetween(1.03, 1.15),
          lurker: randomBetween(1.001, 1.01),
        }[player.activityPattern];
        player.souls = Math.floor(player.souls * growth);

        if (Math.random() < 0.15) {
          this.simulateAction(player);
        }
      }
    }

    if (Math.random() < 0.02) {
      this.addRandomChat();
    }

    if (this.globalEvent && Date.now() > this.globalEvent.endsAt) {
      this.startGlobalEvent();
    }

    this.updateRanks();
  }

  private simulateAction(player: SimulatedPlayer): void {
    const action = pickRandom(ACTIONS);
    const n = formatNumber(Math.floor(player.souls * randomBetween(0.001, 0.05)));
    player.lastAction = action.replace('{n}', n);
    player.lastActionTime = Date.now();

    if (Math.random() < 0.08) {
      this.addChat(player.name, player.lastAction);
    }
  }

  private addRandomChat(): void {
    const player = pickRandom(this.players.filter((p) => p.isOnline));
    if (!player) return;

    const messages = [
      `anyone else grinding ${player.planet}?`,
      `just hit ${formatNumber(player.souls)} souls lfg`,
      `merge tips? stuck on tier 6`,
      `gg ${pickRandom(this.players).name} on that ascension`,
      `void event when??`,
      `my reapers are OP after merge catalyst`,
      `who's in ${player.guild}?`,
      `tap or idle build?`,
      `new planet is wild`,
      `soul warlock best class fight me`,
      `LF guild, active player`,
      `brb soul break`,
    ];
    this.addChat(player.name, pickRandom(messages));
  }

  addChat(sender: string, message: string): void {
    this.chatMessages.push({
      id: `chat_${Date.now()}_${Math.random().toString(36).slice(2, 5)}`,
      sender,
      message,
      timestamp: Date.now(),
      isSystem: false,
    });
    if (this.chatMessages.length > 50) {
      this.chatMessages = this.chatMessages.slice(-50);
    }
  }

  addSystemMessage(message: string): void {
    this.chatMessages.push({
      id: `sys_${Date.now()}`,
      sender: 'SYSTEM',
      message,
      timestamp: Date.now(),
      isSystem: true,
    });
  }

  startGlobalEvent(): void {
    const events: Omit<GlobalEvent, 'endsAt'>[] = [
      { name: 'Soul Surge', description: '2x tap harvest for all players!', bonus: 2, type: 'tap' },
      { name: 'Void Storm', description: '3x idle income galaxy-wide!', bonus: 3, type: 'idle' },
      { name: 'Merge Frenzy', description: 'Merge costs reduced 50%!', bonus: 0.5, type: 'merge' },
      { name: 'Planetary Alignment', description: 'All planets yield +100%!', bonus: 2, type: 'planet' },
      { name: 'Blood Moon', description: 'Critical harvest chance doubled!', bonus: 2, type: 'crit' },
    ];
    const event = pickRandom(events);
    this.globalEvent = {
      ...event,
      endsAt: Date.now() + randomBetween(60000, 180000),
    };
    this.addSystemMessage(`🌟 GLOBAL EVENT: ${event.name} — ${event.description}`);
  }

  getLeaderboard(): SimulatedPlayer[] {
    return [...this.players].sort((a, b) => b.souls - a.souls).slice(0, 20);
  }
}

export interface GlobalEvent {
  name: string;
  description: string;
  bonus: number;
  type: 'tap' | 'idle' | 'merge' | 'planet' | 'crit';
  endsAt: number;
}

export interface ChatMessage {
  id: string;
  sender: string;
  message: string;
  timestamp: number;
  isSystem: boolean;
}
