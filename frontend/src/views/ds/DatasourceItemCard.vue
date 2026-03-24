<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import ExcelDs from '@/assets/svg/ds/Excel-ds.svg'
import PgDs from '@/assets/svg/ds/pg-ds.svg'
import MysqlDs from '@/assets/svg/ds/mysql-ds.svg'
import OracleDs from '@/assets/svg/ds/oracle-ds.svg'
import ClickHouseDs from '@/assets/svg/ds/clickhouse-ds.svg'
import { Connection } from '@element-plus/icons-vue'
import { Document } from '@element-plus/icons-vue'
import { Icon } from '@/components/icon-custom'
import { datasourceApi } from '@/api/datasource'

const { t } = useI18n()

const props = defineProps<{
  ds: any
}>()

// 连接状态检测
const connectionStatus = ref<'unknown' | 'connected' | 'disconnected'>('unknown')

onMounted(() => {
  // 仅对数据库类型（非文件类型）检测连接状态
  if (props.ds.type !== 'excel' && props.ds.type !== 'csv' && props.ds.type !== 'pdf') {
    datasourceApi.check_by_id(props.ds.id).then((res: any) => {
      connectionStatus.value = res ? 'connected' : 'disconnected'
    }).catch(() => {
      connectionStatus.value = 'disconnected'
    })
  } else {
    connectionStatus.value = 'connected'
  }
})

/** 根据数据源类型返回支持的功能标签列表 */
function getCapabilities(type: string): string[] {
  const capKey = type === 'pdf' ? 'cap_pdf'
    : (type === 'pg' || type === 'mysql' || type === 'oracle') ? 'cap_database'
    : type === 'excel' ? 'cap_excel'
    : type === 'csv' ? 'cap_csv'
    : 'cap_database'
  return t(`ds.${capKey}`).split(' · ')
}
</script>

<template>
  <div class="ds-card">
    <!-- 顶部渐变条 -->
    <div class="card-gradient-bar"></div>

    <div class="card-body">
      <!-- 数据库图标 -->
      <div class="db-icon">
        <Icon>
          <MysqlDs v-if="ds.type === 'mysql'" />
          <PgDs v-else-if="ds.type === 'pg'" />
          <ExcelDs v-else-if="ds.type === 'excel'" />
          <Document v-else-if="ds.type === 'pdf'" />
          <OracleDs v-else-if="ds.type === 'oracle'" />
          <ClickHouseDs v-else-if="ds.type === 'clickhouse'" />
          <Connection v-else />
        </Icon>
      </div>

      <!-- 信息区域 -->
      <div class="card-info">
        <div class="card-header">
          <h3 class="ds-name">{{ ds.name }}</h3>
          <span class="ds-type">{{ ds.type_name }}</span>
          <span
            class="connection-status"
            :class="{
              'status-connected': connectionStatus === 'connected',
              'status-disconnected': connectionStatus === 'disconnected',
              'status-unknown': connectionStatus === 'unknown'
            }"
          >
            <span class="status-dot"></span>
            {{ connectionStatus === 'connected' ? $t('ds.status_connected') : connectionStatus === 'disconnected' ? $t('ds.status_disconnected') : $t('ds.status_checking') }}
          </span>
        </div>

        <p class="ds-desc">{{ ds.description || $t('ds.no_description') }}</p>

        <!-- 支持的功能 -->
        <div class="ds-capabilities">
          <span v-for="cap in getCapabilities(ds.type)" :key="cap" class="cap-tag">{{ cap }}</span>
        </div>

        <div class="card-stats">
          <div class="stat-item">
            <el-icon class="stat-icon"><Document /></el-icon>
            <span class="stat-value">{{ ds.num || '0' }}</span>
            <span class="stat-label">{{ ds.type === 'pdf' ? $t('ds.doc_chunks') : $t('ds.tables') }}</span>
          </div>
        </div>
      </div>

      <!-- 操作按钮插槽 -->
      <slot></slot>
    </div>
  </div>
</template>

<style scoped lang="less">
// ChatBI 数据源卡片 - 重新设计的深色主题
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@primary-600: #7c3aed;
@dark-bg-card: rgba(26, 18, 37, 0.85);
@dark-border: rgba(139, 92, 246, 0.2);
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@dark-text-muted: rgba(196, 181, 253, 0.5);

.ds-card {
  position: relative;
  background: @dark-bg-card;
  backdrop-filter: blur(20px);
  border: 1.5px solid @dark-border;
  border-radius: 18px;
  overflow: hidden;
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
  
  // 悬停时的发光效果
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: radial-gradient(circle at top right, rgba(139, 92, 246, 0.1) 0%, transparent 60%);
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
    
    .db-icon {
      background: rgba(139, 92, 246, 0.25);
      border-color: rgba(139, 92, 246, 0.4);
      transform: scale(1.05);
      
      :deep(svg) {
        transform: scale(1.1);
      }
    }
  }
}

