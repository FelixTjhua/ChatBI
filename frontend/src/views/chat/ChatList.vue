<script setup lang="ts">
// import icon_more_outlined from '@/assets/svg/icon_more_outlined.svg'
import icon_expand_down_filled from '@/assets/embedded/icon_expand-down_filled.svg'
import { ElMessageBox } from 'element-plus-secondary'
import rename from '@/assets/svg/icon_rename_outlined.svg'
import delIcon from '@/assets/svg/icon_delete.svg'
import { type Chat, chatApi } from '@/api/chat.ts'
import { computed, reactive, ref } from 'vue'
import dayjs from 'dayjs'
import { getDate } from '@/utils/utils.ts'
import { groupBy } from 'lodash-es'
import { useI18n } from 'vue-i18n'

const props = withDefaults(
  defineProps<{
    currentChatId?: number
    chatList: Array<Chat>
    loading?: boolean
  }>(),
  {
    currentChatId: undefined,
    chatList: () => [],
    loading: false,
  }
)

const { t } = useI18n()

// 处理聊天标题，如果是翻译键则翻译，否则直接返回
function getBriefText(brief: string | undefined): string {
  if (!brief) return t('qa.new_chat')
  
  // 修复旧版本的翻译键（没有下划线的情况）
  const keyMapping: Record<string, string> = {
    'chat.suggestions.top': 'chat.suggestions.top_records',
    'chat.suggestions.show': 'chat.suggestions.show_tables',
    'chat.suggestions.count': 'chat.suggestions.count_records',
    'chat.suggestions.table': 'chat.suggestions.table_structure',
  }
  
  let translationKey = brief
  
  // 如果是已知的旧键，映射到新键
  if (keyMapping[brief]) {
    translationKey = keyMapping[brief]
  }
  
  // 检查是否是翻译键（包含点号且以 chat. 或 qa. 等开头）
  if (translationKey.includes('.') && (translationKey.startsWith('chat.') || translationKey.startsWith('qa.') || translationKey.startsWith('datasource.'))) {
    // 尝试翻译，如果翻译键不存在则返回原文
    const translated = t(translationKey)
    return translated === translationKey ? brief : translated
  }
  
  return brief
}

function groupByDate(chat: Chat) {
  const todayStart = dayjs(dayjs().format('YYYY-MM-DD') + ' 00:00:00').toDate()
  const todayEnd = dayjs(dayjs().format('YYYY-MM-DD') + ' 23:59:59').toDate()
  const weekStart = dayjs(dayjs().subtract(7, 'day').format('YYYY-MM-DD') + ' 00:00:00').toDate()

  const time = getDate(chat.create_time)

  if (time) {
    if (time >= todayStart && time <= todayEnd) {
      return t('qa.today')
    }
    if (time < todayStart && time >= weekStart) {
      return t('qa.week')
    }
    if (time < weekStart) {
      return t('qa.earlier')
    }
  }

  return t('qa.no_time')
}

const computedChatGroup = computed(() => {
  return groupBy(props.chatList, groupByDate)
})

const expandMap = ref({
  [t('qa.today')]: true,
  [t('qa.week')]: true,
  [t('qa.earlier')]: true,
  [t('qa.no_time')]: true,
})

const computedChatList = computed(() => {
  const _list = []
  if (computedChatGroup.value[t('qa.today')]) {
    _list.push({
      key: t('qa.today'),
      list: computedChatGroup.value[t('qa.today')],
    })
  }
  if (computedChatGroup.value[t('qa.week')]) {
    _list.push({
      key: t('qa.week'),
      list: computedChatGroup.value[t('qa.week')],
    })
  }
  if (computedChatGroup.value[t('qa.earlier')]) {
    _list.push({
      key: t('qa.earlier'),
      list: computedChatGroup.value[t('qa.earlier')],
    })
  }
  if (computedChatGroup.value[t('qa.no_time')]) {
    _list.push({
      key: t('qa.no_time'),
      list: computedChatGroup.value[t('qa.no_time')],
    })
  }

  return _list
})

const emits = defineEmits(['chatSelected', 'chatRenamed', 'chatDeleted', 'update:loading'])

const _loading = computed({
  get() {
    return props.loading
  },
  set(v) {
    emits('update:loading', v)
  },
})

function onClickHistory(chat: Chat) {
  emits('chatSelected', chat)
}

