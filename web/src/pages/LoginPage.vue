<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LogoMark from '@/components/LogoMark.vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import { login, register, requestPasswordCode, resetPassword } from '@/stores/auth'

type Mode = 'login' | 'register' | 'forgot'

const route = useRoute()
const router = useRouter()

const mode = ref<Mode>('login')

const account = ref('')
const password = ref('')
const confirm = ref('')
const code = ref('')
const newPassword = ref('')

const submitting = ref(false)
const sending = ref(false)
const error = ref('')
const notice = ref('')
/** mock 模式下验证码无法走邮件/短信通道，由 API 直接回显 */
const sentCode = ref('')

const title = computed(
  () => ({ login: '欢迎回来', register: '创建账号', forgot: '重置密码' })[mode.value],
)
const subtitle = computed(
  () =>
    ({
      login: '',
      register: '注册一个新账号，开始管理你的知识库',
      forgot: '输入账号获取验证码，设置新密码',
    })[mode.value],
)

/** 登录成功后回跳的目标页面（仅接受站内路径） */
const redirect = computed(() => {
  const r = route.query.redirect
  return typeof r === 'string' && r.startsWith('/') ? r : '/'
})

function clearFeedback() {
  error.value = ''
  notice.value = ''
}

function switchMode(m: Mode) {
  mode.value = m
  clearFeedback()
  sentCode.value = ''
  code.value = ''
  newPassword.value = ''
  confirm.value = ''
  password.value = ''
}

function errText(e: unknown, fallback: string): string {
  return e instanceof Error ? e.message : fallback
}

function checkPassword(pw: string): string | null {
  if (pw.length < 6) return '密码长度至少 6 位'
  return null
}

async function onLogin() {
  clearFeedback()
  if (!account.value.trim() || !password.value) {
    error.value = '请输入账号和密码'
    return
  }
  submitting.value = true
  try {
    await login(account.value, password.value)
    router.replace(redirect.value)
  } catch (e) {
    error.value = errText(e, '登录失败，请重试')
  } finally {
    submitting.value = false
  }
}

async function onRegister() {
  clearFeedback()
  if (!account.value.trim()) {
    error.value = '请输入账号'
    return
  }
  const pwErr = checkPassword(password.value)
  if (pwErr) {
    error.value = pwErr
    return
  }
  if (password.value !== confirm.value) {
    error.value = '两次输入的密码不一致'
    return
  }
  submitting.value = true
  try {
    await register(account.value, password.value)
    router.replace(redirect.value)
  } catch (e) {
    error.value = errText(e, '注册失败，请重试')
  } finally {
    submitting.value = false
  }
}

async function onSendCode() {
  clearFeedback()
  if (!account.value.trim()) {
    error.value = '请先输入账号'
    return
  }
  sending.value = true
  try {
    sentCode.value = await requestPasswordCode(account.value)
    notice.value = '验证码已下发（mock 模式直接回显，5 分钟内有效）'
  } catch (e) {
    error.value = errText(e, '验证码下发失败，请重试')
  } finally {
    sending.value = false
  }
}

