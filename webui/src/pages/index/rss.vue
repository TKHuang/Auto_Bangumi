<script lang="tsx" setup>
import { NDataTable } from 'naive-ui';
import type { RSS } from '#/rss';
import { rssTemplate } from '#/rss';

definePage({
  name: 'RSS',
});

const { t } = useMyI18n();
const { rss, selectedRSS } = storeToRefs(useRSSStore());
const { getAll, deleteSelected, disableSelected, enableSelected, refreshRSS } =
  useRSSStore();

const showEdit = ref(false);
const editRSS = ref<RSS>(rssTemplate);


function handleEdit(item: RSS) {
  editRSS.value = { ...item };
  showEdit.value = true;
}


const message = useMessage();

const recreateDialog = ref<InstanceType<typeof import('./components/ab-rss-recreate.vue').default>>();

async function handleRecreate(rssId: number) {
  recreateDialog.value?.open(rssId);
}

onActivated(() => {
  getAll();
});

const RSSTableOptions = computed(() => {
  const columns = [
    {
      type: 'selection',
    },
    {
      title: t('rss.name'),
      key: 'name',
      className: 'text-h3',
      ellipsis: {
        tooltip: true,
      },
    },
    {
      title: t('rss.url'),
      key: 'url',
      className: 'text-h3',
      ellipsis: {
        tooltip: true,
      },
    },
    {
      title: t('rss.last_update') || 'Last Update',
      key: 'last_update',
      className: 'text-h3',
      width: 160,
      align: 'right',
    },
    {
      title: t('rss.status') || 'Status',
      key: 'status',
      className: 'text-h3',
      align: 'right',
      width: 200,
      render(rss: RSS) {
        return (
          <div flex="~ justify-end gap-x-4 items-center">
            {rss.last_status === 'Success' && (
              <ab-tag type="active" title="Success" />
            )}
            {rss.last_status === 'Error' && (
              <n-tooltip trigger="hover">
                {{
                  trigger: () => <ab-tag type="inactive" title="Error" />,
                  default: () => rss.last_error,
                }}
              </n-tooltip>
            )}
            {rss.parser && <ab-tag type="primary" title={rss.parser} />}
            {rss.aggregate && <ab-tag type="primary" title="Agg" />}
            {rss.enabled ? (
              <ab-tag type="active" title="On" />
            ) : (
              <ab-tag type="inactive" title="Off" />
            )}
          </div>
        );
      },
    },
    {
      title: t('rss.action') || 'Action',
      key: 'action',
      width: 280,
      align: 'right',
      render(rss: RSS) {
        return (
          <div flex="~ justify-end gap-x-8">
            <ab-button
              type="primary"
              onClick={() => refreshRSS(rss.id)}
            >
              <div flex="~ items-center gap-x-4 px-4">
                <div class="i-mdi:refresh w-16 h-16" />
                <span class="text-12">{t('rss.refresh')}</span>
              </div>
            </ab-button>
            <ab-button
              onClick={() => handleRecreate(rss.id)}
            >
              <div flex="~ items-center gap-x-4 px-4">
                <div class="i-mdi:refresh-circle w-16 h-16" />
                <span class="text-12">{t('rss.recreate')}</span>
              </div>
            </ab-button>
            <ab-button onClick={() => handleEdit(rss)}>
              <div flex="~ items-center gap-x-4 px-4">
                <div class="i-mdi:edit w-16 h-16" />
                <span class="text-12">{t('rss.edit')}</span>
              </div>
            </ab-button>
          </div>
        );
      },
    },
  ];

  const rowKey = (rss: RSS) => rss.id;

  return {
    columns,
    data: rss.value,
    pagination: false,
    bordered: false,
    rowKey,
    maxHeight: 500,
  } as unknown as InstanceType<typeof NDataTable>;
});
</script>

<template>
  <div overflow-auto mt-12 flex-grow>
    <ab-container :title="$t('rss.title')">
      <NDataTable
        v-bind="RSSTableOptions"
        @update:checked-row-keys="(e) => (selectedRSS = (e as number[]))"
      ></NDataTable>

      <div v-if="selectedRSS.length > 0">
        <div line my-12></div>
        <div flex="~ justify-end gap-x-10">
          <ab-button @click="enableSelected">{{ $t('rss.enable') }}</ab-button>
          <ab-button @click="disableSelected">{{
            $t('rss.disable')
          }}</ab-button>
          <ab-button class="type-warn" @click="deleteSelected">{{
            $t('rss.delete')
          }}</ab-button>
        </div>
      </div>
    </ab-container>

    <ab-add-rss v-model:show="showEdit" v-model:rss="editRSS" />

    <ab-rss-recreate ref="recreateDialog" />
  </div>
</template>
