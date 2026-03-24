<script lang="ts" setup>
defineProps({
  name: {
    type: String,
    default: '-',
  },
  t: {
    type: Function,
    default: () => {},
  },
})
</script>

<template>
  <div class="del-box_message">
    <div class="del-title">
      {{ t('datasource.data_source', { msg: name }) }}
    </div>
    <div class="use-panel">
      {{ t('workspace.confirm_to_delete') }}
    </div>
  </div>
</template>

<style lang="less" scoped>
// ChatBI 删除确认框 - 深色主题设计
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@primary-400: #a78bfa;

.del-box_message {
  .del-title {
    font-weight: 600;
    font-size: 16px;
    line-height: 24px;
    color: @dark-text;
  }

  .use-panel {
    font-weight: 400;
    font-size: 14px;
    line-height: 22px;
    margin-top: 20px;
    color: @dark-text-secondary;

    span {
      text-decoration: underline;
      text-decoration-style: solid;
      cursor: pointer;
      color: @primary-400;
      transition: color 0.2s ease;

      &:hover {
        color: lighten(@primary-400, 10%);
      }
    }
  }
}
</style>
