<script lang="ts" setup>
import {
  Dialog,
  DialogPanel,
  TransitionChild,
  TransitionRoot,
} from '@headlessui/vue';
import { onMounted, onUnmounted } from 'vue';

const props = withDefaults(
  defineProps<{
    title: string;
    showClose?: boolean;
    escapeClose?: boolean;
    showProgress?: boolean;
    css?: string;
  }>(),
  {
    title: 'title',
    showClose: true,
    escapeClose: true,
    showProgress: false,
    css: '',
  }
);

const show = defineModel('show', { default: false });

// Never close on backdrop click - completely disabled
function handleBackdropClose() {
  // Do nothing - click outside is disabled
}

// Global keydown handler for Escape key (works regardless of focus)
function handleGlobalKeydown(e: KeyboardEvent) {
  if (!show.value) return; // Only when dialog is open
  if (e.key === 'Escape') {
    if (props.escapeClose) {
      show.value = false;
    }
    e.preventDefault();
    e.stopPropagation();
  }
}

// Register global keydown listener
onMounted(() => {
  window.addEventListener('keydown', handleGlobalKeydown);
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKeydown);
});

function closeDialog() {
  show.value = false;
}
</script>

<template>
  <TransitionRoot appear :show="show" as="template">
    <Dialog as="div" class="relative z-10" @close="handleBackdropClose">
      <TransitionChild
        as="template"
        enter="duration-300 ease-out"
        enter-from="opacity-0"
        enter-to="opacity-100"
        leave="duration-200 ease-in"
        leave-from="opacity-100"
        leave-to="opacity-0"
      >
        <div class="popup-backdrop" fixed inset-0 />
      </TransitionChild>

      <div fixed inset-0 overflow-y-auto>
        <div flex="~ items-center justify-center" min-h-full p-4 text-center>
          <TransitionChild
            as="template"
            enter="duration-300 ease-out"
            enter-from="opacity-0 scale-95"
            enter-to="opacity-100 scale-100"
            leave="duration-200 ease-in"
            leave-from="opacity-100 scale-100"
            leave-to="opacity-0 scale-95"
          >
            <DialogPanel class="relative">
              <!-- Progress indicator when loading -->
              <div v-if="showProgress" class="progress-bar">
                <div class="progress-bar-inner" />
              </div>
              <ab-container :title="title" :class="[css]">
                <!-- Close button in title-right slot -->
                <template #title-right>
                  <button
                    v-if="showClose"
                    class="close-button"
                    :disabled="!escapeClose"
                    :class="{ 'close-button-disabled': !escapeClose }"
                    @click="closeDialog"
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      class="w-18 h-18"
                    >
                      <line x1="18" y1="6" x2="6" y2="18"></line>
                      <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                  </button>
                </template>
                <slot></slot>
              </ab-container>
            </DialogPanel>
          </TransitionChild>
        </div>
      </div>
    </Dialog>
  </TransitionRoot>
</template>

<style scoped>
.popup-backdrop {
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(4px);
}

.progress-bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: rgba(0, 0, 0, 0.1);
  border-radius: 9999px 9999px 0 0;
  overflow: hidden;
  z-index: 10;
}

.progress-bar-inner {
  height: 100%;
  width: 30%;
  background: linear-gradient(90deg, #3b82f6, #60a5fa);
  border-radius: 9999px;
  animation: progress-indeterminate 1.5s ease-in-out infinite;
}

@keyframes progress-indeterminate {
  0% {
    transform: translateX(-100%);
  }
  50% {
    transform: translateX(250%);
  }
  100% {
    transform: translateX(-100%);
  }
}

.close-button {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px;
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.8);
  transition: all 0.2s ease;
  cursor: pointer;
  background: transparent;
  border: none;
}

.close-button:hover:not(:disabled) {
  color: white;
  background: rgba(255, 255, 255, 0.15);
}

.close-button:active:not(:disabled) {
  transform: scale(0.95);
}

.close-button-disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
