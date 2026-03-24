<script setup lang="ts">
import { Search } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus-secondary'
import ChatList from '@/views/chat/ChatList.vue'
import { useI18n } from 'vue-i18n'
import { computed, nextTick, ref } from 'vue'
import { Chat, chatApi, ChatInfo } from '@/api/chat.ts'
import { filter, includes } from 'lodash-es'
import ChatCreator from '@/views/chat/ChatCreator.vue'
import icon_sidebar_outlined from '@/assets/svg/icon_sidebar_outlined.svg'
import icon_new_chat_outlined from '@/assets/svg/icon_new_chat_outlined.svg'
import { useUserStore } from '@/stores/user'
import router from '@/router'
const userStore = useUserStore()
const props = withDefaults(
  defineProps<{
    inPopover?: boolean
    chatList?: Array<ChatInfo>
    currentChatId?: number
    currentChat?: ChatInfo
    loading?: boolean
    appName?: string
  }>(),
  {
    chatList: () => [],
    currentChatId: undefined,
    currentChat: () => new ChatInfo(),
    loading: false,
    inPopover: false,
    appName: '',
  }
)

const emits = defineEmits([
  'goEmpty',
  'onChatCreated',
  'onClickHistory',
  'onChatDeleted',
  'onChatRenamed',
  'onClickSideBarBtn',
  'update:loading',
  'update:chatList',
  'update:currentChat',
  'update:currentChatId',
])

const isCompletePage = ref(true)

const search = ref<string>()

const _currentChatId = computed({
  get() {
    return props.currentChatId
  },
  set(v) {
    emits('update:currentChatId', v)
  },
})
const _currentChat = computed({
  get() {
    return props.currentChat
  },
  set(v) {
    emits('update:currentChat', v)
  },
})

const _chatList = computed({
  get() {
    return props.chatList
  },
  set(v) {
    emits('update:chatList', v)
  },
})

const computedChatList = computed<Array<ChatInfo>>(() => {
  if (search.value && search.value.length > 0) {
    return filter(_chatList.value, (c) =>
      includes(c.brief?.toLowerCase(), search.value?.toLowerCase())
    )
  } else {
    return _chatList.value
  }
})

const _loading = computed({
  get() {
    return props.loading
  },
  set(v) {
    emits('update:loading', v)
  },
})

const { t } = useI18n()

function onClickSideBarBtn() {
  emits('onClickSideBarBtn')
}

function onChatCreated(chat: ChatInfo) {
  _chatList.value.unshift(chat)
  _currentChatId.value = chat.id
  _currentChat.value = chat
  emits('onChatCreated', chat)
}

const chatCreatorRef = ref()

function goEmpty(func?: (...p: any[]) => void, ...params: any[]) {
  _currentChat.value = new ChatInfo()
  _currentChatId.value = undefined
  emits('goEmpty', func, ...params)
}

const createNewChat = async () => {
  try {
    await chatApi.checkLLMModel()
  } catch (error: any) {
    let errorMsg = t('model.default_miss')
    let confirm_text = t('datasource.got_it')
    if (userStore.isAdmin) {
      errorMsg = t('model.default_miss_admin')
      confirm_text = t('model.to_config')
    }
    ElMessageBox.confirm(t('qa.ask_failed'), {
      confirmButtonType: 'primary',
      tip: errorMsg,
      showCancelButton: userStore.isAdmin,
      confirmButtonText: confirm_text,
      cancelButtonText: t('common.cancel'),
      customClass: 'confirm-no_icon',
      autofocus: false,
      showClose: false,
      callback: (val: string) => {
        if (userStore.isAdmin && val === 'confirm') {
          router.push('/system/model')
        }
      },
    })
    return
  }
  goEmpty(doCreateNewChat)
}

async function doCreateNewChat() {
  if (!isCompletePage.value) {
    return
  }
  chatCreatorRef.value?.showDs()
}

function onClickHistory(chat: Chat) {
  if (chat !== undefined && chat.id !== undefined) {
    if (_currentChatId.value === chat.id) {
      return
    }
    // 直接加载历史记录，不清空界面
    goHistory(chat)
  }
}

function goHistory(chat: Chat) {
  if (chat !== undefined && chat.id !== undefined) {
    // 切换对话时保持loading状态，避免显示首页
    _loading.value = true
    
    // 先清空当前聊天数据再更新 ID，避免旧数据短暂渲染导致的数据混乱
    // 这确保 computedMessages 在 API 返回前为空，不会渲染旧聊天的消息
    _currentChat.value = new ChatInfo()
    _currentChatId.value = chat.id
    
    chatApi
      .get(chat.id)
      .then((res) => {
        const info = chatApi.toChatInfo(res)
        // 只有当 chat.id 仍然是当前选中的对话时，才更新数据（避免快速切换时的数据错乱）
        if (info && info.id === _currentChatId.value) {
          _currentChat.value = info
          emits('onClickHistory', info)
        }
      })
      .catch(() => {
        ElMessage({ type: 'error', message: t('qa.load_chat_failed') })
      })
      .finally(() => {
        _loading.value = false
      })
  }
}

