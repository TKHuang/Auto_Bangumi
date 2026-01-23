<script lang="tsx" setup>
import { NDataTable, NDropdown, NTooltip, useDialog } from 'naive-ui';
import type { DropdownOption } from 'naive-ui';
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

// Pending review counts per RSS
const pendingCounts = ref<Record<number, number>>({});

// AR Manage Dialog state
const showManageDialog = ref(false);
const manageDialogRssId = ref(0);
const manageDialogRssName = ref('');

function openManageDialog(rss: RSS) {
  manageDialogRssId.value = rss.id;
  manageDialogRssName.value = rss.name;
  showManageDialog.value = true;
}

function handlePendingClick(rss: RSS) {
  if (rss.aggregate) {
    // For aggregate RSS: open the manage dialog
    openManageDialog(rss);
  } else {
    // For non-aggregate RSS: open the recreate dialog to review and re-activate
    handleRecreate(rss.id);
  }
}

// Context menu state
const showContextMenu = ref(false);
const contextMenuX = ref(0);
const contextMenuY = ref(0);
const contextMenuRss = ref<RSS | null>(null);

const contextMenuOptions = computed<DropdownOption[]>(() => {
  const rssItem = contextMenuRss.value;
  if (!rssItem) {
    return [];
  }
  // Show context menu for aggregate RSS (always) or non-aggregate RSS with pending review
  const pendingCount = pendingCounts.value[rssItem.id] || 0;
  if (!rssItem.aggregate && pendingCount === 0) {
    return [];
  }
  return [
    {
      label: rssItem.aggregate ? t('rss.manage_bangumi') : t('rss.review_pending'),
      key: 'manage',
    },
  ];
});

function handleContextMenu(e: MouseEvent, rss: RSS) {
  e.preventDefault();
  contextMenuRss.value = rss;
  showContextMenu.value = false;
  nextTick().then(() => {
    showContextMenu.value = true;
    contextMenuX.value = e.clientX;
    contextMenuY.value = e.clientY;
  });
}

function handleContextMenuSelect(key: string | number) {
  showContextMenu.value = false;
  if (key === 'manage' && contextMenuRss.value) {
    handlePendingClick(contextMenuRss.value);
  }
}

function handleClickOutside() {
  showContextMenu.value = false;
}

async function fetchPendingCounts() {
  // Fetch pending counts for ALL RSS items (both aggregate and non-aggregate)
  const results = await Promise.all(
    rss.value.map(async (r) => {
      try {
        const res = await apiRSS.getPendingCount(r.id);
        return { id: r.id, count: res.pending_count };
      } catch {
        return { id: r.id, count: 0 };
      }
    })
  );
  const counts: Record<number, number> = {};
  results.forEach((r) => {
    counts[r.id] = r.count;
  });
  pendingCounts.value = counts;
}

function handleEdit(item: RSS) {
  editRSS.value = { ...item };
  showEdit.value = true;
}

const message = useMessage();
const dialog = useDialog();

const recreateDialog =
  ref<
    InstanceType<typeof import('./components/ab-rss-recreate.vue').default>
  >();

async function handleRecreate(rssId: number) {
  recreateDialog.value?.open(rssId);
}

// Action dropdown options for each RSS row
const actionOptions: DropdownOption[] = [
  {
    label: t('rss.refresh'),
    key: 'refresh',
  },
  {
    label: t('rss.recreate'),
    key: 'recreate',
  },
  {
    label: t('rss.edit'),
    key: 'edit',
  },
  {
    type: 'divider',
    key: 'd1',
  },
  {
    label: t('rss.delete'),
    key: 'delete',
    props: {
      style: { color: '#e53935' },
    },
  },
];

function handleActionSelect(key: string | number, rss: RSS) {
  switch (key) {
    case 'refresh':
      refreshRSS(rss.id);
      break;
    case 'recreate':
      handleRecreate(rss.id);
      break;
    case 'edit':
      handleEdit(rss);
      break;
    case 'delete':
      handleDeleteRSS(rss);
      break;
  }
}

