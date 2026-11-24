<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import * as api from '@/api/knowledge'
import * as modelsApi from '@/api/models'
import * as projectApi from '@/api/project'
import type { KnowledgeBase } from '@/types/knowledge'
import type { EmbeddingModelOption } from '@/types/models'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppModal from '@/components/ui/AppModal.vue'
import AppSelect from '@/components/ui/AppSelect.vue'
import AppTextarea from '@/components/ui/AppTextarea.vue'

const props = defineProps<{ open: boolean; /** 传入则在对应项目下创建知识库 */ projectId?: string }>()
const emit = defineEmits<{ close: []; created: [kb: KnowledgeBase] }>()

const name = ref('')
const description = ref('')
const submitting = ref(false)

/** ---------------- 嵌入模型（项目内模型实例下的 embedding 模型） ---------------- */
const embeddingModels = ref<EmbeddingModelOption[]>([])
const embedModelId = ref('')
const loadingEmbedding = ref(false)
const embeddingLoadFailed = ref(false)

const embedModelOptions = computed(() =>
  embeddingModels.value.map((model) => ({ value: model.id, label: model.label })),
)
const selectedEmbeddingModel = computed(
  () => embeddingModels.value.find((model) => model.id === embedModelId.value) ?? null,
)
const embedModelPlaceholder = computed(() => {
  if (loadingEmbedding.value) return '加载中…'
  if (embeddingLoadFailed.value) return '加载失败'
  return '暂无可用的嵌入模型'
})

async function loadEmbeddingModels() {
  if (!props.projectId || loadingEmbedding.value) return
  loadingEmbedding.value = true
  embeddingLoadFailed.value = false
  try {
    const models = await modelsApi.listEmbeddingModels(props.projectId)
    embeddingModels.value = models
    // 保持已选项；不可用时回退到第一个可选模型
    if (!models.some((model) => model.id === embedModelId.value)) {
      embedModelId.value = models[0]?.id ?? ''
    }
  } catch {
    embeddingModels.value = []
    embedModelId.value = ''
    embeddingLoadFailed.value = true
  } finally {
    loadingEmbedding.value = false
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) void loadEmbeddingModels()
  },
  { immediate: true },
)

async function onSubmit() {
  if (!name.value.trim() || submitting.value) return
  if (props.projectId && !selectedEmbeddingModel.value) return
  submitting.value = true
  try {
    const embedModel = selectedEmbeddingModel.value?.name ?? ''
    const kb = props.projectId
      ? await projectApi.createProjectKnowledgeBase(
          props.projectId, name.value, description.value, embedModel,
        )
      : await api.createKnowledgeBase(name.value, description.value)
    emit('created', kb)
    name.value = ''
    description.value = ''
    emit('close')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AppModal :open="props.open" title="新建知识库" @close="emit('close')">
    <form class="space-y-4" @submit.prevent="onSubmit">
      <div class="space-y-1.5">
        <label for="kb-name" class="text-xs font-medium text-muted">名称 <span class="text-accent">*</span></label>
        <AppInput id="kb-name" v-model="name" placeholder="例如：产品需求文档库" />
      </div>
      <div class="space-y-1.5">
        <label for="kb-desc" class="text-xs font-medium text-muted">描述</label>
        <AppTextarea
          id="kb-desc"
          v-model="description"
          :rows="3"
          placeholder="简单描述这个知识库的用途（可选）"
        />
      </div>
      <div class="space-y-1.5">
        <label for="kb-embed-model" class="text-xs font-medium text-muted">嵌入模型</label>
        <AppSelect
          id="kb-embed-model"
          v-model="embedModelId"
          :options="embedModelOptions"
          :placeholder="embedModelPlaceholder"
          :disabled="loadingEmbedding || !embedModelOptions.length"
        />
        <p v-if="embeddingLoadFailed" class="text-xs text-muted/80">
          嵌入模型加载失败，请稍后重试。
        </p>
        <p v-else-if="!loadingEmbedding && !embedModelOptions.length" class="text-xs text-muted/80">
          项目内暂无可用的嵌入模型，请先在「模型配置」中为实例添加 embedding 模型。
        </p>
        <p v-else class="text-xs text-muted/80">展示格式：实例名/嵌入模型，用于文档向量化。</p>
      </div>
      <!-- 隐藏提交按钮以支持回车提交 -->
      <button type="submit" class="hidden" />
    </form>

    <template #footer>
      <AppButton variant="ghost" @click="emit('close')">取消</AppButton>
      <AppButton
        variant="primary"
        :loading="submitting"
        :disabled="!name.trim() || (!!props.projectId && !selectedEmbeddingModel)"
        @click="onSubmit"
      >
        创建
      </AppButton>
    </template>
  </AppModal>
</template>
