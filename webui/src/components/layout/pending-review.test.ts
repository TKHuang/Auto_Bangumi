import { describe, expect, it } from 'vitest';
import {
  getPendingReviewInteraction,
  getPendingReviewSources,
  getPendingReviewTotal,
} from './pending-review';
import type { RSS } from '#/rss';

function rss(id: number, name: string): RSS {
  return {
    id,
    name,
    url: `https://example.test/${id}`,
    aggregate: id === 1,
    parser: 'mikan',
    enabled: true,
    last_update: null,
    last_status: null,
    last_error: null,
  };
}

describe('pending review navigation policy', () => {
  it('keeps only RSS sources with actionable pending reviews', () => {
    const sources = getPendingReviewSources(
      [rss(1, 'Aggregate'), rss(2, 'Single'), rss(3, 'Clear')],
      { 1: 4, 2: 2, 3: 0 }
    );

    expect(sources.map(({ rss, count }) => [rss.id, count])).toEqual([
      [1, 4],
      [2, 2],
    ]);
    expect(getPendingReviewTotal(sources)).toBe(6);
  });

  it('opens one source directly and asks the user to choose among many', () => {
    expect(getPendingReviewInteraction(0)).toBe('hidden');
    expect(getPendingReviewInteraction(1)).toBe('direct');
    expect(getPendingReviewInteraction(2)).toBe('choose');
  });
});
