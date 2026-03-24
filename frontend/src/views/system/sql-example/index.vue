<script lang="ts" setup>
import TrainingTab from './TrainingTab.vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <div class="sql-example-page">
    <div class="page-header">
      <div class="header-left-content">
        <div class="chatbi-page-title">
          <span class="title-text">{{ t('training.data_training') }}</span>
        </div>
        <span class="page-subtitle">{{ t('training.data_training_desc') }}</span>
      </div>
    </div>
    <div class="page-body">
      <TrainingTab standalone />
    </div>
  </div>
</template>

<style lang="less" scoped>
.sql-example-page {
  padding: 24px;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;

  .page-header {
    margin-bottom: 20px;
    flex-shrink: 0;

    .header-left-content {
      display: flex;
      align-items: baseline;
      gap: 16px;
    }

    .chatbi-page-title {
      .title-text {
        font-size: 22px;
        font-weight: 700;
        background: linear-gradient(135deg, #a78bfa, #818cf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
      }
    }

    .page-subtitle {
      font-size: 13px;
      color: rgba(255, 255, 255, 0.45);
    }
  }

  .page-body {
    flex: 1;
    overflow: auto;
  }
}
</style>
