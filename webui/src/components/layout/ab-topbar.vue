<script lang="ts" setup>
import {
  Format,
  Me,
  Pause,
  PlayOne,
  Power,
  Refresh,
} from '@icon-park/vue-next';
import { ruleTemplate } from '#/bangumi';
import type { BangumiRule } from '#/bangumi';
import AbRssRecreate from '@/components/ab-rss-recreate.vue';

const { t, changeLocale } = useMyI18n();
const { running, onUpdate, offUpdate } = useAppInfo();

const showAccount = ref(false);
const showAddRSS = ref(false);
const showRecreate = ref(false);
const searchRule = ref<BangumiRule>();

// Track RSS ID for auto-delete on cancel
const pendingRssId = ref<number | null>(null);

// Ref for ab-rss-recreate component
const recreateDialogRef = ref<InstanceType<typeof AbRssRecreate>>();

const { start, pause, shutdown, restart, resetRule } = useProgramStore();
const { refreshPoster } = useBangumiStore();
const { getAll: getRSS } = useRSSStore();

const items = [
  {
    id: 1,
    label: () => t('topbar.start'),
    icon: PlayOne,
    handle: start,
  },
  {
    id: 2,
    label: () => t('topbar.pause'),
    icon: Pause,
    handle: pause,
  },
  {
    id: 3,
    label: () => t('topbar.restart'),
    icon: Refresh,
    handle: restart,
  },
  {
    id: 4,
    label: () => t('topbar.shutdown'),
    icon: Power,
    handle: shutdown,
  },
  {
    id: 5,
    label: () => t('topbar.refresh_poster'),
    icon: Refresh,
    handle: refreshPoster,
  },
  {
    id: 6,
    label: () => t('topbar.reset_rule'),
    icon: Format,
    handle: resetRule,
  },
  {
    id: 7,
    label: () => t('topbar.profile.title'),
    icon: Me,
    handle: () => {
      showAccount.value = true;
    },
  },
];

const onSearchFocus = ref(false);

function addSearchResult(bangumi: BangumiRule) {
  showAddRSS.value = true;
  searchRule.value = bangumi;
  console.log('searchRule', searchRule.value);
}

// Handle rss-created event from ab-add-rss
function handleRssCreated(payload: { rssId: number; aggregate: boolean }) {
  console.log('[Topbar] RSS created:', payload);
  pendingRssId.value = payload.rssId;
  // Open the recreate dialog to show rule review
  recreateDialogRef.value?.open(payload.rssId);
}

// Handle cancelled event from ab-rss-recreate (auto-delete orphan RSS)
async function handleRecreateCancel(rssId: number) {
  console.log('[Topbar] Recreate cancelled, deleting RSS:', rssId);
  if (pendingRssId.value === rssId) {
    try {
      await apiRSS.delete(rssId);
      console.log('[Topbar] Orphan RSS deleted:', rssId);
    } catch (e) {
      console.error('[Topbar] Failed to delete orphan RSS:', e);
      // Fire-and-forget - don't block UI
    }
    pendingRssId.value = null;
  }
}

// Handle subscribed event from ab-rss-recreate
function handleRecreateSubscribed() {
  console.log('[Topbar] Subscription completed');
  pendingRssId.value = null;
  // Refresh RSS list to show the new entry
  getRSS();
}

watch(showAddRSS, (val) => {
  if (!val) {
    searchRule.value = { ...ruleTemplate };
    setTimeout(() => {
      onSearchFocus.value = false;
    }, 300);
  }
});

onBeforeMount(() => {
  onUpdate();
});

onUnmounted(() => {
  offUpdate();
});
</script>

<template>
  <div
    h="pc:60 50"
    bg-theme-row
    text-white
    rounded="pc:16 10"
    fx-cer
    px="pc:24 15"
  >
    <div flex="~ gap-x-16">
      <div fx-cer gap-x="pc:16 10">
        <img src="/images/logo-light.svg" alt="favicon" wh="pc:24 20" />
        <img
          v-show="onSearchFocus === false"
          src="/images/AutoBangumi.svg"
          alt="AutoBangumi"
          rel
          h="18 pc:24"
          pc:top-2
        />
      </div>
    </div>

    <div ml-auto fx-cer>
      <ab-search-bar mr="pc:16 10" fx-cer @add-bangumi="addSearchResult" />

      <ab-status-bar
        :items="items"
        :running="running"
        @click-add="() => (showAddRSS = true)"
        @change-lang="changeLocale"
      />
    </div>
  </div>

  <ab-change-account v-model:show="showAccount"></ab-change-account>
  <ab-add-rss
    v-model:show="showAddRSS"
    v-model:rule="searchRule"
    @rss-created="handleRssCreated"
  ></ab-add-rss>
  <ab-rss-recreate
    ref="recreateDialogRef"
    v-model:show="showRecreate"
    :auto-delete-on-cancel="true"
    @cancelled="handleRecreateCancel"
    @subscribed="handleRecreateSubscribed"
  />
</template>
