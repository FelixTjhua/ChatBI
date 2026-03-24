<script lang="ts" setup>
import { ref, shallowRef, computed } from 'vue'
import icon_searchOutline_outlined from '@/assets/svg/icon_search-outline_outlined.svg'
import EmptyBackground from '@/components/EmptyBackground.vue'
import { dsTypeWithImg } from './js/ds-type'

interface Datasource {
  name: string
  type: string
  img: string
  rate?: string
  id?: string
}
const keywords = ref('')
const modelList = shallowRef(dsTypeWithImg as Datasource[])
const modelListWithSearch = computed(() => {
  if (!keywords.value) return modelList.value
  return modelList.value.filter((ele) =>
    ele.name.toLowerCase().includes(keywords.value.toLowerCase())
  )
})
const emits = defineEmits(['clickDatasource'])
const handleModelClick = (item: any) => {
  emits('clickDatasource', item)
}
</script>

<template>
  <div class="datasouce-list">
    <div class="title">{{ $t('qa.select_datasource') }}</div>
    <el-input
      v-model="keywords"
      clearable
      style="width: 100%; margin-right: 12px"
      :placeholder="$t('datasource.search')"
    >
      <template #prefix>
        <el-icon>
          <icon_searchOutline_outlined class="svg-icon" />
        </el-icon>
      </template>
    </el-input>
    <div class="list-content">
      <div
        v-for="ele in modelListWithSearch"
        :key="ele.name"
        class="model"
        @click="handleModelClick(ele)"
      >
        <img width="32px" height="32px" :src="ele.img" />
        <span class="name">{{ ele.name }}</span>
      </div>
      <EmptyBackground
        v-if="!!keywords && !modelListWithSearch.length"
        :description="$t('datasource.relevant_content_found')"
        img-type="tree"
        style="width: 100%; margin-top: 100px"
      />
    </div>
  </div>
</template>

<style lang="less" scoped>
// ChatBI 数据源列表 - 深色主题设计
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@primary-600: #7c3aed;
@dark-bg-secondary: #1a1225;
@dark-bg-card: rgba(26, 18, 37, 0.85);
@dark-border: rgba(139, 92, 246, 0.2);
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@dark-text-muted: rgba(196, 181, 253, 0.5);

.datasouce-list {
  width: 800px;
  margin: 0 auto;
  max-height: 100%;
  padding: 24px;

  .title {
    font-weight: 600;
    font-size: 18px;
    line-height: 28px;
    margin-bottom: 20px;
    color: @dark-text;
    background: linear-gradient(135deg, @primary-400 0%, @primary-500 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  :deep(.ed-input__wrapper) {
    background: rgba(139, 92, 246, 0.08) !important;
    border: 1px solid @dark-border !important;
    border-radius: 12px;
    box-shadow: none !important;

    &:hover {
      border-color: rgba(139, 92, 246, 0.35) !important;
    }

    &:focus-within {
      border-color: @primary-500 !important;
      box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.15) !important;
    }
  }

  :deep(.ed-input__inner) {
    color: @dark-text !important;

    &::placeholder {
      color: @dark-text-muted !important;
    }
  }

  :deep(.ed-input__prefix) {
    color: @dark-text-muted;
  }

  .list-content {
    margin-top: 20px;
    display: flex;
    height: calc(100% - 80px);
    flex-wrap: wrap;
    gap: 16px;
    overflow-y: auto;

    // 深色滚动条
    &::-webkit-scrollbar {
      width: 6px;
    }

    &::-webkit-scrollbar-track {
      background: transparent;
    }

    &::-webkit-scrollbar-thumb {
      background: rgba(139, 92, 246, 0.3);
      border-radius: 3px;

      &:hover {
        background: rgba(139, 92, 246, 0.5);
      }
    }

    .model {
      width: calc(50% - 8px);
      height: 72px;
      display: flex;
      align-items: center;
      padding: 0 20px;
      background: @dark-bg-card;
      backdrop-filter: blur(12px);
      border: 1.5px solid @dark-border;
      border-radius: 14px;
      cursor: pointer;
      transition: all 0.25s ease;

      img {
        border-radius: 8px;
        padding: 4px;
        background: rgba(139, 92, 246, 0.1);
      }

      &:hover {
        border-color: rgba(139, 92, 246, 0.4);
        box-shadow:
          0 8px 32px rgba(0, 0, 0, 0.3),
          0 0 0 1px rgba(139, 92, 246, 0.15);
        transform: translateY(-2px);

        img {
          background: rgba(139, 92, 246, 0.2);
        }
      }

      .name {
        margin-left: 14px;
        font-weight: 600;
        font-size: 15px;
        line-height: 22px;
        color: @dark-text;
      }
    }
  }
}

// 响应式适配
@media (max-width: 900px) {
  .datasouce-list {
    width: 100%;
    padding: 20px;

    .list-content {
      .model {
        width: 100%;
      }
    }
  }
}
</style>
