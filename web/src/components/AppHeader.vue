<script setup lang="ts">
import UserMenu from '@/components/UserMenu.vue'
</script>

<template>
  <header class="sticky top-0 z-40 border-b border-white/6 bg-base/70 backdrop-blur-xl">
    <!-- 背景细节层：高光发丝线 + 声纹波纹 + 环境光晕 + 噪点颗粒（纯装饰） -->
    <div aria-hidden="true" class="pointer-events-none absolute inset-0 overflow-hidden">
      <!-- 顶部高光发丝线，与底部边框呼应成玻璃厚度感 -->
      <div
        class="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/12 to-transparent"
      />
      <!-- 声纹波纹：多条不同频率的正弦波缓慢漂移，边缘渐隐 -->
      <svg
        class="absolute inset-x-0 bottom-0 h-full w-full opacity-70"
        viewBox="0 0 1440 56"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="hp-wave-fade" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="1440" y2="0">
            <stop offset="0" stop-color="#fff" stop-opacity="0" />
            <stop offset="0.15" stop-color="#fff" stop-opacity="1" />
            <stop offset="0.85" stop-color="#fff" stop-opacity="1" />
            <stop offset="1" stop-color="#fff" stop-opacity="0" />
          </linearGradient>
          <mask id="hp-wave-mask" maskUnits="userSpaceOnUse" x="0" y="0" width="1440" height="56">
            <rect width="1440" height="56" fill="url(#hp-wave-fade)" />
          </mask>
        </defs>
        <g mask="url(#hp-wave-mask)" fill="none" stroke-linecap="round">
          <path
            class="hp-w1"
            d="M0 32 Q90 22 180 32 T360 32 T540 32 T720 32 T900 32 T1080 32 T1260 32 T1440 32 T1620 32 T1800 32"
            stroke="#5E6AD2"
            stroke-opacity="0.5"
            stroke-width="1.25"
            vector-effect="non-scaling-stroke"
          />
          <path
            class="hp-w2"
            d="M0 32 Q45 14 90 32 T180 32 T270 32 T360 32 T450 32 T540 32 T630 32 T720 32 T810 32 T900 32 T990 32 T1080 32 T1170 32 T1260 32 T1350 32 T1440 32 T1530 32 T1620 32"
            stroke="#8B94E8"
            stroke-opacity="0.35"
            stroke-width="1"
            vector-effect="non-scaling-stroke"
          />
          <path
            class="hp-w3"
            d="M0 32 Q30 25 60 32 T120 32 T180 32 T240 32 T300 32 T360 32 T420 32 T480 32 T540 32 T600 32 T660 32 T720 32 T780 32 T840 32 T900 32 T960 32 T1020 32 T1080 32 T1140 32 T1200 32 T1260 32 T1320 32 T1380 32 T1440 32 T1500 32 T1560 32"
            stroke="#5E6AD2"
            stroke-opacity="0.3"
            stroke-width="1"
            vector-effect="non-scaling-stroke"
          />
        </g>
      </svg>
      <!-- 环境光晕：左 accent / 右品红，呼应页面流动光斑 -->
      <div class="absolute -top-20 left-[12%] h-36 w-[480px] rounded-full bg-accent/15 blur-[70px]" />
      <div class="absolute -top-16 right-[8%] h-28 w-[360px] rounded-full bg-fuchsia-500/10 blur-[60px]" />
      <!-- 噪点纹理：防条带、加颗粒质感 -->
      <div class="absolute inset-0 bg-noise opacity-[0.04]" />
    </div>
    <div
      class="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent"
    />
    <!-- 品牌 LOGO 在侧边栏；账号菜单已移至侧边栏左下角（桌面端），
         移动端侧边栏不可见，此处保留顶栏入口（md 以下展示） -->
    <div class="mx-auto flex h-14 w-full max-w-7xl items-center justify-end px-4 sm:px-6 md:px-8">
      <div class="md:hidden">
        <UserMenu />
      </div>
    </div>
  </header>
</template>

<style scoped>
/* 声纹波纹漂移：每条波按自身周期平移一个波长，无缝循环 */
.hp-w1 {
  animation: hp-drift-1 36s linear infinite;
}
.hp-w2 {
  animation: hp-drift-2 24s linear infinite;
}
.hp-w3 {
  animation: hp-drift-3 16s linear infinite;
}
@keyframes hp-drift-1 {
  to {
    transform: translateX(-360px);
  }
}
@keyframes hp-drift-2 {
  to {
    transform: translateX(-180px);
  }
}
@keyframes hp-drift-3 {
  to {
    transform: translateX(-120px);
  }
}
@media (prefers-reduced-motion: reduce) {
  .hp-w1,
  .hp-w2,
  .hp-w3 {
    animation: none;
  }
}
</style>
