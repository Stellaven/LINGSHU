<script setup lang="ts">
import { computed, inject, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as api from '@/api/project'
import type { ProjectMember } from '@/types/team'
import { projectContextKey } from '@/components/project/context'
import EditProjectNicknameModal from '@/components/project/EditProjectNicknameModal.vue'
import TransferProjectModal from '@/components/project/TransferProjectModal.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'

const route = useRoute()
const router = useRouter()
const teamId = route.params.teamId as string
const projectId = route.params.projectId as string

const { project, myRole } = inject(projectContextKey)!
const isOwner = computed(() => myRole.value === 'owner')

const me = ref<ProjectMember | null>(null)

onMounted(async () => {
  me.value = await api.getMyProjectMembership(projectId)
})

const nicknameOpen = ref(false)
const transferOpen = ref(false)
const dissolveOpen = ref(false)
const leaveOpen = ref(false)
const busy = ref(false)

function onNicknameSaved(member: ProjectMember) {
  me.value = member
}

/** 移交负责人：我的项目身份变为项目成员（头部徽标同步） */
function onTransferred() {
  myRole.value = 'member'
}

/** 解散项目：删除项目全部数据并返回团队项目列表 */
async function onDissolve() {
  busy.value = true
  try {
    await api.deleteProject(projectId)
    dissolveOpen.value = false
    router.push(`/team/${teamId}/projects`)
  } finally {
    busy.value = false
  }
}

/** 退出项目：移除我的项目成员身份并返回团队项目列表 */
async function onLeave() {
  busy.value = true
  try {
    await api.leaveProject(projectId)
    leaveOpen.value = false
    router.push(`/team/${teamId}/projects`)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div v-if="project" class="max-w-2xl">
    <!-- 基础信息 -->
    <h2 class="text-sm font-semibold">基础信息</h2>
    <div class="mt-3 divide-y divide-white/6 rounded-2xl border border-white/6 bg-white/[0.02]">
      <div class="flex items-center justify-between gap-4 px-5 py-4">
        <div class="min-w-0">
          <p class="text-sm font-medium">项目名称</p>
          <p class="mt-0.5 truncate text-sm text-muted">{{ project.name }}</p>
        </div>
      </div>
      <div class="flex items-center justify-between gap-4 px-5 py-4">
        <div class="min-w-0">
          <p class="text-sm font-medium">项目描述</p>
          <p class="mt-0.5 text-sm leading-relaxed text-muted">{{ project.description || '暂无描述' }}</p>
        </div>
      </div>
      <div class="flex items-center justify-between gap-4 px-5 py-4">
        <div class="min-w-0">
          <p class="text-sm font-medium">我的项目内昵称</p>
          <p class="mt-0.5 truncate text-sm text-muted">{{ me?.nickname ?? '…' }}</p>
        </div>
        <button
          type="button"
          aria-label="编辑项目内昵称"
          class="shrink-0 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-ink transition-colors hover:bg-white/8"
          @click="nicknameOpen = true"
        >
          编辑
        </button>
      </div>
    </div>

    <!-- 危险区域：移交/解散仅项目负责人可见，退出仅项目成员可见 -->
    <h2 class="mt-10 text-sm font-semibold text-red-400">危险区域</h2>
    <div class="mt-3 divide-y divide-white/6 rounded-2xl border border-red-400/15 bg-white/[0.02]">
      <template v-if="isOwner">
        <div class="flex items-center justify-between gap-4 px-5 py-4">
          <div class="min-w-0">
            <p class="text-sm font-medium">移交</p>
            <p class="mt-0.5 text-sm text-muted">将项目负责人身份移交给其他成员</p>
          </div>
          <button
            type="button"
            class="shrink-0 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-ink transition-colors hover:bg-white/8"
            @click="transferOpen = true"
          >
            移交
          </button>
        </div>
        <div class="flex items-center justify-between gap-4 px-5 py-4">
          <div class="min-w-0">
            <p class="text-sm font-medium">解散项目</p>
            <p class="mt-0.5 text-sm text-muted">解散项目并删除项目的所有数据，此操作不可恢复</p>
          </div>
          <button
            type="button"
            class="shrink-0 rounded-lg border border-red-400/30 bg-red-400/10 px-3 py-1.5 text-xs text-red-400 transition-colors hover:bg-red-400/20"
            @click="dissolveOpen = true"
          >
            解散
          </button>
        </div>
      </template>
      <template v-else>
        <div class="flex items-center justify-between gap-4 px-5 py-4">
          <div class="min-w-0">
            <p class="text-sm font-medium">退出项目</p>
            <p class="mt-0.5 text-sm text-muted">退出后将无法再访问该项目的知识库与数据</p>
          </div>
          <button
            type="button"
            class="shrink-0 rounded-lg border border-red-400/30 bg-red-400/10 px-3 py-1.5 text-xs text-red-400 transition-colors hover:bg-red-400/20"
            @click="leaveOpen = true"
          >
            退出
          </button>
        </div>
      </template>
    </div>

    <EditProjectNicknameModal
      :open="nicknameOpen"
      :project-id="projectId"
      :nickname="me?.nickname ?? ''"
      @close="nicknameOpen = false"
      @saved="onNicknameSaved"
    />
    <TransferProjectModal
      :open="transferOpen"
      :project-id="projectId"
      @close="transferOpen = false"
      @transferred="onTransferred"
    />
    <ConfirmModal
      :open="dissolveOpen"
      title="解散项目"
      :description="`确定解散「${project.name}」？项目内的所有知识库与数据将被永久删除，此操作不可恢复。`"
      confirm-text="解散"
      danger
      :loading="busy"
      @close="dissolveOpen = false"
      @confirm="onDissolve"
    />
    <ConfirmModal
      :open="leaveOpen"
      title="退出项目"
      :description="`确定退出「${project.name}」？退出后将无法再访问该项目的知识库与数据。`"
      confirm-text="退出"
      danger
      :loading="busy"
      @close="leaveOpen = false"
      @confirm="onLeave"
    />
  </div>
</template>
