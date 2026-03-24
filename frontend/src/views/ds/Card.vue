<script lang="ts" setup>
import delIcon from '@/assets/svg/icon_delete.svg'
import icon_form_outlined from '@/assets/svg/icon_form_outlined.svg'
import icon_chat_outlined from '@/assets/svg/icon_new-chat_outlined.svg'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { dsTypeWithImg, getDsIcon } from './js/ds-type'
import edit from '@/assets/svg/icon_edit_outlined.svg'
import { datasourceApi } from '@/api/datasource.ts'

const props = withDefaults(
  defineProps<{
    name: string
    type: string
    typeName: string
    num: string
    description?: string
    id?: string
  }>(),
  {
    name: '-',
    type: '-',
    description: '-',
    id: '-',
    typeName: '-',
  }
)

const emits = defineEmits(['edit', 'del', 'question', 'dataTableDetail', 'showTable'])
const icon = computed(() => {
  return getDsIcon(props.type)
})

const { t } = useI18n()

/** 根据数据源类型返回支持的功能标签 */
const capabilities = computed(() => {
  const capKey = props.type === 'pdf' ? 'cap_pdf'
    : (props.type === 'pg' || props.type === 'mysql' || props.type === 'oracle') ? 'cap_database'
    : props.type === 'excel' ? 'cap_excel'
    : props.type === 'csv' ? 'cap_csv'
    : 'cap_database'
  return t(`ds.${capKey}`).split(' · ')
})
const handleEdit = () => {
  emits('edit')
}

const handleDel = () => {
  emits('del')
}

const handleQuestion = () => {
  if (props.type === 'pdf' || props.type === 'excel' || props.type === 'csv') {
    emits('question', props.id)
    return
  }
  //check first
  datasourceApi.check_by_id(props.id).then((res: any) => {
    if (res) {
      emits('question', props.id)
    }
  }).catch(() => {
    // 连接检测失败时仍允许用户尝试对话，避免网络异常导致功能不可用
    emits('question', props.id)
  })
}

const dataTableDetail = () => {
  emits('dataTableDetail')
}
</script>

<template>
  <div class="ds-card-modern">
    <!-- 顶部渐变装饰条 -->
    <div class="card-gradient-bar"></div>
    
    <!-- 卡片主体内容 -->
    <div class="card-body" @click="dataTableDetail">
      <!-- 头部：图标 + 名称 + 类型 -->
      <div class="card-header">
        <div class="icon-wrapper">
          <img :src="icon" class="ds-icon" />
        </div>
        <div class="header-info">
          <h3 :title="name" class="ds-name">{{ name }}</h3>
          <span class="ds-type-badge">{{ typeName }}</span>
        </div>
      </div>

      <!-- 描述区域 -->
      <div class="card-description">
        <p :title="description" class="description-text">
          {{ description || $t('ds.no_description') }}
        </p>
      </div>

      <!-- 支持的功能 -->
      <div class="card-capabilities">
        <span v-for="cap in capabilities" :key="cap" class="cap-tag">{{ cap }}</span>
      </div>

      <!-- 统计信息 -->
      <div class="card-stats">
        <div class="stat-item">
          <el-icon class="stat-icon" size="16">
            <icon_form_outlined></icon_form_outlined>
          </el-icon>
          <span class="stat-value">{{ num }}</span>
          <span class="stat-label">{{ type === 'pdf' ? $t('ds.doc_chunks') : $t('ds.tables') }}</span>
        </div>
      </div>
    </div>

    <!-- 操作按钮区域 -->
    <div class="card-actions">
      <el-tooltip :content="$t('ds.start_chat_tip')" placement="top">
        <button class="action-btn primary-btn" @click.stop="handleQuestion">
          <el-icon size="16">
            <icon_chat_outlined></icon_chat_outlined>
          </el-icon>
          <span class="btn-label">{{ $t('datasource.open_query') }}</span>
        </button>
      </el-tooltip>
      
      <div class="secondary-actions">
        <el-tooltip :content="$t('datasource.edit')" placement="top">
          <button class="action-btn icon-btn edit-btn" @click.stop="handleEdit">
            <el-icon size="16">
              <edit></edit>
            </el-icon>
          </button>
        </el-tooltip>
        
        <el-tooltip :content="$t('dashboard.delete')" placement="top">
          <button class="action-btn icon-btn delete-btn" @click.stop="handleDel">
            <el-icon size="16">
              <delIcon></delIcon>
            </el-icon>
          </button>
        </el-tooltip>
      </div>
    </div>
  </div>
</template>

