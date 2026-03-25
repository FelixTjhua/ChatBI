<template>
  <el-container class="chat-container no-padding">
    <el-aside
      v-if="chatListSideBarShow"
      class="chat-container-left"
      :class="{ 'embedded-history-hidden': embeddedHistoryHidden }"
    >
      <ChatListContainer
        v-model:chat-list="chatList"
        v-model:current-chat-id="currentChatId"
        v-model:current-chat="currentChat"
        v-model:loading="loading"
        :in-popover="!chatListSideBarShow"
        :app-name="customName"
        @go-empty="goEmpty"
        @on-chat-created="onChatCreated"
        @on-click-history="onClickHistory"
        @on-chat-deleted="onChatDeleted"
        @on-chat-renamed="onChatRenamed"
        @on-click-side-bar-btn="hideSideBar"
      />
    </el-aside>


    <el-container :loading="loading">
      <el-main
        class="chat-record-list"
        :class="{
          'hide-sidebar': !chatListSideBarShow,
          'welcome-mode': computedMessages.length == 0 && !loading && isCompletePage,
        }"
      >
        <!-- 页面标题已删除 -->
        
        <!-- 侧边栏切换按钮 - 只在有对话时显示 -->
        <transition name="fade-slide">
          <div
            v-if="computedMessages.length > 0"
            class="sidebar-toggle-btn"
            :class="{ 'sidebar-hidden': !chatListSideBarShow }"
            @click="toggleSideBar"
          >
            <div class="toggle-btn-inner">
              <svg
                v-if="chatListSideBarShow"
                class="toggle-icon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                <line x1="9" y1="3" x2="9" y2="21"></line>
                <line x1="14" y1="8" x2="14" y2="16"></line>
                <line x1="14" y1="8" x2="18" y2="12"></line>
                <line x1="14" y1="16" x2="18" y2="12"></line>
              </svg>
              <svg
                v-else
                class="toggle-icon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                <line x1="9" y1="3" x2="9" y2="21"></line>
                <line x1="14" y1="8" x2="14" y2="16"></line>
                <line x1="10" y1="12" x2="14" y2="8"></line>
                <line x1="10" y1="12" x2="14" y2="16"></line>
              </svg>
            </div>
            <div class="toggle-tooltip">
              {{ chatListSideBarShow ? t('qa.hide_history') : t('qa.show_history') }}
            </div>
          </div>
        </transition>
        
        <div v-if="computedMessages.length == 0 && !loading && currentChatId === undefined" class="welcome-content-block">
          <div class="welcome-content">
            <template v-if="isCompletePage">
              <!-- 简洁高级背景 -->
              <div class="welcome-bg">
                <div class="bg-gradient"></div>
                <div class="bg-glow"></div>
              </div>

              <!-- 主内容 -->
              <div class="welcome-main">
                <!-- 品牌标识 -->
                <div class="brand-section">
                  <h1 class="brand-title">
                    <span class="brand-chat">Chat</span><span class="brand-bi">BI</span>
                  </h1>
                  <p class="brand-tagline">{{ t('qa.tagline_tech') }}</p>
                  <p class="brand-slogan">{{ t('qa.tagline_value') }}</p>
                </div>

                <!-- 核心流程 - 垂直布局 -->
                <div class="flow-vertical">
                  <div class="flow-step flow-step-highlight">
                    <div class="step-icon">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                        <path d="M8 9h8M8 13h6" />
                      </svg>
                    </div>
                    <div class="step-content">
                      <span class="step-title">{{ t('qa.flow_question') }}</span>
                      <span class="step-desc">{{ t('qa.flow_question_desc') }}</span>
                    </div>
                  </div>

                  <div class="flow-arrow-down">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M12 5v14M5 12l7 7 7-7" />
                    </svg>
                  </div>

                  <div class="flow-step flow-step-highlight">
                    <div class="step-icon">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <circle cx="11" cy="11" r="8" />
                        <path d="M21 21l-4.35-4.35" />
                        <path d="M11 8v6M8 11h6" />
                      </svg>
                    </div>
                    <div class="step-content">
                      <span class="step-title">{{ t('qa.flow_retrieve') }}</span>
                      <span class="step-desc">{{ t('qa.flow_retrieve_desc') }}</span>
                    </div>
                  </div>

                  <div class="flow-arrow-down">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M12 5v14M5 12l7 7 7-7" />
                    </svg>
                  </div>

                  <div class="flow-step flow-step-highlight">
                    <div class="step-icon">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <rect x="3" y="3" width="18" height="18" rx="2" />
                        <path d="M3 9h18M9 21V9" />
                        <path d="M13 13h4M13 17h4" />
                      </svg>
                    </div>
                    <div class="step-content">
                      <span class="step-title">{{ t('qa.flow_output') }}</span>
                      <span class="step-desc">{{ t('qa.flow_output_desc') }}</span>
                    </div>
                  </div>
                </div>

                <!-- 开始按钮 -->
                <el-button
                  v-if="currentChatId === undefined"
                  size="large"
                  type="primary"
                  class="start-btn"
                  @click="createNewChatSimple"
                >
                  <span class="btn-content">
                    <span>{{ t('qa.start_chatbi') }}</span>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                      <path d="M5 12h14M12 5l7 7-7 7" />
                    </svg>
                  </span>
                </el-button>

                <!-- 底部提示 -->
                <p class="welcome-tip">{{ t('qa.welcome_hint') }}</p>
              </div>
            </template>

            <div v-else class="assistant-desc">
              <img
                v-if="logoAssistant"
                :src="logoAssistant"
                class="logo"
                width="30px"
                height="30px"
                alt=""
              />
              <el-icon v-else size="32">
                <logo_fold />
              </el-icon>
              <div class="i-am">{{ welcome }}</div>
              <div class="i-can">{{ welcomeDesc }}</div>
            </div>
          </div>
        </div>
        <div v-else-if="computedMessages.length == 0 && loading && currentChatId !== undefined" class="welcome-content-block">
          <div style="display: flex; align-items: center; height: 30px">
            <img
              v-if="logoAssistant || loginBg"
              height="30"
              width="30"
              :src="logoAssistant ? logoAssistant : loginBg"
              alt=""
            />
            <el-icon v-else size="30"
              ><custom_small v-if="appearanceStore.themeColor !== 'default'"></custom_small>
              <LOGO_fold v-else></LOGO_fold
            ></el-icon>
            <span style="margin-left: 12px">{{ t('qa.loading_chat') }}</span>
          </div>
        </div>
        <el-scrollbar
          v-if="computedMessages.length > 0"
          ref="chatListRef"
          class="no-horizontal"
          @scroll="handleScroll"
        >
          <div
            ref="innerRef"
            class="chat-scroll"
            :class="{
              'no-sidebar': isCompletePage && !chatListSideBarShow,
              pad16: !isCompletePage,
            }"
          >
            <template v-for="(message, _index) in computedMessages" :key="`${currentChatId}-${_index}-${message.role}`">
              <transition name="message-delete" mode="out-in">
                <ChatRow
                  v-if="!message.isDeleting"
                  :logo-assistant="logoAssistant"
                  :current-chat="currentChat"
                  :msg="message"
                  :is-recommend="message.first_chat"
                  :is-error="!!message.record?.error"
                >
                <RecommendQuestion
                  v-if="message.role === 'assistant' && message.first_chat"
                  ref="recommendQuestionRef"
                  :current-chat="currentChat"
                  :record-id="message.record?.id"
                  :questions="message.recommended_question"
                  :disabled="isTyping"
                  :first-chat="message.first_chat"
                  @click-question="quickAsk"
                  @stop="onChatStop"
                  @loading-over="loadingOver"
                />
                <UserChat v-if="message.role === 'user'" :message="message" />
                <template v-if="message.role === 'assistant' && !message.first_chat">
                  <ChartAnswer
                    v-if="
                      (message?.record?.analysis_record_id === undefined ||
                        message?.record?.analysis_record_id === null) &&
                      (message?.record?.predict_record_id === undefined ||
                        message?.record?.predict_record_id === null)
                    "
                    ref="chartAnswerRef"
                    :chat-list="chatList"
                    :current-chat="currentChat"
                    :current-chat-id="currentChatId"
                    :record-id="message.record?.id"
                    :loading="isTyping"
                    :message="message"
                    :reasoning-name="['sql_answer', 'chart_answer']"
                    :input-type="currentInputType"
                    @scroll-bottom="scrollToBottom"
                    @finish="onChartAnswerFinish"
                    @error="onChartAnswerError"
                    @stop="onChatStop"
                    @click-question="quickAsk"
                  >
                    <ErrorInfo :error="message.record?.error" class="error-container" />
                    <template #tool>
                      <ChatToolBar v-if="!message.isTyping" :message="message" @delete="deleteMessage">
                        <!-- 重新生成按钮 -->
                        <el-tooltip
                          effect="dark"
                          :offset="8"
                          :content="t('qa.ask_again_desc')"
                          placement="top"
                          :disabled="isTyping"
                        >
                          <template #default>
                            <el-button
                              class="tool-btn"
                              text
                              :disabled="isTyping"
                              @click="askAgain(message)"
                            >
                              <span class="tool-btn-inner">
                                <el-icon size="18">
                                  <icon_replace_outlined />
                                </el-icon>
                                <span class="btn-text">
                                  {{ t('qa.ask_again') }}
                                </span>
                              </span>
                            </el-button>
                          </template>
                        </el-tooltip>
                        <!-- 复制按钮 - smart_answer/direct_answer等有文字内容时显示 -->
                        <el-tooltip
                          v-if="hasCopyableContent(message.record)"
                          effect="dark"
                          :offset="8"
                          :content="t('qa.copy_content')"
                          placement="top"
                        >
                          <template #default>
                            <el-button
                              class="tool-btn"
                              :class="{ 'is-copied': copiedMessageId === message.record?.id }"
                              text
                              @click="copyAnswer(message)"
                            >
                              <span class="tool-btn-inner">
                                <el-icon size="18">
                                  <icon_copy_outlined v-if="copiedMessageId !== message.record?.id" />
                                  <span v-else class="check-icon">✓</span>
                                </el-icon>
                                <span class="btn-text">
                                  {{ copiedMessageId === message.record?.id ? t('qa.copied') : t('qa.copy_content') }}
                                </span>
                              </span>
                            </el-button>
                          </template>
                        </el-tooltip>
                      </ChatToolBar>
                    </template>
                    <template #footer>
                      <RecommendQuestion
                        ref="recommendQuestionRef"
                        :current-chat="currentChat"
                        :record-id="message.record?.id"
                        :questions="message.recommended_question"
                        :first-chat="message.first_chat"
                        :disabled="isTyping"
                        @click-question="quickAsk"
                        @loading-over="loadingOver"
                        @stop="onChatStop"
                      />
                    </template>
                  </ChartAnswer>
                  <AnalysisAnswer
                    v-if="
                      message?.record?.analysis_record_id !== undefined &&
                      message?.record?.analysis_record_id !== null
                    "
                    ref="analysisAnswerRef"
                    :chat-list="chatList"
                    :current-chat="currentChat"
                    :current-chat-id="currentChatId"
                    :loading="isTyping"
                    :message="message"
                    @finish="onAnalysisAnswerFinish"
                    @error="onAnalysisAnswerError"
                    @stop="onChatStop"
                  >
                    <ErrorInfo :error="message.record?.error" class="error-container" />
                    <template #tool>
                      <ChatToolBar v-if="!message.isTyping" :message="message" @delete="deleteMessage">
                        <el-tooltip
                          effect="dark"
                          :offset="8"
                          :content="t('qa.ask_again_desc')"
                          placement="top"
                          :disabled="isTyping"
                        >
                          <template #default>
                            <el-button
                              class="tool-btn"
                              text
                              :disabled="isTyping"
                              @click="askAgainAnalysis(message)"
                            >
                              <span class="tool-btn-inner">
                                <el-icon size="18">
                                  <icon_replace_outlined />
                                </el-icon>
                                <span class="btn-text">
                                  {{ t('qa.ask_again') }}
                                </span>
                              </span>
                            </el-button>
                          </template>
                        </el-tooltip>
                        <!-- 复制按钮 - 只在有文字内容时显示 -->
                        <el-tooltip
                          v-if="hasCopyableContent(message.record)"
                          effect="dark"
                          :offset="8"
                          :content="t('qa.copy_content')"
                          placement="top"
                        >
                          <template #default>
                            <el-button
                              class="tool-btn"
                              :class="{ 'is-copied': copiedMessageId === message.record?.id }"
                              text
                              @click="copyAnswer(message)"
                            >
                              <span class="tool-btn-inner">
                                <el-icon size="18">
                                  <icon_copy_outlined v-if="copiedMessageId !== message.record?.id" />
                                  <span v-else class="check-icon">✓</span>
                                </el-icon>
                                <span class="btn-text">
                                  {{ copiedMessageId === message.record?.id ? t('qa.copied') : t('qa.copy_content') }}
                                </span>
                              </span>
                            </el-button>
                          </template>
                        </el-tooltip>
                      </ChatToolBar>
                    </template>
                  </AnalysisAnswer>
                  <PredictAnswer
                    v-if="
                      message?.record?.predict_record_id !== undefined &&
                      message?.record?.predict_record_id !== null
                    "
                    ref="predictAnswerRef"
                    :chat-list="chatList"
                    :current-chat="currentChat"
                    :current-chat-id="currentChatId"
                    :record-id="message.record?.id"
                    :loading="isTyping"
                    :message="message"
                    @scroll-bottom="scrollToBottom"
                    @finish="onPredictAnswerFinish"
                    @error="onPredictAnswerError"
                    @stop="onChatStop"
                  >
                    <ErrorInfo :error="message.record?.error" class="error-container" />
                    <template #tool>
                      <ChatToolBar v-if="!message.isTyping" :message="message" @delete="deleteMessage">
                        <el-tooltip
                          effect="dark"
                          :offset="8"
                          :content="t('qa.ask_again_desc')"
                          placement="top"
                          :disabled="isTyping"
                        >
                          <template #default>
                            <el-button
                              class="tool-btn"
                              text
                              :disabled="isTyping"
                              @click="askAgainPredict(message)"
                            >
                              <span class="tool-btn-inner">
                                <el-icon size="18">
                                  <icon_replace_outlined />
                                </el-icon>
                                <span class="btn-text">
                                  {{ t('qa.ask_again') }}
                                </span>
                              </span>
                            </el-button>
                          </template>
                        </el-tooltip>
                        <!-- 复制按钮 - 只在有文字内容时显示 -->
                        <el-tooltip
                          v-if="hasCopyableContent(message.record)"
                          effect="dark"
                          :offset="8"
                          :content="t('qa.copy_content')"
                          placement="top"
                        >
                          <template #default>
                            <el-button
                              class="tool-btn"
                              :class="{ 'is-copied': copiedMessageId === message.record?.id }"
                              text
                              @click="copyAnswer(message)"
                            >
                              <span class="tool-btn-inner">
                                <el-icon size="18">
                                  <icon_copy_outlined v-if="copiedMessageId !== message.record?.id" />
                                  <span v-else class="check-icon">✓</span>
                                </el-icon>
                                <span class="btn-text">
                                  {{ copiedMessageId === message.record?.id ? t('qa.copied') : t('qa.copy_content') }}
                                </span>
                              </span>
                            </el-button>
                          </template>
                        </el-tooltip>
                      </ChatToolBar>
                    </template>
                  </PredictAnswer>
                </template>
              </ChatRow>
              </transition>
            </template>
          </div>
        </el-scrollbar>
      </el-main>
      <el-footer v-if="computedMessages.length > 0 || !isCompletePage" class="chat-footer">
        <div class="input-wrapper">
          <!-- 数据源标签 + 关键词提示 -->
          <div class="input-top-bar">
            <div v-if="isCompletePage && currentChat.datasource" class="datasource-badge">
              <div class="badge-glow"></div>
              <div class="badge-content">
                <img
                  v-if="currentChatEngineType && currentChat.datasource_exists !== false"
                  :src="currentChatEngineType"
                  width="18px"
                  height="18px"
                  alt=""
                  class="ds-icon"
                />
                <span class="ds-indicator" v-else>🗄️</span>
                <span
                  class="ds-name"
                  :class="{ 'ds-not-exist': currentChat.datasource_exists === false }"
                >
                  {{
                    currentChat.datasource_exists === false
                      ? t('qa.datasource_not_exist')
                      : currentChat.datasource_name
                  }}
                </span>
              </div>
            </div>

            <!-- 关键词提示按钮 -->
            <el-popover
              v-model:visible="keywordHintsVisible"
              placement="top-end"
              :width="340"
              trigger="click"
              popper-class="keyword-hints-popover"
            >
              <template #reference>
                <button
                  class="action-btn keyword-btn"
                  :class="{ 'is-active': keywordHintsVisible }"
                  @click.stop
                >
                  <div class="btn-bg"></div>
                  <svg class="btn-icon" viewBox="0 0 24 24" fill="none">
                    <!-- 灯泡外发光 -->
                    <circle cx="12" cy="10" r="8" fill="#FFD700" opacity="0.10" />
                    <circle cx="12" cy="10" r="6" fill="#FFD700" opacity="0.08" />
                    <!-- 灯泡主体 -->
                    <path d="M9 21h6M10 17h4" stroke="#FFD700" stroke-width="1.6" stroke-linecap="round"/>
                    <path d="M15.5 14.5c1.5-1.3 2.5-3.2 2.5-5.5a6 6 0 1 0-12 0c0 2.3 1 4.2 2.5 5.5.5.4.5.8.5 1.5h6c0-.7 0-1.1.5-1.5z" stroke="#FFD700" stroke-width="1.6" fill="#FFD700" fill-opacity="0.15" stroke-linejoin="round"/>
                    <!-- 灯丝高光 -->
                    <path d="M10 10.5c.5-1 1-1.5 2-1.5s1.5.5 2 1.5" stroke="#FFD700" stroke-width="1" stroke-linecap="round" opacity="0.7"/>
                  </svg>
                </button>
              </template>
              <div class="kw-hints-panel">
                <div class="kw-hints-header">
                  <span class="kw-hints-title">{{ t('qa.keyword_hints_title') }}</span>
                  <span class="kw-hints-desc">{{ t('qa.keyword_hints_desc') }}</span>
                </div>
                <div class="kw-hints-list">
                  <div
                    v-for="cat in keywordCategories"
                    :key="cat.key"
                    class="kw-cat-item"
                  >
                    <div class="kw-cat-header">
                      <span class="kw-cat-icon">{{ cat.icon }}</span>
                      <span class="kw-cat-name">{{ t(cat.label) }}</span>
                      <span class="kw-cat-intent">{{ t(cat.intent) }}</span>
                    </div>
                    <div class="kw-tag-list">
                      <span
                        v-for="kw in cat.keywords"
                        :key="kw"
                        class="kw-tag"
                        @click="insertKeyword(kw)"
                      >{{ kw }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </el-popover>
          </div>

          <!-- 主输入区域 - 现代化设计 -->
          <div class="input-main-container" :class="{ 'is-focused': inputFocused, 'is-typing': isTyping }">
            <!-- 装饰性边框光效 -->
            <div class="input-border-glow"></div>
            
            <!-- 输入框容器 -->
            <div class="input-inner" @click="clickInput">
              <el-input
                ref="inputRef"
                v-model="inputMessage"
                :disabled="isTyping"
                clearable
                class="input-area"
                :class="[!isCompletePage && 'is-assistant', isTyping && 'is-typing']"
                type="textarea"
                :autosize="{ minRows: 1, maxRows: 6 }"
                :placeholder="isTyping ? t('qa.wait_for_response') : t('qa.question_placeholder')"
                @focus="inputFocused = true"
                @blur="inputFocused = false"
                @keydown.enter.exact.prevent="($event: any) => sendMessage($event)"
                @keydown.ctrl.enter.exact.prevent="handleCtrlEnter"
              />

              <!-- 发送/停止按钮 -->
              <div class="action-btn-wrapper">
                <transition name="btn-switch" mode="out-in">
                  <button
                    v-if="!isTyping"
                    key="send"
                    class="action-btn send-btn"
                    :class="{ 'is-active': inputMessage.trim() }"
                    :disabled="!inputMessage.trim()"
                    @click.stop="sendMessage"
                  >
                    <div class="btn-bg"></div>
                    <svg class="btn-icon" viewBox="0 0 24 24" fill="none">
                      <path d="M22 2L11 13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                      <path d="M22 2L15 22L11 13L2 9L22 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                  </button>
                  <button
                    v-else
                    key="stop"
                    class="action-btn stop-btn"
                    @click.stop="stopAllGeneration"
                  >
                    <div class="btn-bg"></div>
                    <div class="stop-icon">
                      <span></span>
                    </div>
                  </button>
                </transition>
              </div>
            </div>
          </div>

          <!-- 快捷键提示 - 更简洁 -->
          <div class="input-shortcuts">
            <transition name="fade" mode="out-in">
              <div v-if="isTyping" key="typing" class="shortcuts-typing">
                <button class="shortcut-stop" @click="stopAllGeneration">
                  <kbd>Esc</kbd>
                  <span>{{ t('qa.stop_generating') }}</span>
                </button>
              </div>
              <div v-else key="normal" class="shortcuts-normal">
                <span class="shortcut-item">
                  <kbd>Enter</kbd>
                  <span>{{ t('qa.to_send') }}</span>
                </span>
                <span class="shortcut-divider">·</span>
                <span class="shortcut-item">
                  <kbd>Ctrl+Enter</kbd>
                  <span>{{ t('qa.to_newline') }}</span>
                </span>
              </div>
            </transition>
          </div>
        </div>
      </el-footer>
    </el-container>

    <ChatCreator v-if="isCompletePage" ref="chatCreatorRef" @on-chat-created="onChatCreatedQuick" />
    <ChatCreator ref="hiddenChatCreatorRef" hidden @on-chat-created="onChatCreatedQuick" />
  </el-container>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onBeforeUnmount, ref, watch, getCurrentInstance } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus-secondary'
