export async function triggerHaptic(style: 'light' | 'medium' | 'heavy' = 'light'): Promise<void> {
  try {
    const { Haptics, ImpactStyle } = await import('@capacitor/haptics');
    const map = {
      light: ImpactStyle.Light,
      medium: ImpactStyle.Medium,
      heavy: ImpactStyle.Heavy,
    };
    await Haptics.impact({ style: map[style] });
  } catch {
    if (navigator.vibrate) {
      navigator.vibrate(style === 'heavy' ? 18 : style === 'medium' ? 10 : 6);
    }
  }
}

export function spawnRipple(host: HTMLElement, x: number, y: number): void {
  const ripple = document.createElement('div');
  ripple.className = 'touch-ripple';
  ripple.style.left = `${x}px`;
  ripple.style.top = `${y}px`;
  host.appendChild(ripple);
  setTimeout(() => ripple.remove(), 500);
}

export function spawnLootToast(icon: string, name: string): void {
  const host = document.getElementById('fx-layer');
  if (!host) return;
  const el = document.createElement('div');
  el.className = 'loot-toast';
  el.textContent = `${icon} ${name}`;
  host.appendChild(el);
  setTimeout(() => el.remove(), 1600);
}

export function shake(el: HTMLElement | null, ms = 220): void {
  if (!el) return;
  el.classList.add('shake');
  setTimeout(() => el.classList.remove('shake'), ms);
}

export function floatText(host: HTMLElement, x: number, y: number, text: string, crit = false): void {
  const el = document.createElement('div');
  el.className = `floating-number ${crit ? 'crit' : ''}`;
  el.textContent = text;
  el.style.left = `${x}px`;
  el.style.top = `${y}px`;
  host.appendChild(el);
  setTimeout(() => el.remove(), 1000);
}