<style lang="less" scoped>
// ChatBI 数据源卡片 - 全新高级设计
@primary-300: #c4b5fd;
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@primary-600: #7c3aed;
@primary-700: #6d28d9;
@dark-bg: #0f0a1a;
@dark-bg-secondary: #1a1225;
@dark-bg-card: rgba(26, 18, 37, 0.9);
@dark-border: rgba(139, 92, 246, 0.2);
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@dark-text-muted: rgba(196, 181, 253, 0.5);

.ds-card-modern {
  position: relative;
  background: @dark-bg-card;
  backdrop-filter: blur(20px);
  border: 1.5px solid @dark-border;
  border-radius: 18px;
  overflow: hidden;
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
  display: flex;
  flex-direction: column;
  height: 100%;
  
  // 悬停时的发光效果背景
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: radial-gradient(circle at top right, rgba(139, 92, 246, 0.12) 0%, transparent 60%);
    opacity: 0;
    transition: opacity 0.35s ease;
    pointer-events: none;
    z-index: 0;
  }
  
  &:hover {
    border-color: rgba(139, 92, 246, 0.45);
    box-shadow: 
      0 12px 48px rgba(0, 0, 0, 0.4),
      0 0 0 1px rgba(139, 92, 246, 0.2) inset,
      0 0 40px rgba(139, 92, 246, 0.15);
    transform: translateY(-4px);
    
    &::before {
      opacity: 1;
    }
    
    .card-gradient-bar {
      height: 4px;
      opacity: 1;
      box-shadow: 0 0 16px rgba(139, 92, 246, 0.6);
    }
    
    .icon-wrapper {
      background: rgba(139, 92, 246, 0.25);
      border-color: rgba(139, 92, 246, 0.4);
      transform: scale(1.05);
      
      .ds-icon {
        transform: scale(1.1);
      }
    }
    
    .card-actions {
      opacity: 1;
      transform: translateY(0);
    }
  }
}

// 顶部渐变装饰条
.card-gradient-bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, @primary-700 0%, @primary-600 30%, @primary-500 60%, @primary-400 100%);
  opacity: 0.7;
  transition: all 0.35s ease;
  z-index: 1;
}

// 卡片主体
.card-body {
  padding: 24px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  position: relative;
  z-index: 1;
  cursor: pointer;
}

// 头部区域
.card-header {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  
  .icon-wrapper {
    width: 56px;
    height: 56px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(139, 92, 246, 0.15);
    border: 1.5px solid @dark-border;
    border-radius: 14px;
    transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
    
    .ds-icon {
      width: 32px;
      height: 32px;
      transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
    }
  }
  
  .header-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding-top: 2px;
    
    .ds-name {
      margin: 0;
      font-size: 17px;
      font-weight: 600;
      line-height: 1.3;
      color: @dark-text;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      letter-spacing: -0.2px;
    }
    
    .ds-type-badge {
      display: inline-flex;
      align-items: center;
      align-self: flex-start;
      padding: 4px 12px;
      font-size: 12px;
      font-weight: 600;
      line-height: 1;
      color: @primary-400;
      background: rgba(139, 92, 246, 0.18);
      border: 1px solid rgba(139, 92, 246, 0.25);
      border-radius: 8px;
      letter-spacing: 0.3px;
      text-transform: uppercase;
    }
  }
}

// 描述区域
.card-description {
  flex: 1;
  min-height: 44px;
  
  .description-text {
    margin: 0;
    font-size: 13px;
    line-height: 1.6;
    color: @dark-text-muted;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    overflow: hidden;
    word-break: break-word;
  }
}

// 功能标签
.card-capabilities {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;

  .cap-tag {
    display: inline-flex;
    align-items: center;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 500;
    color: @primary-400;
    background: rgba(139, 92, 246, 0.08);
    border: 1px solid rgba(139, 92, 246, 0.15);
    border-radius: 6px;
    letter-spacing: 0.2px;
  }
}

// 统计信息
.card-stats {
  display: flex;
  gap: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(139, 92, 246, 0.15);
  
  .stat-item {
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 7px 14px;
    background: rgba(139, 92, 246, 0.12);
    border: 1px solid rgba(139, 92, 246, 0.18);
    border-radius: 10px;
    font-size: 13px;
    transition: all 0.25s ease;
    
    &:hover {
      background: rgba(139, 92, 246, 0.18);
      border-color: rgba(139, 92, 246, 0.3);
    }
    
    .stat-icon {
      color: @primary-400;
      flex-shrink: 0;
    }
    
    .stat-value {
      font-weight: 700;
      color: @dark-text;
    }
    
    .stat-label {
      color: @dark-text-muted;
      font-weight: 500;
    }
  }
}

