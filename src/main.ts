import { getGameEngine } from './game/engine';
import { PLANETS } from './game/planets';
import { REAPER_CLASSES, getReaperTierInfo, getReaperPower } from './game/reapers';
import { UPGRADES, getUpgradeCost } from './game/upgrades';
import { formatNumber, formatTime } from './utils/format';
import type { Reaper } from './game/reapers';

const engine = getGameEngine();
let currentTab = 'harvest';
let selectedReaperId: string | null = null;

function init(): void {
  setTimeout(() => {
    document.getElementById('loading-screen')?.classList.add('hidden');
    render();
    engine.start();

    engine.subscribe(() => {
      render();
      engine.save();
    });

    setInterval(() => engine.save(), 30000);
  }, 1500);
}

function render(): void {
  const app = document.getElementById('app');
  if (!app) return;

  const planet = engine.getCurrentPlanet();
  const idleRate = engine.getIdleRate();
  const rank = engine.simulatedWorld.getPlayerRank();
  const onlineCount = engine.simulatedWorld.players.filter((p) => p.isOnline).length;
  const event = engine.simulatedWorld.globalEvent;

  app.innerHTML = `
    <div class="game-container">
      ${renderTopBar(idleRate, rank, onlineCount)}
      ${event ? renderEventBanner(event) : ''}
      <div class="main-content">
        <div class="tab-panel ${currentTab === 'harvest' ? 'active' : ''}" id="tab-harvest">
          ${renderHarvestTab(planet)}
        </div>
        <div class="tab-panel ${currentTab === 'planets' ? 'active' : ''}" id="tab-planets">
          ${renderPlanetsTab()}
        </div>
        <div class="tab-panel ${currentTab === 'reapers' ? 'active' : ''}" id="tab-reapers">
          ${renderReapersTab()}
        </div>
        <div class="tab-panel ${currentTab === 'upgrades' ? 'active' : ''}" id="tab-upgrades">
          ${renderUpgradesTab()}
        </div>
        <div class="tab-panel ${currentTab === 'world' ? 'active' : ''}" id="tab-world">
          ${renderWorldTab()}
        </div>
        <div class="tab-panel ${currentTab === 'void' ? 'active' : ''}" id="tab-void">
          ${renderVoidTab()}
        </div>
      </div>
      ${renderBottomNav()}
    </div>
  `;

  bindEvents();
}

function renderTopBar(idleRate: number, rank: number, onlineCount: number): string {
  return `
    <div class="top-bar">
      <div class="soul-counter">
        <span class="soul-icon">💀</span>
        <div>
          <div class="soul-amount">${formatNumber(engine.souls)}</div>
          <div class="soul-rate">+${formatNumber(idleRate)}/s</div>
        </div>
      </div>
      <div class="top-bar-right">
        <div class="player-rank">Rank #${rank}</div>
        <div class="online-badge">
          <span class="online-dot"></span>
          ${onlineCount + 1} online
        </div>
      </div>
    </div>
  `;
}

function renderEventBanner(event: { name: string; description: string; endsAt: number }): string {
  const remaining = Math.max(0, (event.endsAt - Date.now()) / 1000);
  return `
    <div class="event-banner">
      🌟 ${event.name}: ${event.description} (${formatTime(remaining)})
    </div>
  `;
}

function renderHarvestTab(planet: { name: string; description: string; flavorText: string; icon: string; ambientColor: string }): string {
  return `
    <div class="harvest-view">
      <div class="planet-header">
        <div class="planet-name">${planet.icon} ${planet.name}</div>
        <div class="planet-desc">${planet.description}</div>
        <div class="planet-flavor">"${planet.flavorText}"</div>
      </div>
      <div class="tap-zone" id="tap-zone" style="background: radial-gradient(circle at center, ${planet.ambientColor}33 0%, transparent 70%)">
        <div class="tap-orb" style="background: radial-gradient(circle, ${planet.ambientColor}88, ${planet.ambientColor}44); box-shadow: 0 0 40px ${planet.ambientColor}66">
          ${planet.icon}
        </div>
      </div>
      <div class="harvest-actions">
        <button class="btn btn-primary" id="btn-summon">
          <span class="btn-icon">👻</span>
          Summon Reaper<br>${formatNumber(engine.getReaperSummonCost())}
        </button>
        <button class="btn" id="btn-auto-merge">
          <span class="btn-icon">⚗️</span>
          Auto Merge
        </button>
      </div>
    </div>
  `;
}

