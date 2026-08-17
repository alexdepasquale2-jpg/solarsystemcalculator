import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.soulharvest.game',
  appName: 'Soul Harvest',
  webDir: 'dist',
  android: {
    backgroundColor: '#0a0612',
    allowMixedContent: false,
  },
  ios: {
    backgroundColor: '#0a0612',
    contentInset: 'automatic',
    preferredContentMode: 'mobile',
    scheme: 'Soul Harvest',
  },
  plugins: {
    StatusBar: {
      style: 'DARK',
      backgroundColor: '#0a0612',
      overlaysWebView: true,
    },
    SplashScreen: {
      launchShowDuration: 1400,
      launchAutoHide: true,
      backgroundColor: '#0a0612',
      androidScaleType: 'CENTER',
      showSpinner: false,
      splashFullScreen: true,
      splashImmersive: true,
    },
    Keyboard: {
      resize: 'body',
      resizeOnFullScreen: true,
    },
  },
};

export default config;
