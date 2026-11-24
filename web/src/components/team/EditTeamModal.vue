<script setup lang="ts">
import { ref, watch } from 'vue'
import { updateTeam } from '@/stores/team'
import type { Team } from '@/types/team'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppModal from '@/components/ui/AppModal.vue'
import AppTextarea from '@/components/ui/AppTextarea.vue'

const props = defineProps<{ open: boolean; team: Team | null }>()
const emit = defineEmits<{ close: []; saved: [] }>()

const name = ref('')
const description = ref('')
const submitting = ref(false)

watch(
  () => props.open,
  (open) => {
    if (open && props.team) {
      name.value = props.team.name
      description.value = props.team.description
    }
  },
)

async function onSubmit() {
  if (!props.team || !name.value.trim() || submitting.value) return
  submitting.value = true
  try {
    await updateTeam(props.team.id, { name: name.value, description: description.value })
    emit('saved')
    emit('close')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AppModal :open="props.open" title="编辑团队信息" @close="emit('close')">
    <form class="space-y-4" @submit.prevent="onSubmit">
      <div class="space-y-1.5">
        <label for="edit-team-name" class="text-xs font-medium text-muted">
          团队名称 <span class="text-accent">*</span>
        </label>
        <AppInput id="edit-team-name" v-model="name" placeholder="团队名称" />
      </div>
      <div class="space-y-1.5">
        <label for="edit-team-desc" class="text-xs font-medium text-muted">团队描述</label>
        <AppTextarea
          id="edit-team-desc"
          v-model="description"
          :rows="3"
          placeholder="简单描述这个团队（可选）"
        />
      </div>
      <!-- 隐藏提交按钮以支持回车提交 -->
      <button type="submit" class="hidden" />
    </form>

    <template #footer>
      <AppButton variant="ghost" @click="emit('close')">取消</AppButton>
      <AppButton variant="primary" :loading="submitting" :disabled="!name.trim()" @click="onSubmit">
        保存
      </AppButton>
    </template>
  </AppModal>
</template>
