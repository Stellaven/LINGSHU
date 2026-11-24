<script setup lang="ts">
import { Check } from '@lucide/vue'
import { ref, watch } from 'vue'
import * as api from '@/api/team'
import { currentUser } from '@/stores/auth'
import { transferOwnership } from '@/stores/team'
import type { TeamMember } from '@/types/team'
import AppButton from '@/components/ui/AppButton.vue'
import AppModal from '@/components/ui/AppModal.vue'

const props = defineProps<{ open: boolean; teamId: string }>()
const emit = defineEmits<{ close: []; transferred: [] }>()

const members = ref<TeamMember[]>([])
const loading = ref(false)
const submitting = ref(false)
const targetId = ref('')

watch(
  () => props.open,
  async (open) => {
    if (!open) return
    loading.value = true
    targetId.value = ''
    try {
      // 候选：除自己与所有者外的全部成员
      const res = await api.listMembers(props.teamId, { page: 1, pageSize: 50 })
      members.value = res.items.filter(
        (m) => m.role !== 'owner' && m.account !== currentUser.value?.account,
      )
      targetId.value = members.value[0]?.id ?? ''
    } finally {
      loading.value = false
    }
  },
)

async function onConfirm() {
  if (!targetId.value || submitting.value) return
  submitting.value = true
  try {
    await transferOwnership(props.teamId, targetId.value)
    emit('transferred')
    emit('close')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AppModal :open="props.open" title="移交团队" width="max-w-md" @close="emit('close')">
    <p class="mb-4 text-sm leading-relaxed text-muted">
      选择一位成员接任团队所有者，移交后你将变为团队成员。
    </p>

    <div v-if="loading" class="space-y-2">
      <div v-for="i in 3" :key="i" class="h-10 animate-pulse rounded-lg bg-white/5" />
    </div>
    <div v-else-if="members.length" class="max-h-64 space-y-1 overflow-y-auto pr-1">
      <button
        v-for="m in members"
        :key="m.id"
        type="button"
        class="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-left text-sm transition-colors"
        :class="m.id === targetId ? 'bg-accent/15 text-ink' : 'text-muted hover:bg-white/5 hover:text-ink'"
        @click="targetId = m.id"
      >
        <span
          class="flex size-7 shrink-0 items-center justify-center rounded-full border border-accent/40 bg-accent/20 text-xs font-semibold text-accent"
        >
          {{ m.nickname.slice(0, 1).toUpperCase() }}
        </span>
        <span class="font-medium">{{ m.nickname }}</span>
        <span class="font-mono text-xs text-muted">{{ m.account }}</span>
        <Check v-if="m.id === targetId" class="ml-auto size-4 text-accent" />
      </button>
    </div>
    <p v-else class="text-sm text-muted">团队中暂无其他成员，请先添加成员。</p>

    <template #footer>
      <AppButton variant="ghost" @click="emit('close')">取消</AppButton>
      <AppButton variant="primary" :loading="submitting" :disabled="!targetId" @click="onConfirm">
        确认移交
      </AppButton>
    </template>
  </AppModal>
</template>
