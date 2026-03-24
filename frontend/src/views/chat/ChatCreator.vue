<script lang="ts" setup>
import { onMounted, ref, computed, shallowRef } from 'vue'
import icon_close_outlined from '@/assets/svg/operate/ope-close.svg'
import icon_add_outlined from '@/assets/svg/icon_add_outlined.svg'
import EmptyBackground from '@/components/EmptyBackground.vue'
import icon_searchOutline_outlined from '@/assets/svg/icon_search-outline_outlined.svg'
import { chatApi, ChatInfo } from '@/api/chat.ts'
import { datasourceApi } from '@/api/datasource.ts'
import Card from '@/views/ds/ChatCard.vue'
import AddDrawer from '@/views/ds/AddDrawer.vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = withDefaults(
  defineProps<{
    hidden?: boolean
  }>(),
  {
    hidden: false,
  }
)

const addDrawerRef = ref()
const searchLoading = ref(false)
const datasourceConfigVisible = ref(false)
const keywords = ref('')
const datasourceList = shallowRef([] as any[])
const datasourceListWithSearch = computed(() => {
  if (!keywords.value) return datasourceList.value
  return datasourceList.value.filter((ele) =>
    ele.name.toLowerCase().includes(keywords.value.toLowerCase())
  )
})
const beforeClose = () => {
  datasourceConfigVisible.value = false
  keywords.value = ''
}

const emits = defineEmits(['onChatCreated'])

function listDs() {
  searchLoading.value = true
  datasourceApi
    .list()
    .then((res) => {
      datasourceList.value = res
    })
    .catch(() => {
      ElMessage({ type: 'error', message: t('common.operation_failed') })
    })
    .finally(() => {
      searchLoading.value = false
    })
}

const innerDs = ref()

const loading = ref(false)
const statusLoading = ref(false)

function showDs() {
  listDs()
  datasourceConfigVisible.value = true
}

function hideDs() {
  innerDs.value = undefined
  datasourceConfigVisible.value = false
}

function selectDsInDialog(ds: any) {
  innerDs.value = ds.id
}

function confirmSelectDs() {
  if (innerDs.value) {
    statusLoading.value = true
    //check first
    datasourceApi
      .check_by_id(innerDs.value)
      .then((res: any) => {
        if (res) {
          createChat(innerDs.value)
        } else {
          // 数据源检查返回 falsy 时给用户反馈，避免静默失败
          ElMessage({ type: 'warning', message: t('datasource.source_connection_failed') })
        }
      })
      .catch(() => {
        ElMessage({ type: 'error', message: t('datasource.source_connection_failed') })
      })
      .finally(() => {
        statusLoading.value = false
      })
  }
}

function createChat(datasource: number) {
  loading.value = true
  chatApi
    .startChat({
      datasource: datasource,
    })
    .then((res) => {
      const chat: ChatInfo | undefined = chatApi.toChatInfo(res)
      if (chat == undefined) {
        throw Error('chat is undefined')
      }
      emits('onChatCreated', chat)
      hideDs()
    })
    .catch(() => {
      ElMessage({ type: 'error', message: t('common.operation_failed') })
    })
    .finally(() => {
      loading.value = false
    })
}

onMounted(() => {
  if (props.hidden) {
    return
  }
})

const handleAddDatasource = () => {
  addDrawerRef.value.handleAddDatasource()
}

defineExpose({
  showDs,
  hideDs,
  createChat,
})
</script>

<template>
  <div v-loading.body.fullscreen.lock="loading || statusLoading">
    <el-drawer
      v-model="datasourceConfigVisible"
      :close-on-click-modal="false"
      size="calc(100% - 100px)"
      modal-class="datasource-drawer-chat"
      direction="btt"
      :before-close="beforeClose"
      :show-close="false"
    >
      <template #header="{ close }">
        <span style="white-space: nowrap">{{ $t('qa.select_datasource') }}</span>
        <div class="flex-center" style="width: 100%">
          <el-input
            v-model="keywords"
            clearable
            style="width: 320px"
            :placeholder="$t('datasource.search')"
          >
            <template #prefix>
              <el-icon>
                <icon_searchOutline_outlined />
              </el-icon>
            </template>
          </el-input>
        </div>
        <el-icon class="ed-dialog__headerbtn mrt" style="cursor: pointer" @click="close">
          <icon_close_outlined></icon_close_outlined>
        </el-icon>
      </template>
      <div v-if="datasourceListWithSearch.length" class="card-content">
        <el-row :gutter="16" class="w-full">
          <el-col
            v-for="ele in datasourceListWithSearch"
            :key="ele.id"
            :xs="24"
            :sm="12"
            :md="12"
            :lg="8"
            :xl="6"
            class="mb-16"
          >
            <Card
              :id="ele.id"
              :key="ele.id"
              :name="ele.name"
              :type="ele.type"
              :type-name="ele.type_name"
              :num="ele.num"
              :is-selected="ele.id === innerDs"
              :description="ele.description"
              @select-ds="selectDsInDialog(ele)"
            ></Card>
          </el-col>
        </el-row>
      </div>
      <template v-if="!keywords && !datasourceListWithSearch.length && !searchLoading">
        <EmptyBackground
          class="datasource-yet_btn"
          :description="$t('datasource.data_source_yet')"
          img-type="noneWhite"
        />

        <div style="text-align: center; margin-top: 12px">
          <el-button type="primary" @click="handleAddDatasource">
            <template #icon>
              <icon_add_outlined></icon_add_outlined>
            </template>
            {{ $t('datasource.new_data_source') }}
          </el-button>
        </div>
      </template>
      <EmptyBackground
        v-if="!!keywords && !datasourceListWithSearch.length"
        :description="$t('datasource.relevant_content_found')"
        class="datasource-yet"
        img-type="tree"
      />
      <template #footer>
        <div class="dialog-footer">
          <el-button secondary :disabled="loading" @click="hideDs">{{
            $t('common.cancel')
          }}</el-button>
          <el-button
            :type="loading || statusLoading || innerDs === undefined ? 'info' : 'primary'"
            :disabled="loading || statusLoading || innerDs === undefined"
            @click="confirmSelectDs"
          >
            {{ $t('datasource.confirm') }}
          </el-button>
        </div>
      </template>
    </el-drawer>
    <AddDrawer ref="addDrawerRef" @search="listDs"></AddDrawer>
  </div>
