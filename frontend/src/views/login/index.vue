<template>
  <div
    v-if="showLoading"
    v-loading="true"
    :element-loading-text="t('qa.loading')"
    class="loading-mask"
    element-loading-background="rgba(250, 251, 255, 0.95)"
  ></div>

  <div class="login-page" :class="{ 'hide-page': showLoading }">
    <!-- 动态背景层 -->
    <div class="bg-layer">
      <div class="bg-gradient"></div>
      <div class="bg-orb orb-1"></div>
      <div class="bg-orb orb-2"></div>
      <div class="bg-orb orb-3"></div>
      <div class="bg-grid"></div>
      <div class="bg-particles">
        <div v-for="i in 20" :key="i" class="particle" :style="getParticleStyle()"></div>
      </div>
    </div>

    <!-- 主容器 -->
    <div class="main-container">
      <!-- 左侧：品牌展示区 -->
      <div class="brand-side">
        <div class="brand-content">
          <!-- Logo 区域 - 确保始终可见 -->
          <div class="logo-section">
            <div class="logo-wrapper">
              <div class="logo-container">
                <img src="@/assets/chatbi-logo-new.svg?url" alt="ChatBI Logo" class="logo-img" />
              </div>
              <h1 class="brand-name">ChatBI</h1>
            </div>
          </div>

          <!-- 论文主题展示 -->
          <div class="thesis-section">
            <p class="thesis-desc">{{ t('login.hero_subtitle') }}</p>
          </div>

          <!-- 核心功能卡片 -->
          <div class="features-grid">
            <div v-for="(feature, index) in features" :key="index" class="feature-card">
              <div class="feature-icon" :class="`icon-${feature.color}`">
                <component :is="feature.icon" />
              </div>
              <div class="feature-content">
                <h3 class="feature-title">{{ t(feature.title) }}</h3>
                <p class="feature-desc">{{ t(feature.desc) }}</p>
              </div>
            </div>
          </div>

          <!-- 技术栈展示 -->
          <div class="tech-stack">
            <span class="tech-label">{{ t('login.tech_stack') }}</span>
            <div class="tech-tags">
              <span v-for="tech in techStack" :key="tech" class="tech-tag">{{ tech }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：表单区域 -->
      <div class="form-side">
        <!-- 表单容器 - 靠右对齐 -->
        <div class="form-container">
          <!-- 语言切换器 - 表单右上角 -->
          <div class="language-switcher">
            <el-dropdown trigger="click" @command="changeLang" popper-class="login-lang-dropdown">
              <button class="lang-button" type="button">
                <span class="lang-flag">{{ currentLangFlag }}</span>
                <span class="lang-text">{{ langLabel }}</span>
                <svg class="lang-arrow" viewBox="0 0 20 20" width="14" height="14" fill="currentColor">
                  <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" />
                </svg>
              </button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item
                    v-for="lang in languages"
                    :key="lang.value"
                    :command="lang.value"
                    :class="{ 'is-active': locale === lang.value }"
                  >
                    <span class="dropdown-flag">{{ lang.flag }}</span>
                    <span class="dropdown-name">{{ lang.name }}</span>
                    <span v-if="locale === lang.value" class="dropdown-check">✓</span>
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
          <!-- 移动端 Logo -->
          <div class="mobile-logo-section">
            <div class="mobile-logo-wrapper">
              <img src="@/assets/chatbi-logo-new.svg?url" alt="ChatBI Logo" class="mobile-logo-img" />
              <span class="mobile-brand-name">ChatBI</span>
            </div>
          </div>

          <!-- 表单卡片 -->
          <div class="form-card">
            <!-- 表单头部 -->
            <div class="form-header">
              <h2 class="form-title">
                {{ isRegister ? t('login.register_title') : t('login.welcome_back') }}
              </h2>
              <p class="form-subtitle">
                {{ isRegister ? t('login.register_subtitle') : t('login.login_subtitle') }}
              </p>
            </div>

            <!-- 登录表单 -->
            <el-form
              v-if="!isRegister"
              ref="loginFormRef"
              :model="loginForm"
              :rules="loginRules"
              class="auth-form"
              @submit.prevent="handleLogin"
            >
              <el-form-item prop="username">
                <el-input
                  v-model="loginForm.username"
                  :placeholder="t('login.username_placeholder')"
                  size="large"
                  :prefix-icon="User"
                  clearable
                />
              </el-form-item>
              <el-form-item prop="password">
                <el-input
                  v-model="loginForm.password"
                  type="password"
                  :placeholder="t('login.password_placeholder')"
                  size="large"
                  :prefix-icon="Lock"
                  show-password
                  @keyup.enter="handleLogin"
                />
              </el-form-item>
              <el-form-item>
                <el-button
                  type="primary"
                  size="large"
                  class="submit-button"
                  :loading="loading"
                  @click="handleLogin"
                >
                  {{ t('login.login_btn') }}
                </el-button>
              </el-form-item>
            </el-form>

            <!-- 注册表单 -->
            <el-form
              v-else
              ref="registerFormRef"
              :model="registerForm"
              :rules="registerRules"
              class="auth-form"
              @submit.prevent="handleRegister"
            >
              <el-form-item prop="username">
                <el-input
                  v-model="registerForm.username"
                  :placeholder="t('login.reg_username_placeholder')"
                  size="large"
                  :prefix-icon="User"
                  maxlength="50"
                />
              </el-form-item>
              <el-form-item prop="name">
                <el-input
                  v-model="registerForm.name"
                  :placeholder="t('login.reg_name_placeholder')"
                  size="large"
                  :prefix-icon="UserFilled"
                  maxlength="50"
                />
              </el-form-item>
              <el-form-item prop="email">
                <el-input
                  v-model="registerForm.email"
                  :placeholder="t('login.reg_email_placeholder')"
                  size="large"
                  :prefix-icon="Message"
                  maxlength="100"
                />
              </el-form-item>
              <el-form-item prop="password">
                <el-input
                  v-model="registerForm.password"
                  type="password"
                  :placeholder="t('login.reg_password_placeholder')"
                  size="large"
                  :prefix-icon="Lock"
                  show-password
                  maxlength="20"
                />
                <div class="password-hint">{{ t('login.reg_password_format') }}</div>
              </el-form-item>
              <el-form-item prop="confirmPassword">
                <el-input
                  v-model="registerForm.confirmPassword"
                  type="password"
                  :placeholder="t('login.reg_confirm_placeholder')"
                  size="large"
                  :prefix-icon="Lock"
                  show-password
                  maxlength="20"
                  @keyup.enter="handleRegister"
                />
              </el-form-item>
              <el-form-item>
                <el-button
                  type="primary"
                  size="large"
                  class="submit-button"
                  :loading="loading"
                  @click="handleRegister"
                >
                  {{ t('login.register_btn') }}
                </el-button>
              </el-form-item>
            </el-form>

            <!-- 切换登录/注册 -->
            <div class="form-switch">
              <span>{{ isRegister ? t('login.has_account') : t('login.no_account') }}</span>
              <a href="javascript:;" @click="toggleMode">
                {{ isRegister ? t('login.go_login') : t('login.go_register') }}
              </a>
            </div>

            <!-- 安全提示 -->
            <div class="security-badge">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
              <span>{{ t('login.security_note') }}</span>
            </div>
          </div>

          <!-- 版权信息 -->
          <div class="copyright">
            © Felix Alvin Juandra（蔡威广）
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, h } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { type FormInstance, type FormRules, ElMessage } from 'element-plus-secondary'
import { User, Lock, Message, UserFilled } from '@element-plus/icons-vue'
import { AuthApi } from '@/api/login'
import { useUserStore } from '@/stores/user'

