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
withDefaults(
  defineProps<{
    activeName: string
  }>(),
  {
    activeName: '',
  }
)
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
  <div class="model-list_side">
    <el-input
      v-model="keywords"
      clearable
      style="width: 232px; margin: 16px 0 8px 24px"
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
        :class="activeName === ele.name && 'isActive'"
        @click="handleModelClick(ele)"
      >
        <img width="20px" height="20px" :src="ele.img" />
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
// ChatBI 数据源侧边列表 - 深色主题设计
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@dark-border: rgba(139, 92, 246, 0.2);
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@dark-text-muted: rgba(196, 181, 253, 0.5);

.model-list_side {
  width: 280px;
  height: 100%;
  border-right: 1px solid @dark-border;
  background: rgba(139, 92, 246, 0.02);

  :deep(.ed-input__wrapper) {
    background: rgba(139, 92, 246, 0.08) !important;
    border: 1px solid @dark-border !important;
    border-radius: 10px;
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
    height: calc(100% - 56px);
    padding: 8px 16px;
    overflow-y: auto;

    // 深色滚动条
    &::-webkit-scrollbar {
      width: 5px;
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
      width: 100%;
      height: 42px;
      display: flex;
      align-items: center;
      padding: 0 12px;
      border-radius: 10px;
      cursor: pointer;
      margin-bottom: 4px;
      color: @dark-text-secondary;
      transition: all 0.2s ease;

      img {
        border-radius: 6px;
        padding: 2px;
        background: rgba(139, 92, 246, 0.1);
      }

      .name {
        margin-left: 10px;
        font-weight: 500;
        font-size: 14px;
        line-height: 22px;
      }

      &:hover {
        background: rgba(139, 92, 246, 0.12);
        color: @dark-text;

        img {
          background: rgba(139, 92, 246, 0.2);
        }
      }

      &.isActive {
        background: rgba(139, 92, 246, 0.2);
        color: @primary-400;

        img {
          background: rgba(139, 92, 246, 0.25);
        }
      }
    }
  }
}
</style>