async function onReset() {
  clearFeedback()
  if (!account.value.trim() || !code.value.trim()) {
    error.value = '请输入账号和验证码'
    return
  }
  const pwErr = checkPassword(newPassword.value)
  if (pwErr) {
    error.value = pwErr
    return
  }
  if (newPassword.value !== confirm.value) {
    error.value = '两次输入的密码不一致'
    return
  }
  submitting.value = true
  try {
    await resetPassword(account.value, code.value, newPassword.value)
    switchMode('login')
    notice.value = '密码已重置，请使用新密码登录'
  } catch (e) {
    error.value = errText(e, '密码重置失败，请重试')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center px-4 py-10 sm:py-12">
    <div class="w-full max-w-sm animate-fade-up">
      <!-- 品牌区：图标 + 灵书 -->
      <div class="mb-8 flex flex-col items-center gap-5 text-center">
        <div class="flex items-center gap-2.5">
          <LogoMark class="size-11 rounded-xl shadow-[0_8px_24px_rgba(94,106,210,0.35)]" />
          <span class="text-gradient text-2xl font-semibold tracking-tight">灵书</span>
        </div>
        <div class="space-y-1">
          <h1 class="text-lg font-semibold tracking-tight">{{ title }}</h1>
          <p v-if="subtitle" class="text-sm text-muted">{{ subtitle }}</p>
        </div>
      </div>

      <!-- 表单卡片 -->
      <div class="card-surface spotlight p-5 sm:p-6">
        <!-- 错误提示 -->
        <p
          v-if="error"
          class="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300"
        >
          {{ error }}
        </p>
        <!-- 成功 / 提示信息 -->
        <p
          v-else-if="notice"
          class="mb-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-300"
        >
          {{ notice }}
        </p>

        <!-- ---------- 登录 ---------- -->
        <form v-if="mode === 'login'" class="space-y-4" @submit.prevent="onLogin">
          <div class="space-y-1.5">
            <label for="login-account" class="text-xs font-medium text-muted">账号</label>
            <AppInput id="login-account" v-model="account" placeholder="请输入账号" autocomplete="username" />
          </div>
          <div class="space-y-1.5">
            <div class="flex items-center justify-between">
              <label for="login-password" class="text-xs font-medium text-muted">密码</label>
              <button
                type="button"
                class="text-xs text-muted transition-colors hover:text-accent"
                @click="switchMode('forgot')"
              >
                忘记密码？
              </button>
            </div>
            <AppInput id="login-password" v-model="password" type="password" placeholder="请输入密码" autocomplete="current-password" />
          </div>
          <AppButton variant="primary" type="submit" class="w-full" :loading="submitting">登录</AppButton>
          <p class="text-center text-xs text-muted">
            没有账号？
            <button type="button" class="text-accent transition-colors hover:text-accent-bright" @click="switchMode('register')">
              立即注册
            </button>
          </p>
        </form>

        <!-- ---------- 注册 ---------- -->
        <form v-else-if="mode === 'register'" class="space-y-4" @submit.prevent="onRegister">
          <div class="space-y-1.5">
            <label for="reg-account" class="text-xs font-medium text-muted">账号</label>
            <AppInput id="reg-account" v-model="account" placeholder="设置你的账号" autocomplete="username" />
          </div>
          <div class="space-y-1.5">
            <label for="reg-password" class="text-xs font-medium text-muted">密码 <span class="text-muted/60">（至少 6 位）</span></label>
            <AppInput id="reg-password" v-model="password" type="password" placeholder="请输入密码" autocomplete="new-password" />
          </div>
          <div class="space-y-1.5">
            <label for="reg-confirm" class="text-xs font-medium text-muted">确认密码</label>
            <AppInput id="reg-confirm" v-model="confirm" type="password" placeholder="请再次输入密码" autocomplete="new-password" />
          </div>
          <AppButton variant="primary" type="submit" class="w-full" :loading="submitting">注册</AppButton>
          <p class="text-center text-xs text-muted">
            已有账号？
            <button type="button" class="text-accent transition-colors hover:text-accent-bright" @click="switchMode('login')">
              返回登录
            </button>
          </p>
        </form>

        <!-- ---------- 忘记密码 ---------- -->
        <form v-else class="space-y-4" @submit.prevent="onReset">
          <div class="space-y-1.5">
            <label for="fp-account" class="text-xs font-medium text-muted">账号</label>
            <AppInput id="fp-account" v-model="account" placeholder="请输入注册时的账号" />
          </div>
          <div class="space-y-1.5">
            <label for="fp-code" class="text-xs font-medium text-muted">验证码</label>
            <div class="flex items-center gap-2">
              <AppInput id="fp-code" v-model="code" placeholder="6 位验证码" class="flex-1" />
              <AppButton :loading="sending" @click="onSendCode">获取验证码</AppButton>
            </div>
            <p v-if="sentCode" class="font-mono text-xs text-muted">
              Mock 验证码：<span class="text-accent">{{ sentCode }}</span>
            </p>
          </div>
          <div class="space-y-1.5">
            <label for="fp-new-password" class="text-xs font-medium text-muted">新密码 <span class="text-muted/60">（至少 6 位）</span></label>
            <AppInput id="fp-new-password" v-model="newPassword" type="password" placeholder="请输入新密码" autocomplete="new-password" />
          </div>
          <div class="space-y-1.5">
            <label for="fp-confirm" class="text-xs font-medium text-muted">确认新密码</label>
            <AppInput id="fp-confirm" v-model="confirm" type="password" placeholder="请再次输入新密码" autocomplete="new-password" />
          </div>
          <AppButton variant="primary" type="submit" class="w-full" :loading="submitting">重置密码</AppButton>
          <p class="text-center text-xs text-muted">
            <button type="button" class="text-accent transition-colors hover:text-accent-bright" @click="switchMode('login')">
              返回登录
            </button>
          </p>
        </form>
      </div>
    </div>
  </div>
</template>
