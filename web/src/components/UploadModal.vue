<script setup lang="ts">
import { FileText, Upload, X } from '@lucide/vue'
import { computed, ref, watch } from 'vue'
import * as api from '@/api/knowledge'
import type { FileParseStrategy, KnowledgeFile } from '@/types/knowledge'
import AppButton from '@/components/ui/AppButton.vue'
import AppModal from '@/components/ui/AppModal.vue'
import AppSelect from '@/components/ui/AppSelect.vue'
import { formatBytes } from '@/utils/format'

const props = defineProps<{ open: boolean; kbId: string }>()
const emit = defineEmits<{ close: []; uploaded: [files: KnowledgeFile[]] }>()

const ACCEPT = '.pdf,.md,.txt,.docx,.pptx,.csv,.html,.yaml,.yml,.json'

const selected = ref<File | null>(null)
const strategyId = ref('')
const strategies = ref<FileParseStrategy[]>([])
const strategiesLoading = ref(false)
const dragging = ref(false)
const submitting = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

const strategyOptions = computed(() =>
  strategies.value.map((s) => ({ value: s.id, label: s.name })),
)
const canSubmit = computed(() => !!selected.value && !!strategyId.value)

/** 打开弹窗时拉取该知识库的策略列表 */
watch(
  () => props.open,
  async (open) => {
    if (!open) return
    selected.value = null
    strategyId.value = ''
    strategiesLoading.value = true
    try {
      strategies.value = await api.listParseStrategies(props.kbId)
    } finally {
      strategiesLoading.value = false
    }
  },
)

function addFiles(list: FileList | File[] | null) {
  if (!list) return
  const incoming = Array.from(list)
  // 单文件上传：仅保留最后一次选择的文件（重复选择同一文件时保持不变）
  selected.value = incoming[incoming.length - 1] ?? null
}

function onDrop(e: DragEvent) {
  dragging.value = false
  addFiles(e.dataTransfer?.files ?? null)
}

function removeSelected() {
  selected.value = null
  if (fileInput.value) fileInput.value.value = ''
}

async function onSubmit() {
  if (!canSubmit.value || submitting.value) return
  submitting.value = true
  try {
    const created = await api.uploadFiles(props.kbId, [selected.value!], strategyId.value)
    emit('uploaded', created)
    selected.value = null
    emit('close')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AppModal :open="props.open" title="上传文件" @close="emit('close')">
    <div class="space-y-4">
      <!-- 拖拽区 -->
      <div
        :class="[
          'flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed px-6 py-10 text-center transition-all duration-200',
          dragging
            ? 'border-accent bg-accent/5 shadow-[0_0_0_3px_rgba(94,106,210,0.15)]'
            : 'border-white/12 bg-white/[0.015] hover:border-white/20',
        ]"
        role="button"
        tabindex="0"
        aria-label="选择或拖拽文件"
        @click="fileInput?.click()"
        @keydown.enter.prevent="fileInput?.click()"
        @dragover.prevent="dragging = true"
        @dragleave="dragging = false"
        @drop.prevent="onDrop"
      >
        <div
          class="flex size-11 items-center justify-center rounded-xl border border-white/10 bg-gradient-to-br from-accent/30 to-accent/5 text-accent"
        >
          <Upload class="size-5" :stroke-width="1.75" />
        </div>
        <p class="mt-3 text-sm font-medium">拖拽文件到此处，或点击选择</p>
        <p class="mt-1 text-xs text-muted">单次仅支持上传 1 个文件 · 单文件 ≤ 50MB</p>
        <input
          ref="fileInput"
          type="file"
          :accept="ACCEPT"
          class="hidden"
          @change="addFiles(($event.target as HTMLInputElement).files); ($event.target as HTMLInputElement).value = ''"
        />
      </div>

      <!-- 已选文件 -->
      <div
        v-if="selected"
        class="group flex items-center gap-3 rounded-lg border border-white/6 bg-white/[0.03] px-3 py-2"
      >
        <FileText class="size-4 shrink-0 text-accent" :stroke-width="1.75" />
        <span class="min-w-0 flex-1 truncate text-sm">{{ selected.name }}</span>
        <span class="shrink-0 font-mono text-xs text-muted">{{ formatBytes(selected.size) }}</span>
        <button
          type="button"
          class="flex size-6 shrink-0 items-center justify-center rounded-md text-muted transition-all duration-200 hover:bg-white/8 hover:text-ink"
          :aria-label="`移除 ${selected.name}`"
          @click="removeSelected"
        >
          <X class="size-3.5" />
        </button>
      </div>

      <!-- 文件处理策略（必选，来自该知识库的策略列表） -->
      <div class="space-y-1.5">
        <label class="text-sm font-medium" for="upload-strategy">文件处理策略</label>
        <AppSelect
          id="upload-strategy"
          v-model="strategyId"
          :options="strategyOptions"
          :disabled="strategiesLoading"
          placeholder="请选择文件处理策略"
        />
        <p v-if="!strategiesLoading && !strategyOptions.length" class="text-xs text-muted">
          该知识库还没有文件处理策略，请先在「处理策略」中创建
        </p>
      </div>
    </div>

    <template #footer>
      <AppButton variant="ghost" @click="emit('close')">取消</AppButton>
      <AppButton variant="primary" :loading="submitting" :disabled="!canSubmit" @click="onSubmit">
        上传
      </AppButton>
    </template>
  </AppModal>
</template>