function onChatDeleted(id: number) {
  for (let i = 0; i < _chatList.value.length; i++) {
    if (_chatList.value[i].id === id) {
      _chatList.value.splice(i, 1)
      break
    }
  }
  if (id === _currentChatId.value) {
    goEmpty()
  }
  emits('onChatDeleted', id)
}

function onChatRenamed(chat: Chat) {
  _chatList.value.forEach((c: Chat) => {
    if (c.id === chat.id) {
      c.brief = chat.brief
    }
  })
  if (_currentChat.value.id === chat.id) {
    _currentChat.value.brief = chat.brief
  }
  emits('onChatRenamed', chat)
}
</script>

<template>
  <el-container class="chat-container-right-container">
    <el-header class="chat-list-header" :class="{ 'in-popover': inPopover }">
      <div v-if="!inPopover" class="title">
        <div class="chatbi-page-title sidebar-chat-title">
          <span class="title-text">{{ appName || t('qa.title') }}</span>
        </div>
      </div>
      <el-button class="btn" type="primary" @click="createNewChat">
        <el-icon style="margin-right: 6px">
          <icon_new_chat_outlined />
        </el-icon>
        {{ t('qa.new_chat') }}
      </el-button>
      <el-input
        v-model="search"
        :prefix-icon="Search"
        class="search"
        name="quick-search"
        autocomplete="off"
        :placeholder="t('qa.chat_search')"
        clearable
      />
    </el-header>
    <el-main class="chat-list">
      <div v-if="!computedChatList.length" class="empty-search">
        {{ !!search ? $t('datasource.relevant_content_found') : $t('dashboard.no_chat') }}
      </div>
      <ChatList
        v-else
        v-model:loading="_loading"
        :current-chat-id="_currentChatId"
        :chat-list="computedChatList"
        @chat-selected="onClickHistory"
        @chat-deleted="onChatDeleted"
        @chat-renamed="onChatRenamed"
      />
    </el-main>

    <ChatCreator v-if="isCompletePage" ref="chatCreatorRef" @on-chat-created="onChatCreated" />
  </el-container>
</template>

<style scoped lang="less">
// ============================================
// ChatBI 聊天列表容器 - 高级亮眼深色主题
// ============================================

// 主色调 - 更鲜艳的紫色系
@bg-deep: #0a0812;
@bg-main: #0f0c18;
@accent-bright: #c084fc; // 更亮的紫色
@accent-purple: #a855f7;
@accent-violet: #8b5cf6;
@accent-glow: #d8b4fe; // 发光色
@text-bright: #ffffff;
@text-primary: #f1f5f9;
@text-secondary: rgba(241, 245, 249, 0.7);
@text-muted: rgba(241, 245, 249, 0.4);
@border-glow: rgba(192, 132, 252, 0.3);
@border-subtle: rgba(139, 92, 246, 0.15);