const { t, locale } = useI18n()
const router = useRouter()
const userStore = useUserStore()

// 状态
const showLoading = ref(false)
const loading = ref(false)
const isRegister = ref(false)
const loginFormRef = ref<FormInstance>()
const registerFormRef = ref<FormInstance>()

// 登录表单
const loginForm = ref({
  username: '',
  password: '',
})

// 注册表单
const registerForm = ref({
  username: '',
  name: '',
  email: '',
  password: '',
  confirmPassword: '',
})

// 登录验证规则
const loginRules = computed<FormRules>(() => ({
  username: [{ required: true, message: t('login.username_required'), trigger: 'blur' }],
  password: [{ required: true, message: t('login.password_required'), trigger: 'blur' }],
}))

// 注册验证规则
const registerRules = computed<FormRules>(() => ({
  username: [
    { required: true, message: t('login.reg_username_required'), trigger: 'blur' },
    { min: 2, max: 50, message: t('login.reg_username_length'), trigger: 'blur' },
  ],
  name: [{ required: true, message: t('login.reg_name_required'), trigger: 'blur' }],
  email: [
    { required: true, message: t('login.reg_email_required'), trigger: 'blur' },
    { type: 'email', message: t('login.reg_email_invalid'), trigger: 'blur' },
  ],
  password: [
    { required: true, message: t('login.reg_password_required'), trigger: 'blur' },
    {
      pattern: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*(),.?":{}|<>]).{8,20}$/,
      message: t('login.reg_password_format'),
      trigger: 'blur',
    },
  ],
  confirmPassword: [
    { required: true, message: t('login.reg_confirm_required'), trigger: 'blur' },
    {
      validator: (_rule: any, value: string, callback: Function) => {
        if (value !== registerForm.value.password) {
          callback(new Error(t('login.reg_password_mismatch')))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}))

// 功能特性图标
const features = [
  {
    icon: h(
      'svg',
      {
        viewBox: '0 0 24 24',
        width: 20,
        height: 20,
        fill: 'none',
        stroke: 'currentColor',
        'stroke-width': 2,
      },
      [h('path', { d: 'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z' })]
    ),
    title: 'login.feature_chat',
    desc: 'login.feature_chat_desc',
    color: 'purple',
  },
  {
    icon: h(
      'svg',
      {
        viewBox: '0 0 24 24',
        width: 20,
        height: 20,
        fill: 'none',
        stroke: 'currentColor',
        'stroke-width': 2,
      },
      [
        h('ellipse', { cx: 12, cy: 5, rx: 9, ry: 3 }),
        h('path', { d: 'M21 12c0 1.66-4 3-9 3s-9-1.34-9-3' }),
        h('path', { d: 'M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5' }),
      ]
    ),
    title: 'login.feature_data',
    desc: 'login.feature_data_desc',
    color: 'blue',
  },
  {
    icon: h(
      'svg',
      {
        viewBox: '0 0 24 24',
        width: 20,
        height: 20,
        fill: 'none',
        stroke: 'currentColor',
        'stroke-width': 2,
      },
      [
        h('circle', { cx: 11, cy: 11, r: 8 }),
        h('path', { d: 'M21 21l-4.35-4.35' }),
        h('path', { d: 'M11 8v6M8 11h6' }),
      ]
    ),
    title: 'login.feature_rag',
    desc: 'login.feature_rag_desc',
    color: 'green',
  },
  {
    icon: h(
      'svg',
      {
        viewBox: '0 0 24 24',
        width: 20,
        height: 20,
        fill: 'none',
        stroke: 'currentColor',
        'stroke-width': 2,
      },
      [h('rect', { x: 3, y: 3, width: 18, height: 18, rx: 2 }), h('path', { d: 'M3 9h18M9 21V9' })]
    ),
    title: 'login.feature_chart',
    desc: 'login.feature_chart_desc',
    color: 'orange',
  },
]

// 技术栈
const techStack = ['Vue 3', 'FastAPI', 'PostgreSQL', 'LangChain', 'LLM']

// 语言选项
const languages = [
  { name: '简体中文', value: 'zh-CN', flag: '🇨🇳' },
  { name: 'English', value: 'en', flag: '🇺🇸' },
]

const langLabel = computed(() => {
  const current = languages.find((l) => l.value === locale.value)
  return current?.name || 'English'
})

const currentLangFlag = computed(() => {
  const current = languages.find((l) => l.value === locale.value)
  return current?.flag || '🌐'
})

// 粒子动画样式
const getParticleStyle = () => {
  const size = Math.random() * 4 + 2
  const duration = Math.random() * 20 + 10
  const delay = Math.random() * 5
  const x = Math.random() * 100
  const y = Math.random() * 100
  
  return {
    width: `${size}px`,
    height: `${size}px`,
    left: `${x}%`,
    top: `${y}%`,
    animationDuration: `${duration}s`,
    animationDelay: `${delay}s`,
  }
}

// 切换语言
const changeLang = (lang: string) => {
  locale.value = lang
  localStorage.setItem('language', lang)
}

// 切换登录/注册模式
const toggleMode = () => {
  isRegister.value = !isRegister.value
  if (isRegister.value) {
    loginFormRef.value?.resetFields()
  } else {
    registerFormRef.value?.resetFields()
  }
}

// 登录处理
const handleLogin = async () => {
  if (!loginFormRef.value) return
  await loginFormRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      await userStore.login({
        username: loginForm.value.username,
        password: loginForm.value.password,
      })
      await userStore.info()
      router.push('/chat/index')
    } catch (e: any) {
      ElMessage.error(e.message || t('login.login_failed'))
    } finally {
      loading.value = false
    }
  })
}

// 注册处理
const handleRegister = async () => {
  if (!registerFormRef.value) return
  await registerFormRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      await AuthApi.register({
        username: registerForm.value.username,
        password: registerForm.value.password,
        email: registerForm.value.email,
        name: registerForm.value.name,
      })
      ElMessage.success(t('login.register_success'))
      isRegister.value = false
      loginForm.value.username = registerForm.value.username
      loginForm.value.password = ''
      registerFormRef.value?.resetFields()
    } catch (e: any) {
      // 不显示任何消息，让request拦截器统一处理
    } finally {
      loading.value = false
    }
  })
}