import { chatApi, ChatInfo, type ChatMessage, ChatRecord } from '@/api/chat'
import ChatRow from './ChatRow.vue'
import ChartAnswer from './answer/ChartAnswer.vue'
import AnalysisAnswer from './answer/AnalysisAnswer.vue'
import PredictAnswer from './answer/PredictAnswer.vue'
import UserChat from './chat-block/UserChat.vue'
import RecommendQuestion from './RecommendQuestion.vue'
import ChatListContainer from './ChatListContainer.vue'
import ChatCreator from '@/views/chat/ChatCreator.vue'
import ErrorInfo from './ErrorInfo.vue'
import ChatToolBar from './ChatToolBar.vue'
import { getDsIcon } from '@/views/ds/js/ds-type'
import { useI18n } from 'vue-i18n'
import { find, forEach } from 'lodash-es'
import { validatePredictionAdvanced } from '@/utils/advancedPredictionValidator'
import { validateAnalysisData } from '@/utils/analysisValidator'
import custom_small from '@/assets/svg/logo-custom_small.svg'
import LOGO_fold from '@/assets/LOGO-fold.svg'
import icon_replace_outlined from '@/assets/svg/icon_replace_outlined.svg'
import icon_copy_outlined from '@/assets/svg/icon_copy_outlined.svg'
import logo_fold from '@/assets/svg/logo-custom_small.svg'
import { onClickOutside } from '@vueuse/core'
import { useClipboard } from '@vueuse/core'
import { useAppearanceStoreWithOut } from '@/stores/appearance'
import { useUserStore } from '@/stores/user'
import { debounce } from 'lodash-es'
import { isMobile } from '@/utils/utils'
import router from '@/router'
import { useRoute } from 'vue-router'
const route = useRoute()
const userStore = useUserStore()
const props = defineProps<{
  startChatDsId?: number
  welcomeDesc?: string
  logoAssistant?: string
  welcome?: string
  appName?: string
}>()
const floatPopoverRef = ref()
const floatPopoverVisible = ref(false)
const defaultFloatPopoverStyle = ref({
  padding: '0',
  height: '654px',
  border: '1px solid rgba(222, 224, 227, 1)',
  borderRadius: '6px',
})

const isCompletePage = true
const embeddedHistoryHidden = false
const customName = computed(() => {
  return ''
})
const { t } = useI18n()
const appContext = getCurrentInstance()?.appContext
const isPhone = computed(() => {
  return isMobile()
})
const inputMessage = ref('')
const inputFocused = ref(false)
const keywordHintsVisible = ref(false)

// 关键词分类 - 根据数据源类型动态显示
const splitKeywords = (text: string) => text.split(/[、,]\s*/).filter(Boolean)

