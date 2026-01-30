<script lang="ts" setup>
import { useDebounceFn } from '@vueuse/core';
import type { BangumiRule } from '#/bangumi';
import type { RSS } from '#/rss';
import { rssTemplate } from '#/rss';
import { ruleTemplate } from '#/bangumi';

/** v-model show */
const show = defineModel('show', { default: false });

const emit = defineEmits<{
  'rss-created': [{ rssId: number; aggregate: boolean }];
}>();

const message = useMessage();
const { getAll } = useBangumiStore();
const { getAll: getRSS } = useRSSStore();
const { t, returnUserLangText } = useMyI18n();

const rssModel = defineModel<RSS>('rss');
const rss = ref<RSS>({ ...rssTemplate });
const rule = defineModel<BangumiRule>('rule', { default: ruleTemplate });
const parserType = ['mikan', 'tmdb', 'parser'];

// Sync from model to local when model changes (for edit mode)
watch(
  rssModel,
  (val) => {
    if (val) {
      rss.value = { ...val };
    }
  },
  { immediate: true }
);

// Sync back to model when local changes (for edit mode)
watch(
  rss,
  (val) => {
    if (rssModel.value !== undefined) {
      Object.assign(rssModel.value, val);
    }
  },
  { deep: true }
);

const windowState = reactive({
  loading: false,
  rule: false,
  next: false,
});
const loading = reactive({
  collect: false,
  subscribe: false,
  torrents: false,
});

const torrents = ref<
  { name: string; url: string; homepage: string; filter: boolean }[]
>([]);

const torrentsKeep = computed(() => torrents.value.filter((t) => !t.filter));
const torrentsExclude = computed(() => torrents.value.filter((t) => t.filter));

async function getTorrents() {
  // Use rss.value.url if set, otherwise fallback to rule.rss_link (for search results)
  const rssUrl = rss.value.url || (rule.value.rss_link?.[0] ?? '');
  if (rssUrl) {
    loading.torrents = true;
    try {
      // Create RSS object with the resolved URL for API call
      const rssForApi = rss.value.url
        ? rss.value
        : { ...rss.value, url: rssUrl };
      const res = await apiDownload.analysisTorrents(
        rssForApi,
        rule.value.filter.join(',')
      );
      torrents.value = res;
    } catch (e) {
      console.error(e);
    } finally {
      loading.torrents = false;
    }
  }
}

const debouncedGetTorrents = useDebounceFn(getTorrents, 300);

watch(
  () => rule.value.filter,
  () => {
    if (windowState.rule) {
      debouncedGetTorrents();
    }
  },
  { deep: true }
);

watch(
  () => windowState.rule,
  (val) => {
    if (val) {
      getTorrents();
    }
  }
);

watch(show, (val) => {
  if (!val) {
    rss.value = { ...rssTemplate };
    rule.value = { ...ruleTemplate };
    setTimeout(() => {
      windowState.next = false;
      windowState.rule = false;
    }, 300);
  } else if (val && rule.value.official_title !== '') {
    windowState.next = true;
    windowState.rule = true;
  }
});

interface DuplicateError {
  status: boolean;
  status_code: number;
  error_type: 'duplicate_official_title' | 'duplicate_rss_link';
  msg_en: string;
  msg_zh: string;
  existing_bangumi: {
    id: number;
    official_title: string;
    season: number;
    group_name: string;
    rss_link?: string;
  };
}

function isDuplicateError(err: unknown): err is DuplicateError {
  return (
    typeof err === 'object' &&
    err !== null &&
    'error_type' in err &&
    ((err as DuplicateError).error_type === 'duplicate_official_title' ||
      (err as DuplicateError).error_type === 'duplicate_rss_link')
  );
}

function addRss() {
  if (rss.value.url === '') {
    message.error(t('notify.please_enter', [t('notify.rss_link')]));
  } else if (rss.value.id !== 0) {
    useApi(apiRSS.update, {
      showMessage: true,
      onBeforeExecute() {
        windowState.loading = true;
      },
      onSuccess() {
        show.value = false;
        getRSS();
      },
      onFinally() {
        windowState.loading = false;
      },
    }).execute(rss.value.id, rss.value);
  } else {
    // For NEW RSS (both aggregate and regular)
    useApi(apiRSS.add, {
      showMessage: false, // Handle success manually to emit event
      onBeforeExecute() {
        windowState.loading = true;
      },
      onSuccess(res) {
        // res is the response data from apiRSS.add
        if (res && res.rss_id) {
          emit('rss-created', {
            rssId: res.rss_id,
            aggregate: rss.value.aggregate,
          });
          show.value = false;
          // Do NOT call getRSS() - parent handles refresh after subscription/setup
        } else {
           // Fallback if no rss_id returned (shouldn't happen with updated API)
           message.success(t('notify.success'));
           show.value = false;
           getRSS();
        }
      },
      onError(err) {
        if (isDuplicateError(err)) {
          message.error(
            returnUserLangText({
              en: err.msg_en,
              'zh-CN': err.msg_zh,
            })
          );
        } else {
          // If not a duplicate error, try to show the error message from the object if available
          // or fallback to generic error.
          // Since we removed isBangumiParsingFailedError, we treat it as generic error if it somehow happens (shouldn't with skipBangumi=true)
          const msg = (err as any).msg_en || (err as any).message || String(err);
           message.error(msg);
        }
      },
      onFinally() {
        windowState.loading = false;
      },
    }).execute(rss.value, { skipBangumi: true });
  }
}

