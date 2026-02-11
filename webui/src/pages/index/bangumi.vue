<script lang="ts" setup>
definePage({
  name: 'Bangumi List',
});

const store = useBangumiStore();
const { bangumi, editRule, selectMode, selectedCount } = storeToRefs(store);
const {
  getAll,
  updateRule,
  enableRule,
  retriggerRename,
  openEditPopup,
  ruleManage,
  enterSelectMode,
  exitSelectMode,
  toggleSelect,
  selectAll,
  isSelected,
  batchDelete,
  batchDisable,
} = store;

const { isMobile } = useBreakpointQuery();
const { t } = useMyI18n();
const message = useMessage();

const deleteFileDialog = reactive<{
  show: boolean;
  action: 'delete' | 'disable';
}>({
  show: false,
  action: 'delete',
});

function startBatchAction(action: 'delete' | 'disable') {
  if (selectedCount.value === 0) return;
  deleteFileDialog.action = action;
  deleteFileDialog.show = true;
}

function executeBatchAction(deleteFile: boolean) {
  const ids = Array.from(store.selectedIds);
  deleteFileDialog.show = false;
  if (deleteFileDialog.action === 'delete') {
    batchDelete(ids, deleteFile);
  } else {
    batchDisable(ids, deleteFile);
  }
}

onActivated(() => {
  getAll();
});
</script>

<template>
  <div overflow-auto pr-10 mt-12 flex-grow>
    <div>
      <!-- Toolbar -->
      <div flex="~ items-center justify-between" mb-12 min-h-36>
        <div v-if="selectMode" flex="~ items-center gap-x-10">
          <ab-button size="small" @click="exitSelectMode">
            {{ t('bangumi.cancel_select') }}
          </ab-button>
          <ab-button size="small" @click="selectAll">
            {{ t('bangumi.select_all') }}
          </ab-button>
          <span v-if="selectedCount > 0" text="14 blue-500" font-medium>
            {{ t('bangumi.selected_count', { count: selectedCount }) }}
          </span>
        </div>
        <div v-else>
          <ab-button size="small" @click="enterSelectMode">
            {{ t('bangumi.select_mode') }}
          </ab-button>
        </div>

        <div v-if="selectMode && selectedCount > 0" flex="~ items-center gap-x-8">
          <ab-button size="small" type="warn" @click="startBatchAction('delete')">
            {{ t('bangumi.batch_delete') }}
          </ab-button>
          <ab-button size="small" @click="startBatchAction('disable')">
            {{ t('bangumi.batch_disable') }}
          </ab-button>
        </div>
      </div>

      <transition-group
        name="bangumi"
        tag="div"
        gap="10"
        pc:gap="20"
        :class="[
          { 'justify-center': isMobile },
          isMobile ? 'grid grid-cols-3' : 'flex flex-wrap',
        ]"
      >
        <ab-bangumi-card
          v-for="i in bangumi"
          :key="i.id"
          :class="[i.deleted && 'grayscale']"
          :bangumi="i"
          :select-mode="selectMode"
          :selected="isSelected(i.id)"
          type="primary"
          @click="() => openEditPopup(i)"
          @select="() => toggleSelect(i.id)"
        ></ab-bangumi-card>
      </transition-group>

      <ab-edit-rule
        v-model:show="editRule.show"
        v-model:rule="editRule.item"
        @enable="(id) => enableRule(id)"
        @retrigger-rename="(id) => retriggerRename(id)"
        @delete-file="
          (type, { id, deleteFile }) => ruleManage(type, id, deleteFile)
        "
        @apply="(rule) => updateRule(rule.id, rule)"
      ></ab-edit-rule>

      <!-- Batch delete/disable confirmation -->
      <ab-popup
        v-model:show="deleteFileDialog.show"
        :title="
          deleteFileDialog.action === 'delete'
            ? t('bangumi.batch_delete_confirm', { count: selectedCount })
            : t('bangumi.batch_disable_confirm', { count: selectedCount })
        "
      >
        <div>{{ t('bangumi.delete_files_confirm') }}</div>
        <div line my-8></div>
        <div f-cer gap-x-10>
          <ab-button size="small" type="warn" @click="executeBatchAction(true)">
            {{ t('homepage.rule.yes_btn') }}
          </ab-button>
          <ab-button size="small" @click="executeBatchAction(false)">
            {{ t('homepage.rule.no_btn') }}
          </ab-button>
        </div>
      </ab-popup>
    </div>
  </div>
</template>

<style>
.bangumi-enter-active,
.bangumi-leave-active {
  transition: all 0.5s ease;
}
.bangumi-enter-from,
.bangumi-leave-to {
  opacity: 0;
}
</style>