const keywordCategories = computed(() => {
  const isPdf = currentChat.value?.ds_type === 'pdf'
  if (isPdf) {
    return [
      { key: 'pdf_qa', icon: '📄', label: 'qa.keyword_cat_pdf_qa', intent: 'qa.keyword_intent_pdf_qa', keywords: splitKeywords(t('qa.keyword_pdf_qa_examples')) },
    ]
  }
  return [
    { key: 'fact_query', icon: '🔍', label: 'qa.keyword_cat_fact_query', intent: 'qa.keyword_intent_fact_query', keywords: splitKeywords(t('qa.keyword_fact_query_examples')) },
    { key: 'statistical', icon: '📊', label: 'qa.keyword_cat_statistical', intent: 'qa.keyword_intent_statistical', keywords: splitKeywords(t('qa.keyword_statistical_examples')) },
    { key: 'compare', icon: '⚖️', label: 'qa.keyword_cat_compare', intent: 'qa.keyword_intent_compare', keywords: splitKeywords(t('qa.keyword_compare_examples')) },
    { key: 'trend', icon: '📈', label: 'qa.keyword_cat_trend', intent: 'qa.keyword_intent_trend', keywords: splitKeywords(t('qa.keyword_trend_examples')) },
    { key: 'predict', icon: '🔮', label: 'qa.keyword_cat_predict', intent: 'qa.keyword_intent_predict', keywords: splitKeywords(t('qa.keyword_predict_examples')) },
    { key: 'explain', icon: '💡', label: 'qa.keyword_cat_explain', intent: 'qa.keyword_intent_explain', keywords: splitKeywords(t('qa.keyword_explain_examples')) },
    { key: 'follow_up', icon: '🔄', label: 'qa.keyword_cat_follow_up', intent: 'qa.keyword_intent_follow_up', keywords: splitKeywords(t('qa.keyword_follow_up_examples')) },
    { key: 'ambiguous', icon: '❓', label: 'qa.keyword_cat_ambiguous', intent: 'qa.keyword_intent_ambiguous', keywords: splitKeywords(t('qa.keyword_ambiguous_examples')) },
  ]
})

function insertKeyword(kw: string) {
  const current = inputMessage.value.trim()
  inputMessage.value = current ? current + ' ' + kw : kw
  keywordHintsVisible.value = false
  nextTick(() => {
    inputRef.value?.focus()
  })
}

const chatListRef = ref()
const innerRef = ref()
const chatCreatorRef = ref()

const scrollToBottom = debounce(() => {
  if (scrolling) return
  nextTick(() => {
    chatListRef.value?.scrollTo({
      top: chatListRef.value.wrapRef.scrollHeight,
      behavior: 'smooth',
    })
  })
}, 300)

const loading = ref<boolean>(false)
const chatList = ref<Array<ChatInfo>>([])
const appearanceStore = useAppearanceStoreWithOut()

const currentChatId = ref<number | undefined>()
const currentChat = ref<ChatInfo>(new ChatInfo())
const isTyping = ref<boolean>(false)
const loginBg = computed(() => {
  return appearanceStore.getLogin
})
const computedMessages = computed<Array<ChatMessage>>(() => {
  const messages: Array<ChatMessage> = []
  if (currentChatId.value === undefined) {
    return messages
  }
  for (let i = 0; i < currentChat.value.records.length; i++) {
    const record = currentChat.value.records[i]
    if (record.question !== undefined && !record.first_chat) {
      messages.push({
        role: 'user',
        create_time: record.create_time,
        record: record,
        content: record.question,
        index: i,
      })
    }
    messages.push({
      role: 'assistant',
      create_time: record.create_time,
      record: record,
      isTyping: i === currentChat.value.records.length - 1 && isTyping.value,
      first_chat: record.first_chat,
      recommended_question: record.recommended_question,
      index: i,
    })
  }

  return messages
})

// 通知 HelpButton 组件聊天内容状态变化
watch(
  computedMessages,
  (newMessages) => {
    window.dispatchEvent(
      new CustomEvent('chatContentChange', {
        detail: { hasContent: newMessages.length > 0 },
      })
    )
  },
  { immediate: true }
)

const goEmpty = (func?: (...p: any[]) => void, ...param: any[]) => {
  inputMessage.value = ''
  stop(func, ...param)
}

let scrollTime: any
let scrollingTime: any
let scrollTopVal = 0
let scrolling = false
const scrollBottom = () => {
  if (scrolling) return
  if (!isTyping.value && !getRecommendQuestionsLoading.value) {
    clearInterval(scrollTime)
  }
  if (!chatListRef.value) {
    clearInterval(scrollTime)
    return
  }
  chatListRef.value!.setScrollTop(innerRef.value!.clientHeight)
}

const handleScroll = (val: any) => {
  scrollTopVal = val.scrollTop
  scrolling = true
  clearTimeout(scrollingTime)
  scrollingTime = setTimeout(() => {
    scrolling = false
  }, 400)
  if (
    scrollTopVal + 200 <
    innerRef.value!.clientHeight - (document.querySelector('.chat-record-list')!.clientHeight - 20)
  ) {
    clearInterval(scrollTime)
    scrollTime = null
    return
  }

  if (
    !scrollTime &&
    isTyping.value &&
    scrollTopVal + 30 <
      innerRef.value!.clientHeight -
        (document.querySelector('.chat-record-list')!.clientHeight - 20)
  ) {
    scrollTime = setInterval(() => {
      scrollBottom()
    }, 300)
  }
}

const createNewChatSimple = async () => {
  currentChat.value = new ChatInfo()
  currentChatId.value = undefined
  await createNewChat()
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
  goEmpty()
  chatCreatorRef.value?.showDs()
}

function getChatList(callback?: () => void) {
  loading.value = true
  chatApi
    .list()
    .then((res) => {
      chatList.value = chatApi.toChatInfoList(res)
    })
    .catch(() => {
      ElMessage({ type: 'error', message: t('qa.load_chat_failed') })
    })
    .finally(() => {
      loading.value = false
      if (callback && typeof callback === 'function') {
        callback()
      }
    })
}

function onClickHistory(chat: ChatInfo) {
  scrollToBottom()
  
  // 移除所有数据预加载，避免与子组件 onMounted 的数据加载竞态
  // ChartAnswer/AnalysisAnswer/PredictAnswer 组件挂载时会自行检查并加载数据

  // 切换对话后，检查最后一条记录是否缺少推荐问题
  // 如果推荐问题为空（可能是上次SSE中断导致），自动重新请求
  nextTick(() => {
    if (chat.records && chat.records.length > 0) {
      const lastRecord = chat.records[chat.records.length - 1]
      if (lastRecord && lastRecord.finish && !lastRecord.error && !lastRecord.recommended_question) {
        getRecommendQuestions(lastRecord.id)
      }
    }
  })
}

const currentChatEngineType = computed(() => {
  return getDsIcon(currentChat.value.ds_type)
})

function onChatDeleted(deletedChatId: number) {
  // ChatListContainer 已经处理了状态清理和 goEmpty 调用
  // 这里只需要确保停止所有正在进行的操作
  if (currentChatId.value === deletedChatId || currentChatId.value === undefined) {
    stop()
    inputMessage.value = ''
    loading.value = false
  }
}

function onChatRenamed() {
  // Chat renamed callback - reserved for future use
}

const chatListSideBarShow = ref<boolean>(true)
function hideSideBar() {
  if (isPhone.value) {
    floatPopoverVisible.value = false
    return
  }
  chatListSideBarShow.value = false
}

function showSideBar() {
  if (isPhone.value) {
    showFloatPopover()
    return
  }
  chatListSideBarShow.value = true
}

function toggleSideBar() {
  if (chatListSideBarShow.value) {
    hideSideBar()
  } else {
    showSideBar()
  }
}

function onChatCreatedQuick(chat: ChatInfo) {
  chatList.value.unshift(chat)
  currentChatId.value = chat.id
  currentChat.value = chat
  onChatCreated(chat)
}

function onChatCreated(chat: ChatInfo) {
  if (chat.records.length === 1) {
    getRecommendQuestions(chat.records[0].id)
  }
}

const recommendQuestionRef = ref()

function getRecommendQuestions(id?: number) {
  nextTick(() => {
    if (recommendQuestionRef.value) {
      if (recommendQuestionRef.value instanceof Array) {
        for (let i = 0; i < recommendQuestionRef.value.length; i++) {
          const refId = recommendQuestionRef.value[i].id()
          if (refId === id) {
            recommendQuestionRef.value[i].getRecommendQuestions()
            break
          }
        }
      } else {
        recommendQuestionRef.value.getRecommendQuestions()
      }
    }
  })
}

// 标记当前提问来源：manual=手动输入, recommend=推荐问题点击
const currentInputType = ref<'manual' | 'recommend'>('manual')

function quickAsk(question: string) {
  inputMessage.value = question
  currentInputType.value = 'recommend'
  nextTick(() => {
    sendMessage()
  })
}

const chartAnswerRef = ref()
const getRecommendQuestionsLoading = ref(false)
async function onChartAnswerFinish(id: number) {
  getRecommendQuestionsLoading.value = true
  loading.value = false
  isTyping.value = false
  getRecommendQuestions(id)
}

const loadingOver = () => {
  getRecommendQuestionsLoading.value = false
}

function onChartAnswerError() {
  loading.value = false
  isTyping.value = false
}

function onChatStop() {
  loading.value = false
  isTyping.value = false
}
const assistantPrepareSend = async () => {
  // 嵌入式助手功能已移除，此函数保留为空实现
}
const sendMessage = async ($event: any = {}) => {
  if ($event?.isComposing) {
    return
  }
  if (!inputMessage.value.trim()) {
    // 空输入时给用户友好提示
    ElMessage({
      type: 'warning',
      message: t('qa.empty_question'),
      duration: 2000,
    })
    return
  }

  // 纯特殊字符检测 - 输入必须包含至少一个字母、数字或中文字符
  const meaningfulCharPattern = /[\w\u4e00-\u9fff\u3400-\u4dbf\uF900-\uFAFF]/
  if (!meaningfulCharPattern.test(inputMessage.value.trim())) {
    ElMessage({
      type: 'warning',
      message: t('qa.invalid_input'),
      duration: 2000,
    })
    return
  }

  // 输入长度限制 - 与后端保持一致，最大2000字符
  const MAX_INPUT_LENGTH = 2000
  if (inputMessage.value.trim().length > MAX_INPUT_LENGTH) {
    ElMessage({
      type: 'warning',
      message: t('qa.input_too_long', { max: MAX_INPUT_LENGTH }),
      duration: 3000,
    })
    return
  }

  loading.value = true
  isTyping.value = true
  if (isCompletePage && innerRef.value) {
    scrollTopVal = innerRef.value!.clientHeight
    scrollTime = setInterval(() => {
      scrollBottom()
    }, 300)
  }
  await assistantPrepareSend()
  const currentRecord = new ChatRecord()
  currentRecord.create_time = new Date()
  currentRecord.chat_id = currentChatId.value
  currentRecord.question = inputMessage.value
  currentRecord.sql_answer = ''
  currentRecord.sql = ''
  currentRecord.chart_answer = ''
  currentRecord.chart = ''

  currentChat.value.records.push(currentRecord)
  inputMessage.value = ''

  // 延迟重置 currentInputType，确保 ChartAnswer.sendMessage() 能读取到正确的值
    // 改为在 nextTick 回调末尾重置，确保 ChartAnswer 组件已读取到正确的 input_type

  nextTick(async () => {
    if (!isCompletePage && innerRef.value) {
      scrollTopVal = innerRef.value!.clientHeight
      scrollTime = setInterval(() => {
        scrollBottom()
      }, 300)
    }
    const index = currentChat.value.records.length - 1
    if (chartAnswerRef.value) {
      if (chartAnswerRef.value instanceof Array) {
        for (let i = 0; i < chartAnswerRef.value.length; i++) {
          const _index = chartAnswerRef.value[i].index()
          if (index === _index) {
            await chartAnswerRef.value[i].sendMessage()
            break
          }
        }
      } else {
        await chartAnswerRef.value.sendMessage()
      }
    }
    // 在 ChartAnswer.sendMessage() 执行后再重置 input_type
    currentInputType.value = 'manual'
  })
}

const analysisAnswerRef = ref()

// 复制功能
const { copy } = useClipboard({ legacy: true })
const copiedMessageId = ref<number | null>(null)

