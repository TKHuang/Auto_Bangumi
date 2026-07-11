import type { MikanHealth } from '../../api/health';

type MikanHealthSignal = Pick<
  MikanHealth,
  'pending_count' | 'consecutive_failures'
>;

export function shouldShowMikanHealthBanner(
  health: MikanHealthSignal | null | undefined
): boolean {
  return Boolean(
    health && (health.pending_count > 0 || health.consecutive_failures > 0)
  );
}

export function mikanHealthBannerClass(
  status: MikanHealth['status'] | null | undefined,
  visible: boolean
): string {
  if (!visible) return '';
  if (status === 'down') return 'banner banner-down';
  return 'banner banner-warn';
}
