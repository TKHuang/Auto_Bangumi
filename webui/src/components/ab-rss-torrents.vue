<script lang="ts" setup>
const show = defineModel<boolean>('show', { default: false });
const rssId = defineModel<number>('rssId', { default: 0 });

const torrents = ref<any[]>([]);
const loading = ref(false);

const { t, returnUserLangText } = useMyI18n();
const message = useMessage();

async function getTorrents() {
  if (!rssId.value) return;
  loading.value = true;
  try {
    const result = await apiRSS.getTorrent(rssId.value);
    console.log('RSS Torrents result:', result);
    torrents.value = result || [];
  } catch (e) {
    console.error('Error fetching torrents:', e);
    torrents.value = [];
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

watch([show, rssId], async ([newShow, newId]) => {
  if (newShow && newId !== 0) {
    getTorrents();
  } else if (!newShow) {
    torrents.value = [];
  }
});
</script>

<template>
  <ab-popup
    v-model:show="show"
    :title="$t('rss.torrents')"
    css="w-600 max-w-90vw"
  >
    <div v-if="loading" f-cer h-200>
      <n-spin size="large" />
    </div>
    <div
      v-else-if="!torrents || torrents.length === 0"
      f-cer
      h-200
      flex-col
      gap-y-12
    >
      <n-empty :description="$t('rss.no_torrents_hint')">
        <template #icon>
          <div class="i-mdi-file-document-outline w-48 h-48 text-gray-400" />
        </template>
      </n-empty>
    </div>
    <div v-else class="max-h-60vh overflow-y-auto">
      <div
        v-for="torrent in torrents"
        :key="torrent.id"
        class="p-8 border-b border-gray-200 last:border-0 flex justify-between items-center"
      >
        <div class="flex-1 mr-8 overflow-hidden">
          <div class="truncate text-14 font-medium" :title="torrent.name">
            {{ torrent.name }}
          </div>
          <div class="flex gap-x-8 mt-4 text-12 text-gray-500">
            <n-tag
              :type="torrent.status === 'missing' ? 'error' : torrent.status === 'archived' ? 'warning' : 'success'"
              size="small"
              round
            >
              {{ torrent.status }}
            </n-tag>
            <span v-if="torrent.status !== 'missing'">
              {{ (torrent.progress * 100).toFixed(1) }}%
            </span>
          </div>
        </div>
        <ab-button
          size="small"
          :type="torrent.status === 'missing' ? 'primary' : undefined"
          @click="handleDownload(torrent.id)"
        >
          {{ $t('topbar.add.subscribe') }}
        </ab-button>
      </div>
    </div>
  </ab-popup>
</template>