function copyAnswer(message: ChatMessage) {
  if (!message.record) return
  
  // 构建要复制的内容
  let content = ''
  
  // 添加问题
  if (message.record.question) {
    content += `${t('qa.copy_label_question')}${message.record.question}\n\n`
  }
  
  // 添加SQL（如果有）
  if (message.record.sql) {
    content += `SQL：\n${message.record.sql}\n\n`
  }
  
  // 添加图表答案（如果有）
  if (message.record.chart_answer) {
    content += `${t('qa.copy_label_chart_analysis')}\n${message.record.chart_answer}\n\n`
  }
  
  // 添加数据分析内容（如果有）- 这是AnalysisAnswer的主要内容
  if (message.record.analysis) {
    content += `${t('qa.copy_label_analysis_report')}\n${message.record.analysis}\n\n`
  }
  
  // 添加直接回答内容（总结/概括/一般对话路径）
  if (message.record.direct_answer && message.record.direct_answer !== message.record.analysis) {
    content += `${t('qa.copy_label_analysis_report')}\n${message.record.direct_answer}\n\n`
  }
  
  // 添加智能输出回答（单行极值结果的自然语言回答）
  if (message.record.smart_answer) {
    content += `${message.record.smart_answer}\n\n`
  }
  
  // 添加数据分析思考过程（如果有）
  if (message.record.analysis_thinking) {
    content += `${t('qa.copy_label_analysis_thinking')}\n${message.record.analysis_thinking}\n\n`
  }
  
  // 添加预测报告内容（如果有）- 这是PredictAnswer的主要内容
  if (message.record.predict_content) {
    content += `${t('qa.copy_label_predict_report')}\n${message.record.predict_content}\n\n`
  }
  
  // predict字段在format_record后是预测报告文本（非思考过程）
  // 如果predict_content已复制，predict可能重复，只在predict_content为空时使用predict
  if (message.record.predict && !message.record.predict_content) {
    content += `${t('qa.copy_label_predict_report')}\n${message.record.predict}\n\n`
  }
  
  // 添加预测思考过程（如果有）
  if (message.record.predict_thinking) {
    content += `${t('qa.copy_label_predict_thinking')}\n${message.record.predict_thinking}\n\n`
  }
  
  // 执行复制
  copy(content.trim()).then(() => {
    copiedMessageId.value = message.record?.id || null
    ElMessage.success(t('common.copy_successful'))
    setTimeout(() => {
      copiedMessageId.value = null
    }, 2000)
  }).catch(() => {
    ElMessage.error(t('qa.copy_failed'))
  })
}

// 检查是否有可复制的文字内容（不包括问题本身和图表配置）
function hasCopyableContent(record: any): boolean {
  if (!record) return false
  
  // format_record已将analysis/predict从JSON解析为纯文本
  // 不需要再尝试JSON.parse，直接检查字符串内容即可
  const hasSql = record.sql && record.sql.trim().length > 0
  const hasChartAnswer = record.chart_answer && record.chart_answer.trim().length > 0
  const hasAnalysisThinking = record.analysis_thinking && record.analysis_thinking.trim().length > 0
  const hasAnalysis = record.analysis && record.analysis.trim().length > 0
  const hasPredict = record.predict && record.predict.trim().length > 0
  const hasPredictContent = record.predict_content && record.predict_content.trim().length > 0
  const hasPredictThinking = record.predict_thinking && record.predict_thinking.trim().length > 0
  const hasDirectAnswer = record.direct_answer && record.direct_answer.trim().length > 0
  const hasSmartAnswer = record.smart_answer && record.smart_answer.trim().length > 0
  
  return hasSql || hasChartAnswer || hasAnalysisThinking || hasAnalysis || hasPredict || hasPredictContent || hasPredictThinking || hasDirectAnswer || hasSmartAnswer
}

async function onAnalysisAnswerFinish() {
  loading.value = false
  isTyping.value = false
}
function onAnalysisAnswerError() {
  loading.value = false
  isTyping.value = false
}

async function askAgain(message: ChatMessage) {
  if (!message.record || message.index === undefined) {
    return
  }
  
  // 保存原始问题和旧的 record_id
  const originalQuestion = message.record.question
  const oldRecordId = message.record.id
  const targetIndex = message.index
  
  try {
    // 1. 如果有旧的 record_id，先删除数据库中的旧记录
    if (oldRecordId) {
      await chatApi.deleteRecord(oldRecordId)
    }
    
    // 2. 重置当前记录的所有字段（保留问题和基本信息）
    const currentRecord = currentChat.value.records[targetIndex]
    
    currentRecord.id = undefined  // 清除旧 id，后端会返回新 id
    currentRecord.sql_answer = ''
    currentRecord.sql = ''
    currentRecord.data = undefined
    currentRecord.chart_answer = ''
    currentRecord.chart = ''
    currentRecord.error = undefined
    currentRecord.finish = false
    currentRecord.recommended_question = undefined
    currentRecord.rag_results = undefined
    currentRecord.sql_reasoning_content = ''
    currentRecord.chart_reasoning_content = ''
    // 重置文档类型直接回答相关字段，防止重新生成时内容重复
    currentRecord.direct_answer = undefined
    currentRecord.intent = undefined
    currentRecord.thinking_process = undefined
    // 重置内联分析/预测字段（非独立的analysis/predict记录）
    currentRecord.analysis = ''
    currentRecord.analysis_reasoning_content = ''
    currentRecord.predict = ''
    currentRecord.predict_content = ''
    currentRecord.predict_data = undefined
    currentRecord.predict_reasoning_content = ''
    currentRecord.predict_unavailable_reason = undefined
    // 重置 smart_answer（智能输出路径），防止旧的单行极值回答残留
    currentRecord.smart_answer = undefined
    // 重置 predict_thinking（内联预测推理内容），防止旧推理残留
    currentRecord.predict_thinking = undefined
    
    // 保持问题不变
    currentRecord.question = originalQuestion
    
    // 3. 设置加载状态
    loading.value = true
    isTyping.value = true
    
    // 4. 触发重新生成
    await nextTick()
    
    if (isCompletePage && innerRef.value) {
      scrollTopVal = innerRef.value!.clientHeight
      scrollTime = setInterval(() => {
        scrollBottom()
      }, 300)
    }
    
    // 找到对应的 chartAnswerRef 并调用 sendMessage
    if (chartAnswerRef.value) {
      if (chartAnswerRef.value instanceof Array) {
        for (let i = 0; i < chartAnswerRef.value.length; i++) {
          const _index = chartAnswerRef.value[i].index()
          if (targetIndex === _index) {
            await chartAnswerRef.value[i].sendMessage()
            break
          }
        }
      } else {
        if (chartAnswerRef.value.index() === targetIndex) {
          await chartAnswerRef.value.sendMessage()
        }
      }
    }
    
  } catch (error: any) {
    loading.value = false
    isTyping.value = false
    ElMessage({
      type: 'error',
      message: error.message || t('qa.ask_again_failed'),
      duration: 3000,
    })
  }
}

async function askAgainAnalysis(message: ChatMessage) {
  if (!message.record || message.index === undefined) return
  
  const analysisRecordId = message.record?.analysis_record_id
  const targetIndex = message.index
  
  try {
    // 1. 如果有旧的 record_id，先删除数据库中的旧记录
    if (message.record.id) {
      await chatApi.deleteRecord(message.record.id)
    }
    
    // 2. 重置当前记录的所有字段
    const currentRecord = currentChat.value.records[targetIndex]
    currentRecord.id = undefined
    currentRecord.analysis = ''
    currentRecord.analysis_thinking = ''
    currentRecord.error = undefined
    currentRecord.finish = false
    currentRecord.analysis_reasoning_content = ''
    // 重置思考过程和RAG结果，防止旧数据残留
    currentRecord.thinking_process = undefined
    currentRecord.rag_results = undefined
    
    // 保持原始信息
    currentRecord.analysis_record_id = analysisRecordId
    
    // 3. 设置加载状态
    loading.value = true
    isTyping.value = true
    
    // 4. 触发重新生成
    await nextTick()
    
    if (analysisAnswerRef.value) {
      if (analysisAnswerRef.value instanceof Array) {
        for (let i = 0; i < analysisAnswerRef.value.length; i++) {
          const _index = analysisAnswerRef.value[i].index()
          if (targetIndex === _index) {
            await analysisAnswerRef.value[i].sendMessage()
            break
          }
        }
      } else {
        if (analysisAnswerRef.value.index() === targetIndex) {
          await analysisAnswerRef.value.sendMessage()
        }
      }
    }
    
  } catch (error: any) {
    loading.value = false
    isTyping.value = false
    ElMessage({
      type: 'error',
      message: error.message || t('qa.ask_again_failed'),
      duration: 3000,
    })
  }
}

async function askAgainPredict(message: ChatMessage) {
  if (!message.record || message.index === undefined) return
  
  const predictRecordId = message.record?.predict_record_id
  const targetIndex = message.index
  
  try {
    // 1. 如果有旧的 record_id，先删除数据库中的旧记录
    if (message.record.id) {
      await chatApi.deleteRecord(message.record.id)
    }
    
    // 2. 重置当前记录的所有字段
    const currentRecord = currentChat.value.records[targetIndex]
    currentRecord.id = undefined
    currentRecord.predict = ''
    currentRecord.predict_content = ''
    currentRecord.predict_data = undefined
    currentRecord.error = undefined
    currentRecord.finish = false
    currentRecord.predict_reasoning_content = ''
    // 重置 predict_thinking（推理内容展示字段），防止旧推理残留
    currentRecord.predict_thinking = undefined
    // 重置 predict_unavailable_reason，防止旧的不可用原因残留
    currentRecord.predict_unavailable_reason = undefined
    // 重置思考过程和RAG结果，防止旧数据残留
    currentRecord.thinking_process = undefined
    currentRecord.rag_results = undefined
    
    // 保持原始信息
    currentRecord.predict_record_id = predictRecordId
    
    // 3. 设置加载状态
    loading.value = true
    isTyping.value = true
    
    // 4. 触发重新生成
    await nextTick()
    
    if (predictAnswerRef.value) {
      if (predictAnswerRef.value instanceof Array) {
        for (let i = 0; i < predictAnswerRef.value.length; i++) {
          const _index = predictAnswerRef.value[i].index()
          if (targetIndex === _index) {
            await predictAnswerRef.value[i].sendMessage()
            break
          }
        }
      } else {
        if (predictAnswerRef.value.index() === targetIndex) {
          await predictAnswerRef.value.sendMessage()
        }
      }
    }
    
  } catch (error: any) {
    loading.value = false
    isTyping.value = false
    ElMessage({
      type: 'error',
      message: error.message || t('qa.ask_again_failed'),
      duration: 3000,
    })
  }
}

async function clickAnalysis(id?: number) {
  const baseRecord = find(currentChat.value.records, (value) => id === value.id)
  if (baseRecord == undefined) {
    return
  }

  // PDF数据源不支持数据分析，在前端提前拦截
  if (currentChat.value?.ds_type === 'pdf') {
    ElMessage({
      type: 'warning',
      message: t('qa.pdf_no_analysis'),
      duration: 3000,
    })
    return
  }

  // 检查数据是否真正存在（不是空对象）
  const hasValidData = baseRecord.data && 
    typeof baseRecord.data === 'object' && 
    ((Array.isArray(baseRecord.data) && baseRecord.data.length > 0) ||
     (baseRecord.data.data && Array.isArray(baseRecord.data.data) && baseRecord.data.data.length > 0))

  // 确保数据已加载
  if (!hasValidData && baseRecord.id) {
    // 显示加载提示
    const loadingMessage = ElMessage({
      type: 'info',
      message: t('chat.loading_data'),
      duration: 0, // 不自动关闭
      showClose: false,
    })
    
    try {
      const success = await loadRecordData(baseRecord.id)
      loadingMessage.close()
      
      if (!success) {
        ElMessage({
          type: 'error',
          message: t('qa.load_data_failed'),
          duration: 3000,
        })
        return
      }
      
      // 再次检查数据是否有效
      const hasValidDataAfterLoad = baseRecord.data && 
        typeof baseRecord.data === 'object' && 
        ((Array.isArray(baseRecord.data) && baseRecord.data.length > 0) ||
         (baseRecord.data.data && Array.isArray(baseRecord.data.data) && baseRecord.data.data.length > 0))
      
      if (!hasValidDataAfterLoad) {
        ElMessage({
          type: 'warning',
          message: t('qa.no_data_for_analysis'),
          duration: 3000,
        })
        return
      }
    } catch (error) {
      loadingMessage.close()
      ElMessage({
        type: 'error',
        message: t('qa.load_data_failed'),
        duration: 3000,
      })
      return
    }
  }

  // 再次验证数据（数据已加载）
  const validation = validateAnalysisData(baseRecord)
  if (!validation.canAnalyze) {
    // 提供更详细的错误信息
    let errorMsg = t('chat.cannot_analyze')
    if (validation.reason) {
      const reasonKey = 'chat.error_' + validation.reason
      errorMsg += ': ' + t(reasonKey)
    }
    
    ElMessage({
      type: 'warning',
      message: errorMsg,
      duration: 3000,
    })
    return
  }

  loading.value = true
  isTyping.value = true

  const currentRecord = new ChatRecord()
  currentRecord.create_time = new Date()
  currentRecord.chat_id = baseRecord.chat_id
  currentRecord.question = baseRecord.question
  // 不复制 chart 和 data，后端会从 analysis_record_id 读取
  currentRecord.analysis_record_id = id
  currentRecord.analysis = ''

  currentChat.value.records.push(currentRecord)

  nextTick(async () => {
    const index = currentChat.value.records.length - 1
    if (analysisAnswerRef.value) {
      if (analysisAnswerRef.value instanceof Array) {
        for (let i = 0; i < analysisAnswerRef.value.length; i++) {
          const _index = analysisAnswerRef.value[i].index()
          if (index === _index) {
            await analysisAnswerRef.value[i].sendMessage()
            break
          }
        }
      } else {
        await analysisAnswerRef.value.sendMessage()
      }
    }
  })

  return
}

