<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
// import { useClipboard } from '@vueuse/core'

const { t } = useI18n()

interface Terminology {
  word: string
  description: string
  other_words?: string[]
  similarity: number
  used: boolean
  match_type?: 'keyword' | 'vector'
}

interface SqlExample {
  question: string
  sql: string
  similarity: number
  used: boolean
  match_type?: 'keyword' | 'vector'
}

interface CustomPrompt {
  type: string
  content: string
  used: boolean
  empty: boolean
}

// PDF文档检索结果接口
// 后端发送 document_chunks 但前端未渲染，导致PDF数据源的步骤2（知识检索）显示为空
interface DocumentChunk {
  text: string
  source_type: string
  source_name: string
  source_file: string
  section_title: string
  page_number?: number
  similarity: number
  chunk_type: string
}

const props = defineProps<{
  terminologies: Terminology[]
  sqlExamples: SqlExample[]
  customPrompts?: CustomPrompt[]
  documentChunks?: DocumentChunk[]
  ragEnabled?: boolean  // RAG 永远开启，此字段仅用于历史兼容
  customPromptChecked?: boolean
  metadata?: {
    retrieval_time_ms?: number
    keyword_match_count?: number
    vector_match_count?: number
    datasource_type?: 'global' | 'specific'
    datasource_name?: string
  }
}>()

// 主面板展开/折叠状态
const isExpanded = ref(false)

const toggleExpanded = () => {
  isExpanded.value = !isExpanded.value
}

// 展开状态管理
// const expandedItems = ref<Set<string>>(new Set())

// const toggleDetails = (id: string) => {

// 复制功能
// const { copy } = useClipboard()

// const copyContent = (content: string) => {
const totalCount = computed(() => {
  return props.terminologies.length + props.sqlExamples.length + (props.documentChunks?.length || 0)
})

// 计算有效的自定义提示词数量
const effectiveCustomPrompts = computed(() => {
  return (props.customPrompts || []).filter(p => p.used && !p.empty)
})

const hasResults = computed(() => {
  return totalCount.value > 0 || effectiveCustomPrompts.value.length > 0 || props.customPromptChecked
})

// 归一化相似度到 0-1 范围
// 后端可能返回 0-1 或 0-100 范围的值，统一归一化后再显示
const normalizeSimilarity = (similarity: number): number => {
  if (similarity > 1) return similarity / 100
  return similarity
}

// 计算平均相似度
const avgSimilarity = computed(() => {
  if (totalCount.value === 0) return 0
  const total = [...props.terminologies, ...props.sqlExamples]
    .reduce((sum, item) => sum + normalizeSimilarity(item.similarity), 0)
  return ((total / totalCount.value) * 100).toFixed(1)
})

// 计算使用的知识数量
const usedCount = computed(() => {
  return [...props.terminologies, ...props.sqlExamples]
    .filter(item => item.used).length
})

// 计算检索方式统计
const keywordMatchCount = computed(() => {
  return [...props.terminologies, ...props.sqlExamples]
    .filter(item => item.match_type === 'keyword').length
})

const vectorMatchCount = computed(() => {
  return [...props.terminologies, ...props.sqlExamples]
    .filter(item => item.match_type === 'vector').length
})

// 获取相似度等级
const getSimilarityLevel = (similarity: number) => {
  const norm = normalizeSimilarity(similarity)
  if (norm >= 0.9) return 'excellent'
  if (norm >= 0.7) return 'good'
  if (norm >= 0.5) return 'fair'
  return 'low'
}

// 获取相似度等级文本
const getSimilarityLevelText = (similarity: number) => {
  const level = getSimilarityLevel(similarity)
  const texts = {
    excellent: t('rag.similarity_excellent'),
    good: t('rag.similarity_good'),
    fair: t('rag.similarity_fair'),
    low: t('rag.similarity_low')
  }
  return texts[level] || ''
}

// 移除永远为 false 的 isPureLLMMode
// RAG 永远开启，此计算属性和所有引用它的模板分支均为死代码
</script>