function handleDeleteRSS(rss: RSS) {
  dialog.warning({
    title: t('rss.confirm'),
    content: t('rss.delete_confirm', { name: rss.name }),
    positiveText: t('rss.confirm'),
    negativeText: t('rss.cancel'),
    onPositiveClick: async () => {
      try {
        await apiRSS.delete(rss.id);
        message.success(t('rss.delete_success'));
        await getAll();
        fetchPendingCounts();
      } catch (e) {
        message.error(t('rss.delete_failed'));
      }
    },
  });
}

onActivated(async () => {
  await getAll();
  fetchPendingCounts();
});

const RSSTableOptions = computed(() => {
  // Access pendingCounts.value at top level to track as dependency for Vue reactivity
  const currentPendingCounts = pendingCounts.value;

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
      width: 180,
      render(rss: RSS) {
        const pendingCount = currentPendingCounts[rss.id] || 0;
        return (
          <div flex="~ col gap-y-4 items-end">
            {/* Row 1: Pending badge, Status, Parser */}
            <div flex="~ gap-x-4 items-center">
              {pendingCount > 0 && (
                <NTooltip trigger="hover">
                  {{
                    trigger: () => (
                      <div
                        class="inline-flex items-center px-6 py-2 rounded-10
                               bg-amber-500 hover:bg-amber-600
                               text-white text-11 font-semibold
                               cursor-pointer transition-colors"
                        style={{ gap: '4px' }}
                        onClick={(e: Event) => {
                          e.stopPropagation();
                          handlePendingClick(rss);
                        }}
                      >
                        <span
                          class="i-mdi:alert-circle"
                          style={{
                            width: '12px',
                            height: '12px',
                            flexShrink: 0,
                          }}
                        />
                        <span>{pendingCount}</span>
                      </div>
                    ),
                    default: () =>
                      t('rss.pending_review_count', { count: pendingCount }),
                  }}
                </NTooltip>
              )}
              {rss.last_status === 'Success' && (
                <ab-tag type="active" title="Success" />
              )}
              {rss.last_status === 'Error' && (
                <NTooltip trigger="hover">
                  {{
                    trigger: () => <ab-tag type="inactive" title="Error" />,
                    default: () => rss.last_error,
                  }}
                </NTooltip>
              )}
              {rss.parser && <ab-tag type="primary" title={rss.parser} />}
            </div>
            {/* Row 2: Agg, On/Off */}
            <div flex="~ gap-x-4 items-center">
              {rss.aggregate && <ab-tag type="primary" title="Agg" />}
              {rss.enabled ? (
                <ab-tag type="active" title="On" />
              ) : (
                <ab-tag type="inactive" title="Off" />
              )}
            </div>
          </div>
        );
      },
    },
    {
      title: '',
      key: 'action',
      width: 50,
      align: 'center',
      render(rss: RSS) {
        return (
          <NDropdown
            trigger="click"
            placement="bottom-end"
            options={actionOptions}
            onSelect={(key: string | number) => handleActionSelect(key, rss)}
          >
            <div class="cursor-pointer p-4 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-4">
              <div class="i-mdi:dots-vertical w-18 h-18" />
            </div>
          </NDropdown>
        );
      },
    },
  ];

  const rowKey = (rss: RSS) => rss.id;

  const rowProps = (row: RSS) => {
    return {
      onContextmenu: (e: MouseEvent) => handleContextMenu(e, row),
    };
  };

  return {
    columns,
    data: rss.value,
    pagination: false,
    bordered: false,
    rowKey,
    rowProps,
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

    <ab-ar-manage
      v-model:show="showManageDialog"
      :rss-id="manageDialogRssId"
      :rss-name="manageDialogRssName"
      @activated="fetchPendingCounts"
    />

    <NDropdown
      placement="bottom-start"
      trigger="manual"
      :x="contextMenuX"
      :y="contextMenuY"
      :options="contextMenuOptions"
      :show="showContextMenu"
      @select="handleContextMenuSelect"
      @clickoutside="handleClickOutside"
    />
  </div>
</template>