onMounted(() => {
  // 添加登录页面专用class到body，用于覆盖全局深色主题样式
  document.body.classList.add('login-page-active')
  
  const token = userStore.getToken
  if (token) {
    showLoading.value = true
    userStore
      .info()
      .then(() => {
        router.push('/chat/index')
      })
      .catch(() => {
        showLoading.value = false
        userStore.clear()
      })
  }
  const savedLang = localStorage.getItem('language')
  if (savedLang) {
    locale.value = savedLang
  }
})

onUnmounted(() => {
  // 离开登录页面时移除class
  document.body.classList.remove('login-page-active')
})
</script>

<style scoped lang="less">
/* ==================== 基础样式 ==================== */
.loading-mask {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
}

.login-page {
  min-height: 100vh;
  display: flex;
  position: relative;
  overflow: hidden;
  background: linear-gradient(135deg, #fafbff 0%, #f5f3ff 50%, #faf5ff 100%);
  transition: opacity 0.3s ease;

  &.hide-page {
    opacity: 0;
  }
}

/* ==================== 动态背景层 ==================== */
.bg-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
  z-index: 0;
}

.bg-gradient {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse at 30% 20%, rgba(124, 58, 237, 0.1) 0%, transparent 50%),
    radial-gradient(ellipse at 70% 80%, rgba(168, 85, 247, 0.08) 0%, transparent 50%);
  animation: gradientShift 15s ease-in-out infinite;
}

