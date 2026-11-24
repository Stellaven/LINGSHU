<script setup lang="ts">
import { computed } from 'vue'
import type { ProjectRole, TeamRole } from '@/types/team'

const props = withDefaults(
  defineProps<{ role: TeamRole | ProjectRole; /** 身份域：团队或项目 */ kind?: 'team' | 'project' }>(),
  { kind: 'team' },
)

const LABELS = {
  team: { owner: '团队所有者', member: '团队成员' },
  project: { owner: '项目负责人', member: '项目成员' },
} as const

const label = computed(() => LABELS[props.kind][props.role])
</script>

<template>
  <span
    class="inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-xs leading-none"
    :class="
      role === 'owner'
        ? 'border-red-400/30 bg-red-400/10 text-red-400'
        : 'border-emerald-400/30 bg-emerald-400/10 text-emerald-400'
    "
  >
    {{ label }}
  </span>
</template>