function renderPlanetsTab(): string {
  return `
    <div class="section-header">🪐 Planets</div>
    ${PLANETS.map((p) => {
      const unlocked = engine.unlockedPlanetIds.includes(p.id);
      const isActive = engine.currentPlanetId === p.id;
      return `
        <div class="planet-card ${unlocked ? '' : 'locked'} ${isActive ? 'active' : ''}"
             data-planet="${p.id}" data-unlocked="${unlocked}">
          <div class="planet-card-icon">${p.icon}</div>
          <div class="planet-card-info">
            <div class="planet-card-name">${p.name}</div>
            <div class="planet-card-soul">${p.soulType} souls · ${formatNumber(p.baseSoulValue)}/tap</div>
          </div>
          ${unlocked
            ? (isActive ? '<span style="color:var(--accent-green);font-size:0.7rem">● Active</span>' : '')
            : `<div class="planet-card-cost">🔓 ${formatNumber(p.unlockCost)}</div>`
          }
        </div>
      `;
    }).join('')}
  `;
}

function renderReapersTab(): string {
  const reapers = engine.reapers;
  if (reapers.length === 0) {
    return `
      <div class="empty-state">
        <div class="empty-state-icon">👻</div>
        <div class="empty-state-text">No reapers yet. Summon one from the Harvest tab!</div>
      </div>
    `;
  }

  return `
    <div class="section-header">👻 Reapers (${reapers.length}) · Tap two to merge</div>
    <div class="reaper-grid">
      ${reapers.map((r) => renderReaperCard(r)).join('')}
    </div>
    <div class="section-header">📜 Class</div>
    <div class="class-grid">
      ${Object.values(REAPER_CLASSES).map((c) => `
        <div class="class-card ${engine.playerClass === c.id ? 'selected' : ''}" data-class="${c.id}">
          <div class="class-card-icon">${c.icon}</div>
          <div class="class-card-name">${c.name}</div>
          <div class="class-card-desc">${c.description}</div>
        </div>
      `).join('')}
    </div>
  `;
}

function renderReaperCard(r: Reaper): string {
  const tier = getReaperTierInfo(r.tier);
  const power = getReaperPower(r);
  const cls = REAPER_CLASSES[r.classId];
  return `
    <div class="reaper-card ${selectedReaperId === r.id ? 'selected' : ''}" data-reaper="${r.id}">
      <div class="reaper-card-icon">${tier.icon}</div>
      <div class="reaper-card-name">${tier.name}</div>
      <div class="reaper-card-tier">Tier ${r.tier} · ${cls.icon}</div>
      <div class="reaper-card-power">${formatNumber(power)}/s</div>
    </div>
  `;
}

function renderUpgradesTab(): string {
  return `
    <div class="section-header">⚡ Upgrades</div>
    ${UPGRADES.map((u) => {
      const level = engine.upgradeLevels[u.id] ?? 0;
      const maxed = level >= u.maxLevel;
      const cost = getUpgradeCost(u, level);
      return `
        <div class="upgrade-item ${maxed ? 'maxed' : ''}" data-upgrade="${u.id}">
          <div class="upgrade-icon">${u.icon}</div>
          <div class="upgrade-info">
            <div class="upgrade-name">${u.name}</div>
            <div class="upgrade-desc">${u.description}</div>
            <div class="upgrade-level">Lv ${level}/${u.maxLevel}</div>
          </div>
          <div class="upgrade-cost">${maxed ? 'MAX' : formatNumber(cost)}</div>
        </div>
      `;
    }).join('')}
  `;
}