@keyframes gradientShift {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.8; }
}

.bg-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.4;
  animation: float 25s ease-in-out infinite;

  &.orb-1 {
    width: 500px;
    height: 500px;
    background: linear-gradient(135deg, rgba(124, 58, 237, 0.2), rgba(168, 85, 247, 0.15));
    top: -150px;
    left: -150px;
  }

  &.orb-2 {
    width: 400px;
    height: 400px;
    background: linear-gradient(135deg, rgba(168, 85, 247, 0.15), rgba(192, 132, 252, 0.1));
    bottom: -100px;
    right: -100px;
    animation-delay: -8s;
  }

  &.orb-3 {
    width: 300px;
    height: 300px;
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.12), rgba(167, 139, 250, 0.08));
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    animation-delay: -16s;
  }
}

@keyframes float {
  0%, 100% {
    transform: translate(0, 0) scale(1);
  }
  33% {
    transform: translate(40px, -40px) scale(1.08);
  }
  66% {
    transform: translate(-30px, 30px) scale(0.92);
  }
}

.bg-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(124, 58, 237, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(124, 58, 237, 0.04) 1px, transparent 1px);
  background-size: 60px 60px;
  animation: gridMove 20s linear infinite;
}

@keyframes gridMove {
  0% { background-position: 0 0; }
  100% { background-position: 60px 60px; }
}

.bg-particles {
  position: absolute;
  inset: 0;
  
  .particle {
    position: absolute;
    background: radial-gradient(circle, rgba(124, 58, 237, 0.6), transparent);
    border-radius: 50%;
    animation: particleFloat linear infinite;
  }
}

@keyframes particleFloat {
  0% {
    transform: translateY(0) translateX(0);
    opacity: 0;
  }
  10% {
    opacity: 0.6;
  }
  90% {
    opacity: 0.6;
  }
  100% {
    transform: translateY(-100vh) translateX(50px);
    opacity: 0;
  }
}

/* ==================== 主容器 ==================== */
.main-container {
  display: flex;
  width: 100%;
  min-height: 100vh;
  position: relative;
  z-index: 1;

  @media (max-width: 768px) {
    flex-direction: column;
  }
}

/* ==================== 左侧品牌展示区 ==================== */
.brand-side {
  flex: 0 0 58%;
  max-width: 800px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 60px;
  background: linear-gradient(135deg, rgba(124, 58, 237, 0.04) 0%, rgba(168, 85, 247, 0.02) 100%);
  backdrop-filter: blur(10px);
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);

  @media (max-width: 1400px) {
    flex: 0 0 55%;
    padding: 48px 50px;
  }

  @media (max-width: 1200px) {
    flex: 0 0 52%;
    padding: 40px 40px;
  }

  @media (max-width: 1000px) {
    flex: 0 0 48%;
    padding: 40px 32px;
  }

  @media (max-width: 768px) {
    display: none;
  }
}

.brand-content {
  max-width: 560px;
  width: 100%;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);

  @media (max-width: 1200px) {
    max-width: 100%;
  }
}

