import type { BangumiRule } from '#/bangumi';
import { ruleTemplate } from '#/bangumi';

export const useBangumiStore = defineStore('bangumi', () => {
  const message = useMessage();
  const { t } = useMyI18n();
  const bangumi = ref<BangumiRule[]>();
  const editRule = reactive<{
    show: boolean;
    item: BangumiRule;
  }>({
    show: false,
    item: ruleTemplate,
  });

  const selectMode = ref(false);
  const selectedIds = ref<Set<number>>(new Set());

  const selectedCount = computed(() => selectedIds.value.size);

  function enterSelectMode() {
    selectMode.value = true;
    selectedIds.value = new Set();
  }

  function exitSelectMode() {
    selectMode.value = false;
    selectedIds.value = new Set();
  }

  function toggleSelect(id: number) {
    const next = new Set(selectedIds.value);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    selectedIds.value = next;
  }

  function selectAll() {
    if (!bangumi.value) return;
    selectedIds.value = new Set(bangumi.value.map((b) => b.id));
  }

  function isSelected(id: number) {
    return selectedIds.value.has(id);
  }

  async function getAll() {
    const res = await apiBangumi.getAll();
    const sort = (arr: BangumiRule[]) => arr.sort((a, b) => b.id - a.id);

    const enabled = sort(res.filter((e) => !e.deleted));
    const disabled = sort(res.filter((e) => e.deleted));

    bangumi.value = [...enabled, ...disabled];
  }

  function refreshData() {
    editRule.show = false;
    getAll();
  }

  function showRenameBusy(error: any) {
    if (error?.status === 409) {
      message.error(t('notify.rename_busy'));
    }
  }

  const opts = {
    showMessage: true,
    onSuccess() {
      refreshData();
    },
  };

  const { execute: updateRule } = useApi(apiBangumi.updateRule, {
    ...opts,
    onError: showRenameBusy,
  });
  const { execute: enableRule } = useApi(apiBangumi.enableRule, opts);
  const { execute: disableRule } = useApi(apiBangumi.disableRule, opts);
  const { execute: deleteRule } = useApi(apiBangumi.deleteRule, opts);
  const { execute: refreshPoster } = useApi(apiBangumi.refreshPoster, opts);
  const { execute: retriggerRename } = useApi(apiBangumi.retriggerRename, {
    ...opts,
    onError: showRenameBusy,
  });
  const { execute: backfillSource } = useApi(apiBangumi.backfillSource, opts);

  const batchOpts = {
    showMessage: true,
    onSuccess() {
      exitSelectMode();
      getAll();
    },
  };
  const { execute: batchDelete } = useApi(apiBangumi.deleteRule, batchOpts);
  const { execute: batchDisable } = useApi(apiBangumi.disableRule, batchOpts);

  function openEditPopup(data: BangumiRule) {
    editRule.show = true;
    editRule.item = data;
  }

  function ruleManage(
    type: 'disable' | 'delete',
    id: number,
    deleteFile: boolean
  ) {
    switch (type) {
      case 'disable':
        disableRule(id, deleteFile);
        break;

      case 'delete':
        deleteRule(id, deleteFile);
        break;
    }
  }

  return {
    bangumi,
    editRule,
    selectMode,
    selectedIds,
    selectedCount,

    getAll,
    updateRule,
    enableRule,
    disableRule,
    deleteRule,
    refreshPoster,
    retriggerRename,
    backfillSource,
    openEditPopup,
    ruleManage,
    enterSelectMode,
    exitSelectMode,
    toggleSelect,
    selectAll,
    isSelected,
    batchDelete,
    batchDisable,
  };
});