.chat-container-right-container {
  background: linear-gradient(170deg, #12101c 0%, @bg-deep 100%);
  height: 100%;
  position: relative;
  overflow: hidden;

  // 顶部发光效果 - 更明显
  &::before {
    content: '';
    position: absolute;
    top: -100px;
    left: 50%;
    transform: translateX(-50%);
    width: 300%;
    height: 300px;
    background: radial-gradient(
      ellipse 50% 80% at 50% 0%,
      rgba(168, 85, 247, 0.22) 0%,
      rgba(139, 92, 246, 0.1) 40%,
      transparent 70%
    );
    pointer-events: none;
    z-index: 0;
  }

  // 右边缘发光线 - 更亮
  &::after {
    content: '';
    position: absolute;
    top: 0;
    right: 0;
    width: 1px;
    height: 100%;
    background: linear-gradient(
      180deg,
      rgba(192, 132, 252, 0.55) 0%,
      rgba(168, 85, 247, 0.35) 30%,
      rgba(139, 92, 246, 0.18) 60%,
      rgba(168, 85, 247, 0.45) 100%
    );
    pointer-events: none;
    z-index: 2;
  }

  // 侧边栏折叠按钮
  // 头部区域
  .chat-list-header {
    --ed-header-padding: 18px;
    --ed-header-height: calc(22px + 42px + 16px + 52px + 14px + 46px + 22px);
    position: relative;
    z-index: 1;
    padding-top: 22px;
    padding-bottom: 22px;

    &.in-popover {
      --ed-header-height: calc(22px + 52px + 14px + 46px + 22px);
    }

    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    gap: 14px;
    border-bottom: 1px solid @border-subtle;
    background: transparent;

    // 标题栏 - 使用全局 .chatbi-page-title，统一尺寸
    .title {
      width: 100%;
      display: flex;
      flex-direction: row;
      align-items: center;
      justify-content: space-between;
      position: relative;
      padding-bottom: 10px;

      .sidebar-chat-title {
        padding: 4px 0 8px 0 !important;
      }
    }

    // 新建对话按钮 - 简洁高级
    .btn {
      width: 100%;
      height: 42px;
      padding: 0 20px;
      border-radius: 10px !important;
      font-size: 14px;
      font-weight: 500;
      letter-spacing: 0.3px;
      background: linear-gradient(
        135deg,
        @accent-violet 0%,
        @accent-purple 100%
      ) !important;
      border: 1px solid rgba(216, 180, 254, 0.25) !important;
      color: #ffffff !important;
      transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
      box-shadow: 0 2px 8px rgba(168, 85, 247, 0.3);
      position: relative;
      overflow: hidden;

      :deep(span),
      :deep(.ed-button__text) {
        white-space: nowrap !important;
        color: #ffffff !important;
        position: relative;
        z-index: 1;
      }

      :deep(.ed-icon) {
        color: #ffffff !important;
        position: relative;
        z-index: 1;
      }

      &:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 16px rgba(168, 85, 247, 0.4);
        border-color: rgba(216, 180, 254, 0.4) !important;
      }

      &:active {
        transform: translateY(0);
        box-shadow: 0 1px 4px rgba(168, 85, 247, 0.3);
      }
    }

    // 搜索框 - 清晰可读
    .search {
      height: 46px;
      width: 100%;

      :deep(.ed-input__wrapper) {
        height: 46px;
        background: linear-gradient(
          145deg,
          rgba(139, 92, 246, 0.1) 0%,
          rgba(168, 85, 247, 0.06) 100%
        );
        border: 1.5px solid rgba(139, 92, 246, 0.25);
        border-radius: 14px;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        padding: 0 16px;

        &:hover {
          border-color: rgba(168, 85, 247, 0.4);
          background: linear-gradient(
            145deg,
            rgba(139, 92, 246, 0.14) 0%,
            rgba(168, 85, 247, 0.08) 100%
          );
        }

        &:focus-within {
          border-color: @accent-purple;
          background: linear-gradient(
            145deg,
            rgba(139, 92, 246, 0.18) 0%,
            rgba(168, 85, 247, 0.1) 100%
          );
          box-shadow: 0 0 0 4px rgba(139, 92, 246, 0.12);
        }
      }

      :deep(.ed-input__prefix) {
        color: rgba(192, 132, 252, 0.85);
        margin-right: 12px;
      }

      :deep(.ed-input__inner) {
        height: 44px;
        color: #ffffff;
        font-size: 14px;
        font-weight: 400;
        letter-spacing: 0.2px;

        &::placeholder {
          color: rgba(192, 132, 252, 0.65);
          font-weight: 400;
        }
      }

      :deep(.ed-input__suffix) {
        .ed-input__clear {
          color: rgba(192, 132, 252, 0.55);

          &:hover {
            color: rgba(216, 180, 254, 0.95);
          }
        }
      }
    }
  }

  // 聊天列表区域
  .chat-list {
    padding: 18px 0 26px 0;
    background: transparent;
    position: relative;
    z-index: 1;

    // 自定义滚动条 - 紫色发光
    :deep(.ed-scrollbar) {
      .ed-scrollbar__bar {
        &.is-vertical {
          width: 6px;
          right: 3px;

          .ed-scrollbar__thumb {
            background: linear-gradient(180deg, @accent-bright 0%, @accent-violet 100%);
            border-radius: 3px;
            opacity: 0.55;

            &:hover {
              opacity: 1;
              box-shadow: 0 0 10px rgba(168, 85, 247, 0.55);
            }
          }
        }
      }
    }

    // 空状态
    .empty-search {
      width: 100%;
      text-align: center;
      margin-top: 80px;
      color: rgba(192, 132, 252, 0.45);
      font-weight: 500;
      font-size: 14px;
      line-height: 24px;
    }
  }
}

// 响应式
@media (max-width: 768px) {
  .chat-container-right-container {
    .chat-list-header {
      --ed-header-padding: 14px;
      padding-top: 18px;
      padding-bottom: 18px;
      gap: 12px;

      .btn {
        height: 48px;
        font-size: 14px;
        border-radius: 14px;
      }

      .search {
        height: 44px;

        :deep(.ed-input__wrapper) {
          height: 44px;
          border-radius: 12px;
        }

        :deep(.ed-input__inner) {
          height: 42px;
          font-size: 13px;
        }
      }
    }
  }
}
</style>
