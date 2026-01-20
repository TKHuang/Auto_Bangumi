<script lang="ts" setup>
withDefaults(
  defineProps<{
    variant?: 'card' | 'list' | 'compact';
    lines?: number;
    showPoster?: boolean;
  }>(),
  {
    variant: 'card',
    lines: 3,
    showPoster: true,
  }
);

function getLineWidth(n: number): string {
  const widths = ['100%', '85%', '70%', '90%', '60%'];
  return widths[(n - 1) % widths.length];
}
</script>

<template>
  <div class="skeleton-card" :class="[variant]">
    <!-- Poster Skeleton -->
    <div v-if="showPoster" class="skeleton-poster shimmer" />

    <!-- Content Lines -->
    <div class="skeleton-content">
      <div
        v-for="n in lines"
        :key="n"
        class="skeleton-line shimmer"
        :style="{ width: getLineWidth(n) }"
      />
    </div>
  </div>
</template>

<style scoped>
.skeleton-card {
  display: flex;
  gap: 12px;
  padding: 16px;
  border-radius: 12px;
  background: rgb(249 250 251);
}

.dark .skeleton-card {
  background: rgba(31, 41, 55, 0.5);
}

.skeleton-card.compact {
  padding: 12px;
  gap: 8px;
}

.skeleton-card.list {
  padding: 12px 16px;
}

.skeleton-poster {
  width: 80px;
  height: 112px;
  border-radius: 8px;
  background: rgb(229 231 235);
  flex-shrink: 0;
}

.dark .skeleton-poster {
  background: rgb(55 65 81);
}

.skeleton-card.compact .skeleton-poster {
  width: 60px;
  height: 84px;
}

.skeleton-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 0;
}

.skeleton-line {
  height: 16px;
  border-radius: 4px;
  background: rgb(229 231 235);
}

.dark .skeleton-line {
  background: rgb(55 65 81);
}

.skeleton-card.compact .skeleton-line {
  height: 12px;
}

/* Shimmer Animation */
.shimmer {
  position: relative;
  overflow: hidden;
}

.shimmer::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.4) 50%,
    transparent 100%
  );
  animation: shimmer 1.5s infinite;
}

.dark .shimmer::after {
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.1) 50%,
    transparent 100%
  );
}

@keyframes shimmer {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
  }
}

/* Stagger animation for multiple cards */
.skeleton-card {
  animation: fadeSlideIn 0.3s ease-out both;
}

@keyframes fadeSlideIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