const predictAnswerRef = ref()

async function onPredictAnswerFinish(recordId?: number) {
  loading.value = false
  isTyping.value = false
  
  // 预测完成后，重新加载聊天记录以确保chart配置被加载
  // 记录当前chatId，防止快速切换后将旧聊天数据写入新聊天
  const chatIdAtFinish = currentChat.value.id
  if (chatIdAtFinish) {
    try {
      const response = await chatApi.get_with_Data(chatIdAtFinish)
      
      // 异步返回后再次检查chatId是否仍然一致
      if (currentChat.value.id !== chatIdAtFinish) return
      
      // 不直接替换 currentChat.value（会丢失内存中的临时状态如 _predict_full_text、isDeleting 等）
      // 只更新每条 record 的持久化字段（chart、data、finish 等），保留内存状态
      if (response && response.records) {
        for (const serverRecord of response.records) {
          const localRecord = currentChat.value.records.find(r => r.id === serverRecord.id)
          if (localRecord) {
            // 只同步后端持久化字段，不覆盖前端临时状态
            if (serverRecord.chart) localRecord.chart = serverRecord.chart
            if (serverRecord.data) localRecord.data = serverRecord.data
            if (serverRecord.predict_data) localRecord.predict_data = serverRecord.predict_data
            if (serverRecord.predict_content) localRecord.predict_content = serverRecord.predict_content
            localRecord.finish = serverRecord.finish
          }
        }
      }
      
      // 强制触发响应式更新
      await nextTick()
      
      // 滚动到底部
      await nextTick()
      scrollToBottom()
    } catch (error) {
      // 重新加载记录失败，静默处理
    }
  }
}
function onPredictAnswerError() {
  loading.value = false
  isTyping.value = false
}

async function clickPredict(id?: number) {
  const baseRecord = find(currentChat.value.records, (value) => id === value.id)
  
  if (baseRecord == undefined) {
    return
  }

  // PDF数据源不支持数据预测，在前端提前拦截
  if (currentChat.value?.ds_type === 'pdf') {
    ElMessage({
      type: 'warning',
      message: t('qa.pdf_no_prediction'),
      duration: 3000,
    })
    return
  }

  // 检查数据是否真正存在（不是空对象）
  const hasValidData = baseRecord.data && 
    typeof baseRecord.data === 'object' && 
    ((Array.isArray(baseRecord.data) && baseRecord.data.length > 0) ||
     (baseRecord.data.data && Array.isArray(baseRecord.data.data) && baseRecord.data.data.length > 0))

  // 确保数据已加载（带加载提示）
  if (!hasValidData && baseRecord.id) {
    
    // 显示加载提示
    const loadingMessage = ElMessage({
      type: 'info',
      message: t('chat.loading_data'),
      duration: 0, // 不自动关闭
      showClose: false,
    })
    
    try {
      const success = await loadRecordData(baseRecord.id)
      loadingMessage.close()
      
      if (!success) {
        ElMessage({
          type: 'error',
          message: t('qa.load_data_failed'),
          duration: 3000,
        })
        return
      }
      
      // 再次检查数据是否有效
      const hasValidDataAfterLoad = baseRecord.data && 
        typeof baseRecord.data === 'object' && 
        ((Array.isArray(baseRecord.data) && baseRecord.data.length > 0) ||
         (baseRecord.data.data && Array.isArray(baseRecord.data.data) && baseRecord.data.data.length > 0))
      
      if (!hasValidDataAfterLoad) {
        ElMessage({
          type: 'warning',
          message: t('qa.no_data_for_prediction'),
          duration: 3000,
        })
        return
      }
    } catch (error) {
      loadingMessage.close()
      ElMessage({
        type: 'error',
        message: t('qa.load_data_failed'),
        duration: 3000,
      })
      return
    }
  }

  // 使用高级验证检查数据质量
  const validation = validatePredictionAdvanced(baseRecord)
  
  // 如果不满足预测条件，显示简单提示
  if (!validation.canPredict) {
    
    let message = t('qa.prediction_requirements_not_met')
    
    if (validation.dataCount === 0) {
      message = t('qa.no_data_for_prediction')
    } else if (!validation.timeFieldName) {
      message = t('qa.no_time_field_for_prediction')
    } else if (validation.numericFields.length === 0) {
      message = t('qa.no_numeric_field_for_prediction')
    }
    
    ElMessage({
      type: 'warning',
      message: message,
      duration: 4000,
      showClose: true,
    })
    return
  }
  
  // 如果数据质量不是优秀，显示警告但继续
  if (validation.quality !== 'excellent') {
    
    ElMessage({
      type: 'info',
      message: t('qa.prediction_quality_warning'),
      duration: 3000,
    })
  }
  
  // 数据质量优秀，直接开始预测
  await startPrediction(baseRecord)
}

// 开始预测的实际逻辑
async function startPrediction(baseRecord: ChatRecord) {
  loading.value = true
  isTyping.value = true

  const currentRecord = new ChatRecord()
  currentRecord.create_time = new Date()
  currentRecord.chat_id = baseRecord.chat_id
  currentRecord.question = baseRecord.question
  // 不复制 chart 和 data，后端会从 predict_record_id 读取
  currentRecord.predict_record_id = baseRecord.id
  currentRecord.predict = ''
  currentRecord.predict_data = ''

  currentChat.value.records.push(currentRecord)

  nextTick(async () => {
    
    const index = currentChat.value.records.length - 1
    if (predictAnswerRef.value) {
      if (predictAnswerRef.value instanceof Array) {
        for (let i = 0; i < predictAnswerRef.value.length; i++) {
          const _index = predictAnswerRef.value[i].index()
          if (index === _index) {
            await predictAnswerRef.value[i].sendMessage()
            break
          }
        }
      } else {
        await predictAnswerRef.value.sendMessage()
      }
    }
  })

  return
}

// 数据加载状态追踪
const recordDataStates = ref<Map<number, {
  loaded: boolean
  loading: boolean
  error: string | null
}>>(new Map())



// 加载记录数据（带重试机制）
async function loadRecordData(recordId: number, retryCount: number = 0): Promise<boolean> {
  if (!recordId) return false
  
  // 检查是否正在加载
  const state = recordDataStates.value.get(recordId)
  if (state?.loading) {
    // 如果正在加载，等待加载完成
    return new Promise((resolve) => {
      let checkInterval: ReturnType<typeof setInterval> | null = null
      let timeoutId: ReturnType<typeof setTimeout> | null = null
      
      const cleanup = () => {
        if (checkInterval) clearInterval(checkInterval)
        if (timeoutId) clearTimeout(timeoutId)
      }
      
      checkInterval = setInterval(() => {
        const currentState = recordDataStates.value.get(recordId)
        if (!currentState?.loading) {
          cleanup()
          resolve(currentState?.loaded || false)
        }
      }, 100)
      
      // 超时保护（10秒）
      timeoutId = setTimeout(() => {
        cleanup()
        resolve(false)
      }, 10000)
    })
  }
  
  // 如果已经加载成功，直接返回
  if (state?.loaded) return true
  
  // 设置加载状态
  recordDataStates.value.set(recordId, {
    loaded: false,
    loading: true,
    error: null
  })
  
  try {
    const response = await chatApi.get_chart_data(recordId)
    
    // 验证响应数据（允许空数据集，只拒绝无效响应）
    if (!response) {
      throw new Error('No response from server')
    }
    
    // 更新记录数据
    const record = currentChat.value.records.find(r => r.id === recordId)
    if (record) {
      record.data = response
    }
    
    // 更新加载状态
    recordDataStates.value.set(recordId, {
      loaded: true,
      loading: false,
      error: null
    })
    
    return true
  } catch (error: any) {
    // 重试逻辑（最多重试2次）
    if (retryCount < 2) {
      await new Promise(resolve => setTimeout(resolve, 1000))
      return loadRecordData(recordId, retryCount + 1)
    }
    
    // 更新错误状态
    recordDataStates.value.set(recordId, {
      loaded: false,
      loading: false,
      error: error.message || 'Failed to load data'
    })
    
    return false
  }
}



const handleCtrlEnter = (e: KeyboardEvent) => {
  const textarea = e.target as HTMLTextAreaElement
  const start = textarea.selectionStart
  const end = textarea.selectionEnd
  const value = textarea.value

  inputMessage.value = value.substring(0, start) + '\n' + value.substring(end)

  nextTick(() => {
    textarea.selectionStart = textarea.selectionEnd = start + 1
  })
}

// 处理 Esc 键停止生成
const handleEscKey = (e: KeyboardEvent) => {
  if (e.key === 'Escape' && isTyping.value) {
    stopAllGeneration()
  }
}

// 删除单个对话记录
async function deleteMessage(message: ChatMessage) {
  if (!message.record || !message.record.id) {
    return
  }
  
  // 不允许删除第一条欢迎消息
  if (message.record.first_chat) {
    ElMessage({
      type: 'warning',
      message: t('qa.cannot_delete_first_chat'),
      duration: 2000,
    })
    return
  }
  
  try {
    const confirmText = t('qa.delete_message_confirm')
    const titleText = t('qa.delete_message_title')
    const confirmButtonText = t('common.confirm')
    const cancelButtonText = t('common.cancel')
    
    await ElMessageBox.confirm(
      confirmText,
      titleText,
      {
        confirmButtonText: confirmButtonText,
        cancelButtonText: cancelButtonText,
        type: 'warning',
        confirmButtonType: 'danger',
        showClose: false,
      }
    )
    
    // 标记消息正在删除，触发动画
    message.isDeleting = true
    
    // 等待动画完成（300ms）
    await new Promise(resolve => setTimeout(resolve, 300))
    
    // 调用后端API删除记录
    await chatApi.deleteRecord(message.record.id)
    
    // 使用 record.id 查找实际索引，而非 message.index
    // message.index 基于 computedMessages 构建时的 records 数组位置，
    // 索引可能已过时，需重新查找
    const actualIndex = currentChat.value.records.findIndex(r => r.id === message.record!.id)
    if (actualIndex >= 0) {
      currentChat.value.records.splice(actualIndex, 1)
    }
    
    ElMessage({
      type: 'success',
      message: t('qa.delete_message_success'),
      duration: 2000,
    })
  } catch (error: any) {
    // 如果删除失败，取消删除标记
    message.isDeleting = false
    
    if (error !== 'cancel') {
      ElMessage({
        type: 'error',
        message: error.message || t('qa.delete_message_failed'),
        duration: 3000,
      })
    }
  }
}

const inputRef = ref()

function clickInput() {
  inputRef.value?.focus()
}

// 停止所有生成（用户点击停止按钮或按 Esc）
function stopAllGeneration() {
  stop()
  loading.value = false
  isTyping.value = false
  ElMessage({
    type: 'info',
    message: t('qa.generation_stopped'),
    duration: 2000,
  })
}

