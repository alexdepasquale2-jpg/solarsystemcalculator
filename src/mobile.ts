export type InstallHint = 'android' | 'ios' | 'desktop' | 'installed' | 'native';

const INSTALL_DISMISS_KEY = 'soul_harvest_install_dismissed';

export function isStandaloneDisplay(): boolean {
  if (typeof window === 'undefined') return false;
  const nav = window.navigator as Navigator & { standalone?: boolean };
  return nav.standalone === true || Boolean(window.matchMedia?.('(display-mode: standalone)')?.matches);
}

export function isIosDevice(): boolean {
  if (typeof navigator === 'undefined') return false;
  return (
    /iPad|iPhone|iPod/i.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
  );
}

export function isAndroidDevice(): boolean {
  return typeof navigator !== 'undefined' && /Android/i.test(navigator.userAgent);
}

export function getInstallHint(isNative = false): InstallHint {
  if (isNative) return 'native';
  if (isStandaloneDisplay()) return 'installed';
  if (isIosDevice()) return 'ios';
  if (isAndroidDevice()) return 'android';
  return 'desktop';
}

export function shouldShowInstallBanner(isNative = false, dismissed = false): boolean {
  if (dismissed || isNative) return false;
  const hint = getInstallHint(isNative);
  return hint === 'android' || hint === 'ios';
}

export async function bootMobile(): Promise<void> {
  document.documentElement.classList.add('mobile-ready');
  lockPortrait();
  preventBrowserChrome();
  bindViewportKeyboard();
  bindWakeLock();
  await bootNativeShell();
  registerServiceWorker();
  mountInstallBanner();
}

function lockPortrait(): void {
  const orientation = screen.orientation as ScreenOrientation & {
    lock?: (mode: string) => Promise<void>;
  };
  orientation.lock?.('portrait').catch(() => undefined);
}

function preventBrowserChrome(): void {
  document.addEventListener(
    'gesturestart',
    (e) => {
      e.preventDefault();
    },
    { passive: false }
  );
  document.addEventListener('contextmenu', (e) => {
    const target = e.target as HTMLElement | null;
    if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')) return;
    e.preventDefault();
  });
  document.addEventListener(
    'touchmove',
    (e) => {
      if ((e.target as HTMLElement | null)?.closest?.('.tab-panel.active, .chat-messages')) return;
      if (e.touches.length > 1) e.preventDefault();
    },
    { passive: false }
  );
}

function bindViewportKeyboard(): void {
  const sync = (): void => {
    const vv = window.visualViewport;
    if (!vv) {
      document.documentElement.style.setProperty('--keyboard', '0px');
      return;
    }
    const keyboard = Math.max(0, window.innerHeight - vv.height - vv.offsetTop);
    document.documentElement.style.setProperty('--keyboard', `${Math.round(keyboard)}px`);
  };
  window.visualViewport?.addEventListener('resize', sync);
  window.visualViewport?.addEventListener('scroll', sync);
  window.addEventListener('resize', sync);
  sync();
}

function bindWakeLock(): void {
  const request = async (): Promise<void> => {
    try {
      await navigator.wakeLock?.request('screen');
    } catch {
      // Unsupported or permission denied
    }
  };
  document.addEventListener('pointerdown', request, { once: true });
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') void request();
  });
}

async function bootNativeShell(): Promise<boolean> {
  try {
    const { Capacitor } = await import('@capacitor/core');
    if (!Capacitor.isNativePlatform()) return false;
    document.documentElement.classList.add('native-app');

    try {
      const { StatusBar, Style } = await import('@capacitor/status-bar');
      await StatusBar.setStyle({ style: Style.Dark });
      await StatusBar.setBackgroundColor({ color: '#0a0612' });
      await StatusBar.setOverlaysWebView({ overlay: true });
    } catch {
      // Web or plugin unavailable
    }

    try {
      const { SplashScreen } = await import('@capacitor/splash-screen');
      await SplashScreen.hide({ fadeOutDuration: 350 });
    } catch {
      // Web or plugin unavailable
    }

    try {
      const { Keyboard } = await import('@capacitor/keyboard');
      await Keyboard.setAccessoryBarVisible({ isVisible: false });
      Keyboard.addListener('keyboardWillShow', (info) => {
        document.documentElement.style.setProperty('--keyboard', `${info.keyboardHeight}px`);
      });
      Keyboard.addListener('keyboardWillHide', () => {
        document.documentElement.style.setProperty('--keyboard', '0px');
      });
    } catch {
      // Web or plugin unavailable
    }

    try {
      const { App } = await import('@capacitor/app');
      App.addListener('backButton', ({ canGoBack }) => {
        if (canGoBack) window.history.back();
      });
      App.addListener('appStateChange', ({ isActive }) => {
        if (isActive) return;
        void import('./game/engine').then(({ getGameEngine }) => getGameEngine().save());
      });
    } catch {
      // Web or plugin unavailable
    }

    return true;
  } catch {
    return false;
  }
}

function registerServiceWorker(): void {
  if (!import.meta.env.PROD) return;
  if (!('serviceWorker' in navigator)) return;
  if (document.documentElement.classList.contains('native-app')) return;
  window.addEventListener('load', () => {
    void navigator.serviceWorker.register('./sw.js');
  });
}

function mountInstallBanner(): void {
  const native = document.documentElement.classList.contains('native-app');
  const dismissed = localStorage.getItem(INSTALL_DISMISS_KEY) === '1';
  if (!shouldShowInstallBanner(native, dismissed)) return;

  const hint = getInstallHint(native);
  const banner = document.createElement('div');
  banner.id = 'install-banner';
  banner.innerHTML =
    hint === 'ios'
      ? `<span>Install: tap Share, then Add to Home Screen</span><button type="button" id="btn-install-dismiss" aria-label="Dismiss">×</button>`
      : `<span>Install Soul Harvest on your phone</span><button type="button" id="btn-install">Add</button><button type="button" id="btn-install-dismiss" aria-label="Dismiss">×</button>`;
  document.body.appendChild(banner);

  let deferred: BeforeInstallPromptEvent | null = null;
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferred = e;
    banner.hidden = false;
  });

  document.getElementById('btn-install')?.addEventListener('click', async () => {
    if (deferred) {
      await deferred.prompt();
      deferred = null;
    }
    banner.remove();
  });
  document.getElementById('btn-install-dismiss')?.addEventListener('click', () => {
    localStorage.setItem(INSTALL_DISMISS_KEY, '1');
    banner.remove();
  });
}