function handleCommand(command: string | number | object, chat: Chat) {
  if (chat && chat.id !== undefined) {
    switch (command) {
      case 'rename':
        password.id = chat.id
        password.name = chat.brief as string
        dialogVisiblePassword.value = true
        break
      case 'delete':
        ElMessageBox.confirm(t('common.confirm_delete_chat', { msg: chat.brief }), {
          confirmButtonType: 'danger',
          tip: t('common.proceed_with_caution'),
          confirmButtonText: t('dashboard.delete'),
          cancelButtonText: t('common.cancel'),
          customClass: 'confirm-no_icon',
          showClose: false,
          autofocus: false,
        }).then(() => {
          _loading.value = true
          chatApi
            .deleteChat(chat.id)
            .then(() => {
              ElMessage({
                type: 'success',
                message: t('dashboard.delete_success'),
              })
              emits('chatDeleted', chat.id)
            })
            .catch((err) => {
              ElMessage({
                type: 'error',
                message: err.message,
              })
            })
            .finally(() => {
              _loading.value = false
            })
        }).catch(() => {})

        break
    }
  }
}

const passwordRef = ref()
const dialogVisiblePassword = ref(false)
const password = reactive({
  name: '',
  id: 0,
})

const passwordRules = {
  name: [
    {
      required: true,
      message: t('datasource.please_enter') + t('common.empty') + t('qa.conversation_title'),
      trigger: 'blur',
    },
  ],
}

const handleClosePassword = () => {
  passwordRef.value.clearValidate()
  dialogVisiblePassword.value = false
  password.id = 0
  password.name = ''
}
const handleConfirmPassword = () => {
  passwordRef.value.validate((res: any) => {
    if (res) {
      chatApi
        .renameChat(password.id, password.name)
        .then((res) => {
          ElMessage({
            type: 'success',
            message: t('common.save_success'),
          })
          emits('chatRenamed', { id: password.id, brief: res })
          handleClosePassword()
        })
        .catch((err) => {
          ElMessage({
            type: 'error',
            message: err.message,
          })
        })
        .finally(() => {
          _loading.value = false
        })
    }
  })
}
</script>

