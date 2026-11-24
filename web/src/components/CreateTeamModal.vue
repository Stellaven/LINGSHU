<script setup lang="ts">
import { ref } from 'vue'
import { createTeam } from '@/stores/team'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppModal from '@/components/ui/AppModal.vue'
import AppTextarea from '@/components/ui/AppTextarea.vue'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()

const name = ref('')
const description = ref('')
const submitting = ref(false)

async function onSubmit() {
  if (!name.value.trim() || submitting.value) return
  submitting.value = true
  try {
    await createTeam(name.value, description.value)
    name.value = ''
    description.value = ''
    emit('close')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AppModal :open="props.open" title="新建团队" @close="emit('close')">
    <form class="space-y-4" @submit.prevent="onSubmit">
      <div class="space-y-1.5">
        <label for="team-name" class="text-xs font-medium text-muted">
          名称 <span class="text-accent">*</span>
        </label>
        <AppInput id="team-name" v-model="name" placeholder="例如：搜索与推荐组" />
      </div>
      <div class="space-y-1.5">
        <label for="team-desc" class="text-xs font-medium text-muted">描述</label>
        <AppTextarea
          id="team-desc"
          v-model="description"
          :rows="3"
          placeholder="简单描述这个团队的用途（可选）"
        />
      </div>
      <!-- 隐藏提交按钮以支持回车提交 -->
      <button type="submit" class="hidden" />
    </form>

    <template #footer>
      <AppButton variant="ghost" @click="emit('close')">取消</AppButton>
      <AppButton variant="primary" :loading="submitting" :disabled="!name.trim()" @click="onSubmit">
        创建
      </AppButton>
    </template>
  </AppModal>
</template>
