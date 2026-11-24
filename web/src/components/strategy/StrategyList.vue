<script setup lang="ts">
import { ClipboardList, Link2, Pencil, Plus, Trash2 } from '@lucide/vue'
import type { FileParseStrategy } from '@/types/knowledge'
import AppButton from '@/components/ui/AppButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import { CHUNKERS, EXTRACTORS, PARSERS, findOption, normalizeSplitEntries } from './options'

const props = defineProps<{
  strategies: FileParseStrategy[]
  loading: boolean
}>()

const emit = defineEmits<{
  create: []
  open: [strategy: FileParseStrategy]
  edit: [strategy: FileParseStrategy]
  delete: [strategy: FileParseStrategy]
}>()

/** 列表展示：解析器取编排序列首项；分块器/提取器展示全部名称（悬停 title 查看完整列表） */
const parserName = (s: FileParseStrategy) => findOption(PARSERS, s.stages.parser[0]).name
const chunkerNames = (s: FileParseStrategy) =>
  normalizeSplitEntries(s.stages.split)
    .map((entry) => findOption(CHUNKERS, entry.id).name)
    .join('、')
const extractorNames = (s: FileParseStrategy) =>
  s.stages.post_extract.length
    ? s.stages.post_extract.map((e) => findOption(EXTRACTORS, e.id).name).join('、')
    : findOption(EXTRACTORS, 'none').name
</script>