</template>

<style lang="less">
// 深色主题变量
@dark-bg: #0f0a1a;
@dark-bg-secondary: #1a1225;
@dark-border: rgba(139, 92, 246, 0.2);
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@dark-text-muted: rgba(196, 181, 253, 0.7);
@primary-400: #a78bfa;
@primary-500: #8b5cf6;

.datasource-drawer-chat {
  background: rgba(15, 10, 26, 0.85) !important;
  backdrop-filter: blur(24px);

  .ed-drawer {
    background: linear-gradient(180deg, @dark-bg-secondary 0%, @dark-bg 100%) !important;
    border-radius: 28px 28px 0 0 !important;
    border: 1px solid rgba(139, 92, 246, 0.25) !important;
    border-bottom: none !important;
    box-shadow:
      0 -20px 60px rgba(0, 0, 0, 0.4),
      0 0 0 1px rgba(139, 92, 246, 0.1) inset;
    position: relative;
    overflow: hidden;

    // 顶部高光
    &::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 1px;
      background: linear-gradient(
        90deg,
        transparent 0%,
        rgba(139, 92, 246, 0.5) 50%,
        transparent 100%
      );
      pointer-events: none;
      z-index: 1;
    }

    .ed-drawer__header {
      background: transparent;
      border-bottom: 1px solid @dark-border;
      padding: 22px 28px;
      color: @dark-text;
      position: relative;

      span {
        color: @dark-text;
        font-weight: 700;
        font-size: 17px;
        letter-spacing: 0.3px;
      }

      .ed-input {
        .ed-input__wrapper {
          background: linear-gradient(
            135deg,
            rgba(139, 92, 246, 0.12) 0%,
            rgba(168, 85, 247, 0.08) 100%
          );
          border: 1px solid rgba(139, 92, 246, 0.2);
          border-radius: 14px;
          transition: all 0.25s ease;

          &:hover {
            border-color: rgba(139, 92, 246, 0.35);
            background: linear-gradient(
              135deg,
              rgba(139, 92, 246, 0.15) 0%,
              rgba(168, 85, 247, 0.1) 100%
            );
          }

          &:focus-within {
            border-color: rgba(139, 92, 246, 0.5);
            box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.1);
          }

          .ed-input__inner {
            color: @dark-text;

            &::placeholder {
              color: @dark-text-muted;
            }
          }
        }

        .ed-input__prefix {
          color: @dark-text-secondary;
        }
      }

      .ed-dialog__headerbtn {
        color: @dark-text-secondary;
        width: 36px;
        height: 36px;
        border-radius: 10px;
        transition: all 0.2s ease;

        &:hover {
          color: @dark-text;
          background: rgba(139, 92, 246, 0.15);
        }
      }
    }

    .ed-drawer__body {
      padding: 24px 0;
      background: transparent;
    }

    .ed-drawer__footer {
      background: linear-gradient(180deg, transparent 0%, rgba(15, 10, 26, 0.5) 100%);
      border-top: 1px solid @dark-border;
      padding: 18px 28px;

      .ed-button {
        border-radius: 12px;
        font-weight: 500;
        transition: all 0.25s ease;

        &--primary {
          box-shadow: 0 4px 16px rgba(139, 92, 246, 0.35);

          &:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 20px rgba(139, 92, 246, 0.45);
          }
        }
      }
    }
  }

  .card-content {
    max-height: calc(100% - 40px);
    overflow-y: auto;
    padding: 0 12px 0 28px;

    .w-full {
      width: 100%;
    }

    .mb-16 {
      margin-bottom: 16px;
    }

    &::-webkit-scrollbar {
      width: 6px;
    }

    &::-webkit-scrollbar-track {
      background: rgba(139, 92, 246, 0.05);
      border-radius: 3px;
    }

    &::-webkit-scrollbar-thumb {
      background: linear-gradient(
        180deg,
        rgba(139, 92, 246, 0.35) 0%,
        rgba(168, 85, 247, 0.25) 100%
      );
      border-radius: 3px;

      &:hover {
        background: linear-gradient(
          180deg,
          rgba(139, 92, 246, 0.5) 0%,
          rgba(168, 85, 247, 0.4) 100%
        );
      }
    }
  }

  .datasource-yet {
    padding-bottom: 0;
    height: auto;
    padding-top: 200px;

    .ed-empty__description {
      color: @dark-text-secondary;
    }
  }

  .datasource-yet_btn {
    height: auto !important;
    padding-top: 200px;
    padding-bottom: 0;

    .ed-empty__description {
      color: @dark-text-secondary;
    }
  }
}
</style>
