import { BaseChart, type ChartAxis, type ChartData } from '@/views/chat/component/BaseChart.ts'
import { TableSheet, type S2Options, type S2DataConfig, type S2MountContainer } from '@antv/s2'

// 深色主题配置
const darkThemeConfig = {
  // 表头样式
  colCell: {
    cell: {
      backgroundColor: 'rgba(139, 92, 246, 0.18)',
      horizontalBorderColor: 'rgba(139, 92, 246, 0.25)',
      verticalBorderColor: 'rgba(139, 92, 246, 0.25)',
      horizontalBorderWidth: 1,
      verticalBorderWidth: 1,
    },
    text: {
      fill: 'rgba(255, 255, 255, 0.98)',
      fontSize: 13,
      fontWeight: 600,
    },
    bolderText: {
      fill: 'rgba(255, 255, 255, 0.98)',
      fontSize: 13,
      fontWeight: 600,
    },
  },
  // 数据单元格样式
  dataCell: {
    cell: {
      backgroundColor: 'transparent',
      horizontalBorderColor: 'rgba(139, 92, 246, 0.15)',
      verticalBorderColor: 'rgba(139, 92, 246, 0.15)',
      horizontalBorderWidth: 1,
      verticalBorderWidth: 1,
      crossBackgroundColor: 'rgba(139, 92, 246, 0.08)',
    },
    text: {
      fill: 'rgba(255, 255, 255, 0.9)',
      fontSize: 13,
      fontWeight: 500,
    },
  },
  // 行头样式
  rowCell: {
    cell: {
      backgroundColor: 'rgba(139, 92, 246, 0.1)',
      horizontalBorderColor: 'rgba(139, 92, 246, 0.2)',
      verticalBorderColor: 'rgba(139, 92, 246, 0.2)',
    },
    text: {
      fill: 'rgba(255, 255, 255, 0.9)',
      fontSize: 13,
    },
  },
  // 滚动条样式
  scrollBar: {
    thumbColor: 'rgba(139, 92, 246, 0.3)',
    thumbHoverColor: 'rgba(139, 92, 246, 0.5)',
    trackColor: 'transparent',
  },
  // 分割线样式
  splitLine: {
    horizontalBorderColor: 'rgba(139, 92, 246, 0.15)',
    verticalBorderColor: 'rgba(139, 92, 246, 0.15)',
    horizontalBorderWidth: 1,
    verticalBorderWidth: 1,
  },
  // 背景
  background: {
    color: 'transparent',
  },
}

export class Table extends BaseChart {
  table?: TableSheet = undefined
  container: S2MountContainer | null = null
  resizeObserver?: ResizeObserver
  private resizeTimeout?: number

  constructor(id: string) {
    super(id, 'table')
    this.container = document.getElementById(id)
  }

  // 获取容器的实际可用宽度
  private getContainerSize(): { width: number; height: number } {
    if (!this.container) {
      return { width: 600, height: 300 }
    }

    const el = this.container as HTMLElement

    // 使用 offsetWidth/offsetHeight 获取实际渲染尺寸
    let width = el.offsetWidth || el.clientWidth
    let height = el.offsetHeight || el.clientHeight

    // 如果容器尺寸为0，尝试从父元素获取
    if (width < 100 || height < 100) {
      const parent = el.parentElement
      if (parent) {
        width = parent.offsetWidth || parent.clientWidth || 600
        height = parent.offsetHeight || parent.clientHeight || 300
      }
    }

    return {
      width: Math.max(width, 200),
      height: Math.max(height, 200),
    }
  }

  // 重新调整表格大小
  private resizeTable() {
    if (!this.table) return

    const { width, height } = this.getContainerSize()
    if (width > 0 && height > 0) {
      this.table.changeSheetSize(width, height)
      this.table.render(false)
    }
  }

  // 设置 ResizeObserver 监听容器大小变化
  private setupResizeObserver() {
    if (this.resizeObserver) {
      this.resizeObserver.disconnect()
    }

    this.resizeObserver = new ResizeObserver(() => {
      if (this.resizeTimeout) {
        window.clearTimeout(this.resizeTimeout)
      }
      this.resizeTimeout = window.setTimeout(() => {
        this.resizeTable()
      }, 100)
    })

    if (this.container) {
      this.resizeObserver.observe(this.container as Element)
    }
  }

  init(axis: Array<ChartAxis>, data: Array<ChartData>) {
    super.init(axis, data)

    const { width, height } = this.getContainerSize()

    const s2DataConfig: S2DataConfig = {
      fields: {
        columns: this.axis?.map((a) => a.value) ?? [],
      },
      meta:
        this.axis?.map((a) => {
          return {
            field: a.value,
            name: a.name,
          }
        }) ?? [],
      data: this.data,
    }

    const s2Options: S2Options = {
      width: width,
      height: height,
      // Note: adaptive is handled by ResizeObserver instead
      placeholder: {
        cell: '-',
        empty: {
          icon: 'Empty',
          description: 'No Data',
        },
      },
      style: {
        colCell: {
          height: 40,
        },
        dataCell: {
          height: 36,
        },
      },
      // 启用自适应宽度
      interaction: {
        resize: {
          colCellVertical: true,
        },
      },
    }

    if (this.container) {
      this.table = new TableSheet(this.container, s2DataConfig, s2Options)
      this.table.setThemeCfg({ theme: darkThemeConfig })
    }
  }

  render() {
    if (!this.table) return

    this.table.render()

    // 设置 ResizeObserver
    this.setupResizeObserver()

    // 延迟多次重新计算尺寸，确保历史对话加载时也能正确适应
    const delays = [50, 150, 300, 500]
    delays.forEach((delay) => {
      setTimeout(() => {
        this.resizeTable()
      }, delay)
    })
  }

  destroy() {
    if (this.resizeTimeout) {
      window.clearTimeout(this.resizeTimeout)
    }
    if (this.resizeObserver) {
      this.resizeObserver.disconnect()
    }
    this.table?.destroy()
  }
}
