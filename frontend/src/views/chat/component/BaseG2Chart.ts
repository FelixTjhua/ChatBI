import { BaseChart } from '@/views/chat/component/BaseChart.ts'
import { Chart } from '@antv/g2'

// 深色主题调色板
export const DARK_CATEGORY10 = [
  '#a78bfa', // primary-400
  '#c084fc', // purple-400
  '#f472b6', // pink-400
  '#67e8f9', // cyan-300
  '#86efac', // green-300
  '#fbbf24', // amber-400
  '#fb923c', // orange-400
  '#f87171', // red-400
  '#a3e635', // lime-400
  '#38bdf8', // sky-400
]

// 深色主题配置 — 不使用 type: 'dark'，手动配置所有暗色样式
// G2 v5 的 dark 主题会强制覆盖 theta coordinate interval 的颜色
const darkTheme = {
  view: {
    viewFill: 'transparent',
  },
  category10: DARK_CATEGORY10,
  color: '#e2e8f0',
  axis: {
    labelFill: '#ffffff',
    labelOpacity: 0.85,
    labelFontSize: 12,
    labelFontWeight: 'normal',
    titleFill: '#ffffff',
    titleOpacity: 0.95,
    titleFontSize: 13,
    titleFontWeight: 600,
    gridStroke: 'rgba(139, 92, 246, 0.12)',
    gridStrokeWidth: 1,
    lineStroke: 'rgba(139, 92, 246, 0.25)',
    lineStrokeWidth: 1,
    tickStroke: 'rgba(139, 92, 246, 0.25)',
  },
  legend: {
    itemLabelFill: 'rgba(255, 255, 255, 0.95)',
    itemLabelFontSize: 13,
    itemLabelFontWeight: 500,
    itemMarkerFillOpacity: 1,
    itemMarkerSize: 10,
    backgroundFill: 'transparent',
  },
  legendCategory: {
    itemLabelFill: '#ffffff',
    itemLabelFillOpacity: 0.95,
    itemLabelFontSize: 13,
    itemLabelFontWeight: 500,
    itemMarkerFillOpacity: 1,
    itemMarkerSize: 10,
    backgroundFill: 'transparent',
    itemValueFill: '#ffffff',
    itemValueFillOpacity: 0.85,
    titleFill: '#ffffff',
    titleFillOpacity: 0.85,
    navButtonFill: '#ffffff',
    navButtonFillOpacity: 0.65,
    navPageNumFill: '#ffffff',
    navPageNumFillOpacity: 0.45,
  },
  legendContinuous: {
    labelFill: '#ffffff',
    labelFillOpacity: 0.85,
    labelFontSize: 12,
    handleLabelFill: '#ffffff',
    handleLabelFillOpacity: 0.85,
    handleMarkerFill: '#ffffff',
    handleMarkerFillOpacity: 0.6,
    titleFillOpacity: 0.9,
  },
  tooltip: {
    crosshairsStroke: '#ffffff',
    crosshairsLineWidth: 1,
    crosshairsStrokeOpacity: 0.25,
    css: {
      '.g2-tooltip': {
        background: 'rgba(26, 18, 37, 0.95)',
        'border-radius': '10px',
        'border': '1px solid rgba(139, 92, 246, 0.3)',
        'box-shadow': '0 8px 32px rgba(0, 0, 0, 0.4)',
        'backdrop-filter': 'blur(8px)',
        color: 'rgba(255, 255, 255, 0.95)',
      },
      '.g2-tooltip-title': {
        color: 'rgba(255, 255, 255, 0.95)',
        'font-size': '13px',
        'font-weight': '600',
      },
      '.g2-tooltip-list-item-name-label': {
        color: 'rgba(196, 181, 253, 0.85)',
        'font-size': '12px',
      },
      '.g2-tooltip-list-item-value': {
        color: 'rgba(255, 255, 255, 0.95)',
        'font-size': '12px',
        'font-weight': '500',
      },
      '.g2-tooltip-list-item-name-icon': {
        width: '8px',
        height: '8px',
      },
    },
  },
  label: {
    fill: '#ffffff',
    fillOpacity: 0.85,
    fontSize: 12,
    connectorStroke: '#ffffff',
    connectorStrokeOpacity: 0.3,
  },
  innerLabel: {
    fill: '#ffffff',
    fillOpacity: 0.85,
    fontSize: 12,
  },
  text: {
    text: {
      fill: '#ffffff',
      fillOpacity: 0.85,
      fontSize: 12,
      connectorStroke: '#ffffff',
      connectorStrokeOpacity: 0.3,
    },
  },
}

