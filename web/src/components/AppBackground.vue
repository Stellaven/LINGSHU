<template>
  <!-- 多层环境光背景：径向渐变 + 网格 + 噪点 + 流动光斑（DESIGN.md 背景系统） -->
  <div aria-hidden="true" class="pointer-events-none fixed inset-0 z-0 overflow-hidden">
    <!-- Layer 1: 基础径向渐变 -->
    <div
      class="absolute inset-0 bg-[radial-gradient(ellipse_at_top,#0a0a0f_0%,#050506_50%,#020203_100%)]"
    />
    <!-- Layer 2: 64px 技术网格 -->
    <div class="absolute inset-0 bg-grid opacity-[0.02]" />
    <!-- Layer 3: 流动光斑（动画在 prefers-reduced-motion 下自动关闭） -->
    <div
      class="absolute -top-48 left-1/2 h-[700px] w-[1200px] -translate-x-1/2 rounded-full bg-accent/25 blur-[150px] motion-safe:animate-float"
    />
    <div
      class="absolute -left-56 top-1/3 h-[600px] w-[800px] rounded-full bg-fuchsia-500/10 blur-[120px] motion-safe:animate-float-slower"
    />
    <div
      class="absolute -right-64 top-1/4 h-[500px] w-[700px] rounded-full bg-sky-500/10 blur-[100px] motion-safe:animate-pulse-slow"
    />
    <div
      class="absolute bottom-[-10%] left-1/4 h-[400px] w-[900px] rounded-full bg-accent/10 blur-[130px] motion-safe:animate-float"
    />
    <!-- Layer 4: 噪点纹理 -->
    <div class="absolute inset-0 bg-noise opacity-[0.015]" />
    <!-- 底部压暗 -->
    <div class="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-deep to-transparent" />
  </div>
</template>
