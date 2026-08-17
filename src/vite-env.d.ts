/// <reference types="vite/client" />

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
}

interface WindowEventMap {
  beforeinstallprompt: BeforeInstallPromptEvent;
}

interface Window {
  __shInstall: BeforeInstallPromptEvent | null;
}
