<script setup lang="ts">
import { ref, watch } from 'vue'
import * as api from '@/api/team'
import type { SystemAccount, TeamMember } from '@/types/team'
import AppButton from '@/components/ui/AppButton.vue'
import AccountSelect from '@/components/ui/AccountSelect.vue'
import AppModal from '@/components/ui/AppModal.vue'

const props = defineProps<{ open: boolean; teamId: string }>()
const emit = defineEmits<{ close: []; added: [member: TeamMember] }>()

const selected = ref<SystemAccount | null>(null)
const submitting = ref(false)
const error = ref('')

/** 搜索系统所有账号（只能从结果中选择） */
async function fetchAccounts(query: string) {
  const rows = await api.searchAccounts(query)
  return rows.map((u) => ({ account: u.account }))
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      selected.value = null
      error.value = ''
    }
  },
)

async function onSubmit() {
  if (!selected.value || submitting.value) return
  submitting.value = true
  error.value = ''
  try {
    const member = await api.addMember(props.teamId, selected.value.account)
    emit('added', member)
    emit('close')
  } catch (e) {
    error.value = e instanceof Error ? e.message : '添加失败，请稍后再试'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AppModal :open="props.open" title="添加成员" width="max-w-md" @close="emit('close')">
    <form class="space-y-4" @submit.prevent="onSubmit">
      <div class="space-y-1.5">
        <label for="member-account" class="text-xs font-medium text-muted">
          账号 <span class="text-accent">*</span>
        </label>
        <AccountSelect
          v-model="selected"
          :fetcher="fetchAccounts"
          placeholder="搜索系统账号后选择"
        />
        <p class="text-xs text-muted/70">输入关键词搜索系统账号，从结果中选择</p>
        <p v-if="error" class="text-xs text-red-400">{{ error }}</p>
      </div>
      <!-- 隐藏提交按钮以支持回车提交（选择器内回车为选中，冒泡的回车触发表单提交） -->
      <button type="submit" class="hidden" />
    </form>

    <template #footer>
      <AppButton variant="ghost" @click="emit('close')">取消</AppButton>
      <AppButton
        variant="primary"
        :loading="submitting"
        :disabled="!selected"
        @click="onSubmit"
      >
        添加
      </AppButton>
    </template>
  </AppModal>
</template>
