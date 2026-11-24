<script setup lang="ts">
import { Check, ChevronDown } from '@lucide/vue'
import { computed, ref, watch } from 'vue'
import * as api from '@/api/team'
import { currentUser } from '@/stores/auth'
import type { ProjectView, TeamMember } from '@/types/team'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppModal from '@/components/ui/AppModal.vue'
import AppTextarea from '@/components/ui/AppTextarea.vue'

const props = defineProps<{ open: boolean; teamId: string }>()
const emit = defineEmits<{ close: []; created: [project: ProjectView] }>()

const name = ref('')
const description = ref('')
const submitting = ref(false)

/** 负责人候选（团队全员）与选中项；不指定时默认当前账号 */
const members = ref<TeamMember[]>([])
const membersLoading = ref(false)
const ownerId = ref('')
const pickerOpen = ref(false)
const pickerDraftId = ref('')

watch(
  () => props.open,
  async (open) => {
    if (!open) return
    name.value = ''
    description.value = ''
    // 拉取团队全员作为负责人候选，默认选中当前账号
    membersLoading.value = true
    try {
      const res = await api.listMembers(props.teamId, { page: 1, pageSize: 50 })
      members.value = res.items
      ownerId.value =
        res.items.find((m) => m.account === currentUser.value?.account)?.id ?? res.items[0]?.id ?? ''
    } finally {
      membersLoading.value = false
    }
  },
)

const selectedOwner = computed(() => members.value.find((m) => m.id === ownerId.value) ?? null)
const ownerInitial = computed(() =>
  (selectedOwner.value?.nickname ?? currentUser.value?.account ?? '?').slice(0, 1).toUpperCase(),
)

function openPicker() {
  pickerDraftId.value = ownerId.value
  pickerOpen.value = true
}

function confirmPicker() {
  if (pickerDraftId.value) ownerId.value = pickerDraftId.value
  pickerOpen.value = false
}

async function onSubmit() {
  if (!name.value.trim() || submitting.value) return
  submitting.value = true
  try {
    const ownerAccount = selectedOwner.value?.account
    const project = await api.createProject(
      props.teamId,
      name.value,
      description.value,
      ownerAccount,
    )
    emit('created', project)
    emit('close')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AppModal :open="props.open" title="新建项目" @close="emit('close')">
    <form class="space-y-4" @submit.prevent="onSubmit">
      <div class="space-y-1.5">
        <label for="project-name" class="text-xs font-medium text-muted">
          名称 <span class="text-accent">*</span>
        </label>
        <AppInput id="project-name" v-model="name" placeholder="例如：智能搜索 v3" />
      </div>
      <div class="space-y-1.5">
        <label for="project-desc" class="text-xs font-medium text-muted">描述</label>
        <AppTextarea
          id="project-desc"
          v-model="description"
          :rows="3"
          placeholder="简单描述这个项目的目标（可选）"
        />
      </div>
      <div class="space-y-1.5">
        <span class="text-xs font-medium text-muted">
          项目负责人 <span class="text-muted/70">（可选，默认当前账号）</span>
        </span>
        <!-- 选人入口：点击弹出成员列表 -->
        <button
          type="button"
          class="flex w-full items-center gap-2.5 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-left text-sm transition-colors hover:bg-white/8"
          @click="openPicker"
        >
          <span
            class="flex size-7 shrink-0 items-center justify-center rounded-full border border-accent/40 bg-accent/20 text-xs font-semibold text-accent"
          >
            {{ ownerInitial }}
          </span>
          <span v-if="membersLoading" class="text-muted">加载中…</span>
          <template v-else>
            <span class="font-medium">{{ selectedOwner?.nickname ?? currentUser?.account }}</span>
            <span class="font-mono text-xs text-muted">{{ selectedOwner?.account ?? currentUser?.account }}</span>
          </template>
          <ChevronDown class="ml-auto size-4 shrink-0 text-muted" />
        </button>
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

  <!-- 负责人选人弹框（展示团队全员，可指定其他成员） -->
  <AppModal :open="pickerOpen" title="选择项目负责人" width="max-w-md" @close="pickerOpen = false">
    <div v-if="membersLoading" class="space-y-2">
      <div v-for="i in 3" :key="i" class="h-10 animate-pulse rounded-lg bg-white/5" />
    </div>
    <div v-else-if="members.length" class="max-h-64 space-y-1 overflow-y-auto pr-1">
      <button
        v-for="m in members"
        :key="m.id"
        type="button"
        class="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-left text-sm transition-colors"
        :class="m.id === pickerDraftId ? 'bg-accent/15 text-ink' : 'text-muted hover:bg-white/5 hover:text-ink'"
        @click="pickerDraftId = m.id"
      >
        <span
          class="flex size-7 shrink-0 items-center justify-center rounded-full border border-accent/40 bg-accent/20 text-xs font-semibold text-accent"
        >
          {{ m.nickname.slice(0, 1).toUpperCase() }}
        </span>
        <span class="font-medium">{{ m.nickname }}</span>
        <span v-if="m.account === currentUser?.account" class="text-xs text-muted">（我）</span>
        <span class="font-mono text-xs text-muted">{{ m.account }}</span>
        <Check v-if="m.id === pickerDraftId" class="ml-auto size-4 text-accent" />
      </button>
    </div>
    <p v-else class="text-sm text-muted">团队中暂无成员。</p>

    <template #footer>
      <AppButton variant="ghost" @click="pickerOpen = false">取消</AppButton>
      <AppButton variant="primary" :disabled="!pickerDraftId" @click="confirmPicker">
        确定
      </AppButton>
    </template>
  </AppModal>
</template>
