<script lang="ts" setup>
import icon_left_outlined from '@/assets/svg/common-back.svg'
import icon_close_outlined from '@/assets/svg/icon_close_outlined.svg'
import icon_deleteTrash_outlined from '@/assets/svg/icon_delete.svg'
import icon_right_outlined from '@/assets/svg/icon_right_outlined.svg'
import { nextTick, ref, watch } from 'vue'
import { Icon } from '@/components/icon-custom'
import { ElButton, ElDivider, ElIcon } from 'element-plus-secondary'
import { propTypes } from '@/utils/propTypes'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const props = defineProps({
  filterTexts: {
    type: Array<string>,
    default: () => [],
  },
  total: propTypes.number.def(0),
})

const emits = defineEmits(['clearFilter'])
const container = ref<any>(null)

const showScroll = ref(false)
const scrollPre = () => {
  container.value!.scrollLeft -= 10
  if (container.value.scrollLeft <= 0) {
    container.value.scrollLeft = 0
  }
}
const scrollNext = () => {
  container.value.scrollLeft += 10
  const width = container.value.scrollWidth - container.value.offsetWidth
  if (container.value.scrollLeft > width) {
    container.value.scrollLeft = width
  }
}
const clearFilter = (index?: number) => {
  emits('clearFilter', index)
}

const clearFilterAll = () => {
  emits('clearFilter', 'empty')
}

watch(
  () => props.filterTexts,
  () => {
    nextTick(() => {
      showScroll.value = container.value?.scrollWidth > container.value?.offsetWidth
    })
  },
  { deep: true }
)
</script>

<template>
  <div v-if="filterTexts.length" class="filter-results-bar">
    <div class="results-info">
      <div class="results-badge">
        <span class="badge-number">{{ total }}</span>
        <span class="badge-label">{{ t('common.result_count') }}</span>
      </div>
      <div class="divider-line"></div>
    </div>
    
    <el-icon v-if="showScroll" class="scroll-arrow scroll-left" @click="scrollPre">
      <Icon name="icon_left_outlined"><icon_left_outlined class="svg-icon" /></Icon>
    </el-icon>
    
    <div ref="container" class="filter-tags-container">
      <div v-for="(ele, index) in filterTexts" :key="index" class="filter-tag">
        <el-tooltip effect="dark" :content="ele" placement="top">
          <span class="tag-text">{{ ele }}</span>
        </el-tooltip>
        <el-icon class="tag-close" @click="clearFilter(index)">
          <Icon name="icon_close_outlined"><icon_close_outlined class="svg-icon" /></Icon>
        </el-icon>
      </div>
      
      <el-button
        v-if="!showScroll"
        text
        class="clear-all-btn inline-btn"
        @click="clearFilterAll"
      >
        <template #icon>
          <Icon name="icon_delete-trash_outlined">
            <icon_deleteTrash_outlined class="svg-icon" />
          </Icon>
        </template>
        {{ t('common.clear_filter') }}
      </el-button>
    </div>
    
    <el-icon v-if="showScroll" class="scroll-arrow scroll-right" @click="scrollNext">
      <Icon name="icon_right_outlined"><icon_right_outlined class="svg-icon" /></Icon>
    </el-icon>
    
    <el-button
      v-if="showScroll"
      text
      class="clear-all-btn"
      @click="clearFilterAll"
    >
      <template #icon>
        <Icon name="icon_delete-trash_outlined">
          <icon_deleteTrash_outlined class="svg-icon" />
        </Icon>
      </template>
      {{ t('common.clear_filter') }}
    </el-button>
  </div>
</template>

