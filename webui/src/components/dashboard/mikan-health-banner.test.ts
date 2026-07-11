import { describe, expect, it } from 'vitest';
import {
  mikanHealthBannerClass,
  shouldShowMikanHealthBanner,
} from './mikan-health-banner';

describe('Mikan health banner policy', () => {
  it('hides a stale degraded status without actionable signals', () => {
    expect(
      shouldShowMikanHealthBanner({
        pending_count: 0,
        consecutive_failures: 0,
      })
    ).toBe(false);
  });

  it('shows pending work', () => {
    expect(
      shouldShowMikanHealthBanner({
        pending_count: 1,
        consecutive_failures: 0,
      })
    ).toBe(true);
  });

  it('shows actual failures without pending work', () => {
    expect(
      shouldShowMikanHealthBanner({
        pending_count: 0,
        consecutive_failures: 1,
      })
    ).toBe(true);
  });

  it('stays hidden before health data loads', () => {
    expect(shouldShowMikanHealthBanner(null)).toBe(false);
  });

  it('preserves degraded and down severity classes', () => {
    expect(mikanHealthBannerClass('degraded', true)).toBe('banner banner-warn');
    expect(mikanHealthBannerClass('down', true)).toBe('banner banner-down');
    expect(mikanHealthBannerClass('ok', true)).toBe('banner banner-warn');
    expect(mikanHealthBannerClass('down', false)).toBe('');
  });
});
