<script lang="ts" setup>
import { ref, reactive, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { userApi } from '@/api/auth'

const { t } = useI18n()
const pwdRef = ref()
const pwdForm = reactive({
  pwd: '',
  new_pwd: '',
  confirm_pwd: '',
})

const PWD_REGEX = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[~!@#$%^&*()_+\-={}|:"<>?`\[\];',./])[A-Za-z\d~!@#$%^&*()_+\-={}|:"<>?`\[\];',./]{8,20}$/

// 实时密码检查
const passwordChecks = computed(() => {
  const pwd = pwdForm.new_pwd
  return {
    length: pwd.length >= 8 && pwd.length <= 20,
    lower: /[a-z]/.test(pwd),
    upper: /[A-Z]/.test(pwd),
    number: /\d/.test(pwd),
    special: /[~!@#$%^&*()_+\-={}|:"<>?`\[\];',./]/.test(pwd),
  }
})

const passwordStrength = computed(() => {
  const checks = passwordChecks.value
  const score = Object.values(checks).filter(v => v).length
  
  if (score === 0) return { level: 0, text: '', color: '', percent: 0 }
  if (score <= 2) return { level: 1, text: '弱', color: '#ef4444', percent: 25 }
  if (score === 3) return { level: 2, text: '中', color: '#f59e0b', percent: 50 }
  if (score === 4) return { level: 3, text: '良好', color: '#10b981', percent: 75 }
  return { level: 4, text: '强', color: '#059669', percent: 100 }
})

const passwordMatch = computed(() => {
  return pwdForm.confirm_pwd && pwdForm.new_pwd === pwdForm.confirm_pwd
})

// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
const validatePass = (rule: any, value: any, callback: any) => {
  if (value === '') {
    callback(new Error(t('common.please_input', { msg: t('user.upgrade_pwd.new_pwd') })))
  } else {
    if (!PWD_REGEX.test(value)) {
      callback(new Error(t('user.upgrade_pwd.pwd_format_error')))
      return
    }
    if (pwdForm.confirm_pwd !== '') {
      if (!pwdRef.value) return
      pwdRef.value.validateField('confirm_pwd')
    }
    callback()
  }
}

// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
const validatePass2 = (rule: any, value: any, callback: any) => {
  if (value === '') {
    callback(new Error(t('common.please_input', { msg: t('user.upgrade_pwd.confirm_pwd') })))
  } else if (!PWD_REGEX.test(value)) {
    callback(new Error(t('user.upgrade_pwd.pwd_format_error')))
  } else if (value !== pwdForm.new_pwd) {
    callback(new Error(t('user.upgrade_pwd.two_pwd_not_match')))
  } else {
    callback()
  }
}

const rules = {
  pwd: [
    {
      required: true,
      message: t('common.please_input', { msg: t('user.upgrade_pwd.old_pwd') }),
      trigger: 'blur',
    },
  ],
  new_pwd: [{ validator: validatePass, trigger: 'blur' }],
  confirm_pwd: [{ validator: validatePass2, trigger: 'blur' }],
}

const emits = defineEmits(['pwdSaved'])

const submit = () => {
  pwdRef.value.validate((res: any) => {
    if (res) {
      const param = {
        pwd: pwdForm.pwd,
        new_pwd: pwdForm.new_pwd,
      }
      userApi.pwd(param).then(() => {
        ElMessage({
          type: 'success',
          message: t('common.save_success'),
        })
        emits('pwdSaved')
      })
    }
  })
}

defineExpose({
  submit,
})
</script>

<template>
  <div class="pwd-form-ultimate">
    <el-form
      ref="pwdRef"
      :rules="rules"
      label-position="top"
      :model="pwdForm"
      @submit.prevent
    >
      <!-- 旧密码 -->
      <el-form-item prop="pwd" class="form-item-ultimate">
        <template #label>
          <div class="label-ultimate">
            <span class="label-icon">🔒</span>
            <span class="label-text">{{ t('user.upgrade_pwd.old_pwd') }}</span>
          </div>
        </template>
        <el-input
          v-model="pwdForm.pwd"
          :placeholder="t('user.upgrade_pwd.old_pwd_placeholder')"
          type="password"
          show-password
          size="large"
          class="input-ultimate"
        />
      </el-form-item>
      
      <!-- 新密码 -->
      <el-form-item prop="new_pwd" class="form-item-ultimate">
        <template #label>
          <div class="label-ultimate">
            <span class="label-icon">🔑</span>
            <span class="label-text">{{ t('user.upgrade_pwd.new_pwd') }}</span>
          </div>
        </template>
        <el-input
          v-model="pwdForm.new_pwd"
          :placeholder="t('user.upgrade_pwd.new_pwd_placeholder')"
          type="password"
          show-password
          size="large"
          class="input-ultimate"
        />
        
        <!-- 高级密码强度分析面板 -->
        <transition name="expand-fade">
          <div v-if="pwdForm.new_pwd" class="strength-panel-ultimate">
            <!-- 强度指示器 -->
            <div class="strength-indicator">
              <div class="strength-bars">
                <div 
                  v-for="i in 4" 
                  :key="i" 
                  class="strength-bar"
                  :class="{ 
                    active: i <= passwordStrength.level,
                    weak: i <= passwordStrength.level && passwordStrength.level === 1,
                    medium: i <= passwordStrength.level && passwordStrength.level === 2,
                    good: i <= passwordStrength.level && passwordStrength.level === 3,
                    strong: i <= passwordStrength.level && passwordStrength.level === 4
                  }"
                ></div>
              </div>
              <div class="strength-label-row">
                <span class="strength-title">{{ t('pwd.strength_label') }}</span>
                <span class="strength-badge" :style="{ 
                  backgroundColor: passwordStrength.color + '20',
                  color: passwordStrength.color,
                  borderColor: passwordStrength.color + '40'
                }">
                  {{ passwordStrength.text || t('pwd.not_set') }}
                </span>
              </div>
            </div>
            
            <!-- 安全要求检查列表 -->
            <div class="security-checks">
              <div class="checks-title">
                <span class="checks-icon">🛡</span>
                <span>{{ t('pwd.security_requirements') }}</span>
              </div>
              <div class="checks-list">
                <div class="check-row" :class="{ passed: passwordChecks.length }">
                  <div class="check-indicator">
                    <span class="check-dot"></span>
                  </div>
                  <span class="check-label">{{ t('pwd.length_8_20') }}</span>
                  <span class="check-status">{{ passwordChecks.length ? '✓' : '' }}</span>
                </div>
                <div class="check-row" :class="{ passed: passwordChecks.lower }">
                  <div class="check-indicator">
                    <span class="check-dot"></span>
                  </div>
                  <span class="check-label">{{ t('pwd.has_lowercase') }}</span>
                  <span class="check-status">{{ passwordChecks.lower ? '✓' : '' }}</span>
                </div>
                <div class="check-row" :class="{ passed: passwordChecks.upper }">
                  <div class="check-indicator">
                    <span class="check-dot"></span>
                  </div>
                  <span class="check-label">{{ t('pwd.has_uppercase') }}</span>
                  <span class="check-status">{{ passwordChecks.upper ? '✓' : '' }}</span>
                </div>
                <div class="check-row" :class="{ passed: passwordChecks.number }">
                  <div class="check-indicator">
                    <span class="check-dot"></span>
                  </div>
                  <span class="check-label">{{ t('pwd.has_number') }}</span>
                  <span class="check-status">{{ passwordChecks.number ? '✓' : '' }}</span>
                </div>
                <div class="check-row" :class="{ passed: passwordChecks.special }">
                  <div class="check-indicator">
                    <span class="check-dot"></span>
                  </div>
                  <span class="check-label">{{ t('pwd.has_special') }}</span>
                  <span class="check-status">{{ passwordChecks.special ? '✓' : '' }}</span>
                </div>
              </div>
            </div>
          </div>
        </transition>
      </el-form-item>
      
      <!-- 确认密码 -->
      <el-form-item prop="confirm_pwd" class="form-item-ultimate">
        <template #label>
          <div class="label-ultimate">
            <span class="label-icon">✓</span>
            <span class="label-text">{{ t('user.upgrade_pwd.confirm_pwd') }}</span>
          </div>
        </template>
        <el-input
          v-model="pwdForm.confirm_pwd"
          :placeholder="t('pwd.confirm_placeholder')"
          type="password"
          show-password
          size="large"
          class="input-ultimate"
        />
        
        <!-- 匹配状态指示器 -->
        <transition name="expand-fade">
          <div v-if="pwdForm.confirm_pwd" class="match-indicator" :class="{ matched: passwordMatch }">
            <div class="match-icon-wrapper">
              <span class="match-icon">{{ passwordMatch ? '✓' : '✕' }}</span>
            </div>
            <div class="match-content">
              <span class="match-title">{{ passwordMatch ? t('pwd.match_success') : t('pwd.match_fail') }}</span>
              <span class="match-desc">{{ passwordMatch ? t('pwd.match_success_desc') : t('pwd.match_fail_desc') }}</span>
            </div>
          </div>
        </transition>
      </el-form-item>
    </el-form>
  </div>
</template>

<style lang="less" scoped>
// 深紫色主题密码表单 - 终极版本
.pwd-form-ultimate,
.pwd-form-premium {
  padding: 0;
  
  // Element Plus 表单全局样式覆盖
  :deep(.el-form) {
    .el-form-item {
      margin-bottom: 24px;
      
      &:last-child {
        margin-bottom: 0;
      }
      
      // 错误提示文字颜色
      .el-form-item__error {
        color: #f87171 !important;
        font-size: 12px;
        font-weight: 500;
        margin-top: 6px;
      }
    }
  }
  
  // 表单项样式
  .form-item-premium,
  .form-item-ultimate {
    margin-bottom: 24px;
    
    &:last-child {
      margin-bottom: 0;
    }
  }
  
  // 标签样式 - 深紫色主题，高级图标设计
  .label-premium,
  .label-ultimate {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
    font-size: 14px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.95) !important;
    letter-spacing: 0.01em;
    
    .label-icon {
      flex-shrink: 0;
      width: 28px;
      height: 28px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
      background: linear-gradient(135deg, rgba(168, 85, 247, 0.2) 0%, rgba(139, 92, 246, 0.15) 100%);
      border: 1.5px solid rgba(168, 85, 247, 0.3);
      border-radius: 8px;
      box-shadow: 
        0 2px 8px rgba(168, 85, 247, 0.2),
        inset 0 1px 0 rgba(255, 255, 255, 0.1);
      transition: all 0.3s ease;
    }
    
    .label-text {
      flex: 1;
      color: rgba(255, 255, 255, 0.95) !important;
    }
  }
  
  // 输入框深紫色主题 - 强制覆盖所有默认样式
  .input-premium,
  .input-ultimate {
    // 最高优先级覆盖
    :deep(.el-input__wrapper),
    :deep(.el-input__wrapper.is-focus),
    :deep(.el-input__wrapper:hover),
    :deep(.el-input__wrapper:focus) {
      background: rgba(20, 10, 40, 0.85) !important;
      border: 2px solid rgba(139, 92, 246, 0.4) !important;
      border-radius: 12px !important;
      box-shadow: 
        inset 0 2px 8px rgba(0, 0, 0, 0.4),
        0 0 0 0 rgba(139, 92, 246, 0) !important;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
      padding: 4px 16px !important;
      min-height: 52px !important;
    }
    
    :deep(.el-input__wrapper:hover) {
      border-color: rgba(139, 92, 246, 0.6) !important;
      background: rgba(25, 15, 50, 0.9) !important;
      box-shadow: 
        inset 0 2px 8px rgba(0, 0, 0, 0.4),
        0 0 0 3px rgba(139, 92, 246, 0.15) !important;
    }
    
    :deep(.el-input__wrapper.is-focus) {
      border-color: #a855f7 !important;
      background: rgba(30, 20, 55, 0.95) !important;
      box-shadow: 
        inset 0 2px 8px rgba(0, 0, 0, 0.4),
        0 0 0 4px rgba(168, 85, 247, 0.3) !important;
    }
    
    :deep(.el-input__inner) {
      color: rgba(255, 255, 255, 0.98) !important;
      font-size: 15px !important;
      font-weight: 500 !important;
      background: transparent !important;
      
      &::placeholder {
        color: rgba(196, 181, 253, 0.45) !important;
        font-weight: 400 !important;
      }
    }
    
    // 密码显示按钮
    :deep(.el-input__suffix) {
      .el-input__password,
      .el-input__clear,
      .el-icon {
        color: rgba(196, 181, 253, 0.65) !important;
        font-size: 18px !important;
        
        &:hover {
          color: #a855f7 !important;
        }
      }
    }
    
    // 前缀图标
    :deep(.el-input__prefix) {
      .el-icon {
        color: rgba(196, 181, 253, 0.65) !important;
        font-size: 18px !important;
      }
    }
  }
  
  // 全局 Element Plus 输入框覆盖（针对密码对话框）
  .pwd-dialog-premium & {
    :deep(.el-input__wrapper) {
      background: rgba(20, 10, 40, 0.85) !important;
      border-color: rgba(139, 92, 246, 0.4) !important;
    }
  }
  
  // 高级密码强度面板
  .strength-panel-ultimate {
    margin-top: 18px;
    padding: 20px;
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.15) 0%, rgba(139, 92, 246, 0.08) 100%);
    border: 2px solid rgba(139, 92, 246, 0.3);
    border-radius: 14px;
    box-shadow: 
      0 4px 16px rgba(139, 92, 246, 0.2),
      inset 0 1px 0 rgba(255, 255, 255, 0.05);
    
    // 强度指示器
    .strength-indicator {
      margin-bottom: 18px;
      
      .strength-bars {
        display: flex;
        gap: 8px;
        margin-bottom: 14px;
        
        .strength-bar {
          flex: 1;
          height: 8px;
          background: rgba(139, 92, 246, 0.18);
          border-radius: 4px;
          transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
          border: 1px solid rgba(139, 92, 246, 0.25);
          
          &.active {
            border-color: transparent;
            box-shadow: 0 0 12px currentColor;
            
            &.weak {
              background: linear-gradient(90deg, #ef4444 0%, #f87171 100%);
            }
            
            &.medium {
              background: linear-gradient(90deg, #f59e0b 0%, #fbbf24 100%);
            }
            
            &.good {
              background: linear-gradient(90deg, #10b981 0%, #34d399 100%);
            }
            
            &.strong {
              background: linear-gradient(90deg, #059669 0%, #10b981 100%);
            }
          }
        }
      }
      
      .strength-label-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        
        .strength-title {
          font-size: 13px;
          font-weight: 600;
          color: rgba(196, 181, 253, 0.85);
        }
        
        .strength-badge {
          padding: 5px 14px;
          border-radius: 14px;
          font-size: 12px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          border: 1.5px solid;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
        }
      }
    }
    
    // 安全要求检查
    .security-checks {
      .checks-title {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 14px;
        font-size: 13px;
        font-weight: 600;
        color: rgba(196, 181, 253, 0.85);
        
        .checks-icon {
          flex-shrink: 0;
          width: 24px;
          height: 24px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 14px;
          background: linear-gradient(135deg, rgba(168, 85, 247, 0.18) 0%, rgba(139, 92, 246, 0.12) 100%);
          border: 1.5px solid rgba(168, 85, 247, 0.25);
          border-radius: 6px;
          box-shadow: 
            0 2px 6px rgba(168, 85, 247, 0.15),
            inset 0 1px 0 rgba(255, 255, 255, 0.08);
        }
      }
      
      .checks-list {
        display: flex;
        flex-direction: column;
        gap: 10px;
        
        .check-row {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 10px 14px;
          background: rgba(139, 92, 246, 0.08);
          border: 1.5px solid rgba(139, 92, 246, 0.2);
          border-radius: 10px;
          transition: all 0.3s ease;
          
          .check-indicator {
            flex-shrink: 0;
            width: 20px;
            height: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            background: rgba(139, 92, 246, 0.15);
            border: 1.5px solid rgba(139, 92, 246, 0.3);
            
            .check-dot {
              width: 10px;
              height: 10px;
              border-radius: 50%;
              background: rgba(196, 181, 253, 0.4);
              transition: all 0.3s ease;
            }
          }
          
          .check-label {
            flex: 1;
            font-size: 13px;
            font-weight: 500;
            color: rgba(196, 181, 253, 0.7);
            transition: all 0.3s ease;
          }
          
          .check-status {
            flex-shrink: 0;
            font-size: 16px;
            font-weight: bold;
            color: transparent;
            transition: all 0.3s ease;
          }
          
          &.passed {
            background: rgba(16, 185, 129, 0.15);
            border-color: rgba(16, 185, 129, 0.4);
            
            .check-indicator {
              background: rgba(16, 185, 129, 0.2);
              border-color: rgba(16, 185, 129, 0.5);
              
              .check-dot {
                background: #10b981;
                box-shadow: 0 0 10px rgba(16, 185, 129, 0.6);
                animation: checkPulse 0.5s ease;
              }
            }
            
            .check-label {
              color: rgba(16, 185, 129, 0.95);
              font-weight: 600;
            }
            
            .check-status {
              color: #10b981;
              animation: checkPop 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55);
            }
          }
        }
      }
    }
  }
  
  // 匹配状态指示器
  .match-indicator {
    margin-top: 16px;
    padding: 16px 18px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    gap: 16px;
    background: rgba(239, 68, 68, 0.15);
    border: 2px solid rgba(239, 68, 68, 0.35);
    transition: all 0.3s ease;
    box-shadow: 
      0 4px 16px rgba(239, 68, 68, 0.2),
      inset 0 1px 0 rgba(255, 255, 255, 0.05);
    
    .match-icon-wrapper {
      flex-shrink: 0;
      width: 40px;
      height: 40px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(239, 68, 68, 0.2);
      border-radius: 50%;
      border: 2px solid rgba(239, 68, 68, 0.4);
      
      .match-icon {
        font-size: 20px;
        font-weight: bold;
        color: #ef4444;
      }
    }
    
    .match-content {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 3px;
      
      .match-title {
        font-size: 14px;
        font-weight: 600;
        color: #ef4444;
      }
      
      .match-desc {
        font-size: 12px;
        color: rgba(239, 68, 68, 0.75);
        line-height: 1.4;
      }
    }
    
    &.matched {
      background: rgba(16, 185, 129, 0.15);
      border-color: rgba(16, 185, 129, 0.4);
      box-shadow: 
        0 4px 16px rgba(16, 185, 129, 0.2),
        inset 0 1px 0 rgba(255, 255, 255, 0.05);
      
      .match-icon-wrapper {
        background: rgba(16, 185, 129, 0.2);
        border-color: rgba(16, 185, 129, 0.5);
        
        .match-icon {
          color: #10b981;
          animation: checkPop 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55);
        }
      }
      
      .match-content {
        .match-title {
          color: #10b981;
        }
        
        .match-desc {
          color: rgba(16, 185, 129, 0.75);
        }
      }
    }
  }
}

// 动画
.expand-fade-enter-active {
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}
.expand-fade-leave-active {
  transition: all 0.3s ease;
}
.expand-fade-enter-from {
  transform: translateY(-10px);
  opacity: 0;
  max-height: 0;
}
.expand-fade-leave-to {
  transform: translateY(-8px);
  opacity: 0;
  max-height: 0;
}

@keyframes checkPop {
  0% { 
    transform: scale(0.7); 
    opacity: 0;
  }
  50% { 
    transform: scale(1.3); 
  }
  100% { 
    transform: scale(1); 
    opacity: 1;
  }
}

@keyframes checkPulse {
  0%, 100% { 
    transform: scale(1); 
  }
  50% { 
    transform: scale(1.2); 
  }
}
</style>