<template>
  <div class="space-y-5">
    <!-- 工具栏：说明 + 新建策略 -->
    <header class="flex flex-wrap items-end justify-between gap-3">
      <div class="min-w-0">
        <h2 class="flex items-center gap-2 text-sm font-medium">
          <ClipboardList class="size-4 text-accent" :stroke-width="1.75" />
          策略列表
        </h2>
        <p class="mt-1 text-xs leading-relaxed text-muted">
          不同文档可使用不同的处理策略；已被文档引用的策略不可修改或删除。
        </p>
      </div>
      <AppButton variant="primary" class="ml-auto" @click="emit('create')">
        <Plus class="size-4" />
        新建策略
      </AppButton>
    </header>

    <!-- 骨架屏 -->
    <section v-if="props.loading" class="card-surface animate-pulse p-2" aria-busy="true">
      <div v-for="i in 3" :key="i" class="flex items-center gap-4 px-4 py-4">
        <div class="size-9 rounded-lg bg-white/5" />
        <div class="h-3.5 w-1/3 rounded bg-white/5" />
        <div class="ml-auto h-7 w-24 rounded bg-white/5" />
      </div>
    </section>

    <!-- 策略表格 -->
    <section
      v-else-if="props.strategies.length"
      class="overflow-hidden rounded-2xl border border-white/6 bg-gradient-to-b from-white/[0.04] to-white/[0.01]"
    >
      <!-- 表头 -->
      <div
        class="hidden border-b border-white/6 px-5 py-3 font-mono text-[11px] tracking-widest text-muted md:grid md:grid-cols-[minmax(0,1.6fr)_108px_108px_108px_148px_100px_112px] md:items-center md:gap-4"
      >
        <span>策略名称</span>
        <span>文档解析器</span>
        <span>分块器</span>
        <span>数据提取器</span>
        <span>嵌入模型</span>
        <span>构建知识图谱</span>
        <span class="text-right">操作</span>
      </div>

      <div class="divide-y divide-white/6">
        <div
          v-for="strategy in props.strategies"
          :key="strategy.id"
          role="button"
          tabindex="0"
          class="group grid w-full cursor-pointer grid-cols-[minmax(0,1fr)_auto] items-center gap-4 px-5 py-4 text-left transition-colors duration-200 hover:bg-white/[0.04] md:grid-cols-[minmax(0,1.6fr)_108px_108px_108px_148px_100px_112px]"
          @click="emit('open', strategy)"
          @keydown.enter.prevent="emit('open', strategy)"
          @keydown.space.prevent="emit('open', strategy)"
        >
          <!-- 名称（移动端附带其余字段摘要） -->
          <span class="flex min-w-0 items-center gap-3">
            <span
              class="flex size-9 shrink-0 items-center justify-center rounded-lg border border-white/10 bg-white/[0.03] text-accent"
            >
              <ClipboardList class="size-4" :stroke-width="1.75" />
            </span>
            <span class="min-w-0">
              <span class="block truncate text-sm font-medium">{{ strategy.name }}</span>
              <span class="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 font-mono text-[11px] text-muted md:hidden">
                <span>{{ parserName(strategy) }}</span>
                <span>· {{ chunkerNames(strategy) }}</span>
                <span>· {{ extractorNames(strategy) }}</span>
                <span>· {{ strategy.embedModel || '未设置' }}</span>
                <span>· 图谱{{ strategy.graph ? '开启' : '关闭' }}</span>
                <span>· {{ strategy.documentCount }} 引用</span>
              </span>
              <span class="mt-1 hidden items-center gap-1 text-[11px] text-muted/80 md:inline-flex">
                <Link2 class="size-3" :stroke-width="1.75" />
                {{ strategy.documentCount }} 个文档引用
              </span>
            </span>
          </span>

          <span class="hidden font-mono text-xs text-muted md:block">
            {{ parserName(strategy) }}
          </span>
          <span class="hidden truncate text-xs text-muted md:block" :title="chunkerNames(strategy)">
            {{ chunkerNames(strategy) }}
          </span>
          <span class="hidden truncate text-xs text-muted md:block" :title="extractorNames(strategy)">
            {{ extractorNames(strategy) }}
          </span>
          <span class="hidden truncate font-mono text-xs text-muted md:block">
            {{ strategy.embedModel || '未设置' }}
          </span>
          <span class="hidden md:block">
            <span
              class="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium"
              :class="
                strategy.graph
                  ? 'border-emerald-400/20 bg-emerald-400/10 text-emerald-300'
                  : 'border-white/10 bg-white/[0.03] text-muted'
              "
            >
              <span
                class="size-1.5 rounded-full"
                :class="strategy.graph ? 'bg-emerald-400' : 'bg-white/20'"
              />
              {{ strategy.graph ? '开启' : '关闭' }}
            </span>
          </span>

          <!-- 操作：修改（已被文档引用的策略不可修改，不展示）/ 删除 -->
          <span class="flex items-center justify-end gap-1">
            <button
              v-if="strategy.documentCount === 0"
              type="button"
              class="inline-flex h-7 items-center gap-1 rounded-md px-1.5 text-xs text-muted transition-colors duration-200 hover:bg-white/8 hover:text-ink"
              :aria-label="`修改策略 ${strategy.name}`"
              @click.stop="emit('edit', strategy)"
              @keydown.stop
            >
              <Pencil class="size-3.5" :stroke-width="1.75" />
              修改
            </button>
            <button
              v-if="strategy.documentCount === 0"
              type="button"
              class="inline-flex h-7 items-center gap-1 rounded-md px-1.5 text-xs text-muted transition-colors duration-200 hover:bg-red-500/10 hover:text-red-300"
              :aria-label="`删除策略 ${strategy.name}`"
              @click.stop="emit('delete', strategy)"
              @keydown.stop
            >
              <Trash2 class="size-3.5" :stroke-width="1.75" />
              删除
            </button>
          </span>
        </div>
      </div>
    </section>

    <!-- 空状态 -->
    <section v-else>
      <EmptyState
        title="还没有处理策略"
        description="创建策略后，可在上传文档时按需选用不同的解析、分块与嵌入方案。"
      >
        <template #icon><ClipboardList class="size-6" :stroke-width="1.5" /></template>
        <template #action>
          <AppButton variant="primary" @click="emit('create')">
            <Plus class="size-4" />
            新建策略
          </AppButton>
        </template>
      </EmptyState>
    </section>
  </div>
</template>