function renderWorldTab(): string {
  const leaderboard = engine.simulatedWorld.getLeaderboard();
  const chat = engine.simulatedWorld.chatMessages;

  return `
    <div class="chat-container">
      <div class="section-header">🏆 Leaderboard</div>
      ${leaderboard.slice(0, 10).map((p, i) => `
        <div class="leaderboard-item">
          <div class="lb-rank ${i < 3 ? 'top3' : ''}">${i + 1}</div>
          <div class="lb-avatar">${p.avatar}</div>
          <div class="lb-info">
            <div class="lb-name">${p.name}</div>
            <div class="lb-guild">${p.guild}</div>
          </div>
          <div class="lb-souls">${formatNumber(p.souls)}</div>
          <div class="${p.isOnline ? 'lb-online' : 'lb-offline'}"></div>
        </div>
      `).join('')}
      <div class="leaderboard-item is-player">
        <div class="lb-rank">${engine.simulatedWorld.getPlayerRank()}</div>
        <div class="lb-avatar">🎮</div>
        <div class="lb-info">
          <div class="lb-name">You</div>
          <div class="lb-guild">${REAPER_CLASSES[engine.playerClass].name}</div>
        </div>
        <div class="lb-souls">${formatNumber(engine.souls)}</div>
        <div class="lb-online"></div>
      </div>
      <div class="section-header">💬 Global Chat</div>
      <div class="chat-messages" id="chat-messages">
        ${chat.map((m) => `
          <div class="chat-msg ${m.isSystem ? 'system' : ''}">
            ${m.isSystem ? m.message : `<span class="chat-sender">${m.sender}:</span> ${m.message}`}
          </div>
        `).join('')}
      </div>
      <div class="chat-input-area">
        <input class="chat-input" id="chat-input" placeholder="Say something..." maxlength="100" />
        <button class="btn btn-primary" id="btn-send-chat" style="flex:0;padding:8px 16px">Send</button>
      </div>
    </div>
  `;
}

function renderVoidTab(): string {
  const canPrestige = engine.canPrestige();
  const reward = engine.getPrestigeReward();

  return `
    <div class="section-header">🌀 Void Ascension</div>
    <div class="prestige-card">
      <div class="prestige-title">Ascend to the Void</div>
      <div class="prestige-desc">
        Reset your progress to gain permanent Prestige Souls.
        Each prestige grants +10% to all soul harvest permanently.
      </div>
      <div>Current Prestige: <strong>${engine.prestigeLevel}</strong> (${engine.prestigeSouls} souls)</div>
      <div class="prestige-reward">+${reward} Prestige Souls</div>
      <button class="btn btn-gold" id="btn-prestige" ${canPrestige ? '' : 'disabled'}>
        ${canPrestige ? '🌀 ASCEND' : `Need ${formatNumber(1_000_000)} total souls`}
      </button>
    </div>
    <div class="section-header">📊 Stats</div>
    <div class="card">
      <div style="font-size:0.8rem;line-height:1.8">
        <div>💀 Total Souls Earned: <strong>${formatNumber(engine.totalSoulsEarned)}</strong></div>
        <div>👆 Taps: <strong>${formatNumber(engine.tapCount)}</strong></div>
        <div>👻 Reapers Summoned: <strong>${engine.reaperSummonCount}</strong></div>
        <div>🪐 Planets Unlocked: <strong>${engine.unlockedPlanetIds.length}/${PLANETS.length}</strong></div>
        <div>⚡ Tap Power: <strong>${formatNumber(engine.getTapPower())}</strong></div>
        <div>🔄 Idle Rate: <strong>${formatNumber(engine.getIdleRate())}/s</strong></div>
      </div>
    </div>
    <div style="padding:12px;text-align:center">
      <button class="btn" id="btn-reset" style="color:var(--accent-red);border-color:var(--accent-red)">
        Reset Save
      </button>
    </div>
  `;
}

function renderBottomNav(): string {
  const tabs = [
    { id: 'harvest', icon: '💀', label: 'Harvest' },
    { id: 'planets', icon: '🪐', label: 'Planets' },
    { id: 'reapers', icon: '👻', label: 'Reapers' },
    { id: 'upgrades', icon: '⚡', label: 'Upgrades' },
    { id: 'world', icon: '🌐', label: 'World' },
    { id: 'void', icon: '🌀', label: 'Void' },
  ];

  return `
    <div class="bottom-nav">
      ${tabs.map((t) => `
        <button class="nav-tab ${currentTab === t.id ? 'active' : ''}" data-tab="${t.id}">
          <span class="nav-tab-icon">${t.icon}</span>
          ${t.label}
        </button>
      `).join('')}
    </div>
  `;
}

