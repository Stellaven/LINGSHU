<script setup lang="ts">
import { Clock, FileSearch, FileText, Layers, Search } from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import * as api from '@/api/knowledge'
import type { Chunk, KnowledgeFile } from '@/types/knowledge'
import BackButton from '@/components/BackButton.vue'
import AppBadge from '@/components/ui/AppBadge.vue'
import AppInput from '@/components/ui/AppInput.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import { formatBytes, formatDateTime } from '@/utils/format'

const route = useRoute()
const kbId = computed(() => route.params.kbId as string)
const fileId = computed(() => route.params.fileId as string)

const file = ref<KnowledgeFile | null>(null)
const chunks = ref<Chunk[]>([])
const loading = ref(true)
const search = ref('')

onMounted(async () => {
  const [fileList, chunkList] = await Promise.all([
    api.listFiles(kbId.value),
    api.listChunks(fileId.value),
  ])
  file.value = fileList.find((f) => f.id === fileId.value) ?? null
  chunks.value = chunkList
  loading.value = false
})

const filteredChunks = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return chunks.value
  return chunks.value.filter(
    (c) =>
      c.content.toLowerCase().includes(q) ||
      Object.entries(c.metadata).some(([k, v]) => `${k}:${v}`.toLowerCase().includes(q)),
  )
})

const metadataEntries = (chunk: Chunk) => Object.entries(chunk.metadata)
</script>

<template>
  <div>
    <!-- 返回 + 标题区 -->
    <section class="pb-8 pt-6 md:pt-8">
      <BackButton :to="`/knowledge/${kbId}`" />

      <div class="mt-5 flex flex-wrap items-end justify-between gap-4">
        <div class="min-w-0">
          <h1 class="text-gradient truncate text-3xl font-semibold tracking-tight md:text-4xl">
            {{ file?.name ?? '加载中…' }}
          </h1>
          <div v-if="file" class="mt-3 flex flex-wrap items-center gap-4 text-xs text-muted">
            <AppBadge v-if="file.status === 'indexed'" tone="success">已索引</AppBadge>
            <AppBadge v-else tone="accent">处理中</AppBadge>
            <span class="inline-flex items-center gap-1.5">
              <Layers class="size-3.5" /> {{ chunks.length }} 分块
            </span>
            <span class="inline-flex items-center gap-1.5">
              <FileText class="size-3.5" /> {{ formatBytes(file.size) }}
            </span>
            <span class="inline-flex items-center gap-1.5">
              <Clock class="size-3.5" /> 更新于 {{ formatDateTime(file.updatedAt) }}
            </span>
          </div>
        </div>
        <div class="relative">
          <Search
            class="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted"
          />
          <AppInput v-model="search" placeholder="搜索分块内容或元数据…" class="w-64 pl-9" />
        </div>
      </div>
    </section>

    <!-- 骨架屏 -->
    <section v-if="loading" class="space-y-4" aria-busy="true">
      <div v-for="i in 2" :key="i" class="card-surface animate-pulse p-5">
        <div class="h-3.5 w-40 rounded bg-white/5" />
        <div class="mt-4 h-3 w-full rounded bg-white/5" />
        <div class="mt-2 h-3 w-3/4 rounded bg-white/5" />
      </div>
    </section>

    <!-- 分块列表 -->
    <section v-else-if="filteredChunks.length" class="space-y-4">
      <article
        v-for="chunk in filteredChunks"
        :key="chunk.id"
        class="card-surface p-5 transition-all duration-300 ease-out hover:border-white/10 hover:shadow-[0_0_0_1px_rgba(255,255,255,0.08),0_8px_32px_rgba(0,0,0,0.4)]"
      >
        <header class="flex flex-wrap items-center gap-2.5">
          <span class="font-mono text-xs font-medium text-accent">
            #{{ String(chunk.index).padStart(3, '0') }}
          </span>
          <span
            class="rounded-full border border-white/8 bg-white/[0.04] px-2 py-0.5 font-mono text-[11px] text-muted"
          >
            {{ chunk.tokens }} tokens
          </span>
          <span class="ml-auto inline-flex items-center gap-1.5 text-xs text-muted">
            <Clock class="size-3.5" />
            {{ formatDateTime(chunk.updatedAt) }}
          </span>
        </header>

        <p class="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-ink/85">
          {{ chunk.content }}
        </p>

        <footer
          v-if="metadataEntries(chunk).length"
          class="mt-4 flex flex-wrap gap-2 border-t border-white/6 pt-4"
        >
          <span
            v-for="[key, value] in metadataEntries(chunk)"
            :key="key"
            class="inline-flex max-w-full items-baseline gap-1.5 rounded-md border border-white/6 bg-white/[0.04] px-2 py-1 font-mono text-[11px]"
            :title="`${key}: ${value}`"
          >
            <span class="shrink-0 text-accent/80">{{ key }}</span>
            <span class="truncate text-muted">{{ value }}</span>
          </span>
        </footer>
      </article>
    </section>

    <!-- 空状态 -->
    <section v-else>
      <EmptyState
        v-if="chunks.length === 0"
        title="暂无分块"
        description="文件索引完成后，解析出的分块会展示在这里。"
      >
        <template #icon><Layers class="size-6" :stroke-width="1.5" /></template>
      </EmptyState>
      <EmptyState v-else title="没有匹配的分块" description="换个关键词试试，或清空搜索条件。">
        <template #icon><FileSearch class="size-6" :stroke-width="1.5" /></template>
      </EmptyState>
    </section>
  </div>
</template>