.card-gradient-bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, @primary-600 0%, @primary-500 50%, @primary-400 100%);
  opacity: 0.7;
  transition: all 0.35s ease;
  z-index: 1;
}

.card-body {
  padding: 24px;
  display: flex;
  gap: 18px;
  position: relative;
  z-index: 1;
}

.db-icon {
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
  
  :deep(svg) {
    width: 30px;
    height: 30px;
    color: @primary-400;
    transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  }
}

.card-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.ds-name {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  color: @dark-text;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 220px;
  letter-spacing: -0.2px;
}

.ds-type {
  display: inline-flex;
  align-items: center;
  padding: 4px 14px;
  font-size: 12px;
  font-weight: 600;
  color: @primary-400;
  background: rgba(139, 92, 246, 0.18);
  border: 1px solid rgba(139, 92, 246, 0.25);
  border-radius: 9px;
  letter-spacing: 0.3px;
  text-transform: uppercase;
}

.ds-desc {
  margin: 0;
  font-size: 13px;
  color: @dark-text-muted;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.5;
}

.ds-capabilities {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;

  .cap-tag {
    display: inline-flex;
    align-items: center;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 500;
    color: rgba(167, 139, 250, 0.9);
    background: rgba(139, 92, 246, 0.08);
    border: 1px solid rgba(139, 92, 246, 0.15);
    border-radius: 6px;
    letter-spacing: 0.2px;
  }
}

.card-stats {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 6px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  background: rgba(139, 92, 246, 0.12);
  border: 1px solid rgba(139, 92, 246, 0.18);
  padding: 6px 14px;
  border-radius: 10px;
  transition: all 0.25s ease;
  
  &:hover {
    background: rgba(139, 92, 246, 0.18);
    border-color: rgba(139, 92, 246, 0.3);
  }
  
  .stat-icon {
    color: @primary-400;
    font-size: 15px;
  }
  
  .stat-value {
    font-weight: 700;
    color: @dark-text;
  }
  
  .stat-label {
    color: @dark-text-muted;
  }
}

// 连接状态指示器
.connection-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 12px;
  font-size: 11px;
  font-weight: 600;
  border-radius: 8px;
  letter-spacing: 0.2px;

  .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  &.status-connected {
    color: #4ade80;
    background: rgba(74, 222, 128, 0.12);
    border: 1px solid rgba(74, 222, 128, 0.25);

    .status-dot {
      background: #4ade80;
      box-shadow: 0 0 6px rgba(74, 222, 128, 0.5);
    }
  }

  &.status-disconnected {
    color: #f87171;
    background: rgba(248, 113, 113, 0.12);
    border: 1px solid rgba(248, 113, 113, 0.25);

    .status-dot {
      background: #f87171;
      box-shadow: 0 0 6px rgba(248, 113, 113, 0.5);
    }
  }

  &.status-unknown {
    color: @dark-text-muted;
    background: rgba(139, 92, 246, 0.08);
    border: 1px solid @dark-border;

    .status-dot {
      background: @dark-text-muted;
      animation: pulse 1.5s ease-in-out infinite;
    }
  }
}

@keyframes pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}

// 响应式适配 - 平板
@media (max-width: 1024px) {
  .card-body {
    padding: 20px;
    gap: 16px;
  }
  
  .db-icon {
    width: 52px;
    height: 52px;
    
    :deep(svg) {
      width: 26px;
      height: 26px;
    }
  }
  
  .ds-name {
    font-size: 16px;
    max-width: 200px;
  }
}

// 响应式适配 - 手机
@media (max-width: 768px) {
  .ds-card {
    border-radius: 16px;
  }
  
  .card-body {
    padding: 18px;
    gap: 14px;
  }
  
  .db-icon {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    
    :deep(svg) {
      width: 24px;
      height: 24px;
    }
  }
  
  .ds-name {
    font-size: 15px;
    max-width: 180px;
  }
  
  .ds-type {
    font-size: 11px;
    padding: 3px 12px;
  }
  
  .ds-desc {
    font-size: 12px;
  }
  
  .stat-item {
    font-size: 12px;
    padding: 5px 12px;
    
    .stat-icon {
      font-size: 14px;
    }
  }
}

// 超小屏幕
@media (max-width: 480px) {
  .card-body {
    padding: 16px;
    flex-direction: column;
    align-items: flex-start;
    gap: 14px;
  }
  
  .db-icon {
    width: 44px;
    height: 44px;
  }
  
  .card-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  
  .ds-name {
    max-width: 100%;
  }
  
  .card-stats {
    width: 100%;
    
    .stat-item {
      flex: 1;
      justify-content: center;
    }
  }
}
</style>