/* Logo 区域 - 确保始终可见 */
.logo-section {
  margin-bottom: 40px;
  animation: fadeInUp 0.6s ease-out;

  @media (max-width: 1200px) {
    margin-bottom: 32px;
  }
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.logo-wrapper {
  display: inline-flex;
  align-items: center;
  gap: 18px;
  padding: 18px 28px;
  background: white;
  border-radius: 20px;
  box-shadow: 
    0 8px 32px rgba(124, 58, 237, 0.12),
    0 2px 8px rgba(0, 0, 0, 0.04);
  border: 1.5px solid rgba(124, 58, 237, 0.1);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

  &:hover {
    box-shadow: 
      0 12px 40px rgba(124, 58, 237, 0.16),
      0 4px 12px rgba(0, 0, 0, 0.06);
    transform: translateY(-3px);
    border-color: rgba(124, 58, 237, 0.2);
  }

  @media (max-width: 1200px) {
    padding: 16px 24px;
    gap: 16px;
  }

  @media (max-width: 900px) {
    padding: 14px 20px;
    gap: 14px;
  }
}

.logo-container {
  width: 56px;
  height: 56px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(124, 58, 237, 0.08), rgba(168, 85, 247, 0.06));
  border-radius: 14px;
  padding: 6px;
  transition: all 0.3s ease;

  &:hover {
    background: linear-gradient(135deg, rgba(124, 58, 237, 0.12), rgba(168, 85, 247, 0.08));
    transform: rotate(5deg) scale(1.05);
  }

  @media (max-width: 1200px) {
    width: 52px;
    height: 52px;
  }

  @media (max-width: 900px) {
    width: 48px;
    height: 48px;
  }
}

.logo-img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: contain;
  /* Ensure SVG renders properly */
  max-width: 100%;
  max-height: 100%;
}

.brand-name {
  font-size: 32px;
  font-weight: 800;
  background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: -0.8px;
  white-space: nowrap;
  transition: all 0.3s ease;

  @media (max-width: 1200px) {
    font-size: 30px;
  }

  @media (max-width: 900px) {
    font-size: 28px;
  }
}

/* 论文主题展示 */
.thesis-section {
  margin-bottom: 40px;
  animation: fadeInUp 0.6s ease-out 0.2s both;

  @media (max-width: 1200px) {
    margin-bottom: 32px;
  }

  @media (max-width: 900px) {
    margin-bottom: 28px;
  }
}

.thesis-desc {
  font-size: 15px;
  color: #6b7280;
  line-height: 1.7;
  transition: font-size 0.3s ease;

  @media (max-width: 1200px) {
    font-size: 14px;
  }

  @media (max-width: 900px) {
    font-size: 13px;
    line-height: 1.6;
  }
}

/* 核心功能卡片 */
.features-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 36px;
  animation: fadeInUp 0.6s ease-out 0.4s both;
  transition: all 0.3s ease;

  @media (max-width: 1200px) {
    gap: 14px;
    margin-bottom: 32px;
  }

  @media (max-width: 900px) {
    gap: 12px;
    margin-bottom: 28px;
  }

  @media (max-width: 850px) {
    grid-template-columns: 1fr;
    gap: 10px;
  }
}

.feature-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px;
  background: rgba(255, 255, 255, 0.75);
  backdrop-filter: blur(10px);
  border-radius: 14px;
  border: 1.5px solid rgba(124, 58, 237, 0.1);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  min-width: 0;
  cursor: pointer;

  @media (max-width: 1200px) {
    padding: 12px;
    gap: 10px;
  }

  @media (max-width: 900px) {
    padding: 11px;
    gap: 9px;
  }

  @media (max-width: 850px) {
    padding: 13px;
    gap: 11px;
  }

  &:hover {
    background: rgba(255, 255, 255, 0.95);
    border-color: rgba(124, 58, 237, 0.2);
    transform: translateY(-3px);
    box-shadow: 
      0 8px 24px rgba(124, 58, 237, 0.12),
      0 2px 8px rgba(0, 0, 0, 0.04);
  }

  &:active {
    transform: translateY(-1px);
  }
}

