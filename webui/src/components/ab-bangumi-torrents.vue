<script lang="ts" setup>
import { h } from 'vue';
import { NButton, NDataTable, NEmpty, NSpin, NTag } from 'naive-ui';

const props = defineProps<{
  bangumiId: number;
}>();

const show = defineModel<boolean>('show', { default: false });

const torrents = ref<any[]>([]);
const loading = ref(false);
const checkedRowKeys = ref<number[]>([]);

const { t, returnUserLangText } = useMyI18n();
const message = useMessage();

const totalCount = computed(() => torrents.value.length);
const existCount = computed(
  () => torrents.value.filter((row) => row.status !== 'missing').length
);
const dialogTitle = computed(() =>
  totalCount.value > 0
    ? `${t('rss.torrents')} (${existCount.value}/${totalCount.value})`
    : t('rss.torrents')
);

const columns = computed<any[]>(() => [
  {
    type: 'selection',
    width: 40,
    fixed: 'left',
  },
  {
    title: t('rss.torrent_name'),
    key: 'name',
    minWidth: 400,
    resizable: true,
    ellipsis: {
      tooltip: true,
    },
  },
  {
    title: 'Status',
    key: 'status',
    width: 100,
    fixed: 'right',
    render: (row: any) => {
      return h(
        NTag,
        {
          type:
            row.status === 'missing'
              ? 'error'
              : row.status === 'downloading'
              ? 'info'
              : 'success',
          size: 'small',
          round: true,
        },
        { default: () => row.status }
      );
    },
  },
  {
    title: 'Progress',
    key: 'progress',
    width: 80,
    fixed: 'right',
    render: (row: any) => {
      return row.status !== 'missing'
        ? `${(row.progress * 100).toFixed(1)}%`
        : '-';
    },
  },
  {
    title: 'Action',
    key: 'action',
    width: 120,
    fixed: 'right',
    render: (row: any) => {
      // Allow redownload for missing files or error states (e.g., file deleted on PikPak)
      const canRedownload = row.status === 'missing' || row.status === 'error';
      return h(
        NButton,
        {
          size: 'small',
          type: canRedownload ? 'primary' : undefined,
          disabled: !canRedownload,
          onClick: () => handleDownload(row.id),
        },
        {
          default: () =>
            canRedownload
              ? t('bangumi.download')
              : t('bangumi.downloaded'),
        }
      );
    },
  },
]);

async function getTorrents() {
  if (!props.bangumiId) return;
  loading.value = true;
  try {
    const res = await apiBangumi.getTorrentStatus(props.bangumiId);
    torrents.value = res;
  } catch (e) {
    message.error(t('notify.update_failed'));
  } finally {
    loading.value = false;
  }
}

async function handleDownload(torrentId: number) {
  try {
    await apiBangumi.downloadTorrent(torrentId);
    message.success(t('notify.update_success'));
    getTorrents();
  } catch (e: any) {
    // Show specific backend error message or generic fallback
    const errorMsg =
      e?.msg_en || e?.msg_zh
        ? returnUserLangText({ en: e.msg_en || '', 'zh-CN': e.msg_zh || '' })
        : t('notify.update_failed');
    message.error(errorMsg);
  }
}

async function handleBatchDownload() {
  if (checkedRowKeys.value.length === 0) {
    message.warning('Please select torrents first');
    return;
  }

  let successCount = 0;
  for (const torrentId of checkedRowKeys.value) {
    try {
      await apiBangumi.downloadTorrent(torrentId);
      successCount++;
    } catch (e) {
      console.error(`Failed to download torrent ${torrentId}`, e);
    }
  }

  message.success(
    `Downloaded ${successCount}/${checkedRowKeys.value.length} torrents`
  );
  checkedRowKeys.value = [];
  getTorrents();
}

watch(
  () => props.bangumiId,
  () => {
    if (show.value) {
      getTorrents();
    }
  }
);

watch(show, (val) => {
  if (val) {
    getTorrents();
  } else {
    torrents.value = [];
    checkedRowKeys.value = [];
  }
});
</script>

<template>
  <ab-popup v-model:show="show" :title="dialogTitle" css="!max-w-95vw !w-auto">
    <div class="resize-wrapper-outer">
      <div class="resize-wrapper-inner">
        <div v-if="loading" f-cer h-200>
          <NSpin size="large" />
        </div>
        <div v-else-if="torrents.length === 0" f-cer h-200 flex-col gap-y-12>
          <NEmpty :description="$t('bangumi.no_torrents_hint')">
            <template #icon>
              <div
                class="i-mdi-file-document-outline w-48 h-48 text-gray-400"
              />
            </template>
          </NEmpty>
        </div>
        <div v-else class="flex flex-col h-full bg-white">
          <div
            class="mb-12 flex items-center justify-between px-8 flex-shrink-0"
          >
            <div class="flex items-center gap-x-8 h-34">
              <template v-if="checkedRowKeys.length > 0">
                <span class="text-14 font-medium"
                  >{{ checkedRowKeys.length }} selected</span
                >
                <NButton
                  size="small"
                  type="primary"
                  @click="handleBatchDownload"
                >
                  Batch Download
                </NButton>
              </template>
            </div>
            <NButton size="small" :loading="loading" @click="getTorrents">
              <template #icon>
                <div class="i-mdi-refresh w-16 h-16" />
              </template>
              {{ $t('rss.refresh') }}
            </NButton>
          </div>
          <div class="flex-1 overflow-hidden">
            <NDataTable
              v-model:checked-row-keys="checkedRowKeys"
              :columns="columns"
              :data="torrents"
              :row-key="(row: any) => row.id"
              :scroll-x="1200"
              flex-height
              class="h-full"
              size="small"
            />
          </div>
        </div>
      </div>
    </div>
  </ab-popup>
</template>

<style scoped>
.resize-wrapper-outer {
  position: relative;
  width: 800px;
  height: 600px;
  min-width: 600px;
  min-height: 400px;
  max-width: 90vw;
  max-height: 80vh;
  resize: both;
  overflow: hidden;
  border: 1px solid transparent; /* Helps with resize handle in some browsers */
}

.resize-wrapper-inner {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 4px;
}

/* Ensure fixed columns have background and stay on top */
:deep(.n-data-table .n-data-table-td--fixed-left),
:deep(.n-data-table .n-data-table-th--fixed-left),
:deep(.n-data-table .n-data-table-td--fixed-right),
:deep(.n-data-table .n-data-table-th--fixed-right) {
  background-color: #fff !important;
  z-index: 10 !important;
}

/* Apply background color on hover to fixed cells too */
:deep(.n-data-table .n-data-table-tr:hover .n-data-table-td--fixed-left),
:deep(.n-data-table .n-data-table-tr:hover .n-data-table-td--fixed-right) {
  background-color: #f7f7f7 !important; /* Slightly darker than white */
}

/* Ensure the resize handle is visible and at the very front */
.resize-wrapper-outer::-webkit-resizer {
  background-color: rgba(0, 0, 0, 0.1);
  border-radius: 4px;
}
</style>