export abstract class BaseG2Chart extends BaseChart {
  chart: Chart
  private resizeObserver?: ResizeObserver
  private resizeTimeout?: number
  private containerId: string
  private destroyed = false
  private pendingTimers: number[] = []

  constructor(id: string, name: string) {
    super(id, name)
    this.containerId = id
    this.chart = new Chart({
      container: id,
      autoFit: true,
      padding: 'auto',
      marginRight: 32,
    })

    this.chart.theme(darkTheme)
  }

  // 设置 ResizeObserver 监听容器大小变化
  private setupResizeObserver() {
    if (this.resizeObserver) {
      this.resizeObserver.disconnect()
    }

    const container = document.getElementById(this.containerId)

    this.resizeObserver = new ResizeObserver((entries) => {
      if (this.destroyed) return
      if (this.resizeTimeout) {
        window.clearTimeout(this.resizeTimeout)
      }
      this.resizeTimeout = window.setTimeout(() => {
        if (this.destroyed || !this.chart) return
        const entry = entries[0]
        const newWidth = entry?.contentRect?.width ?? 0
        if (newWidth > 0 && this.initialWidth > 0 && Math.abs(newWidth - this.initialWidth) > 2) {
          // 宽度变化超过 2px，需要完整重建以修复 legend 位置
          this.initialWidth = newWidth
          this.chart.destroy()
          this.chart = new Chart({
            container: this.containerId,
            autoFit: true,
            padding: 'auto',
            marginRight: 32,
          })
          this.chart.theme(darkTheme)
          this.reinit()
          this.chart.render()
        } else {
          this.chart.forceFit()
        }
      }, 150)
    })

    if (container) {
      this.resizeObserver.observe(container)
    }
  }

  private renderRetryCount = 0
  private static readonly MAX_RENDER_RETRIES = 10
  // 记录首次渲染时的容器宽度，用于检测布局是否已稳定
  private initialWidth = 0

  render() {
    if (this.destroyed) return

    // 渲染前检查容器是否有有效尺寸
    const container = document.getElementById(this.containerId)
    if (container && container.clientWidth === 0 && this.renderRetryCount < BaseG2Chart.MAX_RENDER_RETRIES) {
      this.renderRetryCount++
      const tid = window.setTimeout(() => this.render(), 50)
      this.pendingTimers.push(tid)
      return
    }
    this.renderRetryCount = 0

    this.initialWidth = container?.clientWidth ?? 0
    this.chart?.render()

    // 设置 ResizeObserver — 容器尺寸变化时自动 forceFit
    this.setupResizeObserver()

    // 核心修复：延迟检查容器宽度是否发生了变化
    const checkAndRerender = (delay: number) => {
      const tid = window.setTimeout(() => {
        if (this.destroyed) return
        const currentContainer = document.getElementById(this.containerId)
        if (!currentContainer) return
        const currentWidth = currentContainer.clientWidth
        if (currentWidth > 0 && currentWidth !== this.initialWidth) {
          // 容器宽度变了，forceFit 无法修复 legend 位置，需要完整重建
          this.initialWidth = currentWidth
          this.chart?.destroy()
          this.chart = new Chart({
            container: this.containerId,
            autoFit: true,
            padding: 'auto',
            marginRight: 32,
          })
          this.chart.theme(darkTheme)
          // 子类的 init 已经调用过 this.chart.options(...)，
          // 但 chart 实例被替换了，需要重新 init
          this.reinit()
          this.chart.render()
        }
      }, delay)
      this.pendingTimers.push(tid)
    }

    // 两个时间点检查：覆盖大部分布局变化场景
    checkAndRerender(300)
    checkAndRerender(600)
  }

  /**
   * 子类需要实现：用已有的 axis/data 重新调用 init 配置 chart.options
   * 这样在 render() 检测到容器宽度变化后可以完整重建图表
   */
  protected reinit() {
    // 默认实现：用保存的 axis 和 data 重新 init
    this.init(this.axis, this.data)
  }

  destroy() {
    this.destroyed = true

    // 清除所有待执行的异步操作，防止 destroy 后 forceFit/re-render 竞争
    this.pendingTimers.forEach((tid) => window.clearTimeout(tid))
    this.pendingTimers = []
    if (this.resizeTimeout) {
      window.clearTimeout(this.resizeTimeout)
    }
    if (this.resizeObserver) {
      this.resizeObserver.disconnect()
    }
    this.chart?.destroy()
  }
}
