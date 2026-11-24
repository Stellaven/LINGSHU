<script setup lang="ts">
import { ArrowLeft } from '@lucide/vue'
import { useRouter } from 'vue-router'

/**
 * 统一的「返回」按钮：固定跳转到上一级页面（replace，不残留历史），
 * 按页面层级返回（项目→团队、分块→知识库），而非回退操作历史。
 */
const props = defineProps<{ to: string }>()

const router = useRouter()

function goBack() {
  void router.replace(props.to)
}
</script>

<template>
  <button
    type="button"
    class="inline-flex items-center gap-1 rounded-md px-1 py-0.5 text-sm text-muted transition-colors duration-200 hover:text-ink"
    @click="goBack"
  >
    <ArrowLeft class="size-3.5" />
    返回
  </button>
</template>
