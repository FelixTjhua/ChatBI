import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { store } from './index'

/**
 * RAG模式Store
 *
 * @deprecated RAG 在后端永远开启（对齐 SQLBot 架构），此 Store 仅保留向后兼容。
 * 所有方法均为空操作，isRagEnabled 始终返回 true。
 * 前端不应再展示 RAG 开关 UI，后续版本将移除此文件。
 */
export const useRagModeStore = defineStore('ragMode', () => {
  // RAG 永远开启，不再从 localStorage 读取
  const ragEnabled = ref<boolean>(true)

  const isRagEnabled = computed(() => true)

  /** @deprecated 无操作，RAG 永远开启 */
  function toggleRagMode() {
    // no-op: RAG is always enabled on the backend
  }

  /** @deprecated 无操作，RAG 永远开启 */
  function setRagMode(_value: boolean) {
    // no-op: RAG is always enabled on the backend
  }

  /** @deprecated 无操作，RAG 永远开启 */
  function enableRag() {
    // no-op
  }

  /** @deprecated 无操作，RAG 永远开启 */
  function disableRag() {
    // no-op
  }

  return {
    ragEnabled,
    isRagEnabled,
    toggleRagMode,
    setRagMode,
    enableRag,
    disableRag,
  }
})

export const useRagModeStoreWithOut = () => {
  return useRagModeStore(store)
}
