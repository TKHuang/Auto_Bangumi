import { describe, expect, it } from 'vitest';
import editRuleSource from './ab-edit-rule.vue?raw';
import bangumiPageSource from '../pages/index/bangumi.vue?raw';
import bangumiStoreSource from '../store/bangumi.ts?raw';

describe('retrigger rename progress', () => {
  it('tracks the bangumi currently running re-rename', () => {
    expect(bangumiStoreSource).toContain('renamingIds');
    expect(bangumiStoreSource).toContain('isRenaming');
  });

  it('passes re-rename progress state into the edit popup', () => {
    expect(bangumiPageSource).toContain(':rename-in-progress=');
  });

  it('shows progress inside the edit rule popup while re-rename runs', () => {
    expect(editRuleSource).toContain('renameInProgress');
    expect(editRuleSource).toContain(':show-progress="renameInProgress"');
    expect(editRuleSource).toContain('rename-progress');
  });
});
