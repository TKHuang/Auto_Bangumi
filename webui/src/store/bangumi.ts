import type { BangumiRule } from '#/bangumi';
import { ruleTemplate } from '#/bangumi';

export const useBangumiStore = defineStore('bangumi', () => {
  const message = useMessage();
  const { t, returnUserLangMsg } = useMyI18n();
  const bangumi = ref<BangumiRule[]>();
  const renamingIds = ref<Set<number>>(new Set());
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

  function isRenaming(id: number) {
    return renamingIds.value.has(id);
  }

  async function getAll() {
    const res = await apiBangumi.getAll();
    const sort = (arr: BangumiRule[]) => arr.sort((a, b) => b.id - a.id);

    const enabled = sort(res.filter((e) => !e.deleted));
    const disabled = sort(res.filter((e) => e.deleted));

    bangumi.value = [...enabled, ...disabled];

    // Fetch completion counts in the background. The cards above are
    // already on screen; this patches in real X/Y numbers when the
    // downloader responds. On failure we keep completed_count = null so
    // the card shows a loading indicator (never a misleading stale count).
    apiBangumi
      .getCompletionStatus()
      .then((map) => {
        if (!bangumi.value) return;
        bangumi.value = bangumi.value.map((b) => ({
          ...b,
          completed_count: map[String(b.id)] ?? null,
        }));
      })
      .catch(() => {
        // Intentional: leave completed_count = null so the UI keeps the
        // loading indicator instead of pretending we know the answer.
      });
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
  const { execute: backfillSource } = useApi(apiBangumi.backfillSource, opts);

  async function retriggerRename(id: number) {
    if (renamingIds.value.has(id)) return;

    const next = new Set(renamingIds.value);
    next.add(id);
    renamingIds.value = next;

    try {
      const res = await apiBangumi.retriggerRename(id);
      refreshData();
      const msg = returnUserLangMsg(res);
      if (msg) message.success(msg);
    } catch (error) {
      showRenameBusy(error);
    } finally {
      const done = new Set(renamingIds.value);
      done.delete(id);
      renamingIds.value = done;
    }
  }

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
    renamingIds,
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
    isRenaming,
    batchDelete,
    batchDisable,
  };
});
