import type { RSS } from '#/rss';

export interface PendingReviewSource {
  rss: RSS;
  count: number;
}

export type PendingReviewInteraction = 'hidden' | 'direct' | 'choose';

export function getPendingReviewSources(
  rssItems: RSS[],
  pendingCounts: Record<number, number>
): PendingReviewSource[] {
  return rssItems
    .map((rss) => ({ rss, count: pendingCounts[rss.id] ?? 0 }))
    .filter((source) => source.count > 0);
}

export function getPendingReviewTotal(sources: PendingReviewSource[]): number {
  return sources.reduce((total, source) => total + source.count, 0);
}

export function getPendingReviewInteraction(
  sourceCount: number
): PendingReviewInteraction {
  if (sourceCount === 0) return 'hidden';
  if (sourceCount === 1) return 'direct';
  return 'choose';
}