<template>
  <div v-if="hasResults" class="rag-retrieval-results">
    <!-- 紧凑的摘要卡片 - 默认显示 -->
    <div class="rag-summary-card" @click="toggleExpanded">
      <div class="summary-header">
        <div class="header-left">
          <span class="header-icon">🔎</span>
          <span class="header-text">
            {{ t('rag.retrieval_results') }}
          </span>
          <span class="result-count">
            {{ totalCount }} {{ t('rag.items') }}
          </span>
        </div>
        <div class="header-right">
          <!-- 快速统计 -->
          <div class="quick-stats">
            <span class="stat-badge" v-if="metadata?.retrieval_time_ms">
              <span class="stat-icon">⚡</span>
              {{ metadata.retrieval_time_ms }}ms
            </span>
            <span class="stat-badge success">
              <span class="stat-icon">✓</span>
              {{ usedCount }}/{{ totalCount }}
            </span>
            <span class="stat-badge" v-if="totalCount > 0">
              <span class="stat-icon">🎯</span>
              {{ avgSimilarity }}%
            </span>
          </div>
          <!-- 展开/折叠按钮 -->
          <button class="expand-btn" :class="{ expanded: isExpanded }">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
              <path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z"/>
            </svg>
          </button>
        </div>
      </div>
      
      <!-- 紧凑的知识预览 - 只在折叠时显示 -->
      <div v-if="!isExpanded" class="summary-preview">
        <div class="preview-items">
          <!-- RAG模式预览 -->
            <span v-if="terminologies.length > 0" class="preview-tag">
              📘 {{ terminologies.length }} {{ t('rag.terminology') }}
            </span>
            <span v-if="sqlExamples.length > 0" class="preview-tag">
              🗃️ {{ sqlExamples.length }} {{ t('rag.sql_examples') }}
            </span>
            <span v-if="documentChunks && documentChunks.length > 0" class="preview-tag vector">
              📄 {{ documentChunks.length }} {{ t('rag.document_chunks') || '文档片段' }}
            </span>
            <span v-if="keywordMatchCount > 0" class="preview-tag keyword">
              🔤 {{ keywordMatchCount }} {{ t('rag.keyword') }}
            </span>
            <span v-if="vectorMatchCount > 0" class="preview-tag vector">
              🧠 {{ vectorMatchCount }} {{ t('rag.vector') }}
            </span>
        </div>
        <div class="expand-hint">
          <span>{{ t('rag.click_to_view_details') }}</span>
        </div>
      </div>
    </div>

    <!-- 详细内容 - 展开时显示 -->
    <transition name="expand">
      <div v-if="isExpanded" class="rag-details">
        <!-- 详细统计 -->
        <div class="results-stats">
          <div class="stat-item" v-if="metadata?.retrieval_time_ms">
            <span class="stat-icon">⚡</span>
            <span class="stat-label">{{ t('rag.retrieval_time') }}</span>
            <span class="stat-value">{{ metadata.retrieval_time_ms }}ms</span>
          </div>
          <div class="stat-item">
            <span class="stat-icon">📊</span>
            <span class="stat-label">{{ t('rag.total_items') }}</span>
            <span class="stat-value">{{ totalCount }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-icon">✅</span>
            <span class="stat-label">{{ t('rag.used_items') }}</span>
            <span class="stat-value highlight">{{ usedCount }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-icon">🎯</span>
            <span class="stat-label">{{ t('rag.avg_similarity') }}</span>
            <span class="stat-value">{{ avgSimilarity }}%</span>
          </div>
        </div>

        <!-- RAG 知识注入摘要 — 展示RAG如何弥补LLM三大缺陷 -->
        <div class="rag-injection-summary">
          <div class="injection-header">
            <span class="injection-icon">🛡️</span>
            <span class="injection-title">{{ t('rag.injection_summary_title') }}</span>
          </div>
          <div class="injection-items">
            <!-- 信息滞后 → 实时数据库结构注入 -->
            <div class="injection-item">
              <div class="injection-problem">
                <span class="problem-icon">⏱️</span>
                <span class="problem-label">{{ t('rag.deficiency_lag') }}</span>
              </div>
              <div class="injection-solution">
                <span class="solution-arrow">→</span>
                <span class="solution-text">{{ t('rag.solution_lag') }}</span>
              </div>
            </div>
            <!-- 专业领域知识不足 → 注入术语/SQL/规则 -->
            <div class="injection-item">
              <div class="injection-problem">
                <span class="problem-icon">📚</span>
                <span class="problem-label">{{ t('rag.deficiency_domain') }}</span>
              </div>
              <div class="injection-solution">
                <span class="solution-arrow">→</span>
                <span class="solution-text">
                  {{ t('rag.solution_domain', {
                    termCount: terminologies.length,
                    sqlCount: sqlExamples.length,
                    promptCount: effectiveCustomPrompts.length
                  }) }}
                </span>
              </div>
            </div>
            <!-- 幻觉抑制 → 表结构验证 + SQL检查 -->
            <div class="injection-item">
              <div class="injection-problem">
                <span class="problem-icon">🔒</span>
                <span class="problem-label">{{ t('rag.deficiency_hallucination') }}</span>
              </div>
              <div class="injection-solution">
                <span class="solution-arrow">→</span>
                <span class="solution-text">{{ t('rag.solution_hallucination') }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 检索方式统计 -->
        <div class="retrieval-methods" v-if="keywordMatchCount > 0 || vectorMatchCount > 0">
          <span class="method-label">{{ t('rag.retrieval_methods') }}:</span>
          <span class="method-tag keyword" v-if="keywordMatchCount > 0">
            <span class="method-icon">🔤</span>
            {{ t('rag.keyword_match') }}: {{ keywordMatchCount }}
          </span>
          <span class="method-tag vector" v-if="vectorMatchCount > 0">
            <span class="method-icon">🧠</span>
            {{ t('rag.vector_match') }}: {{ vectorMatchCount }}
          </span>
        </div>

        <!-- 术语检索结果 -->
        <div v-if="terminologies.length > 0" class="result-section">
          <div class="section-header">
            <span class="section-icon">📘</span>
            <span class="section-title">{{ t('rag.terminology') }}</span>
            <span class="section-count">({{ terminologies.length }})</span>
          </div>
          
          <div class="result-items">
            <div 
              v-for="(term, index) in terminologies" 
              :key="index"
              class="result-item"
              :class="{ 'item-used': term.used }"
            >
              <div class="item-header">
                <div class="item-title-group">
                  <span class="item-name">{{ term.word }}</span>
                  <!-- 匹配方式标签 -->
                  <span class="match-type-tag" v-if="term.match_type === 'keyword'">
                    🔤 {{ t('rag.keyword') }}
                  </span>
                  <span class="match-type-tag vector" v-else-if="term.match_type === 'vector'">
                    🧠 {{ t('rag.vector') }}
                  </span>
                </div>
                <div class="item-badges">
                  <span 
                    class="similarity-badge" 
                    :class="`level-${getSimilarityLevel(term.similarity)}`"
                    :title="getSimilarityLevelText(term.similarity)"
                  >
                    {{ (normalizeSimilarity(term.similarity) * 100).toFixed(0) }}%
                  </span>
                  <span v-if="term.used" class="used-badge">
                    <svg viewBox="0 0 24 24" fill="currentColor" width="12" height="12">
                      <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                    </svg>
                    {{ t('rag.applied') }}
                  </span>
                </div>
              </div>
              
              <!-- 相似度可视化进度条 -->
              <div class="similarity-bar">
                <div 
                  class="similarity-fill" 
                  :class="`level-${getSimilarityLevel(term.similarity)}`"
                  :style="{ width: `${normalizeSimilarity(term.similarity) * 100}%` }"
                ></div>
              </div>
              
              <div class="item-description">
                {{ term.description }}
              </div>
              
              <div v-if="term.other_words && term.other_words.length > 0" class="item-synonyms">
                <span class="synonyms-label">{{ t('rag.synonyms') }}:</span>
                <span 
                  v-for="(word, idx) in term.other_words" 
                  :key="idx"
                  class="synonym-tag"
                >
                  {{ word }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- SQL 示例检索结果 -->
        <div v-if="sqlExamples.length > 0" class="result-section">
          <div class="section-header">
            <span class="section-icon">🗃️</span>
            <span class="section-title">{{ t('rag.sql_examples') }}</span>
            <span class="section-count">({{ sqlExamples.length }})</span>
          </div>
          
          <div class="result-items">
            <div 
              v-for="(example, index) in sqlExamples" 
              :key="index"
              class="result-item"
              :class="{ 'item-used': example.used }"
            >
              <div class="item-header">
                <span class="item-name">{{ example.question }}</span>
                <div class="item-badges">
                  <span 
                    class="similarity-badge" 
                    :class="`level-${getSimilarityLevel(example.similarity)}`"
                    :title="getSimilarityLevelText(example.similarity)"
                  >
                    {{ (normalizeSimilarity(example.similarity) * 100).toFixed(0) }}%
                  </span>
                  <span v-if="example.used" class="used-badge">
                    <svg viewBox="0 0 24 24" fill="currentColor" width="12" height="12">
                      <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                    </svg>
                    {{ t('rag.applied') }}
                  </span>
                </div>
              </div>
              
              <!-- 相似度可视化进度条 -->
              <div class="similarity-bar">
                <div 
                  class="similarity-fill" 
                  :class="`level-${getSimilarityLevel(example.similarity)}`"
                  :style="{ width: `${normalizeSimilarity(example.similarity) * 100}%` }"
                ></div>
              </div>
              
              <div class="item-code">
                <pre><code>{{ example.sql }}</code></pre>
              </div>
            </div>
          </div>
        </div>
        <!-- 自定义提示词展示 -->
        <div v-if="documentChunks && documentChunks.length > 0" class="result-section">
          <div class="section-header">
            <span class="section-icon">📄</span>
            <span class="section-title">{{ t('rag.document_chunks') || '文档片段' }}</span>
            <span class="section-count">({{ documentChunks.length }})</span>
          </div>
          
          <div class="result-items">
            <div 
              v-for="(chunk, index) in documentChunks" 
              :key="'dc-' + index"
              class="result-item item-used"
            >
              <div class="item-header">
                <div class="item-title-group">
                  <span class="item-name">{{ chunk.section_title || chunk.source_name || chunk.source_file }}</span>
                  <span v-if="chunk.page_number" class="match-type-tag">
                    📑 {{ t('rag.page') || '第' }}{{ chunk.page_number }}{{ t('rag.page_suffix') || '页' }}
                  </span>
                  <span v-if="chunk.chunk_type === 'table'" class="match-type-tag vector">
                    📊 {{ t('rag.table_data') || '表格数据' }}
                  </span>
                </div>
                <div class="item-badges">
                  <span 
                    class="similarity-badge" 
                    :class="`level-${getSimilarityLevel(chunk.similarity)}`"
                    :title="getSimilarityLevelText(chunk.similarity)"
                  >
                    {{ (normalizeSimilarity(chunk.similarity) * 100).toFixed(0) }}%
                  </span>
                </div>
              </div>
              
              <div class="similarity-bar">
                <div 
                  class="similarity-fill" 
                  :class="`level-${getSimilarityLevel(chunk.similarity)}`"
                  :style="{ width: `${normalizeSimilarity(chunk.similarity) * 100}%` }"
                ></div>
              </div>
              
              <div class="item-description">
                {{ chunk.text.length > 200 ? chunk.text.slice(0, 200) + '...' : chunk.text }}
              </div>
            </div>
          </div>
        </div>

        <!-- 自定义提示词展示（原有） -->
        <div v-if="customPrompts && customPrompts.length > 0" class="result-section">
          <div class="section-header">
            <span class="section-icon">📌</span>
            <span class="section-title">{{ t('prompt.customize_prompt_words') }}</span>
            <span class="section-count">({{ effectiveCustomPrompts.length }})</span>
          </div>
          
          <div class="result-items">
            <div 
              v-for="(prompt, index) in customPrompts" 
              :key="index"
              class="result-item prompt-item"
              :class="{ 'item-used': prompt.used && !prompt.empty, 'item-empty': prompt.empty }"
            >
              <div class="item-header">
                <div class="item-title-group">
                  <span class="item-name">{{ prompt.type }}</span>
                  <span class="prompt-status-tag" v-if="prompt.empty">
                    ⚠️ {{ t('prompt.not_configured') }}
                  </span>
                  <span class="prompt-status-tag active" v-else-if="prompt.used">
                    ✅ {{ t('prompt.in_use') }}
                  </span>
                </div>
              </div>
              
              <div v-if="!prompt.empty" class="item-description prompt-content">
                {{ prompt.content }}
              </div>
              <div v-else class="item-description prompt-empty-hint">
                {{ t('prompt.empty_hint') }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped lang="less">
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@success-400: #4ade80;
@success-500: #22c55e;
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.85);
@dark-text-muted: rgba(196, 181, 253, 0.6);

.rag-retrieval-results {
  display: flex;
  flex-direction: column;
  gap: 0;
  margin-bottom: 16px;
}

// 紧凑的摘要卡片
.rag-summary-card {
  background: linear-gradient(145deg, rgba(139, 92, 246, 0.08) 0%, rgba(168, 85, 247, 0.04) 100%);
  border: 1px solid rgba(139, 92, 246, 0.2);
  border-radius: 12px;
  padding: 12px 16px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  user-select: none;

  &.llm-mode {
    background: linear-gradient(145deg, rgba(139, 92, 246, 0.08) 0%, rgba(88, 28, 135, 0.04) 100%);
    border-color: rgba(139, 92, 246, 0.2);

    &:hover {
      background: linear-gradient(145deg, rgba(139, 92, 246, 0.12) 0%, rgba(88, 28, 135, 0.06) 100%);
      border-color: rgba(139, 92, 246, 0.3);
    }
  }

  &:hover {
    background: linear-gradient(145deg, rgba(139, 92, 246, 0.12) 0%, rgba(168, 85, 247, 0.06) 100%);
    border-color: rgba(139, 92, 246, 0.3);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(139, 92, 246, 0.15);
  }

  &:active {
    transform: translateY(0);
  }

  .summary-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;

    .header-left {
      display: flex;
      align-items: center;
      gap: 8px;
      flex: 1;
      min-width: 0;

      .header-icon {
        font-size: 16px;
        flex-shrink: 0;
      }

      .header-text {
        font-size: 13px;
        font-weight: 600;
        color: @primary-400;
        letter-spacing: 0.3px;
        flex-shrink: 0;
      }

      .result-count {
        font-size: 12px;
        color: @dark-text-muted;
        padding: 2px 8px;
        background: rgba(139, 92, 246, 0.1);
        border-radius: 6px;
        font-weight: 500;
      }
    }

    .header-right {
      display: flex;
      align-items: center;
      gap: 10px;

      .quick-stats {
        display: flex;
        align-items: center;
        gap: 6px;

        .stat-badge {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          padding: 4px 8px;
          background: rgba(139, 92, 246, 0.12);
          border-radius: 6px;
          font-size: 11px;
          font-weight: 600;
          color: @primary-400;
          border: 1px solid rgba(139, 92, 246, 0.2);

          .stat-icon {
            font-size: 12px;
          }

          &.success {
            background: rgba(139, 92, 246, 0.15);
            color: @primary-400;
            border-color: rgba(139, 92, 246, 0.25);
          }

          &.llm {
            background: rgba(139, 92, 246, 0.15);
            color: @primary-400;
            border-color: rgba(139, 92, 246, 0.25);
          }
        }
      }

      .expand-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 24px;
        height: 24px;
        background: rgba(139, 92, 246, 0.12);
        border: 1px solid rgba(139, 92, 246, 0.25);
        border-radius: 6px;
        color: @primary-400;
        cursor: pointer;
        transition: all 0.3s ease;
        padding: 0;

        svg {
          transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        &.expanded svg {
          transform: rotate(180deg);
        }

        &:hover {
          background: rgba(139, 92, 246, 0.2);
          border-color: rgba(139, 92, 246, 0.35);
        }
      }
    }
  }

  .summary-preview {
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid rgba(139, 92, 246, 0.15);

    .preview-items {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 8px;

      .preview-tag {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 4px 10px;
        background: rgba(139, 92, 246, 0.1);
        border: 1px solid rgba(139, 92, 246, 0.2);
        border-radius: 6px;
        font-size: 11px;
        font-weight: 600;
        color: @primary-400;

        &.keyword {
          background: rgba(59, 130, 246, 0.12);
          color: #60a5fa;
          border-color: rgba(59, 130, 246, 0.2);
        }

        &.vector {
          background: rgba(168, 85, 247, 0.12);
          color: @primary-400;
          border-color: rgba(168, 85, 247, 0.2);
        }

        &.llm {
          background: rgba(139, 92, 246, 0.15);
          color: @primary-400;
          border-color: rgba(139, 92, 246, 0.25);
        }

        &.prompt {
          background: rgba(251, 191, 36, 0.15);
          color: #fbbf24;
          border-color: rgba(251, 191, 36, 0.25);
        }

        &.prompt-empty {
          background: rgba(156, 163, 175, 0.15);
          color: #9ca3af;
          border-color: rgba(156, 163, 175, 0.25);
        }
      }
    }

    .expand-hint {
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      color: @dark-text-muted;
      font-style: italic;
      opacity: 0.8;
    }
  }
}

// 详细内容区域
.rag-details {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  background: linear-gradient(145deg, rgba(139, 92, 246, 0.06) 0%, rgba(168, 85, 247, 0.03) 100%);
  border: 1px solid rgba(139, 92, 246, 0.15);
  border-top: none;
  border-radius: 0 0 12px 12px;
  margin-top: -1px;
}

// 展开/折叠动画
.expand-enter-active,
.expand-leave-active {
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  max-height: 2000px;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
  transform: translateY(-10px);
}


.results-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;

  .stat-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 10px 12px;
    background: rgba(139, 92, 246, 0.08);
    border-radius: 10px;
    border: 1px solid rgba(139, 92, 246, 0.15);
    transition: all 0.2s ease;

    &:hover {
      background: rgba(139, 92, 246, 0.12);
      border-color: rgba(139, 92, 246, 0.25);
      transform: translateY(-2px);
    }

    .stat-icon {
      font-size: 16px;
      margin-bottom: 2px;
    }

    .stat-label {
      font-size: 11px;
      color: @dark-text-muted;
      font-weight: 500;
    }

    .stat-value {
      font-size: 18px;
      font-weight: 700;
      color: @primary-400;
      font-variant-numeric: tabular-nums;

      &.highlight {
        color: @primary-400;
      }
    }
  }
}

// RAG 知识注入摘要
.rag-injection-summary {
  padding: 14px 16px;
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.1) 0%, rgba(59, 130, 246, 0.06) 100%);
  border: 1px solid rgba(139, 92, 246, 0.2);
  border-radius: 12px;

  .injection-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;

    .injection-icon {
      font-size: 16px;
    }

    .injection-title {
      font-size: 13px;
      font-weight: 600;
      color: @primary-400;
      letter-spacing: 0.3px;
    }
  }

  .injection-items {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .injection-item {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 8px 12px;
    background: rgba(139, 92, 246, 0.06);
    border-radius: 8px;
    border: 1px solid rgba(139, 92, 246, 0.1);
    transition: all 0.2s ease;

    &:hover {
      background: rgba(139, 92, 246, 0.1);
      border-color: rgba(139, 92, 246, 0.2);
    }

    .injection-problem {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-shrink: 0;
      min-width: 140px;

      .problem-icon {
        font-size: 14px;
      }

      .problem-label {
        font-size: 12px;
        font-weight: 600;
        color: @dark-text-secondary;
      }
    }

    .injection-solution {
      display: flex;
      align-items: flex-start;
      gap: 6px;
      flex: 1;

      .solution-arrow {
        color: @success-400;
        font-weight: 700;
        font-size: 13px;
        flex-shrink: 0;
        margin-top: 1px;
      }

      .solution-text {
        font-size: 12px;
        color: @dark-text-muted;
        line-height: 1.5;
      }
    }
  }
}

