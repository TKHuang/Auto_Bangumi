import type { MergeHistoryItem } from '../api/merge';

export const useMergeHistoryStore = defineStore('mergeHistory', () => {
  const items = ref<MergeHistoryItem[]>([]);
  const total = ref(0);

  async function refresh() {
    const data = await apiMerge.listHistory(100, 0);
    items.value = data.items;
    total.value = data.total;
  }

  async function undo(id: number) {
    await apiMerge.undo(id);
    await refresh();
  }

  return { items, total, refresh, undo };
});
