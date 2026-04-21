import { describe, expect, it } from 'vitest';
import { needsBangumiRuleReview } from './review-status';

describe('needsBangumiRuleReview', () => {
  it('marks parser-fallback bangumi as needing review', () => {
    expect(
      needsBangumiRuleReview({
        pendingReview: true,
        previewLoaded: true,
        previewLoading: false,
        torrents: [{ filter: false }],
      })
    ).toBe(true);
  });

  it('marks loaded previews with zero kept torrents as needing review', () => {
    expect(
      needsBangumiRuleReview({
        pendingReview: false,
        previewLoaded: true,
        previewLoading: false,
        torrents: [{ filter: true }, { filter: true }],
      })
    ).toBe(true);
  });

  it('does not mark still-loading previews as needing review just because keep is zero', () => {
    expect(
      needsBangumiRuleReview({
        pendingReview: false,
        previewLoaded: false,
        previewLoading: true,
        torrents: [],
      })
    ).toBe(false);
  });

  it('does not mark loaded previews that keep at least one torrent', () => {
    expect(
      needsBangumiRuleReview({
        pendingReview: false,
        previewLoaded: true,
        previewLoading: false,
        torrents: [{ filter: true }, { filter: false }],
      })
    ).toBe(false);
  });
});
