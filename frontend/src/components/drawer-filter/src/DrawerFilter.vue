<script setup lang="ts">
import { propTypes } from '@/utils/propTypes'
import { ElSelect, ElOption } from 'element-plus-secondary'
import { computed, reactive } from 'vue'
import { useEmitt } from '@/utils/useEmitt'
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
const props = defineProps({
  optionList: propTypes.arrayOf(
    propTypes.shape({
      id: propTypes.string,
      name: propTypes.string,
    })
  ),
  index: propTypes.number,
  title: propTypes.string,
  property: {
    type: Object,
    default: () => ({}),
  },
})

const state = reactive({
  activeStatus: [],
})
const emits = defineEmits(['filter-change'])

const selectStatus = (ids: any[]) => {
  emits(
    'filter-change',
    ids.map((item) => item.id || item.value)
  )
}

const optionListNotSelect = computed(() => {
  return [...(props.optionList as any[])]
})
const clear = (index: number) => {
  if (index !== props.index) return
  state.activeStatus = []
}

useEmitt({
  name: 'clear-drawer_main',
  callback: clear,
})
</script>

<template>
  <div class="drawer-filter-modern">
    <div class="filter-label">
      <span class="label-text">{{ title }}</span>
      <span v-if="state.activeStatus.length" class="label-count">{{ state.activeStatus.length }}</span>
    </div>
    <el-select
      v-model="state.activeStatus"
      :teleported="false"
      class="filter-select"
      value-key="id"
      filterable
      :placeholder="t('datasource.Please_select') + props.property.placeholder"
      multiple
      collapse-tags
      collapse-tags-tooltip
      @change="selectStatus"
    >
      <el-option
        v-for="item in optionListNotSelect"
        :key="item.name"
        :label="item.name"
        :value="item"
      />
    </el-select>
  </div>
</template>

<style lang="less" scoped>
.drawer-filter-modern {
  margin-bottom: 20px;
  
  .filter-label {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
    
    .label-text {
      font-size: 13px;
      font-weight: 600;
      color: #e2e8f0;
      letter-spacing: 0.3px;
    }
    
    .label-count {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 20px;
      height: 20px;
      padding: 0 6px;
      background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
      border-radius: 10px;
      font-size: 11px;
      font-weight: 700;
      color: #fff;
      box-shadow: 0 2px 8px rgba(139, 92, 246, 0.3);
    }
  }
  
  .filter-select {
    width: 100%;
    
    :deep(.ed-input__wrapper) {
      background: rgba(139, 92, 246, 0.06);
      border: 1.5px solid rgba(139, 92, 246, 0.2);
      border-radius: 10px;
      padding: 6px 12px;
      transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
      
      &:hover {
        background: rgba(139, 92, 246, 0.1);
        border-color: rgba(139, 92, 246, 0.35);
        box-shadow: 0 4px 12px rgba(139, 92, 246, 0.15);
      }
      
      &.is-focus {
        background: rgba(139, 92, 246, 0.12);
        border-color: #8b5cf6;
        box-shadow: 0 0 0 4px rgba(139, 92, 246, 0.15), 0 4px 16px rgba(139, 92, 246, 0.2);
      }
    }
    
    :deep(.ed-input__inner) {
      color: #e2e8f0;
      font-size: 13px;
      
      &::placeholder {
        color: #64748b;
      }
    }
    
    :deep(.ed-select__tags) {
      gap: 6px;
      
      .ed-tag {
        background: linear-gradient(135deg, rgba(139, 92, 246, 0.25) 0%, rgba(124, 58, 237, 0.25) 100%);
        border: 1px solid rgba(139, 92, 246, 0.4);
        border-radius: 6px;
        color: #e9d5ff;
        font-weight: 500;
        padding: 0 8px;
        height: 24px;
        line-height: 22px;
        
        .ed-tag__content {
          font-size: 12px;
        }
        
        .ed-tag__close {
          color: #c4b5fd;
          margin-left: 4px;
          
          &:hover {
            background: rgba(139, 92, 246, 0.3);
            color: #fff;
          }
        }
      }
    }
    
    :deep(.ed-select__suffix) {
      color: #a78bfa;
    }
  }
}
</style>
