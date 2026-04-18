<script lang="ts" setup>
definePage({ name: 'MergeHistory' });

const { t } = useMyI18n();
const store = useMergeHistoryStore();

onMounted(() => store.refresh());

async function undoMerge(id: number) {
  if (!confirm(t('merge.undo_confirm'))) return;
  await store.undo(id);
}
</script>

<template>
  <div class="merge-page">
    <div class="toolbar">
      <button class="btn" @click="store.refresh()">{{ t('common.refresh') }}</button>
      <span class="count">{{ store.total }} {{ t('merge.records') }}</span>
    </div>

    <div v-if="store.items.length === 0" class="empty">
      {{ t('merge.empty') }}
    </div>

    <table v-else class="merge-table">
      <thead>
        <tr>
          <th>{{ t('merge.col.when') }}</th>
          <th>{{ t('merge.col.winner') }}</th>
          <th>{{ t('merge.col.loser') }}</th>
          <th>{{ t('merge.col.reason') }}</th>
          <th>{{ t('merge.col.by') }}</th>
          <th>{{ t('common.actions') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="h in store.items" :key="h.id">
          <td class="date">{{ h.merged_at ?? '-' }}</td>
          <td>{{ h.winner_bangumi_id }}</td>
          <td>{{ h.loser_bangumi_id }}</td>
          <td class="reason">{{ h.merge_reason }}</td>
          <td>{{ h.merged_by ?? '-' }}</td>
          <td>
            <button v-if="!h.undone_at" class="btn btn-sm" @click="undoMerge(h.id)">
              {{ t('merge.undo') }}
            </button>
            <span v-else class="undone">
              {{ t('merge.undone') }}
              <span v-if="h.undone_by">({{ h.undone_by }})</span>
            </span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style lang="scss" scoped>
.merge-page {
  padding: 12px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.count {
  color: #666;
  font-size: 13px;
}

.merge-table {
  width: 100%;
  border-collapse: collapse;

  th,
  td {
    padding: 8px 12px;
    text-align: left;
    border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  }

  th {
    font-size: 12px;
    color: #888;
    font-weight: 600;
    text-transform: uppercase;
  }
}

.date {
  font-size: 12px;
  color: #666;
  white-space: nowrap;
}

.reason {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.empty {
  text-align: center;
  padding: 40px;
  color: #888;
}

.undone {
  color: #718096;
  font-size: 12px;
  font-style: italic;
}

.btn {
  padding: 4px 12px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;

  &:hover {
    background: #f5f5f5;
  }
}

.btn-sm {
  padding: 2px 8px;
  font-size: 12px;
}
</style>
