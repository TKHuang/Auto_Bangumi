import { describe, expect, it } from 'vitest';
import addRssSource from './ab-add-rss.vue?raw';
import recreateSource from './ab-rss-recreate.vue?raw';

describe('collect button removal', () => {
  it('does not render collect button in add-rss flow', () => {
    expect(addRssSource).not.toContain("$t('topbar.add.collect')");
  });

  it('does not render collect button in rss recreate review flow', () => {
    expect(recreateSource).not.toContain("$t('topbar.add.collect')");
  });
});