.feature-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.3s ease;

  @media (max-width: 1200px) {
    width: 32px;
    height: 32px;
  }

  @media (max-width: 900px) {
    width: 30px;
    height: 30px;
  }

  :deep(svg) {
    width: 18px;
    height: 18px;
    display: block;

    @media (max-width: 1200px) {
      width: 16px;
      height: 16px;
    }

    @media (max-width: 900px) {
      width: 15px;
      height: 15px;
    }
  }

  &.icon-purple {
    background: linear-gradient(135deg, #ede9fe, #ddd6fe);
    color: #7c3aed;
    
    :deep(svg) {
      stroke: #7c3aed;
    }
  }
  &.icon-blue {
    background: linear-gradient(135deg, #dbeafe, #bfdbfe);
    color: #2563eb;
    
    :deep(svg) {
      stroke: #2563eb;
    }
  }
  &.icon-green {
    background: linear-gradient(135deg, #d1fae5, #a7f3d0);
    color: #059669;
    
    :deep(svg) {
      stroke: #059669;
    }
  }
  &.icon-orange {
    background: linear-gradient(135deg, #ffedd5, #fed7aa);
    color: #ea580c;
    
    :deep(svg) {
      stroke: #ea580c;
    }
  }
}

.feature-content {
  flex: 1;
  min-width: 0;
}

.feature-title {
  font-size: 14px;
  font-weight: 700;
  color: #1e1b4b;
  margin-bottom: 4px;
  line-height: 1.3;
  word-wrap: break-word;
  overflow-wrap: break-word;
  transition: font-size 0.3s ease;

  @media (max-width: 1200px) {
    font-size: 13px;
  }

  @media (max-width: 900px) {
    font-size: 12px;
  }
}

.feature-desc {
  font-size: 12px;
  color: #6b7280;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: font-size 0.3s ease;

  @media (max-width: 1200px) {
    font-size: 11px;
  }

  @media (max-width: 900px) {
    font-size: 10px;
  }
}

/* 技术栈展示 */
.tech-stack {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  animation: fadeInUp 0.6s ease-out 0.6s both;

  @media (max-width: 1200px) {
    gap: 12px;
  }

  @media (max-width: 900px) {
    gap: 10px;
  }
}

.tech-label {
  font-size: 13px;
  color: #6b7280;
  font-weight: 600;
  white-space: nowrap;
  transition: font-size 0.3s ease;

  @media (max-width: 1200px) {
    font-size: 12px;
  }

  @media (max-width: 900px) {
    font-size: 11px;
  }
}

.tech-tags {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;

  @media (max-width: 1200px) {
    gap: 8px;
  }

  @media (max-width: 900px) {
    gap: 7px;
  }
}

.tech-tag {
  padding: 6px 12px;
  background: rgba(124, 58, 237, 0.1);
  color: #7c3aed;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  transition: all 0.3s ease;

  @media (max-width: 1200px) {
    padding: 5px 10px;
    font-size: 11px;
  }

  @media (max-width: 900px) {
    padding: 4px 9px;
    font-size: 10px;
  }

  &:hover {
    background: rgba(124, 58, 237, 0.15);
    transform: translateY(-2px);
  }
}

.f-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.f-title {
  font-size: 13px;
  font-weight: 600;
  color: #1e1b4b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;

  @media (max-width: 1200px) {
    font-size: 12px;
  }
}

.f-desc {
  font-size: 11px;
  color: #6b7280;
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;

  @media (max-width: 1200px) {
    font-size: 10px;
  }
}

/* 技术栈 */
.tech-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;

  @media (max-width: 1200px) {
    gap: 8px;
  }
}

.tech-label {
  font-size: 13px;
  color: #6b7280;
  font-weight: 500;
  white-space: nowrap;

  @media (max-width: 1200px) {
    font-size: 12px;
  }
}

.tech-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;

  @media (max-width: 1200px) {
    gap: 6px;
  }
}

.tech-item {
  padding: 4px 10px;
  background: rgba(124, 58, 237, 0.08);
  color: #7c3aed;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;

  @media (max-width: 1200px) {
    padding: 3px 8px;
    font-size: 11px;
  }
}

/* 右侧表单区 */
.form-side {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 50px;
  background: rgba(255, 255, 255, 0.5);
  backdrop-filter: blur(10px);
  border-left: 1px solid rgba(124, 58, 237, 0.08);
  position: relative;
  min-height: 100vh;
  transition: all 0.3s ease;

  @media (max-width: 1400px) {
    padding: 40px 45px;
  }

  @media (max-width: 1200px) {
    padding: 40px 40px;
  }

  @media (max-width: 1000px) {
    padding: 40px 35px;
  }

  @media (max-width: 768px) {
    width: 100%;
    border-left: none;
    padding: 40px 32px;
    background: rgba(255, 255, 255, 0.7);
  }

  @media (max-width: 480px) {
    padding: 32px 20px;
  }

  @media (max-width: 360px) {
    padding: 32px 16px;
  }
}

/* 表单容器 */
.form-container {
  width: 100%;
  max-width: 400px;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  position: relative;

  @media (max-width: 1200px) {
    max-width: 380px;
  }

  @media (max-width: 768px) {
    max-width: 420px;
  }

  @media (max-width: 480px) {
    max-width: 100%;
  }
}

/* 表单内容包装器 - 用于垂直居中 */
.form-content-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  max-width: 420px;
  transition: max-width 0.3s ease;

  @media (max-width: 1000px) {
    max-width: 380px;
  }

  @media (max-width: 768px) {
    max-width: 420px;
  }

  @media (max-width: 480px) {
    max-width: 100%;
  }
}

/* 移动端 Logo */
.mobile-logo-section {
  display: none;
  align-items: center;
  justify-content: center;
  margin-bottom: 32px;
  transition: all 0.3s ease;
  width: 100%;

  @media (max-width: 768px) {
    display: flex;
    animation: fadeInDown 0.4s ease;
  }

  @media (max-width: 480px) {
    margin-bottom: 28px;
  }
}

