import { BaseChart, type ChartAxis, type ChartData } from '@/views/chat/component/BaseChart.ts'

export class Kpi extends BaseChart {
  container: HTMLElement | null = null
  private resizeObserver?: ResizeObserver

  constructor(id: string) {
    super(id, 'kpi')
    this.container = document.getElementById(id)
  }

  init(axis: Array<ChartAxis>, data: Array<ChartData>) {
    super.init(axis, data)
  }

  private formatValue(value: number | string): string {
    if (typeof value === 'number') {
      // 格式化数字，添加千分位分隔符
      if (Math.abs(value) >= 1000000) {
        return (value / 1000000).toFixed(2) + 'M'
      } else if (Math.abs(value) >= 1000) {
        return value.toLocaleString('zh-CN', {
          minimumFractionDigits: 0,
          maximumFractionDigits: 2,
        })
      }
      return value.toLocaleString('zh-CN', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
      })
    }
    return String(value)
  }

  render() {
    if (!this.container) return

    // 从数据中提取 KPI 信息
    // 数据格式可能是: { title: string, value: number } 或者从 axis 中获取
    let title = ''
    let value: number | string = 0

    if (this.data && this.data.length > 0) {
      const firstData = this.data[0]
      // 尝试从数据中获取 title 和 value
      if (firstData.title !== undefined) {
        title = firstData.title
      }
      if (firstData.value !== undefined) {
        value = firstData.value
      }
      // 如果没有 title/value 字段，尝试使用 axis 中定义的字段
      if (!title && this.axis.length > 0) {
        const titleAxis = this.axis.find(
          (a) => a.type === 'x' || a.name.includes('名') || a.name.includes('title')
        )
        if (titleAxis) {
          title = firstData[titleAxis.value] || titleAxis.name
        }
      }
      if (value === 0 && this.axis.length > 0) {
        const valueAxis = this.axis.find(
          (a) => a.type === 'y' || a.name.includes('值') || a.name.includes('value')
        )
        if (valueAxis) {
          value = firstData[valueAxis.value] || 0
        }
      }
    }

    // 如果还是没有数据，尝试从 axis 获取标题
    if (!title && this.axis.length > 0) {
      title = this.axis[0].name || 'KPI'
    }

    const formattedValue = this.formatValue(value)

    // 使用 DOM API 构建 KPI 卡片，防止 XSS 注入
    // 原代码使用 innerHTML 直接拼接 title/formattedValue，
    // 如果数据中包含恶意 HTML（如 <img onerror=...>），会被执行
    this.container.innerHTML = ''
    const card = document.createElement('div')
    card.className = 'kpi-card'

    const icon = document.createElement('div')
    icon.className = 'kpi-icon'
    icon.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <path d="M3 3v18h18"/><path d="M18 9l-5 5-4-4-3 3"/><circle cx="18" cy="9" r="2"/>
    </svg>`

    const content = document.createElement('div')
    content.className = 'kpi-content'
    const titleEl = document.createElement('div')
    titleEl.className = 'kpi-title'
    titleEl.textContent = String(title)
    const valueEl = document.createElement('div')
    valueEl.className = 'kpi-value'
    valueEl.textContent = String(formattedValue)
    content.appendChild(titleEl)
    content.appendChild(valueEl)

    const decoration = document.createElement('div')
    decoration.className = 'kpi-decoration'
    decoration.innerHTML = '<div class="decoration-line"></div><div class="decoration-glow"></div>'

    card.appendChild(icon)
    card.appendChild(content)
    card.appendChild(decoration)
    this.container.appendChild(card)

    // 添加样式
    this.addStyles()
  }

  private addStyles() {
    const styleId = 'kpi-chart-styles'
    if (document.getElementById(styleId)) return

    const style = document.createElement('style')
    style.id = styleId
    style.textContent = `
      .kpi-card {
        display: flex;
        align-items: center;
        gap: 20px;
        padding: 28px 32px;
        height: 100%;
        box-sizing: border-box;
        background: linear-gradient(145deg, rgba(139, 92, 246, 0.12) 0%, rgba(168, 85, 247, 0.06) 100%);
        border-radius: 16px;
        position: relative;
        overflow: hidden;
      }

      .kpi-icon {
        width: 56px;
        height: 56px;
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(145deg, rgba(139, 92, 246, 0.25) 0%, rgba(168, 85, 247, 0.15) 100%);
        border-radius: 14px;
        border: 1.5px solid rgba(139, 92, 246, 0.3);
        box-shadow: 0 4px 16px rgba(139, 92, 246, 0.2);
      }

      .kpi-icon svg {
        width: 28px;
        height: 28px;
        color: #a78bfa;
      }

      .kpi-content {
        flex: 1;
        min-width: 0;
      }

      .kpi-title {
        font-size: 14px;
        font-weight: 500;
        color: rgba(196, 181, 253, 0.8);
        margin-bottom: 8px;
        letter-spacing: 0.3px;
      }

      .kpi-value {
        font-size: 36px;
        font-weight: 700;
        color: rgba(255, 255, 255, 0.95);
        letter-spacing: -0.5px;
        line-height: 1.2;
        background: linear-gradient(135deg, #ffffff 0%, #c4b5fd 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
      }

      .kpi-decoration {
        position: absolute;
        top: 0;
        right: 0;
        bottom: 0;
        width: 120px;
        pointer-events: none;
      }

      .decoration-line {
        position: absolute;
        top: 20%;
        right: 40px;
        width: 2px;
        height: 60%;
        background: linear-gradient(180deg, transparent 0%, rgba(139, 92, 246, 0.3) 50%, transparent 100%);
        border-radius: 1px;
      }

      .decoration-glow {
        position: absolute;
        top: 50%;
        right: -30px;
        transform: translateY(-50%);
        width: 100px;
        height: 100px;
        background: radial-gradient(circle, rgba(139, 92, 246, 0.15) 0%, transparent 70%);
        border-radius: 50%;
      }

      @media (max-width: 768px) {
        .kpi-card {
          padding: 20px 24px;
          gap: 16px;
        }

        .kpi-icon {
          width: 48px;
          height: 48px;
          border-radius: 12px;
        }

        .kpi-icon svg {
          width: 24px;
          height: 24px;
        }

        .kpi-title {
          font-size: 13px;
          margin-bottom: 6px;
        }

        .kpi-value {
          font-size: 28px;
        }
      }

      @media (max-width: 480px) {
        .kpi-card {
          padding: 16px 20px;
          gap: 14px;
        }

        .kpi-icon {
          width: 42px;
          height: 42px;
          border-radius: 10px;
        }

        .kpi-icon svg {
          width: 20px;
          height: 20px;
        }

        .kpi-title {
          font-size: 12px;
        }

        .kpi-value {
          font-size: 24px;
        }

        .kpi-decoration {
          display: none;
        }
      }
    `
    document.head.appendChild(style)
  }

  destroy() {
    if (this.resizeObserver) {
      this.resizeObserver.disconnect()
    }
    if (this.container) {
      this.container.innerHTML = ''
    }
  }
}