function collect() {
  if (rule.value) {
    useApi(apiDownload.collection, {
      showMessage: true,
      onBeforeExecute() {
        loading.collect = true;
      },
      onSuccess() {
        getAll();
        show.value = false;
      },
      onFinally() {
        loading.collect = false;
      },
    }).execute(rule.value);
  }
}

function subscribe() {
  if (rule.value) {
    useApi(apiDownload.subscribe, {
      showMessage: true,
      onBeforeExecute() {
        loading.subscribe = true;
      },
      onSuccess() {
        getAll();
        show.value = false;
      },
      onFinally() {
        loading.subscribe = false;
      },
    }).execute(rule.value, rss.value);
  }
}
</script>

<template>
  <ab-popup
    v-model:show="show"
    :title="
      rss.id !== 0 ? $t('rss.edit_title') || 'Edit RSS' : $t('topbar.add.title')
    "
    :css="windowState.rule ? 'max-w-900' : 'w-360'"
  >
    <div v-if="!windowState.next" space-y-12>
      <ab-setting
        v-model:data="rss.url"
        :label="$t('topbar.add.rss_link')"
        type="input"
        :prop="{
          placeholder: $t('topbar.add.placeholder_link'),
        }"
      ></ab-setting>

      <ab-setting
        v-model:data="rss.name"
        :label="$t('topbar.add.name')"
        type="input"
        :prop="{
          placeholder: $t('topbar.add.placeholder_name'),
        }"
      ></ab-setting>

      <ab-setting
        v-model:data="rss.aggregate"
        :label="$t('topbar.add.aggregate')"
        type="switch"
      ></ab-setting>

      <ab-setting
        v-model:data="rss.parser"
        :label="$t('topbar.add.parser')"
        type="select"
        :prop="{
          items: parserType,
        }"
        :bottom-line="true"
      ></ab-setting>

      <div flex="~ justify-end">
        <ab-button size="small" :loading="windowState.loading" @click="addRss">
          {{
            rss.id !== 0
              ? $t('rss.edit_button') || 'Update'
              : $t('topbar.add.next') || 'Next'
          }}
        </ab-button>
      </div>
    </div>

    <div v-else-if="windowState.rule" flex="~ gap-x-12">
      <div class="w-360" space-y-12>
        <ab-rule v-model:rule="rule"></ab-rule>
        <div flex="~ justify-end gap-x-10">
          <ab-button size="small" :loading="loading.collect" @click="collect">
            {{ $t('topbar.add.collect') }}
          </ab-button>

          <ab-button
            size="small"
            :loading="loading.subscribe"
            @click="subscribe"
          >
            {{ $t('topbar.add.subscribe') }}
          </ab-button>
        </div>
      </div>

      <div class="w-500" flex="~ col">
        <div text="14 gray-500" mb-8 flex="~ justify-between items-center">
          <span>{{ $t('rss.torrent_list') || 'Torrent List' }}</span>
          <span v-if="loading.torrents" animate-spin>
            <div i-carbon-renew></div>
          </span>
        </div>

        <div flex="~ gap-x-8" flex-1 overflow-hidden>
          <!-- Keep List -->
          <div flex="~ col" flex-1 overflow-hidden>
            <div text="12 gray-400" mb-4 px-4>
              {{ $t('rss.keep') || 'Keep' }} ({{ torrentsKeep.length }})
            </div>
            <div
              flex-1
              overflow-y-auto
              rounded-8
              bg="green-50 dark:green-900/20"
              p-8
              space-y-4
              max-h-400
            >
              <div
                v-for="torrent in torrentsKeep"
                :key="torrent.url"
                text="12 green-700 dark:green-300"
                p-4
                rounded-4
              >
                {{ torrent.name }}
              </div>
              <div
                v-if="torrentsKeep.length === 0 && !loading.torrents"
                text="12 gray-400 center"
                py-20
              >
                {{ $t('rss.no_torrents') || 'No torrents found' }}
              </div>
            </div>
          </div>

          <!-- Exclude List -->
          <div flex="~ col" flex-1 overflow-hidden>
            <div text="12 gray-400" mb-4 px-4>
              {{ $t('rss.exclude') || 'Exclude' }} ({{
                torrentsExclude.length
              }})
            </div>
            <div
              flex-1
              overflow-y-auto
              rounded-8
              bg="red-50 dark:red-900/20"
              p-8
              space-y-4
              max-h-400
            >
              <div
                v-for="torrent in torrentsExclude"
                :key="torrent.url"
                text="12 red-700 dark:red-300"
                p-4
                rounded-4
                class="opacity-60 line-through"
              >
                {{ torrent.name }}
              </div>
              <div
                v-if="torrentsExclude.length === 0 && !loading.torrents"
                text="12 gray-400 center"
                py-20
              >
                {{ $t('rss.no_torrents') || 'No torrents found' }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </ab-popup>
</template>
