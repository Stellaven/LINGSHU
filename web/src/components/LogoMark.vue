<template>
  <!-- 品牌图标：发光的书本 + 灵动星光（主星 + 绿色伴星 + 白色小闪），128×128 画布 -->
  <svg viewBox="0 0 128 128" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <defs>
      <linearGradient id="logo-bg" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#2A2650" />
        <stop offset="1" stop-color="#141226" />
      </linearGradient>
      <linearGradient id="logo-cover" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#8C76F8" />
        <stop offset="1" stop-color="#43339B" />
      </linearGradient>
      <linearGradient id="logo-page" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#FFFFFF" />
        <stop offset="1" stop-color="#CFCBF6" />
      </linearGradient>
      <linearGradient id="logo-star" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#FFFFFF" />
        <stop offset="1" stop-color="#DCD6FF" />
      </linearGradient>
      <filter id="logo-glow" x="-60%" y="-60%" width="220%" height="220%">
        <feGaussianBlur stdDeviation="3.3" result="b" />
        <feMerge>
          <feMergeNode in="b" />
          <feMergeNode in="SourceGraphic" />
        </feMerge>
      </filter>
    </defs>
    <rect width="128" height="128" rx="32" fill="url(#logo-bg)" />
    <rect
      x="1.33"
      y="1.33"
      width="125.33"
      height="125.33"
      rx="30.67"
      fill="none"
      stroke="rgba(255,255,255,.14)"
      stroke-width="2"
    />
    <!-- 书本：紫色封面 + 浅色内页 -->
    <path
      d="M64 105.33C53.33 95.33 34.67 89.33 18.67 92L18.67 54.67C34.67 50.67 53.33 57.33 64 69.33C74.67 57.33 93.33 50.67 109.33 54.67L109.33 92C93.33 89.33 74.67 95.33 64 105.33Z"
      fill="url(#logo-cover)"
    />
    <path
      d="M64 97.33C56 88.67 40 82.67 26 84.67L26 61.33C40 58.67 56 64.67 64 74.67C72 64.67 88 58.67 102 61.33L102 84.67C88 82.67 72 88.67 64 97.33Z"
      fill="url(#logo-page)"
    />
    <path d="M64 74.67L64 97.33" stroke="#6B5BC4" stroke-opacity=".55" stroke-width="2" />
    <!-- 星光 -->
    <g filter="url(#logo-glow)">
      <path
        d="M64 12c3.33 13.33 8.8 18.93 21.33 22C73.6 37.2 67.87 43.07 64 57.33c-3.87-14-9.6-19.87-21.33-23.33C55.47 30.93 60.67 25.2 64 12Z"
        fill="url(#logo-star)"
      />
      <path
        d="M22.67 32c1.33 5.47 3.6 7.73 8.8 8.8-5.2 1.33-7.47 3.6-8.8 8.8-1.33-5.2-3.6-7.47-8.8-8.8 5.2-1.07 7.47-3.33 8.8-8.8Z"
        fill="#6EE7B7"
      />
      <path
        d="M101.33 16.67c.8 3.47 2.27 4.93 5.6 5.6-3.33.8-4.8 2.27-5.6 5.6-.8-3.33-2.27-4.8-5.6-5.6 3.33-.67 4.8-2.13 5.6-5.6Z"
        fill="url(#logo-star)"
        opacity=".9"
      />
      <circle cx="14.67" cy="60" r="2.13" fill="url(#logo-star)" opacity=".6" />
    </g>
  </svg>
</template>
