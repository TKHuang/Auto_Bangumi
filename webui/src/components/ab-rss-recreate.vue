<script lang="ts" setup>
import type { BangumiAPI, BangumiRule } from '#/bangumi';

const show = defineModel<boolean>('show', { default: false });
const rssId = ref(0);
const bangumi = ref<BangumiRule | null>(null);
const loading = ref(false);

const { t } = useMyI18n();
const message = useMessage();
const { getAll } = useBangumiStore();

defineExpose({
  async open(id: number) {
    rssId.value = id;
    loading.value = true;
    show.value = true;
    await loadBangumi();
  },
});

async function loadBangumi() {
  loading.value = true;
  try {
    const data = await apiRSS.recreate(rssId.value);
    if (data && data.length > 0) {
      // Only take the first result (original Add RSS behavior)
      const first = data[0];
      bangumi.value = {
        ...first,
        filter: first.filter.split(','),
        rss_link: first.rss_link.split(','),
      };
    } else {
      message.info(t('rss.no_new_rules'));
      show.value = false;
    }
  } catch (e) {
    message.error(t('notify.update_failed'));
    show.value = false;
  } finally {
    loading.value = false;
  }
}

async function subscribe() {
  if (!bangumi.value) return;
  
  try {
    const rss = await apiRSS.get();
    const rssItem = rss.find((r) => r.id === rssId.value);
    if (!rssItem) {
      message.error('RSS not found');
      return;
    }
    
    await apiDownload.subscribe(bangumi.value, rssItem);
    message.success(t('notify.update_success'));
    getAll();
    show.value = false;
  } catch (e) {
    message.error(t('notify.update_failed'));
  }
}

async function collect() {
  if (!bangumi.value) return;
  
  try {
    await apiDownload.collection(bangumi.value);
    message.success(t('notify.update_success'));
    getAll();
    show.value = false;
  } catch (e) {
    message.error(t('notify.update_failed'));
  }
}
</script>

<template>
  <ab-popup v-model:show="show" :title="$t('rss.review_rules')" css="w-360">
    <div v-if="loading" f-cer h-200 flex-col gap-y-12>
      <n-spin size="large" />
      <div class="text-14 text-gray-500">{{ $t('rss.parsing_torrents') }}</div>
    </div>
    <div v-else-if="!bangumi" f-cer h-200>
      <n-empty />
    </div>
    <div v-else>
      <ab-rule v-model:rule="bangumi"></ab-rule>
      <div flex="~ justify-end gap-x-10" mt-16>
        <ab-button size="small" @click="collect">
          {{ $t('topbar.add.collect') }}
        </ab-button>
        <ab-button size="small" @click="subscribe">
          {{ $t('topbar.add.subscribe') }}
        </ab-button>
      </div>
    </div>
  </ab-popup>
</template>
