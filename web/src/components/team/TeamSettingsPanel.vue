<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as api from '@/api/team'
import { deleteTeam, leaveTeam, myRole, teams } from '@/stores/team'
import type { TeamMember } from '@/types/team'
import EditNicknameModal from '@/components/team/EditNicknameModal.vue'
import EditTeamModal from '@/components/team/EditTeamModal.vue'
import TransferTeamModal from '@/components/team/TransferTeamModal.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'

const route = useRoute()
const router = useRouter()
const teamId = route.params.teamId as string

const team = computed(() => teams.value.find((t) => t.id === teamId) ?? null)
const role = computed(() => myRole(teamId))

const me = ref<TeamMember | null>(null)

onMounted(async () => {
  me.value = await api.getMyMembership(teamId)
})

const editOpen = ref(false)
const nicknameOpen = ref(false)
const transferOpen = ref(false)
const dissolveOpen = ref(false)
const leaveOpen = ref(false)
const busy = ref(false)

function onNicknameSaved(member: TeamMember) {
  me.value = member
}

/** 解散团队：删除团队全部数据并回到首页（自动进入剩余第一个团队或空状态） */
async function onDissolve() {
  busy.value = true
  try {
    await deleteTeam(teamId)
    dissolveOpen.value = false
    router.push('/')
  } finally {
    busy.value = false
  }
}

/** 退出团队：移除我的成员身份并回到首页（自动进入剩余第一个团队或空状态） */
async function onLeave() {
  busy.value = true
  try {
    await leaveTeam(teamId)
    leaveOpen.value = false
    router.push('/')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div v-if="team" class="max-w-2xl">
    <!-- 基础信息 -->
    <h2 class="text-sm font-semibold">基础信息</h2>
    <div class="mt-3 divide-y divide-white/6 rounded-2xl border border-white/6 bg-white/[0.02]">
      <div class="flex items-center justify-between gap-4 px-5 py-4">
        <div class="min-w-0">
          <p class="text-sm font-medium">团队名称</p>
          <p class="mt-0.5 truncate text-sm text-muted">{{ team.name }}</p>
        </div>
        <!-- 仅团队所有者可编辑团队信息 -->
        <button
          v-if="role === 'owner'"
          type="button"
          aria-label="编辑团队名称"
          class="shrink-0 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-ink transition-colors hover:bg-white/8"
          @click="editOpen = true"
        >
          编辑
        </button>
      </div>
      <div class="flex items-center justify-between gap-4 px-5 py-4">
        <div class="min-w-0">
          <p class="text-sm font-medium">团队描述</p>
          <p class="mt-0.5 text-sm leading-relaxed text-muted">{{ team.description || '暂无描述' }}</p>
        </div>
        <button
          v-if="role === 'owner'"
          type="button"
          aria-label="编辑团队描述"
          class="shrink-0 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-ink transition-colors hover:bg-white/8"
          @click="editOpen = true"
        >
          编辑
        </button>
      </div>
      <div class="flex items-center justify-between gap-4 px-5 py-4">
        <div class="min-w-0">
          <p class="text-sm font-medium">我的团队内昵称</p>
          <p class="mt-0.5 truncate text-sm text-muted">{{ me?.nickname ?? '…' }}</p>
        </div>
        <button
          type="button"
          aria-label="编辑团队内昵称"
          class="shrink-0 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-ink transition-colors hover:bg-white/8"
          @click="nicknameOpen = true"
        >
          编辑
        </button>
      </div>
    </div>

    <!-- 危险区域：移交/解散仅所有者可见，退出仅成员可见 -->
    <h2 class="mt-10 text-sm font-semibold text-red-400">危险区域</h2>
    <div class="mt-3 divide-y divide-white/6 rounded-2xl border border-red-400/15 bg-white/[0.02]">
      <template v-if="role === 'owner'">
        <div class="flex items-center justify-between gap-4 px-5 py-4">
          <div class="min-w-0">
            <p class="text-sm font-medium">移交</p>
            <p class="mt-0.5 text-sm text-muted">将团队所有权移交给其他成员</p>
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
            <p class="text-sm font-medium">解散团队</p>
            <p class="mt-0.5 text-sm text-muted">解散团队并删除所有数据，此操作不可恢复</p>
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
            <p class="text-sm font-medium">退出团队</p>
            <p class="mt-0.5 text-sm text-muted">退出后将无法再访问该团队的项目与数据</p>
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

    <EditTeamModal :open="editOpen" :team="team" @close="editOpen = false" />
    <EditNicknameModal
      :open="nicknameOpen"
      :team-id="teamId"
      :nickname="me?.nickname ?? ''"
      @close="nicknameOpen = false"
      @saved="onNicknameSaved"
    />
    <TransferTeamModal :open="transferOpen" :team-id="teamId" @close="transferOpen = false" />
    <ConfirmModal
      :open="dissolveOpen"
      title="解散团队"
      :description="`确定解散「${team.name}」？团队内的所有项目与数据将被永久删除，此操作不可恢复。`"
      confirm-text="解散"
      danger
      :loading="busy"
      @close="dissolveOpen = false"
      @confirm="onDissolve"
    />
    <ConfirmModal
      :open="leaveOpen"
      title="退出团队"
      :description="`确定退出「${team.name}」？退出后将无法再访问该团队的项目与数据。`"
      confirm-text="退出"
      danger
      :loading="busy"
      @close="leaveOpen = false"
      @confirm="onLeave"
    />
  </div>
</template>
