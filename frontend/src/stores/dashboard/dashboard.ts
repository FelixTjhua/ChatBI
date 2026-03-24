import { defineStore } from 'pinia'
import { store } from '@/stores'

export const dashboardStore = defineStore('dashboard', {
  state: () => {
    return {
      curComponent: null as any,
      curComponentId: null as any,
      componentData: [] as any[],
      canvasStyleData: {
        width: 1920,
        height: 1080,
        scale: 100,
        color: '#0f0a1a',
        opacity: 1,
        background: '#0f0a1a',
      },
      canvasViewInfo: {},
      dashboardInfo: {
        id: null,
        name: null,
        pid: null,
        dataState: null,
        contentId: null,
      },
      fullscreenFlag: false,
      tabMoveInActiveId: null,
      dataPrepareState: false,
      // New state for enhanced dashboard
      autoRefreshInterval: 0,
      lastRefreshTime: null as Date | null,
      aiSummary: '',
      layoutMode: 'grid' as 'grid' | 'free',
      presentationMode: false,
    }
  },
  actions: {
    setCurComponent(value: any) {
      this.curComponent = value?.component || null
      this.curComponentId = value && value.id ? value.id : null
    },
    setDashboardInfo(value: any) {
      this.dashboardInfo = value
    },
    setComponentData(value: any) {
      this.componentData = value
    },
    setCanvasStyleData(value: any) {
      this.canvasStyleData = value
    },
    setCanvasViewInfo(value: any) {
      this.canvasViewInfo = value
    },
    setTabMoveInActiveId(tabId: any) {
      this.tabMoveInActiveId = tabId
    },
    updateDashboardInfo(params: any) {
      Object.keys(params).forEach((key: string) => {
        if (params[key]) {
          // @ts-expect-error
          this.dashboardInfo[key] = params[key]
        }
      })
    },
    setFullscreenFlag(value: boolean) {
      this.fullscreenFlag = value
    },
    setDataPrepareState(value: boolean) {
      this.dataPrepareState = value
    },
    setAutoRefreshInterval(value: number) {
      this.autoRefreshInterval = value
    },
    setLastRefreshTime(value: Date | null) {
      this.lastRefreshTime = value
    },
    setAiSummary(value: string) {
      this.aiSummary = value
    },
    setLayoutMode(value: 'grid' | 'free') {
      this.layoutMode = value
    },
    setPresentationMode(value: boolean) {
      this.presentationMode = value
    },
    canvasDataInit() {
      this.curComponent = null
      this.curComponentId = null
      this.componentData = []
      this.canvasViewInfo = {}
      this.dashboardInfo = {
        id: null,
        name: null,
        pid: null,
        dataState: null,
        contentId: null,
      }
      this.aiSummary = ''
      this.lastRefreshTime = null
    },
  },
})

export const dashboardStoreWithOut = () => {
  return dashboardStore(store)
}
