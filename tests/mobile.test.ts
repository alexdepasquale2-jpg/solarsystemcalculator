import { describe, it, expect } from 'vitest';
import { getInstallHint, isAndroidDevice, isIosDevice, isStandaloneDisplay, shouldShowInstallBanner } from '../src/mobile';

describe('mobile install targeting', () => {
  it('treats standalone display as already installed', () => {
    expect(getInstallHint(false)).not.toBe('native');
    expect(getInstallHint(true)).toBe('native');
  });

  it('hides the install gate in native apps, standalone, and after dismiss', () => {
    expect(shouldShowInstallBanner(true, false, false)).toBe(false);
    expect(shouldShowInstallBanner(false, true, false)).toBe(false);
    expect(shouldShowInstallBanner(false, false, true)).toBe(false);
  });

  it('shows the install gate for a first visit in the browser', () => {
    expect(shouldShowInstallBanner(false, false, false)).toBe(true);
  });

  it('does not crash device checks in jsdom', () => {
    expect(typeof isAndroidDevice()).toBe('boolean');
    expect(typeof isIosDevice()).toBe('boolean');
    expect(typeof isStandaloneDisplay()).toBe('boolean');
  });
});