// 检索方式统计
.retrieval-methods {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: rgba(139, 92, 246, 0.06);
  border-radius: 12px;
  border: 1px solid rgba(139, 92, 246, 0.12);
  margin-bottom: 8px;

  .method-label {
    font-size: 13px;
    font-weight: 600;
    color: @dark-text-secondary;
  }

  .method-tag {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    transition: all 0.2s ease;

    .method-icon {
      font-size: 14px;
    }

    &.keyword {
      background: rgba(59, 130, 246, 0.15);
      color: #60a5fa;
      border: 1px solid rgba(59, 130, 246, 0.25);

      &:hover {
        background: rgba(59, 130, 246, 0.25);
        transform: scale(1.05);
      }
    }

    &.vector {
      background: rgba(168, 85, 247, 0.15);
      color: @primary-400;
      border: 1px solid rgba(168, 85, 247, 0.25);

      &:hover {
        background: rgba(168, 85, 247, 0.25);
        transform: scale(1.05);
      }
    }
  }
}

.result-section {
  display: flex;
  flex-direction: column;
  gap: 12px;

  .section-header {
    display: flex;
    align-items: center;
    gap: 8px;

    .section-icon {
      font-size: 16px;
    }

    .section-title {
      font-size: 14px;
      font-weight: 600;
      color: @dark-text-secondary;
    }

    .section-count {
      font-size: 12px;
      color: @dark-text-muted;
    }
  }

  .result-items {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
}

.result-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 16px;
  background: rgba(139, 92, 246, 0.06);
  border: 1px solid rgba(139, 92, 246, 0.12);
  border-radius: 12px;
  transition: all 0.3s ease;

  &.item-used {
    background: rgba(139, 92, 246, 0.08);
    border-color: rgba(139, 92, 246, 0.25);
  }

  &:hover {
    background: rgba(139, 92, 246, 0.1);
    border-color: rgba(139, 92, 246, 0.2);
    transform: translateX(2px);
  }

  .item-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;

    .item-title-group {
      display: flex;
      align-items: center;
      gap: 8px;
      flex: 1;
      min-width: 0;

      .item-name {
        font-size: 14px;
        font-weight: 600;
        color: @dark-text;
      }

      .match-type-tag {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 600;
        background: rgba(59, 130, 246, 0.15);
        color: #60a5fa;
        border: 1px solid rgba(59, 130, 246, 0.25);
        flex-shrink: 0;

        &.vector {
          background: rgba(168, 85, 247, 0.15);
          color: @primary-400;
          border-color: rgba(168, 85, 247, 0.25);
        }
      }
    }

    .item-badges {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-shrink: 0;
    }

    .similarity-badge {
      font-size: 11px;
      font-weight: 600;
      padding: 3px 8px;
      border-radius: 6px;
      transition: all 0.3s ease;

      &.level-excellent {
        background: rgba(34, 197, 94, 0.2);
        color: #4ade80;
        border: 1px solid rgba(34, 197, 94, 0.3);
      }

      &.level-good {
        background: rgba(59, 130, 246, 0.2);
        color: #60a5fa;
        border: 1px solid rgba(59, 130, 246, 0.3);
      }

      &.level-fair {
        background: rgba(251, 191, 36, 0.2);
        color: #fbbf24;
        border: 1px solid rgba(251, 191, 36, 0.3);
      }

      &.level-low {
        background: rgba(239, 68, 68, 0.2);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.3);
      }
    }

    .used-badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-size: 11px;
      font-weight: 600;
      padding: 3px 8px;
      background: rgba(139, 92, 246, 0.15);
      border-radius: 6px;
      color: @primary-400;

      svg {
        flex-shrink: 0;
      }
    }
  }

  // 相似度可视化进度条
  .similarity-bar {
    width: 100%;
    height: 4px;
    background: rgba(139, 92, 246, 0.1);
    border-radius: 2px;
    overflow: hidden;
    position: relative;

    .similarity-fill {
      height: 100%;
      border-radius: 2px;
      transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
      position: relative;
      overflow: hidden;

      // 添加shimmer动画效果
      &::after {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(
          90deg,
          transparent,
          rgba(255, 255, 255, 0.3),
          transparent
        );
        animation: shimmer 2s ease-in-out infinite;
      }

      &.level-excellent {
        background: linear-gradient(90deg, #22c55e 0%, #4ade80 100%);
      }

      &.level-good {
        background: linear-gradient(90deg, #3b82f6 0%, #60a5fa 100%);
      }

      &.level-fair {
        background: linear-gradient(90deg, #f59e0b 0%, #fbbf24 100%);
      }

      &.level-low {
        background: linear-gradient(90deg, #ef4444 0%, #f87171 100%);
      }
    }
  }

  .item-synonyms {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;

    .synonyms-label {
      font-size: 12px;
      color: @dark-text-muted;
    }

    .synonym-tag {
      font-size: 11px;
      padding: 2px 8px;
      background: rgba(139, 92, 246, 0.1);
      border-radius: 4px;
      color: @dark-text-muted;
    }
  }

  .item-code {
    margin-top: 4px;

    pre {
      margin: 0;
      padding: 12px;
      background: rgba(26, 18, 37, 0.8);
      border-radius: 8px;
      overflow-x: auto;

      code {
        font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
        font-size: 12px;
        line-height: 1.5;
        color: @primary-400;
      }
    }
  }

  // 自定义提示词样式
  &.prompt-item {
    background: rgba(251, 191, 36, 0.06);
    border-color: rgba(251, 191, 36, 0.15);

    &.item-used {
      background: rgba(251, 191, 36, 0.1);
      border-color: rgba(251, 191, 36, 0.25);
    }

    &.item-empty {
      background: rgba(156, 163, 175, 0.06);
      border-color: rgba(156, 163, 175, 0.15);
      opacity: 0.7;
    }

    &:hover {
      background: rgba(251, 191, 36, 0.12);
      border-color: rgba(251, 191, 36, 0.25);
    }

    .prompt-status-tag {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 3px 8px;
      border-radius: 6px;
      font-size: 11px;
      font-weight: 600;
      background: rgba(156, 163, 175, 0.15);
      color: #9ca3af;
      border: 1px solid rgba(156, 163, 175, 0.25);
      flex-shrink: 0;

      &.active {
        background: rgba(34, 197, 94, 0.15);
        color: @success-400;
        border-color: rgba(34, 197, 94, 0.25);
      }
    }

    .prompt-content {
      font-size: 13px;
      line-height: 1.6;
      color: @dark-text-secondary;
      padding: 10px 12px;
      background: rgba(251, 191, 36, 0.12);
      border-radius: 8px;
      border-left: 3px solid rgba(251, 191, 36, 0.5);
    }

    .prompt-empty-hint {
      font-size: 12px;
      color: @dark-text-muted;
      font-style: italic;
    }
  }
}

// 纯LLM模式说明
.llm-mode-notice {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.08) 0%, rgba(88, 28, 135, 0.04) 100%);
  border: 1px solid rgba(139, 92, 246, 0.2);
  border-radius: 12px;
  margin-top: 12px;

  .notice-icon {
    font-size: 24px;
    flex-shrink: 0;
  }

  .notice-content {
    display: flex;
    flex-direction: column;
    gap: 6px;

    .notice-title {
      font-size: 14px;
      font-weight: 600;
      color: @primary-400;
    }

    .notice-desc {
      font-size: 12px;
      color: @dark-text-muted;
      line-height: 1.5;
    }
  }
}

@keyframes shimmer {
  0% {
    left: -100%;
  }
  100% {
    left: 100%;
  }
}

// 响应式
@media (max-width: 768px) {
  .rag-summary-card {
    padding: 10px 14px;

    .summary-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 10px;

      .header-right {
        width: 100%;
        justify-content: space-between;

        .quick-stats {
          flex-wrap: wrap;
        }
      }
    }
  }

  .rag-details {
    padding: 14px;
  }

  .result-item {
    padding: 12px 14px;

    .item-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 8px;

      .item-badges {
        width: 100%;
        justify-content: flex-start;
      }
    }
  }
}
</style>