function stop(func?: (...p: any[]) => void, ...param: any[]) {
  if (recommendQuestionRef.value) {
    if (recommendQuestionRef.value instanceof Array) {
      for (let i = 0; i < recommendQuestionRef.value.length; i++) {
        recommendQuestionRef.value[i].stop()
      }
    } else {
      recommendQuestionRef.value.stop()
    }
  }
  if (chartAnswerRef.value) {
    if (chartAnswerRef.value instanceof Array) {
      for (let i = 0; i < chartAnswerRef.value.length; i++) {
        chartAnswerRef.value[i].stop()
      }
    } else {
      chartAnswerRef.value.stop()
    }
  }
  if (analysisAnswerRef.value) {
    if (analysisAnswerRef.value instanceof Array) {
      for (let i = 0; i < analysisAnswerRef.value.length; i++) {
        analysisAnswerRef.value[i].stop()
      }
    } else {
      analysisAnswerRef.value.stop()
    }
  }
  if (predictAnswerRef.value) {
    if (predictAnswerRef.value instanceof Array) {
      for (let i = 0; i < predictAnswerRef.value.length; i++) {
        predictAnswerRef.value[i].stop()
      }
    } else {
      predictAnswerRef.value.stop()
    }
  }
  if (func && typeof func === 'function') {
    func(...param)
  }
}
const showFloatPopover = () => {
  if (!isCompletePage && !floatPopoverVisible.value) {
    floatPopoverVisible.value = true
  }
}
const registerClickOutside = () => {
  onClickOutside(floatPopoverRef, (event: any) => {
    if (floatPopoverVisible.value) {
      let parentElement: any = event.target
      let isEdOverlay = false
      while (parentElement) {
        if (parentElement.className.includes('ed-overlay')) {
          isEdOverlay = true
          break
        } else {
          parentElement = parentElement.parentElement
        }
      }
      if (isEdOverlay) return
      floatPopoverVisible.value = false
    }
  })
}
const assistantPrepareInit = () => {
  // 嵌入式助手功能已移除，此函数保留为空实现
}
defineExpose({
  createNewChat,
  showFloatPopover,
})

const hiddenChatCreatorRef = ref()

function jumpCreatChat() {
  if (props.startChatDsId) {
    const _id = props.startChatDsId
    nextTick(() => {
      hiddenChatCreatorRef.value?.createChat(_id)
    })
    const newUrl = window.location.hash.replace(/\?.*$/, '')
    history.replaceState({}, '', newUrl)
  }
}

onMounted(() => {
  if (isPhone.value) {
    chatListSideBarShow.value = false
  }
  getChatList(jumpCreatChat)
  assistantPrepareInit()

  // 处理从仪表板跳转过来的预填问题
  const queryQuestion = route.query.q as string
  if (queryQuestion) {
    inputMessage.value = queryQuestion
    // 清除 URL 中的 query 参数，避免刷新时重复
    router.replace({ path: route.path, query: {} })
  }

  // 添加 Esc 键监听
  document.addEventListener('keydown', handleEscKey)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleEscKey)
  // 清除scrollTime定时器，防止组件卸载后内存泄漏
  if (scrollTime) {
    clearInterval(scrollTime)
    scrollTime = null
  }
  // 清除scrollingTime定时器
  if (scrollingTime) {
    clearTimeout(scrollingTime)
    scrollingTime = null
  }
})
</script>

<style lang="less" scoped>
// ============================================
// ChatBI 聊天页面 - 深色主题
// ============================================

// 主色调
@primary-600: #7c3aed;
@primary-500: #a855f7;
@primary-400: #a78bfa;
@primary-300: #c4b5fd;
@primary-100: #f3e8ff;

// 深色主题色
@dark-bg: #0f0a1a;
@dark-bg-secondary: #1a1225;
@dark-bg-card: rgba(139, 92, 246, 0.08);
@dark-border: rgba(139, 92, 246, 0.15);
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@dark-text-muted: rgba(196, 181, 253, 0.5);

// ============================================
// 智能对话页面标题样式
// ============================================
.chat-page-title {
  position: absolute;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 99;
  pointer-events: none;
  
  // 确保标题使用紫色渐变（在 scoped 中也定义以提高优先级）
  :deep(.title-text) {
    background: linear-gradient(135deg, #ddd6fe 0%, #c4b5fd 25%, #a78bfa 50%, #8b5cf6 75%, #7c3aed 100%) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    background-clip: text !important;
  }
}

// ============================================
// 侧边栏切换按钮样式
// ============================================
.sidebar-toggle-btn {
  position: absolute;
  top: 20px;
  left: 20px;
  z-index: 100;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

  .toggle-btn-inner {
    width: 44px;
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(145deg, rgba(139, 92, 246, 0.15) 0%, rgba(124, 58, 237, 0.12) 100%);
    border: 1.5px solid rgba(139, 92, 246, 0.25);
    border-radius: 14px;
    backdrop-filter: blur(12px);
    box-shadow: 
      0 4px 16px rgba(0, 0, 0, 0.3),
      0 0 0 1px rgba(255, 255, 255, 0.05) inset;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    overflow: hidden;

    // 顶部高光
    &::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 50%;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.08) 0%, transparent 100%);
      pointer-events: none;
    }

    // 光晕效果
    &::after {
      content: '';
      position: absolute;
      inset: -2px;
      background: linear-gradient(135deg, rgba(168, 85, 247, 0.4), rgba(139, 92, 246, 0.4));
      border-radius: 14px;
      opacity: 0;
      filter: blur(8px);
      transition: opacity 0.3s ease;
      z-index: -1;
    }

    .toggle-icon {
      width: 22px;
      height: 22px;
      color: rgba(196, 181, 253, 0.9);
      transition: all 0.3s ease;
      filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3));
    }
  }

  .toggle-tooltip {
    position: absolute;
    left: 54px;
    top: 50%;
    transform: translateY(-50%);
    padding: 8px 14px;
    background: linear-gradient(145deg, rgba(18, 16, 28, 0.98) 0%, rgba(10, 8, 18, 0.98) 100%);
    border: 1px solid rgba(139, 92, 246, 0.25);
    border-radius: 10px;
    font-size: 13px;
    font-weight: 500;
    color: rgba(196, 181, 253, 0.9);
    white-space: nowrap;
    opacity: 0;
    pointer-events: none;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 
      0 8px 24px rgba(0, 0, 0, 0.4),
      0 0 0 1px rgba(255, 255, 255, 0.05) inset;
    backdrop-filter: blur(12px);
  }

  // 悬停效果
  &:hover {
    .toggle-btn-inner {
      background: linear-gradient(145deg, rgba(139, 92, 246, 0.25) 0%, rgba(124, 58, 237, 0.2) 100%);
      border-color: rgba(168, 85, 247, 0.4);
      box-shadow: 
        0 6px 24px rgba(139, 92, 246, 0.35),
        0 0 0 1px rgba(255, 255, 255, 0.08) inset;
      transform: translateY(-2px);

      &::after {
        opacity: 1;
      }

      .toggle-icon {
        color: rgba(196, 181, 253, 1);
        transform: scale(1.1);
      }
    }

    .toggle-tooltip {
      opacity: 1;
      left: 58px;
    }
  }

  // 激活效果
  &:active .toggle-btn-inner {
    transform: translateY(0) scale(0.95);
  }

  // 侧边栏隐藏时的样式
  &.sidebar-hidden {
    .toggle-btn-inner {
      background: linear-gradient(145deg, rgba(168, 85, 247, 0.2) 0%, rgba(139, 92, 246, 0.15) 100%);
      border-color: rgba(168, 85, 247, 0.35);
    }
  }
}

// 淡入滑动动画
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateX(-20px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

// ============================================
// 删除消息动画
// ============================================
.message-delete-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 1, 1);
}

.message-delete-leave-to {
  opacity: 0;
  transform: translateX(-30px);
  filter: blur(2px);
}