function bindEvents(): void {
  document.querySelectorAll('.nav-tab').forEach((el) => {
    el.addEventListener('click', () => {
      currentTab = (el as HTMLElement).dataset.tab!;
      render();
    });
  });

  const tapZone = document.getElementById('tap-zone');
  if (tapZone) {
    tapZone.addEventListener('click', (e) => {
      const rect = tapZone.getBoundingClientRect();
      const x = (e as MouseEvent).clientX - rect.left;
      const y = (e as MouseEvent).clientY - rect.top;
      const result = engine.tap(x, y);
      showFloatingNumber(x, y, result.souls, result.isCritical);
      triggerHaptic();
    });
  }

  document.getElementById('btn-summon')?.addEventListener('click', () => {
    engine.summonReaper();
    triggerHaptic();
  });

  document.getElementById('btn-auto-merge')?.addEventListener('click', () => {
    const count = engine.autoMerge();
    if (count > 0) triggerHaptic();
  });

  document.querySelectorAll('.planet-card').forEach((el) => {
    el.addEventListener('click', () => {
      const planetId = (el as HTMLElement).dataset.planet!;
      const unlocked = (el as HTMLElement).dataset.unlocked === 'true';
      if (unlocked) {
        engine.selectPlanet(planetId);
      } else {
        engine.unlockPlanet(planetId);
      }
      triggerHaptic();
    });
  });

  document.querySelectorAll('.reaper-card').forEach((el) => {
    el.addEventListener('click', () => {
      const id = (el as HTMLElement).dataset.reaper!;
      if (selectedReaperId && selectedReaperId !== id) {
        engine.mergeReaperPair(selectedReaperId, id);
        selectedReaperId = null;
        triggerHaptic();
      } else {
        selectedReaperId = selectedReaperId === id ? null : id;
        render();
      }
    });
  });

  document.querySelectorAll('.class-card').forEach((el) => {
    el.addEventListener('click', () => {
      engine.setPlayerClass((el as HTMLElement).dataset.class as any);
      triggerHaptic();
    });
  });

  document.querySelectorAll('.upgrade-item').forEach((el) => {
    el.addEventListener('click', () => {
      engine.buyUpgrade((el as HTMLElement).dataset.upgrade!);
      triggerHaptic();
    });
  });

  document.getElementById('btn-prestige')?.addEventListener('click', () => {
    if (confirm('Ascend to the Void? This resets your progress but grants permanent bonuses.')) {
      engine.prestige();
      triggerHaptic();
    }
  });

  document.getElementById('btn-reset')?.addEventListener('click', () => {
    if (confirm('Reset all progress? This cannot be undone.')) {
      engine.reset();
    }
  });

  const chatInput = document.getElementById('chat-input') as HTMLInputElement;
  const sendChat = () => {
    const msg = chatInput?.value.trim();
    if (msg) {
      engine.simulatedWorld.addChat('You', msg);
      chatInput.value = '';
      render();
    }
  };
  document.getElementById('btn-send-chat')?.addEventListener('click', sendChat);
  chatInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendChat();
  });

  const chatMessages = document.getElementById('chat-messages');
  if (chatMessages) {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }
}

function showFloatingNumber(x: number, y: number, souls: number, isCritical: boolean): void {
  const tapZone = document.getElementById('tap-zone');
  if (!tapZone) return;

  const el = document.createElement('div');
  el.className = `floating-number ${isCritical ? 'crit' : ''}`;
  el.textContent = `+${formatNumber(souls)}${isCritical ? ' CRIT!' : ''}`;
  el.style.left = `${x}px`;
  el.style.top = `${y}px`;
  tapZone.appendChild(el);
  setTimeout(() => el.remove(), 1000);
}

async function triggerHaptic(): Promise<void> {
  try {
    const { Haptics, ImpactStyle } = await import('@capacitor/haptics');
    await Haptics.impact({ style: ImpactStyle.Light });
  } catch {
    // Not on native platform
  }
}

init();