<template>
  <el-scrollbar ref="chatListRef">
    <div class="chat-list-inner">
      <div v-for="group in computedChatList" :key="group.key" class="group">
        <div
          class="group-title"
          style="cursor: pointer"
          @click="expandMap[group.key] = !expandMap[group.key]"
        >
          <el-icon :class="!expandMap[group.key] && 'expand'" style="margin-right: 8px" size="10">
            <icon_expand_down_filled></icon_expand_down_filled>
          </el-icon>
          {{ group.key }}
        </div>
        <template v-for="chat in group.list" :key="chat.id">
          <div
            class="chat-list-item"
            :class="{ active: currentChatId === chat.id, hide: !expandMap[group.key] }"
            @click="onClickHistory(chat)"
          >
            <span class="title">{{ getBriefText(chat.brief) }}</span>
            <div class="action-buttons">
              <el-tooltip :content="t('common.rename')" placement="top" :show-after="500">
                <div class="action-btn rename-btn" @click.stop="handleCommand('rename', chat)">
                  <el-icon :size="16">
                    <rename />
                  </el-icon>
                </div>
              </el-tooltip>
              <el-tooltip :content="t('common.delete')" placement="top" :show-after="500">
                <div class="action-btn delete-btn" @click.stop="handleCommand('delete', chat)">
                  <el-icon :size="16">
                    <delIcon />
                  </el-icon>
                </div>
              </el-tooltip>
            </div>
          </div>
        </template>
      </div>
    </div>
  </el-scrollbar>
  <el-dialog
    v-model="dialogVisiblePassword"
    :title="$t('qa.rename_conversation_title')"
    width="420"
    :before-close="handleClosePassword"
    append-to-body
  >
    <el-form
      ref="passwordRef"
      :model="password"
      label-width="180px"
      label-position="top"
      :rules="passwordRules"
      class="form-content_error"
      @submit.prevent
    >
      <el-form-item prop="name" :label="t('qa.conversation_title')">
        <el-input
          v-model="password.name"
          maxlength="20"
          :placeholder="
            $t('datasource.please_enter') + $t('common.empty') + $t('qa.conversation_title')
          "
          clearable
          autocomplete="off"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <div class="dialog-footer">
        <el-button secondary @click="handleClosePassword">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" @click="handleConfirmPassword">
          {{ $t('common.save') }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped lang="less">
// ============================================
// ChatBI 聊天列表项 - 高级亮眼深色主题
// ============================================

// 主色调 - 清晰可读
@accent-bright: #c084fc;
@accent-purple: #a855f7;
@accent-violet: #8b5cf6;
@accent-glow: #d8b4fe;
@text-bright: #ffffff;
@text-primary: #f8fafc;
@text-secondary: rgba(255, 255, 255, 0.9);
@text-label: rgba(192, 132, 252, 0.9);
@border-glow: rgba(192, 132, 252, 0.3);
@border-subtle: rgba(168, 85, 247, 0.15);

.chat-list-inner {
  padding: 0 8px;
  width: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 18px;

  .group {
    display: flex;
    flex-direction: column;

    // 分组标题 - 清晰可见
    .group-title {
      padding: 0 14px;
      margin-bottom: 10px;
      color: @text-label;
      line-height: 16px;
      font-weight: 600;
      font-size: 11px;
      letter-spacing: 0.8px;
      text-transform: uppercase;
      display: flex;
      align-items: center;
      cursor: pointer;
      transition: all 0.2s ease;

      &:hover {
        color: @accent-glow;
      }

      .expand {
        transform: rotate(-90deg);
      }

      .ed-icon {
        transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        color: rgba(192, 132, 252, 0.7);
      }
    }
  }

  // 聊天列表项
  .chat-list-item {
    width: 100%;
    height: 52px;
    border-radius: 12px;
    line-height: 22px;
    font-size: 14px;
    font-weight: 400;
    margin-bottom: 4px;
    color: rgba(255, 255, 255, 0.88);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 8px 0 14px;
    gap: 8px;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    background: transparent;
    border: 1px solid transparent;
    position: relative;
    box-sizing: border-box;
    cursor: pointer;

    // 悬停背景层
    &::after {
      content: '';
      position: absolute;
      inset: 0;
      background: linear-gradient(
        135deg,
        rgba(139, 92, 246, 0.12) 0%,
        rgba(168, 85, 247, 0.08) 100%
      );
      opacity: 0;
      transition: opacity 0.2s ease;
      pointer-events: none;
      border-radius: 12px;
      z-index: 0;
    }

    .title {
      flex: 1;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      position: relative;
      z-index: 1;
      pointer-events: none;
    }

    // 操作按钮组
    .action-buttons {
      flex-shrink: 0;
      display: flex;
      align-items: center;
      gap: 4px;
      position: relative;
      z-index: 10;
      opacity: 0;
      transition: opacity 0.2s ease;
      pointer-events: auto;

      .action-btn {
        width: 28px;
        height: 28px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 6px;
        cursor: pointer;
        transition: all 0.2s ease;
        background: transparent;
        pointer-events: auto;

        .el-icon,
        .ed-icon {
          transition: all 0.2s ease;
          pointer-events: none;
        }
      }

      .rename-btn {
        .el-icon,
        .ed-icon {
          color: rgba(139, 185, 255, 0.9);
        }

        &:hover {
          background: rgba(59, 130, 246, 0.2);
          transform: scale(1.08);

          .el-icon,
          .ed-icon {
            color: rgb(139, 185, 255);
          }
        }

        &:active {
          transform: scale(0.95);
        }
      }

      .delete-btn {
        .el-icon,
        .ed-icon {
          color: rgba(248, 113, 113, 0.9);
        }

        &:hover {
          background: rgba(239, 68, 68, 0.2);
          transform: scale(1.08);

          .el-icon,
          .ed-icon {
            color: rgb(248, 113, 113);
          }
        }

        &:active {
          transform: scale(0.95);
        }
      }
    }

    // 悬停状态
    &:hover {
      border-color: rgba(139, 92, 246, 0.22);
      color: #ffffff;
      transform: translateX(2px);

      &::after {
        opacity: 1;
      }

      .action-buttons {
        opacity: 1;
        pointer-events: auto;
      }
    }

    // 选中状态
    &.active {
      background: linear-gradient(
        135deg,
        rgba(139, 92, 246, 0.2) 0%,
        rgba(124, 58, 237, 0.14) 100%
      );
      border-color: rgba(168, 85, 247, 0.35);
      color: #ffffff;
      font-weight: 500;
      box-shadow: 0 4px 16px rgba(139, 92, 246, 0.15);

      // 左侧指示条
      &::before {
        content: '';
        position: absolute;
        left: 0;
        top: 50%;
        transform: translateY(-50%);
        width: 3px;
        height: 24px;
        background: linear-gradient(180deg, @accent-bright 0%, @accent-violet 100%);
        border-radius: 0 3px 3px 0;
        box-shadow: 0 0 12px rgba(192, 132, 252, 0.5);
        z-index: 1;
        pointer-events: none;
      }

      &::after {
        opacity: 0;
      }

      .action-buttons {
        opacity: 1;
        pointer-events: auto;
      }
    }

    &.hide {
      display: none;
    }
  }
}
</style>


