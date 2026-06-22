<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import BrandLogo from '../components/BrandLogo.vue'

const router = useRouter()
const auth = useAuthStore()
const form = ref({ username: '', password: '' })
const loading = ref(false)
const isDev = import.meta.env.DEV

async function handleLogin() {
  if (!form.value.username || !form.value.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    await auth.login(form.value.username, form.value.password)
    router.push('/')
  } catch (e) {
    ElMessage.error('登录失败，请检查用户名和密码')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login">
    <!-- Left brand panel (hidden on small screens) -->
    <aside class="login__brand">
      <div class="login__brand-top">
        <BrandLogo :height="36" />
      </div>
      <div class="login__brand-main">
        <h1 class="login__headline">通信项目全生命周期<br />协作管理平台</h1>
        <p class="login__sub">
          覆盖 DIA · 传输 · 裸纤 · SD-WAN 四条产品线，打通从立项到交付的多角色协同。
        </p>
        <ul class="login__features">
          <li>模板驱动的任务流转与阶段自动激活</li>
          <li>看板 · 甘特图 · 报表，多视图掌握进度</li>
          <li>变更 · 暂停 · 升级，全异常场景覆盖</li>
        </ul>
      </div>
      <div class="login__brand-foot">© 2026 通信项目管理系统</div>
    </aside>

    <!-- Right form panel -->
    <main class="login__panel">
      <div class="login__form">
        <div class="login__form-brand">
          <BrandLogo :height="34" text="通信项目管理系统" />
        </div>
        <h2 class="login__title">欢迎登录</h2>
        <p class="login__hint">请输入您的账号信息以继续</p>
        <el-form size="large" @submit.prevent="handleLogin">
          <el-form-item>
            <el-input v-model="form.username" placeholder="用户名" :prefix-icon="User" />
          </el-form-item>
          <el-form-item>
            <el-input v-model="form.password" type="password" placeholder="密码" :prefix-icon="Lock" show-password />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" size="large" :loading="loading" style="width: 100%" native-type="submit">
              登 录
            </el-button>
          </el-form-item>
        </el-form>
        <p v-if="isDev" class="login__demo">演示账号：pm01 / 123456</p>
      </div>
      <div class="login__panel-foot">京ICP备 00000000 号</div>
    </main>
  </div>
</template>

<style scoped>
.login {
  display: flex;
  height: 100vh;
  background: #fff;
}

/* Left brand panel */
.login__brand {
  position: relative;
  flex: 0 0 40%;
  max-width: 560px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 48px;
  overflow: hidden;
  color: #fff;
  background: linear-gradient(150deg, var(--brand-sidebar-bg) 0%, #003a70 55%, #1262b3 140%);
}
.login__brand::after {
  content: '';
  position: absolute;
  inset: 0;
  background-image: radial-gradient(rgba(255, 255, 255, 0.08) 1px, transparent 1px);
  background-size: 22px 22px;
  pointer-events: none;
}
.login__brand-top,
.login__brand-main,
.login__brand-foot {
  position: relative;
  z-index: 1;
}
.login__headline {
  margin: 0 0 16px;
  font-size: 32px;
  font-weight: 600;
  line-height: 1.4;
}
.login__sub {
  max-width: 420px;
  margin: 0 0 28px;
  font-size: 15px;
  line-height: 1.8;
  color: rgba(255, 255, 255, 0.85);
}
.login__features {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.login__features li {
  position: relative;
  padding-left: 24px;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.8);
}
.login__features li::before {
  content: '';
  position: absolute;
  left: 0;
  top: 5px;
  width: 8px;
  height: 8px;
  border-radius: 2px;
  background: var(--el-color-primary);
  box-shadow: 0 0 0 4px rgba(24, 144, 255, 0.25);
}
.login__brand-foot {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

/* Right form panel */
.login__panel {
  position: relative;
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 40px;
}
.login__form {
  width: 100%;
  max-width: 420px;
}
.login__form-brand {
  display: none;
  justify-content: center;
  margin-bottom: 28px;
}
.login__title {
  margin: 0 0 6px;
  font-size: 24px;
  font-weight: 600;
  color: var(--text-title);
  text-align: center;
}
.login__hint {
  margin: 0 0 28px;
  font-size: 14px;
  color: var(--el-text-color-secondary);
  text-align: center;
}
.login__demo {
  margin-top: 16px;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  text-align: center;
}
.login__panel-foot {
  position: absolute;
  bottom: 24px;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

/* Mobile: hide brand panel, show wordmark above the form */
@media (max-width: 860px) {
  .login__brand {
    display: none;
  }
  .login__panel {
    width: 100%;
    flex: 1;
  }
  .login__form-brand {
    display: flex;
  }
}
</style>
