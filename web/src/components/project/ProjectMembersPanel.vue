<script setup lang="ts">
import { Search, UserPlus } from '@lucide/vue'
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import * as api from '@/api/project'
import type { ProjectMember } from '@/types/team'
import { projectContextKey } from '@/components/project/context'
import AddProjectMemberModal from '@/components/project/AddProjectMemberModal.vue'
import RoleBadge from '@/components/team/RoleBadge.vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'

const PAGE_SIZE = 10

const route = useRoute()
const projectId = route.params.projectId as string

const { project, myRole } = inject(projectContextKey)!

const members = ref<ProjectMember[]>([])
const total = ref(0)
const page = ref(1)
const query = ref('')
const loading = ref(true)
const addOpen = ref(false)
const removeTarget = ref<ProjectMember | null>(null)
const removing = ref(false)

const isOwner = computed(() => myRole.value === 'owner')
const pages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

/** 请求序号：丢弃过期响应，避免搜索/翻页竞态 */
let seq = 0
async function fetchMembers() {
  const current = ++seq
  loading.value = true
  try {
    const res = await api.listProjectMembers(projectId, {
      query: query.value,
      page: page.value,
      pageSize: PAGE_SIZE,
    })
    if (current !== seq) return
    members.value = res.items
    total.value = res.total
    // 当前页被删空时回退一页
    if (res.items.length === 0 && res.page > 1) {
      page.value = res.page - 1
      await fetchMembers()
    }
  } finally {
    if (current === seq) loading.value = false
  }
}

onMounted(fetchMembers)

// 模糊搜索：输入即查（回到第一页）
watch(query, () => {
  page.value = 1
  void fetchMembers()
})

function turnPage(delta: number) {
  page.value += delta
  void fetchMembers()
}

async function onRemove() {
  if (!removeTarget.value) return
  removing.value = true
  try {
    await api.removeProjectMember(projectId, removeTarget.value.id)
    removeTarget.value = null
    await fetchMembers()
  } finally {
    removing.value = false
  }
}

function onAdded() {
  void fetchMembers()
}
</script>

<template>
  <div>
    <!-- 工具栏：搜索 + 添加成员 -->
    <section class="flex flex-wrap items-center gap-3 pb-5">
      <div class="relative">
        <Search
          class="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted"
        />
        <AppInput v-model="query" placeholder="搜索昵称、账号、邮箱…" class="w-72 pl-9" />
      </div>
      <AppButton variant="primary" class="ml-auto" @click="addOpen = true">
        <UserPlus class="size-4" />
        添加成员
      </AppButton>
    </section>

    <!-- 成员表格 -->
    <div class="card-surface overflow-hidden" :class="loading && 'animate-pulse'">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-white/6 text-left text-xs text-muted">
            <th class="px-5 py-3 font-medium">昵称</th>
            <th class="px-5 py-3 font-medium">账号</th>
            <th class="px-5 py-3 font-medium">邮箱</th>
            <th class="px-5 py-3 font-medium">项目权限</th>
            <th v-if="isOwner" class="px-5 py-3 text-right font-medium">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="m in members"
            :key="m.id"
            class="border-b border-white/6 transition-colors last:border-0 hover:bg-white/[0.03]"
          >
            <td class="px-5 py-3.5">
              <div class="flex items-center gap-2.5">
                <span
                  class="flex size-7 shrink-0 items-center justify-center rounded-full border border-accent/40 bg-accent/20 text-xs font-semibold text-accent"
                >
                  {{ m.nickname.slice(0, 1).toUpperCase() }}
                </span>
                <span class="font-medium">{{ m.nickname }}</span>
              </div>
            </td>
            <td class="px-5 py-3.5 font-mono text-xs text-muted">{{ m.account }}</td>
            <td class="px-5 py-3.5 text-muted">{{ m.email }}</td>
            <td class="px-5 py-3.5"><RoleBadge kind="project" :role="m.role" /></td>
            <td v-if="isOwner" class="px-5 py-3.5 text-right">
              <button
                v-if="m.role !== 'owner'"
                type="button"
                class="text-sm text-red-400 transition-colors hover:text-red-300"
                @click="removeTarget = m"
              >
                移出
              </button>
            </td>
          </tr>
          <tr v-if="!loading && members.length === 0">
            <td :colspan="isOwner ? 5 : 4" class="px-5 py-10 text-center text-sm text-muted">
              没有匹配的成员
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 分页 -->
    <footer
      v-if="total > 0"
      class="mt-4 flex flex-wrap items-center gap-3"
    >
      <span class="text-xs text-muted">共 {{ total }} 人</span>
      <div class="ml-auto flex items-center gap-3">
        <span class="text-xs text-muted">第 {{ page }} / {{ pages }} 页</span>
        <AppButton size="sm" variant="secondary" :disabled="page <= 1" @click="turnPage(-1)">
          上一页
        </AppButton>
        <AppButton size="sm" variant="secondary" :disabled="page >= pages" @click="turnPage(1)">
          下一页
        </AppButton>
      </div>
    </footer>

    <AddProjectMemberModal
      :open="addOpen"
      :project-id="projectId"
      :team-id="project?.teamId ?? ''"
      @close="addOpen = false"
      @added="onAdded"
    />
    <ConfirmModal
      :open="removeTarget !== null"
      title="移出成员"
      :description="`确定将「${removeTarget?.nickname}」移出项目？移出后该成员将无法访问本项目。`"
      confirm-text="移出"
      danger
      :loading="removing"
      @close="removeTarget = null"
      @confirm="onRemove"
    />
  </div>
</template>
