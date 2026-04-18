<script lang="ts" setup>
const healthStore = useHealthStore();

onMounted(() => healthStore.startPolling(30_000));
onBeforeUnmount(() => healthStore.stopPolling());

const bannerClass = computed(() => {
  const s = healthStore.mikan?.status;
  if (s === 'down') return 'banner banner-down';
  if (s === 'degraded') return 'banner banner-warn';
  return '';
});

const show = computed(() =>
  healthStore.mikan && healthStore.mikan.status !== 'ok'
);
</script>

<template>
  <div v-if="show" :class="bannerClass">
    <strong v-if="healthStore.mikan?.status === 'down'">
      ⚠️ {{ $t('health.down_title') }}
    </strong>
    <strong v-else>
      ⚠️ {{ $t('health.degraded_title') }}
    </strong>
    <span>
      {{ $t('health.pending_count', { n: healthStore.mikan!.pending_count }) }}
    </span>
    <RouterLink to="/pending-resolution" class="banner-link">
      {{ $t('health.view_details') }}
    </RouterLink>
  </div>
</template>

<style lang="scss" scoped>
.banner {
  padding: 10px 16px;
  border-radius: 6px;
  margin-bottom: 12px;
  display: flex;
  gap: 12px;
  align-items: center;
}

.banner-warn {
  background: #fefcbf;
  color: #744210;
  border-left: 4px solid #d69e2e;
}

.banner-down {
  background: #fed7d7;
  color: #822727;
  border-left: 4px solid #c53030;
}

.banner-link {
  margin-left: auto;
  color: inherit;
  text-decoration: underline;
}
</style>