// 操作按钮区域
.card-actions {
  padding: 16px 24px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: rgba(15, 10, 26, 0.5);
  border-top: 1px solid rgba(139, 92, 246, 0.15);
  position: relative;
  z-index: 2;
  opacity: 0;
  transform: translateY(8px);
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  
  .action-btn {
    border: none;
    border-radius: 11px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    font-size: 13px;
    font-weight: 600;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    outline: none;
    
    &.primary-btn {
      flex: 1;
      height: 40px;
      padding: 0 18px;
      background: linear-gradient(135deg, @primary-700 0%, @primary-600 50%, @primary-500 100%);
      color: white;
      box-shadow: 0 4px 16px rgba(139, 92, 246, 0.4);
      
      .btn-label {
        font-weight: 600;
      }
      
      &:hover {
        background: linear-gradient(135deg, @primary-600 0%, @primary-500 50%, @primary-400 100%);
        box-shadow: 0 6px 24px rgba(139, 92, 246, 0.5);
        transform: translateY(-2px);
      }
      
      &:active {
        transform: translateY(0);
      }
    }
    
    &.icon-btn {
      width: 40px;
      height: 40px;
      padding: 0;
      
      &.edit-btn {
        background: rgba(139, 92, 246, 0.15);
        border: 1px solid rgba(139, 92, 246, 0.25);
        color: @primary-400;
        
        &:hover {
          background: rgba(139, 92, 246, 0.25);
          border-color: rgba(139, 92, 246, 0.4);
          color: @primary-300;
          box-shadow: 0 4px 16px rgba(139, 92, 246, 0.3);
          transform: translateY(-2px) scale(1.05);
        }
      }
      
      &.delete-btn {
        background: rgba(239, 68, 68, 0.15);
        border: 1px solid rgba(239, 68, 68, 0.25);
        color: #f87171;
        
        &:hover {
          background: rgba(239, 68, 68, 0.25);
          border-color: rgba(239, 68, 68, 0.4);
          color: #fca5a5;
          box-shadow: 0 4px 16px rgba(239, 68, 68, 0.3);
          transform: translateY(-2px) scale(1.05);
        }
      }
    }
  }
  
  .secondary-actions {
    display: flex;
    gap: 8px;
  }
}

// 响应式适配 - 平板
@media (max-width: 1024px) {
  .card-body {
    padding: 20px;
    gap: 14px;
  }
  
  .card-header {
    .icon-wrapper {
      width: 52px;
      height: 52px;
      
      .ds-icon {
        width: 28px;
        height: 28px;
      }
    }
    
    .header-info {
      .ds-name {
        font-size: 16px;
      }
    }
  }
  
  .card-actions {
    padding: 14px 20px 18px;
  }
}

// 响应式适配 - 手机
@media (max-width: 768px) {
  .ds-card-modern {
    border-radius: 16px;
  }
  
  .card-body {
    padding: 18px;
    gap: 12px;
  }
  
  .card-header {
    gap: 12px;
    
    .icon-wrapper {
      width: 48px;
      height: 48px;
      border-radius: 12px;
      
      .ds-icon {
        width: 26px;
        height: 26px;
      }
    }
    
    .header-info {
      .ds-name {
        font-size: 15px;
      }
      
      .ds-type-badge {
        font-size: 11px;
        padding: 3px 10px;
      }
    }
  }
  
  .card-description {
    min-height: 40px;
    
    .description-text {
      font-size: 12px;
    }
  }
  
  .card-stats {
    .stat-item {
      font-size: 12px;
      padding: 6px 12px;
    }
  }
  
  .card-actions {
    padding: 14px 18px 16px;
    flex-direction: column;
    opacity: 1;
    transform: translateY(0);
    
    .action-btn {
      &.primary-btn {
        width: 100%;
        height: 38px;
        font-size: 13px;
      }
    }
    
    .secondary-actions {
      width: 100%;
      justify-content: flex-end;
      
      .icon-btn {
        width: 38px;
        height: 38px;
      }
    }
  }
}

// 超小屏幕
@media (max-width: 480px) {
  .card-body {
    padding: 16px;
  }
  
  .card-header {
    .icon-wrapper {
      width: 44px;
      height: 44px;
      
      .ds-icon {
        width: 24px;
        height: 24px;
      }
    }
    
    .header-info {
      .ds-name {
        font-size: 14px;
      }
    }
  }
  
  .card-actions {
    padding: 12px 16px 14px;
    gap: 10px;
    
    .action-btn {
      &.primary-btn {
        height: 36px;
        font-size: 12px;
      }
    }
    
    .secondary-actions {
      .icon-btn {
        width: 36px;
        height: 36px;
      }
    }
  }
}
</style>
