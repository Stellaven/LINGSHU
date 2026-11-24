<script setup lang="ts">
import { useRoute } from 'vue-router'
import AppBackground from '@/components/AppBackground.vue'
import AppHeader from '@/components/AppHeader.vue'
import AppSidebar from '@/components/AppSidebar.vue'

const route = useRoute()
</script>

<template>
  <div class="relative min-h-screen">
    <AppBackground />
    <!-- 登录页为独立全屏布局，不套用「侧边栏 + 顶栏」的业务布局 -->
    <main v-if="route.meta.hideHeader" class="relative z-10">
      <RouterView />
    </main>
    <template v-else>
      <AppSidebar />
      <div class="relative z-10 flex min-h-screen flex-col md:pl-60">
        <AppHeader />
        <!-- 流式布局：撑满侧边栏以内的全部宽度，仅保留基础边距 -->
        <main class="w-full flex-1 px-4 pb-8 sm:px-6 md:px-8">
          <RouterView />
        </main>
      </div>
    </template>
  </div>
</template>
