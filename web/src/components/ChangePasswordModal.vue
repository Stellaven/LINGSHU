<script setup lang="ts">
import { ref, watch } from 'vue'
import { changePassword, currentUser } from '@/stores/auth'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppModal from '@/components/ui/AppModal.vue'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()

const oldPassword = ref('')
const newPassword = ref('')
const confirm = ref('')
const submitting = ref(false)
const error = ref('')

// 每次打开重置表单，避免残留上次输入
watch(
  () => props.open,
  (open) => {
    if (open) {
      oldPassword.value = ''
      newPassword.value = ''
      confirm.value = ''
      error.value = ''
    }
  },
)

async function onSubmit() {
  error.value = ''
  if (!oldPassword.value || !newPassword.value) {
    error.value = '请输入原密码和新密码'
    return
  }
  if (newPassword.value.length < 6) {
    error.value = '新密码长度至少 6 位'
    return
  }
  if (newPassword.value === oldPassword.value) {
    error.value = '新密码不能与原密码相同'
    return
  }
  if (newPassword.value !== confirm.value) {
    error.value = '两次输入的新密码不一致'
    return
  }
  if (!currentUser.value) return
  submitting.value = true
  try {
    await changePassword(currentUser.value.account, oldPassword.value, newPassword.value)
    emit('close')
  } catch (e) {
    error.value = e instanceof Error ? e.message : '密码修改失败，请重试'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AppModal :open="open" title="修改密码" width="max-w-sm" @close="emit('close')">
    <form class="space-y-4" @submit.prevent="onSubmit">
      <p
        v-if="error"
        class="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300"
      >
        {{ error }}
      </p>
      <div class="space-y-1.5">
        <label for="cp-old" class="text-xs font-medium text-muted">原密码</label>
        <AppInput
          id="cp-old"
          v-model="oldPassword"
          type="password"
          placeholder="请输入原密码"
          autocomplete="current-password"
        />
      </div>
      <div class="space-y-1.5">
        <label for="cp-new" class="text-xs font-medium text-muted">
          新密码 <span class="text-muted/60">（至少 6 位）</span>
        </label>
        <AppInput
          id="cp-new"
          v-model="newPassword"
          type="password"
          placeholder="请输入新密码"
          autocomplete="new-password"
        />
      </div>
      <div class="space-y-1.5">
        <label for="cp-confirm" class="text-xs font-medium text-muted">确认新密码</label>
        <AppInput
          id="cp-confirm"
          v-model="confirm"
          type="password"
          placeholder="请再次输入新密码"
          autocomplete="new-password"
        />
      </div>
      <div class="flex justify-end gap-3 pt-1">
        <AppButton type="button" @click="emit('close')">取消</AppButton>
        <AppButton variant="primary" type="submit" :loading="submitting">确认修改</AppButton>
      </div>
    </form>
  </AppModal>
</template>
