import type { SeriesItem, SeriesPatch } from '../api/series';

export const useSeriesStore = defineStore('series', () => {
  const items = ref<SeriesItem[]>([]);
  const total = ref(0);
  const loading = ref(false);

  async function refresh(limit = 100, offset = 0) {
    loading.value = true;
    try {
      const data = await apiSeries.list(limit, offset);
      items.value = data.items;
      total.value = data.total;
    } finally {
      loading.value = false;
    }
  }

  async function updateSeries(id: number, patch: SeriesPatch) {
    const updated = await apiSeries.patch(id, patch);
    const idx = items.value.findIndex((s) => s.id === id);
    if (idx >= 0) items.value[idx] = updated;
    return updated;
  }

  return { items, total, loading, refresh, updateSeries };
});
