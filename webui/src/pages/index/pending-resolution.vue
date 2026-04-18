<script lang="ts" setup>
import type { PendingItem } from '@/api/pendingResolution';

definePage({ name: 'PendingResolution' });

const { t } = useMyI18n();

const items = ref<PendingItem[]>([]);
const total = ref(0);
const loading = ref(false);

async function refresh() {
  loading.value = true;
  try {
    const data = await apiPendingResolution.list(200, 0);
    items.value = data.items;
    total.value = data.total;
  } finally {
    loading.value = false;
  }
}

async function retryOne(infoHash: string) {
  await apiPendingResolution.retry(infoHash);
  await refresh();
}

onMounted(refresh);

const timer = window.setInterval(refresh, 30_000);
onBeforeUnmount(() => window.clearInterval(timer));
</script>

<template>
  <div class="pending-page">
    <div class="toolbar">
      <button class="btn" :disabled="loading" @click="refresh">
        {{ t('common.refresh') }}
      </button>
      <span class="count">{{ total }} {{ t('pending.items') }}</span>
    </div>

    <div v-if="loading && items.length === 0" class="loading">
      {{ t('pending.loading') }}
    </div>

    <div v-else-if="items.length === 0" class="empty">
      {{ t('pending.empty') }}
    </div>

    <table v-else class="pending-table">
      <thead>
        <tr>
          <th>{{ t('pending.col.name') }}</th>
          <th>{{ t('pending.col.attempts') }}</th>
          <th>{{ t('pending.col.last_error') }}</th>
          <th>{{ t('pending.col.first_seen') }}</th>
          <th>{{ t('common.actions') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.info_hash">
          <td class="name" :title="item.raw_name">{{ item.raw_name }}</td>
          <td>{{ item.attempt_count }}</td>
          <td class="err">{{ item.last_error || '-' }}</td>
          <td class="date">{{ item.first_seen_at ?? '-' }}</td>
          <td>
            <button class="btn btn-sm" @click="retryOne(item.info_hash)">
              {{ t('pending.retry') }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style lang="scss" scoped>
.pending-page {
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

.pending-table {
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

.name {
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.err {
  color: #c05621;
  font-size: 12px;
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.date {
  font-size: 12px;
  color: #666;
  white-space: nowrap;
}

.loading,
.empty {
  text-align: center;
  padding: 40px;
  color: #888;
}

.btn {
  padding: 4px 12px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;

  &:hover:not(:disabled) {
    background: #f5f5f5;
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.btn-sm {
  padding: 2px 8px;
  font-size: 12px;
}
</style>
