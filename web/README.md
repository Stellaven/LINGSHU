# 灵枢 Web 前端

灵枢（LingShu）知识库平台的 Web 前端，Vue 3 + TypeScript + Vite + Tailwind CSS 4。

## 页面

- 登录 / 注册（密码经 RSA 公钥加密传输）
- 团队 / 项目 / 知识库管理
- 文档上传与处理状态
- 文件分块（Chunks）查看
- 模型提供商配置

## 开发

```bash
npm install
npm run dev        # http://localhost:5173
```

开发模式下 Vite 将 `/api` 前缀代理到本地后端 `http://localhost:8000`（见 `vite.config.ts`），需先启动后端（见根目录 README）。

## 构建

```bash
npm run build      # 类型检查（vue-tsc） + 打包到 dist/
npm run preview    # 本地预览构建产物
```

## 目录结构

```
web/
├── src/
│   ├── api/          # 后端接口封装
│   ├── components/   # 通用组件
│   ├── pages/        # 页面（登录、首页、知识库详情、分块、团队、项目）
│   ├── router/       # 路由
│   ├── stores/       # 状态管理
│   ├── directives/   # 自定义指令
│   ├── styles/       # 全局样式
│   ├── types/        # 类型定义
│   └── utils/        # 工具函数（含 RSA 加密）
└── public/           # 静态资源（favicon、模型提供商 Logo）
```

## 技术栈

| 依赖 | 说明 |
|---|---|
| Vue 3.5 + vue-router 4 | 组合式 API，路由懒加载 |
| Tailwind CSS 4 | 通过 `@tailwindcss/vite` 插件集成 |
| jsencrypt | RSA 密码加密传输 |
| lucide（@lucide/vue） | 图标 |
| Vite 7 + vue-tsc + TypeScript | 构建与类型检查 |