.chat-container {
  height: 100%;
  width: 100%;
  max-width: 100%;
  position: relative;
  border-radius: 0;
  background: @dark-bg;
  overflow: hidden;
  box-sizing: border-box;

  // 欢迎页面模式
  &.welcome-bg-mode {
    background: @dark-bg !important;

    .chat-container-left {
      border-radius: 0 !important;
      border: none !important;
      box-shadow: none !important;
    }

    :deep(.ed-container),
    :deep(.el-container) {
      background: transparent !important;
      border: none !important;
    }
  }

  // 欢迎模式主区域
  :deep(.ed-main.welcome-mode),
  :deep(.el-main.welcome-mode) {
    padding: 0 !important;
    overflow: hidden !important;
    background: @dark-bg !important;
    flex: 1 !important;
    height: 100% !important;
    border-radius: 0 !important;
  }

  // 内部容器
  :deep(.ed-container),
  :deep(.el-container) {
    height: 100%;
    width: 100%;
    min-width: 0;
    max-width: 100%;
    background: transparent;
    box-sizing: border-box;
  }

  .assistant-popover-sidebar {
    button {
      display: none;
    }
  }

  .chat-container-left {
    --ed-aside-width: 280px;
    border-radius: 0;
    background: linear-gradient(170deg, #12101c 0%, #0a0812 100%) !important;
    border-right: 1px solid @dark-border;
  }

  :deep(.chat-record-list) {
    padding: 0;
    margin: 0;
    border-radius: 0;
    background: @dark-bg;
    position: relative;
    overflow: hidden;
    height: 100%;
    width: 100%;
    min-width: 0;
    box-sizing: border-box;

    &.welcome-mode {
      background: @dark-bg !important;
    }

    // 滚动条 - 只允许垂直滚动
    .ed-scrollbar,
    .el-scrollbar {
      width: 100% !important;
      height: 100% !important;
    }

    .ed-scrollbar__wrap,
    .el-scrollbar__wrap {
      overflow-x: hidden !important;
      overflow-y: auto !important;
    }

    .ed-scrollbar__view,
    .el-scrollbar__view {
      width: 100% !important;
      min-width: 0 !important;
      max-width: 100% !important;
    }

    .ed-scrollbar__bar.is-horizontal,
    .el-scrollbar__bar.is-horizontal {
      display: none !important;
    }
  }

  .assistant-chat-main {
    padding: 0;
  }

  // 聊天内容滚动区域
  .chat-scroll {
    width: 100%;
    min-width: 0;
    max-width: 100%;
    min-height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 20px;
    box-sizing: border-box;
    overflow: hidden;

    &.no-sidebar {
      padding-left: 40px;
    }

    &.pad16 {
      padding: 16px;
    }

    // 所有子元素
    > * {
      width: 100%;
      max-width: 900px;
      min-width: 0;
      box-sizing: border-box;
    }
  }

  .chat-footer {
    flex-shrink: 0;
    padding: 0 20px 20px;
    display: flex;
    justify-content: center;
    background: linear-gradient(180deg, transparent 0%, rgba(12, 8, 22, 0.95) 40%);
    position: relative;
    z-index: 10;
    width: 100%;
    min-width: 0;
    max-width: 100%;
    box-sizing: border-box;
    height: auto !important;
    --ed-footer-height: auto !important;

    .input-wrapper {
      width: 100%;
      max-width: 800px;
      min-width: 0;
      display: flex;
      flex-direction: column;
      box-sizing: border-box;
      position: relative;
      gap: 10px;
    }

    // 数据源标签 - 紧凑精致
    .input-top-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 2px;
      min-height: 36px;

      .datasource-badge {
        position: relative;
        display: inline-flex;
        
        .badge-glow {
          position: absolute;
          inset: -2px;
          background: linear-gradient(135deg, rgba(139, 92, 246, 0.3) 0%, rgba(59, 130, 246, 0.2) 100%);
          border-radius: 12px;
          filter: blur(8px);
          opacity: 0;
          transition: opacity 0.3s ease;
        }
        
        &:hover .badge-glow {
          opacity: 1;
        }
        
        .badge-content {
          position: relative;
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 8px 14px;
          background: linear-gradient(135deg, rgba(139, 92, 246, 0.12) 0%, rgba(59, 130, 246, 0.08) 100%);
          border: 1px solid rgba(139, 92, 246, 0.2);
          border-radius: 10px;
          transition: all 0.25s ease;
          cursor: default;
          
          &:hover {
            border-color: rgba(139, 92, 246, 0.35);
            background: linear-gradient(135deg, rgba(139, 92, 246, 0.18) 0%, rgba(59, 130, 246, 0.12) 100%);
            transform: translateY(-1px);
          }
          
          .ds-icon {
            border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
          }
          
          .ds-indicator {
            font-size: 14px;
          }
          
          .ds-name {
            font-size: 13px;
            font-weight: 600;
            color: rgba(196, 181, 253, 0.9);
            letter-spacing: 0.2px;
            
            &.ds-not-exist {
              color: #f87171;
            }
          }
        }
      }
    }

    // 主输入区域 - 现代化设计
    .input-main-container {
      position: relative;
      width: 100%;
      
      // 边框光效
      .input-border-glow {
        position: absolute;
        inset: -2px;
        border-radius: 22px;
        background: linear-gradient(135deg, 
          rgba(139, 92, 246, 0.4) 0%, 
          rgba(59, 130, 246, 0.3) 25%,
          rgba(139, 92, 246, 0.4) 50%,
          rgba(168, 85, 247, 0.3) 75%,
          rgba(139, 92, 246, 0.4) 100%
        );
        background-size: 300% 300%;
        opacity: 0;
        filter: blur(4px);
        transition: opacity 0.4s ease;
        pointer-events: none;
        z-index: 0;
      }
      
      &.is-focused .input-border-glow {
        opacity: 1;
        animation: gradient-flow 4s ease infinite;
      }
      
      &.is-typing .input-border-glow {
        opacity: 0.5;
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.3) 0%, rgba(251, 146, 60, 0.2) 100%);
        animation: pulse-glow 2s ease-in-out infinite;
      }
      
      // 输入框内部容器
      .input-inner {
        position: relative;
        z-index: 1;
        display: flex;
        align-items: center;
        background: linear-gradient(145deg, rgba(26, 20, 44, 0.98) 0%, rgba(18, 14, 32, 0.98) 100%);
        border: 1.5px solid rgba(139, 92, 246, 0.15);
        border-radius: 20px;
        padding: 6px 6px 6px 0;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 
          0 4px 20px rgba(0, 0, 0, 0.25),
          0 0 0 1px rgba(255, 255, 255, 0.02) inset;
        min-height: 56px;
        
        &:hover {
          border-color: rgba(139, 92, 246, 0.25);
          box-shadow: 
            0 6px 24px rgba(0, 0, 0, 0.3),
            0 0 0 1px rgba(255, 255, 255, 0.03) inset;
        }
      }
      
      &.is-focused .input-inner {
        border-color: rgba(139, 92, 246, 0.4);
        box-shadow: 
          0 8px 32px rgba(0, 0, 0, 0.35),
          0 0 0 1px rgba(139, 92, 246, 0.1) inset,
          0 0 40px rgba(139, 92, 246, 0.08);
      }
      
      &.is-typing .input-inner {
        border-color: rgba(239, 68, 68, 0.2);
        background: linear-gradient(145deg, rgba(22, 16, 38, 0.98) 0%, rgba(16, 12, 28, 0.98) 100%);
      }
    }

    // 输入框样式
    .input-area {
      flex: 1;
      min-width: 0;
      display: flex;
      align-items: center;

      :deep(.ed-textarea__inner) {
        padding: 0 16px;
        background: transparent !important;
        border: none !important;
        border-radius: 16px !important;
        line-height: 24px;
        font-size: 15px;
        font-weight: 400;
        letter-spacing: 0.2px;
        box-shadow: none !important;
        color: rgba(255, 255, 255, 0.95) !important;
        min-height: 44px !important;
        height: auto !important;
        resize: none;
        display: flex;
        align-items: center;

        &::placeholder {
          color: rgba(196, 181, 253, 0.4);
          font-weight: 400;
        }
      }

      :deep(.ed-input__wrapper),
      :deep(.ed-textarea__wrapper) {
        background: transparent !important;
        box-shadow: none !important;
        border: none !important;
        padding: 0 !important;
      }
      
      &.is-typing :deep(.ed-textarea__inner) {
        color: rgba(196, 181, 253, 0.5) !important;
        cursor: not-allowed;
      }
    }

    // 操作按钮容器
    .action-btn-wrapper {
      flex-shrink: 0;
      padding-right: 6px;
      display: flex;
      align-items: center;
    }

    // 关键词提示按钮（位于 input-top-bar 中，与数据源图标同行）
    .keyword-btn {
      flex-shrink: 0;
      margin-left: auto;
      width: 34px;
      height: 34px;
      border-radius: 10px;
      
      .btn-bg {
        background: rgba(139, 92, 246, 0.08);
      }
      
      .btn-icon {
        width: 17px;
        height: 17px;
        color: rgba(196, 181, 253, 0.45);
      }
      
      &:hover, &.is-active {
        .btn-bg {
          background: rgba(139, 92, 246, 0.2);
        }
        .btn-icon {
          color: rgba(196, 181, 253, 0.85);
        }
      }
    }

    // 操作按钮 - 统一样式
    .action-btn {
      width: 44px;
      height: 44px;
      border-radius: 14px;
      border: none;
      background: transparent;
      cursor: pointer;
      position: relative;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
      
      .btn-bg {
        position: absolute;
        inset: 0;
        border-radius: 14px;
        transition: all 0.25s ease;
      }
      
      .btn-icon {
        position: relative;
        z-index: 1;
        width: 20px;
        height: 20px;
        transition: all 0.25s ease;
      }
      
      // 发送按钮
      &.send-btn {
        .btn-bg {
          background: rgba(139, 92, 246, 0.15);
        }
        
        .btn-icon {
          color: rgba(139, 92, 246, 0.4);
        }
        
        &.is-active {
          .btn-bg {
            background: linear-gradient(145deg, #8b5cf6 0%, #7c3aed 50%, #6d28d9 100%);
            box-shadow: 0 4px 16px rgba(124, 58, 237, 0.4);
          }
          
          .btn-icon {
            color: #fff;
            filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.2));
          }
          
          &:hover {
            transform: translateY(-2px) scale(1.05);
            
            .btn-bg {
              background: linear-gradient(145deg, #9333ea 0%, #8b5cf6 50%, #7c3aed 100%);
              box-shadow: 0 8px 24px rgba(124, 58, 237, 0.5);
            }
          }
          
          &:active {
            transform: translateY(0) scale(0.95);
          }
        }
        
        &:disabled {
          cursor: not-allowed;
          
          &:hover {
            transform: none;
          }
        }
      }
      
      // 停止按钮
      &.stop-btn {
        .btn-bg {
          background: linear-gradient(145deg, #ef4444 0%, #dc2626 50%, #b91c1c 100%);
          box-shadow: 
            0 4px 16px rgba(239, 68, 68, 0.4),
            0 0 0 1px rgba(255, 255, 255, 0.1) inset;
          animation: pulse-stop 1.5s ease-in-out infinite;
        }
        
        .stop-icon {
          position: relative;
          z-index: 1;
          width: 16px;
          height: 16px;
          
          span {
            display: block;
            width: 100%;
            height: 100%;
            background: #fff;
            border-radius: 3px;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
          }
        }
        
        &:hover {
          transform: translateY(-2px) scale(1.05);
          
          .btn-bg {
            background: linear-gradient(145deg, #f87171 0%, #ef4444 50%, #dc2626 100%);
            box-shadow: 
              0 8px 24px rgba(239, 68, 68, 0.5),
              0 0 0 1px rgba(255, 255, 255, 0.15) inset;
          }
        }
        
        &:active {
          transform: translateY(0) scale(0.95);
        }
      }
    }

    // 快捷键提示
    .input-shortcuts {
      display: flex;
      justify-content: center;
      min-height: 28px;
      
      .shortcuts-normal,
      .shortcuts-typing {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
      }
      
      .shortcut-item {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        font-size: 11px;
        color: rgba(196, 181, 253, 0.4);
        
        kbd {
          padding: 3px 7px;
          background: rgba(139, 92, 246, 0.08);
          border: 1px solid rgba(139, 92, 246, 0.12);
          border-radius: 5px;
          font-family: inherit;
          font-size: 10px;
          font-weight: 600;
          color: rgba(196, 181, 253, 0.5);
        }
      }
      
      .shortcut-divider {
        color: rgba(196, 181, 253, 0.2);
        font-size: 10px;
        margin: 0 4px;
      }
      
      .shortcut-stop {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 5px 12px;
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid rgba(239, 68, 68, 0.2);
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.2s ease;
        font-size: 11px;
        color: rgba(252, 165, 165, 0.85);
        
        kbd {
          padding: 2px 6px;
          background: rgba(239, 68, 68, 0.15);
          border: 1px solid rgba(239, 68, 68, 0.25);
          border-radius: 4px;
          font-family: inherit;
          font-size: 10px;
          font-weight: 600;
          color: rgba(252, 165, 165, 0.9);
        }
        
        &:hover {
          background: rgba(239, 68, 68, 0.18);
          border-color: rgba(239, 68, 68, 0.35);
          transform: translateY(-1px);
        }
      }
    }
  }
}

// 按钮切换动画
.btn-switch-enter-active,
.btn-switch-leave-active {
  transition: all 0.2s ease;
}

.btn-switch-enter-from {
  opacity: 0;
  transform: scale(0.8) rotate(-10deg);
}

.btn-switch-leave-to {
  opacity: 0;
  transform: scale(0.8) rotate(10deg);
}

// 渐变流动动画
@keyframes gradient-flow {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}

// 脉冲光效
@keyframes pulse-glow {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 0.6; }
}

// 淡入淡出动画
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

// 停止按钮脉冲动画
@keyframes pulse-stop {
  0%,
  100% {
    box-shadow:
      0 4px 16px rgba(239, 68, 68, 0.45),
      0 0 0 1px rgba(255, 255, 255, 0.1) inset;
  }
  50% {
    box-shadow:
      0 4px 24px rgba(239, 68, 68, 0.6),
      0 0 0 1px rgba(255, 255, 255, 0.15) inset,
      0 0 0 4px rgba(239, 68, 68, 0.15);
  }
}

// 响应式 - 平板
@media (max-width: 1024px) {
  .sidebar-toggle-btn {
    top: 16px;
    left: 16px;

    .toggle-btn-inner {
      width: 40px;
      height: 40px;
      border-radius: 12px;

      .toggle-icon {
        width: 20px;
        height: 20px;
      }
    }

    .toggle-tooltip {
      font-size: 12px;
      padding: 7px 12px;
    }
  }

  .chat-container .chat-footer {
    padding: 0 16px 18px;

    .input-wrapper {
      max-width: 100%;
      gap: 8px;
    }

    .input-top-bar {
      .datasource-badge .badge-content {
        padding: 7px 12px;
        border-radius: 9px;
      }
    }

    .input-main-container {
      .input-border-glow {
        border-radius: 20px;
      }
      
      .input-inner {
        border-radius: 18px;
      }
    }

    .input-area :deep(.ed-textarea__inner) {
      padding: 12px 14px;
      font-size: 15px;
      min-height: 48px !important;
    }

    .action-btn {
      width: 42px;
      height: 42px;
      border-radius: 13px;
    }
  }
}

