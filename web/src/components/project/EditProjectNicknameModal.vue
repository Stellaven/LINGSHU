<script setup lang="ts">
import { ref, watch } from 'vue'
import * as api from '@/api/project'
import type { ProjectMember } from '@/types/team'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppModal from '@/components/ui/AppModal.vue'

const props = defineProps<{ open: boolean; projectId: string; nickname: string }>()
const emit = defineEmits<{ close: []; saved: [member: ProjectMember] }>()

const value = ref('')
const submitting = ref(false)

watch(
  () => props.open,
  (open) => {
    if (open) value.value = props.nickname
  },
)

async function onSubmit() {
  if (!value.value.trim() || submitting.value) return
  submitting.value = true
  try {
    const member = await api.updateMyProjectNickname(props.projectId, value.value)
    emit('saved', member)
    emit('close')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AppModal :open="props.open" title="修改项目内昵称" width="max-w-md" @close="emit('close')">
    <form class="space-y-4" @submit.prevent="onSubmit">
      <div class="space-y-1.5">
        <label for="edit-project-nickname" class="text-xs font-medium text-muted">
          我的项目内昵称 <span class="text-accent">*</span>
        </label>
        <AppInput id="edit-project-nickname" v-model="value" placeholder="仅本项目成员可见" />
      </div>
      <!-- 隐藏提交按钮以支持回车提交 -->
      <button type="submit" class="hidden" />
    </form>

    <template #footer>
      <AppButton variant="ghost" @click="emit('close')">取消</AppButton>
      <AppButton variant="primary" :loading="submitting" :disabled="!value.trim()" @click="onSubmit">
        保存
      </AppButton>
    </template>
  </AppModal>
</template>