<style lang="less" scoped>
.filter-results-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  margin: 16px 0;
  background: linear-gradient(135deg, rgba(30, 18, 69, 0.6) 0%, rgba(26, 16, 51, 0.6) 100%);
  border: 1px solid rgba(139, 92, 246, 0.2);
  border-radius: 12px;
  backdrop-filter: blur(10px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
  
  .results-info {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-shrink: 0;
    
    .results-badge {
      display: flex;
      align-items: baseline;
      gap: 6px;
      padding: 6px 12px;
      background: linear-gradient(135deg, rgba(139, 92, 246, 0.2) 0%, rgba(124, 58, 237, 0.2) 100%);
      border: 1px solid rgba(139, 92, 246, 0.3);
      border-radius: 8px;
      
      .badge-number {
        font-size: 18px;
        font-weight: 700;
        color: #e9d5ff;
        background: linear-gradient(135deg, #ddd6fe 0%, #c4b5fd 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
      }
      
      .badge-label {
        font-size: 12px;
        font-weight: 500;
        color: #94a3b8;
      }
    }
    
    .divider-line {
      width: 1px;
      height: 24px;
      background: linear-gradient(180deg, transparent 0%, rgba(139, 92, 246, 0.4) 50%, transparent 100%);
    }
  }
  
  .scroll-arrow {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    color: #94a3b8;
    background: rgba(139, 92, 246, 0.08);
    border: 1px solid rgba(139, 92, 246, 0.15);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    
    &:hover {
      background: rgba(139, 92, 246, 0.15);
      border-color: rgba(139, 92, 246, 0.3);
      color: #c4b5fd;
      transform: scale(1.05);
    }
    
    &:active {
      transform: scale(0.95);
    }
    
    &.scroll-left {
      margin-right: 4px;
    }
    
    &.scroll-right {
      margin-left: 4px;
    }
  }
  
  .filter-tags-container {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 8px;
    overflow-x: auto;
    overflow-y: hidden;
    scrollbar-width: none;
    -ms-overflow-style: none;
    
    &::-webkit-scrollbar {
      display: none;
    }
    
    .filter-tag {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 10px 6px 12px;
      background: linear-gradient(135deg, rgba(139, 92, 246, 0.18) 0%, rgba(124, 58, 237, 0.18) 100%);
      border: 1px solid rgba(139, 92, 246, 0.35);
      border-radius: 8px;
      max-width: 280px;
      flex-shrink: 0;
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
      box-shadow: 0 2px 8px rgba(139, 92, 246, 0.1);
      
      &:hover {
        background: linear-gradient(135deg, rgba(139, 92, 246, 0.25) 0%, rgba(124, 58, 237, 0.25) 100%);
        border-color: rgba(139, 92, 246, 0.5);
        box-shadow: 0 4px 12px rgba(139, 92, 246, 0.2);
        transform: translateY(-1px);
      }
      
      .tag-text {
        font-size: 13px;
        font-weight: 500;
        color: #c4b5fd;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      
      .tag-close {
        width: 16px;
        height: 16px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #94a3b8;
        cursor: pointer;
        border-radius: 4px;
        transition: all 0.2s ease;
        flex-shrink: 0;
        
        &:hover {
          background: rgba(139, 92, 246, 0.3);
          color: #e9d5ff;
        }
      }
    }
    
    .inline-btn {
      margin-left: 4px;
    }
  }
  
  .clear-all-btn {
    flex-shrink: 0;
    height: 32px;
    padding: 0 12px;
    font-size: 13px;
    font-weight: 500;
    color: #cbd5e1;
    background: rgba(139, 92, 246, 0.08);
    border: 1px solid rgba(139, 92, 246, 0.15);
    border-radius: 8px;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    
    :deep(.ed-icon) {
      color: #94a3b8;
      transition: color 0.2s ease;
    }
    
    &:hover {
      background: rgba(220, 38, 38, 0.15);
      border-color: rgba(220, 38, 38, 0.3);
      color: #fca5a5;
      
      :deep(.ed-icon) {
        color: #fca5a5;
      }
    }
    
    &:active {
      transform: scale(0.95);
    }
  }
}
</style>
