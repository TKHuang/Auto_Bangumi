# Mikan Health Banner Noise Reduction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop showing the global Mikan warning when the only signal is an old success timestamp, while preserving warnings for pending work and actual failures.

**Architecture:** Extract the banner visibility and severity-class rules into a small pure TypeScript policy module. The Vue component consumes those functions, while Vitest verifies the actionable-signal contract without adding a component-mounting dependency.

**Tech Stack:** Vue 3 Composition API, TypeScript, Pinia, Vitest

## Global Constraints

- Keep the `/api/v1/health/mikan` response and backend status calculation unchanged.
- Show the banner when `pending_count > 0` or `consecutive_failures > 0`.
- Hide the banner when both values are zero, regardless of `hours_since_last_success` or `status`.
- Preserve the existing degraded and down visual classes and the pending-resolution link.
- Do not turn an AutoBangumi health API request error into a Mikan service warning.

---

## File Structure

- Create `webui/src/components/dashboard/mikan-health-banner.ts`: pure visibility and CSS-class policy.
- Create `webui/src/components/dashboard/mikan-health-banner.test.ts`: focused policy tests.
- Modify `webui/src/components/dashboard/MikanHealthBanner.vue`: delegate display decisions to the tested policy.

### Task 1: Make the banner actionable-only

**Files:**

- Create: `webui/src/components/dashboard/mikan-health-banner.ts`
- Create: `webui/src/components/dashboard/mikan-health-banner.test.ts`
- Modify: `webui/src/components/dashboard/MikanHealthBanner.vue:1-16`

**Interfaces:**

- Consumes: `MikanHealth` from `webui/src/api/health.ts`.
- Produces: `shouldShowMikanHealthBanner(health): boolean` and `mikanHealthBannerClass(status, visible): string`.

- [ ] **Step 1: Write the failing policy tests**

Create `webui/src/components/dashboard/mikan-health-banner.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import {
  mikanHealthBannerClass,
  shouldShowMikanHealthBanner,
} from "./mikan-health-banner";

describe("Mikan health banner policy", () => {
  it("hides a stale degraded status without actionable signals", () => {
    expect(
      shouldShowMikanHealthBanner({
        pending_count: 0,
        consecutive_failures: 0,
      })
    ).toBe(false);
  });

  it("shows pending work", () => {
    expect(
      shouldShowMikanHealthBanner({
        pending_count: 1,
        consecutive_failures: 0,
      })
    ).toBe(true);
  });

  it("shows actual failures without pending work", () => {
    expect(
      shouldShowMikanHealthBanner({
        pending_count: 0,
        consecutive_failures: 1,
      })
    ).toBe(true);
  });

  it("stays hidden before health data loads", () => {
    expect(shouldShowMikanHealthBanner(null)).toBe(false);
  });

  it("preserves degraded and down severity classes", () => {
    expect(mikanHealthBannerClass("degraded", true)).toBe("banner banner-warn");
    expect(mikanHealthBannerClass("down", true)).toBe("banner banner-down");
    expect(mikanHealthBannerClass("ok", true)).toBe("banner banner-warn");
    expect(mikanHealthBannerClass("down", false)).toBe("");
  });
});
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
cd webui
pnpm exec vitest run src/components/dashboard/mikan-health-banner.test.ts
```

Expected: FAIL because `./mikan-health-banner` does not exist.

- [ ] **Step 3: Implement the pure banner policy**

Create `webui/src/components/dashboard/mikan-health-banner.ts`:

```typescript
import type { MikanHealth } from "../../api/health";

type MikanHealthSignal = Pick<
  MikanHealth,
  "pending_count" | "consecutive_failures"
>;

export function shouldShowMikanHealthBanner(
  health: MikanHealthSignal | null | undefined
): boolean {
  return Boolean(
    health && (health.pending_count > 0 || health.consecutive_failures > 0)
  );
}

export function mikanHealthBannerClass(
  status: MikanHealth["status"] | null | undefined,
  visible: boolean
): string {
  if (!visible) return "";
  if (status === "down") return "banner banner-down";
  return "banner banner-warn";
}
```

- [ ] **Step 4: Wire the Vue component to the tested policy**

Replace the script block in `webui/src/components/dashboard/MikanHealthBanner.vue` with:

```vue
<script lang="ts" setup>
import {
  mikanHealthBannerClass,
  shouldShowMikanHealthBanner,
} from "./mikan-health-banner";

const healthStore = useHealthStore();

onMounted(() => healthStore.startPolling(30_000));
onBeforeUnmount(() => healthStore.stopPolling());

const show = computed(() => shouldShowMikanHealthBanner(healthStore.mikan));

const bannerClass = computed(() =>
  mikanHealthBannerClass(healthStore.mikan?.status, show.value)
);
</script>
```

- [ ] **Step 5: Run the focused test and verify it passes**

Run:

```bash
cd webui
pnpm exec vitest run src/components/dashboard/mikan-health-banner.test.ts
```

Expected: 1 test file passes with 5 passing tests.

- [ ] **Step 6: Run WebUI regression checks**

Run:

```bash
cd webui
pnpm exec vitest run
pnpm test:build
pnpm exec eslint src/components/dashboard/MikanHealthBanner.vue \
  src/components/dashboard/mikan-health-banner.ts \
  src/components/dashboard/mikan-health-banner.test.ts
```

Expected: all Vitest tests pass, Vue TypeScript reports no errors, and targeted ESLint exits successfully. Full-repository lint currently has unrelated pre-existing errors outside these files.

- [ ] **Step 7: Review and commit the implementation**

Review only the intended files:

```bash
git diff --check
git diff -- webui/src/components/dashboard/MikanHealthBanner.vue \
  webui/src/components/dashboard/mikan-health-banner.ts \
  webui/src/components/dashboard/mikan-health-banner.test.ts
```

Commit:

```bash
git add webui/src/components/dashboard/MikanHealthBanner.vue \
  webui/src/components/dashboard/mikan-health-banner.ts \
  webui/src/components/dashboard/mikan-health-banner.test.ts
git commit -m "fix(webui): Hide stale Mikan health warnings"
```
