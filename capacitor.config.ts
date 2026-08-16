import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.soulharvest.game',
  appName: 'Soul Harvest',
  webDir: 'dist',
  android: {
    backgroundColor: '#0a0612',
  },
  plugins: {
    StatusBar: {
      style: 'DARK',
      backgroundColor: '#0a0612',
    },
  },
};

export default config;