// 响应式 - 手机
@media (max-width: 768px) {
  .sidebar-toggle-btn {
    top: 12px;
    left: 12px;

    .toggle-btn-inner {
      width: 36px;
      height: 36px;
      border-radius: 10px;

      .toggle-icon {
        width: 18px;
        height: 18px;
      }
    }

    .toggle-tooltip {
      display: none;
    }
  }

  .chat-container .chat-footer {
    padding: 0 12px 16px;

    .input-wrapper {
      gap: 8px;
    }

    .input-top-bar {
      min-height: 32px;
      
      .datasource-badge .badge-content {
        padding: 6px 12px;
        gap: 6px;
        border-radius: 8px;
        
        .ds-icon {
          width: 16px !important;
          height: 16px !important;
        }
        
        .ds-name {
          font-size: 12px;
          max-width: 120px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      }

      .keyword-btn {
        width: 30px;
        height: 30px;
        border-radius: 8px;

        .btn-icon {
          width: 15px;
          height: 15px;
        }
      }
    }

    .input-main-container {
      .input-border-glow {
        border-radius: 18px;
      }
      
      .input-inner {
        border-radius: 16px;
        padding: 3px;
      }
    }

    .input-area :deep(.ed-textarea__inner) {
      padding: 12px 14px;
      font-size: 14px;
      line-height: 22px;
      min-height: 46px !important;
    }

    .action-btn-wrapper {
      padding: 4px;
    }

    .action-btn {
      width: 38px;
      height: 38px;
      border-radius: 12px;
      
      .btn-icon {
        width: 18px;
        height: 18px;
      }
      
      .stop-icon {
        width: 14px;
        height: 14px;
      }
    }

    .input-shortcuts {
      min-height: 24px;
      
      .shortcut-item {
        font-size: 10px;
        
        kbd {
          padding: 2px 5px;
          font-size: 9px;
        }
      }
      
      .shortcut-stop {
        padding: 4px 10px;
        font-size: 10px;
        
        kbd {
          padding: 2px 5px;
          font-size: 9px;
        }
      }
    }
  }
}

// 响应式 - 小手机
@media (max-width: 480px) {
  .chat-container .chat-footer {
    padding: 0 10px 14px;

    .input-wrapper {
      gap: 6px;
    }

    .input-top-bar {
      .datasource-badge .badge-content {
        padding: 5px 10px;
        
        .ds-name {
          max-width: 80px;
        }
      }

      .keyword-btn {
        width: 28px;
        height: 28px;
        border-radius: 7px;

        .btn-icon {
          width: 14px;
          height: 14px;
        }
      }
    }

    .input-main-container {
      .input-inner {
        border-radius: 14px;
      }
    }

    .input-area :deep(.ed-textarea__inner) {
      padding: 10px 12px;
      min-height: 42px !important;
    }

    .action-btn {
      width: 36px;
      height: 36px;
      border-radius: 10px;
    }

    .input-shortcuts {
      display: none;
    }
  }
}

.error-container {
  margin-top: 12px;
}

.tool-btns {
  display: flex;
  flex-direction: row;
  align-items: center;
  flex-wrap: wrap;
  column-gap: 16px;
  row-gap: 8px;
}

.tool-btn {
  font-size: 14px;
  font-weight: 400;
  line-height: 22px;
  color: @dark-text-secondary;
  border-radius: 8px;
  padding: 6px 12px;
  transition: all 0.2s ease;

  .tool-btn-inner {
    display: flex;
    flex-direction: row;
    align-items: center;
  }

  &:hover {
    background: rgba(139, 92, 246, 0.15);
    color: @primary-400;
  }
}

.btn-text {
  margin-left: 4px;
}

.divider {
  width: 1px;
  height: 16px;
  border-left: 1px solid @dark-border;
}

// ============================================
// 欢迎页面样式
// ============================================
.welcome-content-block {
  height: 100%;
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  background: @dark-bg;
  position: relative;
  overflow: hidden;

  .welcome-content {
    width: 100%;
    max-width: 600px;
    display: flex;
    gap: 16px;
    align-items: center;
    flex-direction: column;
    padding: 50px 20px 40px;
    position: relative;
    z-index: 1;
  }
}

// 欢迎页面背景
.welcome-bg {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;

  .bg-gradient {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: radial-gradient(
      ellipse 80% 50% at 50% -20%,
      rgba(139, 92, 246, 0.15) 0%,
      transparent 50%
    );
  }

  .bg-glow {
    position: absolute;
    top: 20%;
    left: 50%;
    transform: translateX(-50%);
    width: 400px;
    height: 400px;
    background: radial-gradient(circle, rgba(139, 92, 246, 0.08) 0%, transparent 70%);
    filter: blur(40px);
  }
}

// 欢迎页面主内容
.welcome-main {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 32px;
  width: 100%;
}

// 快速建议样式
.welcome-suggestions {
  width: 100%;
  max-width: 500px;
  margin-top: -8px;
}

// 品牌区域
.brand-section {
  text-align: center;

  .brand-title {
    font-size: 56px;
    font-weight: 700;
    margin: 0 0 12px 0;
    letter-spacing: -2px;

    .brand-chat {
      color: @dark-text;
    }

    .brand-bi {
      background: linear-gradient(135deg, @primary-400 0%, @primary-500 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
  }

  .brand-tagline {
    font-size: 14px;
    color: @dark-text-muted;
    margin: 0 0 8px 0;
    letter-spacing: 1px;
  }

  .brand-slogan {
    font-size: 18px;
    color: @dark-text-secondary;
    margin: 0;
    font-weight: 500;
  }
}

// 流程展示 - 垂直布局
.flow-vertical {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  width: 100%;
  max-width: 320px;
}

.flow-step {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 24px;
  background: rgba(139, 92, 246, 0.08);
  border: 1px solid @dark-border;
  border-radius: 12px;
  width: 100%;
  box-sizing: border-box;
  transition: all 0.3s ease;

  &.flow-step-highlight {
    &:hover {
      background: rgba(139, 92, 246, 0.12);
      border-color: rgba(139, 92, 246, 0.25);
      transform: translateX(4px);
    }
  }

  .step-icon {
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(139, 92, 246, 0.15);
    border-radius: 10px;
    flex-shrink: 0;

    svg {
      width: 22px;
      height: 22px;
      color: @primary-400;
    }
  }

  .step-content {
    display: flex;
    flex-direction: column;
    gap: 2px;

    .step-title {
      font-size: 15px;
      font-weight: 600;
      color: @dark-text;
    }

    .step-desc {
      font-size: 12px;
      color: @dark-text-muted;
      letter-spacing: 0.3px;
    }
  }
}

.flow-arrow-down {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 24px;

  svg {
    width: 16px;
    height: 16px;
    color: @dark-text-muted;
    opacity: 0.5;
  }
}

// 开始按钮
.start-btn {
  height: 52px;
  padding: 0 32px;
  border-radius: 26px;
  font-size: 16px;
  font-weight: 600;
  background: linear-gradient(135deg, @primary-600 0%, @primary-500 100%);
  border: none;
  box-shadow: 0 8px 32px rgba(124, 58, 237, 0.4);
  transition: all 0.3s ease;

  .btn-content {
    display: flex;
    align-items: center;
    gap: 8px;

    svg {
      width: 20px;
      height: 20px;
      transition: transform 0.3s ease;
    }
  }

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 40px rgba(124, 58, 237, 0.5);

    .btn-content svg {
      transform: translateX(4px);
    }
  }
}

// 底部提示
.welcome-tip {
  font-size: 13px;
  color: @dark-text-muted;
  margin: 0;
  text-align: center;
}

// 助手描述
.assistant-desc {
  width: 100%;
  display: flex;
  align-items: center;
  flex-direction: column;

  .i-am {
    font-weight: 600;
    font-size: 24px;
    line-height: 32px;
    margin: 16px 0;
    max-width: 100%;
    word-break: break-all;
    padding: 0 20px;
    color: @dark-text;
  }

  .i-can {
    margin-bottom: 4px;
    text-align: center;
    font-weight: 400;
    font-size: 14px;
    line-height: 24px;
    color: @dark-text-secondary;
    max-width: 88%;
    word-break: break-all;
    padding: 0 20px;
  }
}

.greeting-btn {
  width: 100%;
  max-width: 400px;
  height: 64px;
  border-radius: 16px;
  border: 1px dashed @dark-border;
  background: rgba(139, 92, 246, 0.08);
  transition: all 0.3s ease;

  .inner-icon {
    display: flex;
    flex-direction: row;
    align-items: center;
    margin-right: 8px;
  }

  font-size: 16px;
  line-height: 24px;
  font-weight: 500;
  color: @primary-400;

  &:hover {
    background: rgba(139, 92, 246, 0.15);
    border-color: @primary-500;
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(139, 92, 246, 0.2);
  }
}
</style>

<style lang="less">
// 智能对话页面标题由全局 page-titles.less 提供统一样式

.assistant-popover_sidebar {
  .ed-drawer {
    height: 100% !important;
    margin-top: 0 !important;
  }
  .ed-drawer__body {
    padding: 0;
  }
}

.popover-chat_history {
  box-shadow: 0px 8px 32px rgba(0, 0, 0, 0.4) !important;
  border-radius: 12px !important;
  overflow: hidden;
  background: linear-gradient(170deg, #12101c 0%, #0a0812 100%) !important;
  border: 1px solid rgba(139, 92, 246, 0.2) !important;
}

.popover-chat_history_small {
  height: calc(100% - 54px);
  padding: 0 !important;
  border: 1px solid rgba(139, 92, 246, 0.2);
  border-radius: 6px;
}

.embedded-history-hidden {
  display: none !important;
}

// 预测对话框自定义样式
:deep(.prediction-dialog) {
  max-width: 700px;
  border-radius: 16px;
  overflow: hidden;
  
  .el-message-box__header {
    display: none;
  }
  
  .el-message-box__content {
    padding: 0;
  }
  
  .el-message-box__message {
    padding: 0;
  }
}
</style>

<style lang="less" scoped>
// 按钮禁用状态样式
.tool-btn.btn-disabled {
  opacity: 0.5;
  cursor: not-allowed;
  
  &:hover {
    background: transparent !important;
    transform: none !important;
  }
  
  .tool-btn-inner {
    opacity: 0.6;
  }
}

// 按钮加载状态
.btn-loading {
  .tool-btn-inner {
    opacity: 0.7;
  }
}

.btn-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(139, 92, 246, 0.3);
  border-top-color: #8b5cf6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

// 状态徽章样式
.status-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-left: 6px;
  font-size: 12px;
  
  &.error {
    color: #f87171;
    animation: pulse 2s ease-in-out infinite;
  }
  
  &.quality-excellent {
    filter: drop-shadow(0 0 4px rgba(250, 204, 21, 0.6));
  }
  
  &.quality-good {
    filter: drop-shadow(0 0 4px rgba(139, 92, 246, 0.6));
  }
  
  &.quality-fair {
    filter: drop-shadow(0 0 4px rgba(96, 165, 250, 0.6));
  }
  
  &.quality-poor {
    filter: drop-shadow(0 0 4px rgba(251, 191, 36, 0.6));
  }
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

// 复制按钮样式
.tool-btn.is-copied {
  background: rgba(34, 197, 94, 0.15) !important;
  border-color: rgba(34, 197, 94, 0.3) !important;
  
  &:hover {
    background: rgba(34, 197, 94, 0.22) !important;
    border-color: rgba(34, 197, 94, 0.4) !important;
  }
  
  .tool-btn-inner {
    color: #4ade80 !important;
  }
  
  .check-icon {
    color: #4ade80;
    font-size: 18px;
    font-weight: 700;
    animation: checkmark-pop 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55);
  }
}

@keyframes checkmark-pop {
  0% {
    transform: scale(0.5);
    opacity: 0;
  }
  50% {
    transform: scale(1.2);
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}
</style>

<style lang="less">
// 错误提示样式（全局）
.error-tooltip {
  background: linear-gradient(135deg, rgba(248, 113, 113, 0.95) 0%, rgba(239, 68, 68, 0.95) 100%) !important;
  border: 1px solid rgba(248, 113, 113, 0.3) !important;
  box-shadow: 0 8px 24px rgba(248, 113, 113, 0.3) !important;
  
  .el-popper__arrow::before {
    background: rgba(248, 113, 113, 0.95) !important;
    border: 1px solid rgba(248, 113, 113, 0.3) !important;
  }
}
</style>

<style lang="less">
// 关键词提示弹出面板（全局样式，因为 popover 被 teleport 到 body）
.keyword-hints-popover {
  background: linear-gradient(145deg, rgba(30, 24, 52, 0.98) 0%, rgba(20, 16, 36, 0.98) 100%) !important;
  border: 1px solid rgba(139, 92, 246, 0.2) !important;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(139, 92, 246, 0.08) inset !important;
  border-radius: 16px !important;
  padding: 0 !important;

  .el-popper__arrow::before {
    background: rgba(30, 24, 52, 0.98) !important;
    border-color: rgba(139, 92, 246, 0.2) !important;
  }

  .kw-hints-panel {
    .kw-hints-header {
      padding: 14px 16px 10px;
      border-bottom: 1px solid rgba(139, 92, 246, 0.1);

      .kw-hints-title {
        display: block;
        font-size: 14px;
        font-weight: 600;
        color: rgba(255, 255, 255, 0.9);
        margin-bottom: 2px;
      }

      .kw-hints-desc {
        display: block;
        font-size: 11px;
        color: rgba(196, 181, 253, 0.45);
      }
    }

    .kw-hints-list {
      padding: 8px 12px 12px;
      max-height: 380px;
      overflow-y: auto;

      &::-webkit-scrollbar {
        width: 4px;
      }
      &::-webkit-scrollbar-thumb {
        background: rgba(139, 92, 246, 0.2);
        border-radius: 2px;
      }

      .kw-cat-item {
        padding: 8px 0;

        & + .kw-cat-item {
          border-top: 1px solid rgba(139, 92, 246, 0.06);
        }

        .kw-cat-header {
          display: flex;
          align-items: center;
          gap: 6px;
          margin-bottom: 6px;

          .kw-cat-icon {
            font-size: 14px;
            line-height: 1;
          }

          .kw-cat-name {
            font-size: 12px;
            font-weight: 500;
            color: rgba(196, 181, 253, 0.7);
          }

          .kw-cat-intent {
            margin-left: auto;
            font-size: 11px;
            color: rgba(139, 92, 246, 0.5);
            white-space: nowrap;
          }
        }

        .kw-tag-list {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;

          .kw-tag {
            display: inline-block;
            padding: 3px 10px;
            font-size: 12px;
            color: rgba(196, 181, 253, 0.75);
            background: rgba(139, 92, 246, 0.1);
            border: 1px solid rgba(139, 92, 246, 0.12);
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
            user-select: none;

            &:hover {
              color: #fff;
              background: rgba(139, 92, 246, 0.3);
              border-color: rgba(139, 92, 246, 0.4);
              transform: translateY(-1px);
            }

            &:active {
              transform: translateY(0);
            }
          }
        }
      }
    }
  }
}
</style>