.mobile-logo-wrapper {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 24px;
  background: white;
  border-radius: 16px;
  box-shadow: 0 4px 16px rgba(124, 58, 237, 0.12);
  border: 1px solid rgba(124, 58, 237, 0.08);
  transition: all 0.3s ease;

  &:hover {
    box-shadow: 0 6px 20px rgba(124, 58, 237, 0.15);
    transform: translateY(-2px);
  }

  @media (max-width: 480px) {
    padding: 12px 18px;
    gap: 12px;
  }
}

.mobile-logo-img {
  width: 44px;
  height: 44px;
  display: block;
  flex-shrink: 0;
  /* Ensure SVG renders properly */
  object-fit: contain;

  @media (max-width: 480px) {
    width: 38px;
    height: 38px;
  }
}

.mobile-brand-name {
  font-size: 26px;
  font-weight: 700;
  background: linear-gradient(135deg, #7c3aed, #a855f7);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: -0.5px;

  @media (max-width: 480px) {
    font-size: 22px;
  }
}

@keyframes fadeInDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 语言切换器 */
.language-switcher {
  align-self: flex-end;
  margin-bottom: 28px;
  z-index: 10;

  @media (max-width: 768px) {
    margin-bottom: 24px;
  }
}

.lang-button {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 14px;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid rgba(124, 58, 237, 0.15);
  border-radius: 12px;
  color: #4b5563;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  white-space: nowrap;
  box-shadow: 0 2px 8px rgba(124, 58, 237, 0.08);

  @media (max-width: 480px) {
    padding: 8px 12px;
    font-size: 12px;
    gap: 6px;
  }

  .lang-flag {
    font-size: 16px;
    line-height: 1;

    @media (max-width: 480px) {
      font-size: 15px;
    }
  }

  .lang-text {
    max-width: 90px;
    overflow: hidden;
    text-overflow: ellipsis;

    @media (max-width: 480px) {
      max-width: 70px;
    }
  }

  .lang-arrow {
    opacity: 0.6;
    transition: transform 0.2s ease;

    @media (max-width: 480px) {
      width: 12px;
      height: 12px;
    }
  }

  &:hover {
    background: white;
    border-color: rgba(124, 58, 237, 0.25);
    color: #7c3aed;
    box-shadow: 0 4px 12px rgba(124, 58, 237, 0.15);
    transform: translateY(-1px);

    .lang-arrow {
      opacity: 1;
    }
  }

  &:active {
    transform: translateY(0);
  }
}

.dropdown-flag {
  font-size: 18px;
  line-height: 1;
  flex-shrink: 0;
}

.dropdown-name {
  flex: 1;
  min-width: 0;
}

.dropdown-check {
  color: #7c3aed;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}

/* 表单卡片 */
.form-card {
  width: 100%;
  padding: 36px 32px;
  background: #ffffff;
  border-radius: 20px;
  box-shadow: 
    0 10px 40px rgba(124, 58, 237, 0.15),
    0 2px 8px rgba(0, 0, 0, 0.05);
  border: 1px solid rgba(124, 58, 237, 0.1);
  transition: all 0.3s ease;

  @media (max-width: 1200px) {
    padding: 32px 28px;
  }

  @media (max-width: 768px) {
    padding: 32px 28px;
  }

  @media (max-width: 480px) {
    padding: 28px 24px;
    border-radius: 16px;
  }

  @media (max-width: 360px) {
    padding: 24px 20px;
  }
}

.form-header {
  text-align: center;
  margin-bottom: 26px;
  transition: margin 0.3s ease;

  @media (max-width: 480px) {
    margin-bottom: 22px;
  }
}

.form-title {
  font-size: 24px;
  font-weight: 700;
  color: #1e1b4b;
  margin-bottom: 8px;
  letter-spacing: -0.3px;
  transition: font-size 0.3s ease;

  @media (max-width: 1200px) {
    font-size: 22px;
  }

  @media (max-width: 768px) {
    font-size: 21px;
  }

  @media (max-width: 480px) {
    font-size: 19px;
  }
}

.form-subtitle {
  font-size: 14px;
  color: #6b7280;
  line-height: 1.5;
  transition: font-size 0.3s ease;

  @media (max-width: 480px) {
    font-size: 13px;
  }
}

.auth-form {
  :deep(.ed-form-item),
  :deep(.el-form-item) {
    margin-bottom: 18px;
  }

  // 错误状态输入框 - 微妙的视觉反馈
  :deep(.ed-form-item.is-error),
  :deep(.el-form-item.is-error) {
    .ed-input__wrapper,
    .el-input__wrapper {
      box-shadow: 0 0 0 1px rgba(239, 68, 68, 0.5) inset !important;
      background: rgba(239, 68, 68, 0.02) !important;
    }
  }

  // 错误信息样式 - 内联紧凑
  :deep(.ed-form-item__error),
  :deep(.el-form-item__error) {
    position: relative !important;
    top: auto !important;
    left: auto !important;
    margin-top: 6px;
    font-size: 12px;
    line-height: 1;
    color: #ef4444;
    animation: fadeIn 0.2s ease;
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
      transform: translateY(-2px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  :deep(.el-input__wrapper) {
    border-radius: 10px;
    box-shadow: 0 0 0 1px rgba(124, 58, 237, 0.2) inset !important;
    padding: 4px 12px;
    transition: all 0.2s;
    background: #ffffff !important;
    border: none !important;

    &:hover {
      box-shadow: 0 0 0 1px rgba(124, 58, 237, 0.35) inset !important;
      background: #ffffff !important;
    }

    &.is-focus {
      box-shadow: 0 0 0 2px #7c3aed inset !important;
      background: #ffffff !important;
    }
  }

  :deep(.el-input__inner) {
    height: 42px;
    font-size: 14px;
    color: #1e1b4b !important;
    background: transparent !important;

    &::placeholder {
      color: #9ca3af !important;
      opacity: 1 !important;
    }
  }

  :deep(.el-input__prefix) {
    color: #7c3aed !important;
    opacity: 0.6;
  }

  :deep(.el-input__suffix) {
    color: #6b7280 !important;
  }

  :deep(.el-input__count) {
    font-size: 11px;
    color: #9ca3af !important;
  }

  // 密码显示/隐藏图标
  :deep(.el-input__password) {
    color: #6b7280 !important;
  }
}

.password-hint {
  font-size: 11px;
  color: #6b7280;
  margin-top: 6px;
  line-height: 1.4;
  font-weight: 500;
}

.submit-button {
  width: 100%;
  height: 46px;
  font-size: 15px;
  font-weight: 600;
  border-radius: 10px;
  background: linear-gradient(135deg, #7c3aed, #a855f7);
  border: none;
  transition: all 0.2s;

  &:hover:not(:disabled) {
    background: linear-gradient(135deg, #6d28d9, #9333ea);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3);
  }

  &:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }
}

.form-switch {
  text-align: center;
  margin-top: 18px;
  font-size: 14px;
  color: #6b7280;

  a {
    color: #7c3aed;
    font-weight: 500;
    margin-left: 4px;
    text-decoration: none;
    transition: color 0.2s;

    &:hover {
      color: #6d28d9;
      text-decoration: underline;
    }
  }
}

.security-badge {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid rgba(124, 58, 237, 0.08);
  font-size: 12px;
  color: #9ca3af;

  svg {
    color: #10b981;
    flex-shrink: 0;
  }
}

.copyright {
  margin-top: 32px;
  text-align: center;
  font-size: 12px;
  color: #9ca3af;

  @media (max-width: 480px) {
    margin-top: 24px;
    font-size: 11px;
  }
}
</style>

<style lang="less">
// 登录页面输入框样式覆盖 - 使用body class提高优先级
body.login-page-active {
  .el-input,
  .ed-input {
    .el-input__wrapper,
    .ed-input__wrapper {
      background: #ffffff !important;
      border: none !important;
      box-shadow: 0 0 0 1px rgba(124, 58, 237, 0.2) inset !important;
      transition: all 0.2s ease !important;

      &:hover {
        box-shadow: 0 0 0 1px rgba(124, 58, 237, 0.35) inset !important;
        background: #ffffff !important;
      }

      &.is-focus {
        box-shadow: 0 0 0 2px #7c3aed inset !important;
        background: #ffffff !important;
      }
    }

    .el-input__inner,
    .ed-input__inner,
    input {
      color: #1e1b4b !important;
      background: transparent !important;

      &::placeholder {
        color: #9ca3af !important;
        opacity: 1 !important;
      }
    }

    .el-input__prefix,
    .ed-input__prefix {
      color: #7c3aed !important;
      opacity: 0.6;

      .el-icon,
      .ed-icon,
      svg {
        color: #7c3aed !important;
      }
    }

    .el-input__suffix,
    .ed-input__suffix {
      color: #6b7280 !important;

      .el-icon,
      .ed-icon,
      svg {
        color: #6b7280 !important;
      }
    }
  }

  // 错误状态特殊处理
  .el-form-item.is-error,
  .ed-form-item.is-error {
    .el-input__wrapper,
    .ed-input__wrapper {
      box-shadow: 0 0 0 1px rgba(239, 68, 68, 0.5) inset !important;
      background: rgba(239, 68, 68, 0.02) !important;
    }
  }
}
</style>


