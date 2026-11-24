<script setup lang="ts">
import AppButton from '@/components/ui/AppButton.vue'
import AppModal from '@/components/ui/AppModal.vue'

withDefaults(
  defineProps<{
    open: boolean
    title: string
    description?: string
    confirmText?: string
    /** 危险操作：确认按钮为红色 */
    danger?: boolean
    loading?: boolean
  }>(),
  { description: '', confirmText: '确认', danger: false, loading: false },
)

const emit = defineEmits<{ close: []; confirm: [] }>()
</script>

<template>
  <AppModal :open="open" :title="title" width="max-w-md" @close="emit('close')">
    <p class="text-sm leading-relaxed text-muted">{{ description }}</p>

    <template #footer>
      <AppButton variant="ghost" @click="emit('close')">取消</AppButton>
      <AppButton :variant="danger ? 'danger' : 'primary'" :loading="loading" @click="emit('confirm')">
        {{ confirmText }}
      </AppButton>
    </template>
  </AppModal>
</template>
