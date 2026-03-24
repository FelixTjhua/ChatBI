<script lang="ts" setup>
import { onMounted, onBeforeUnmount, ref, nextTick } from 'vue'
import { ElMessage } from 'element-plus-secondary'
import { datasourceApi } from '@/api/datasource'
import { useI18n } from 'vue-i18n'
import { Graph, Cell, Shape } from '@antv/x6'
import type { AnyColumn } from 'element-plus-secondary/es/components/table-v2/src/common.mjs'

const LINE_HEIGHT = 36
const NODE_WIDTH = 180

const props = withDefaults(
  defineProps<{
    id: number
    dragging: boolean
  }>(),
  {
    id: 0,
    dragging: false,
  }
)

const emits = defineEmits(['getTableName'])

const { t } = useI18n()
const loading = ref(false)

const nodeIds = ref<any[]>([])

const cells = ref<Cell[]>([])
const edgeOPtion = {
  tools: [
    {
      name: 'button-remove', // 工具名称
      args: { x: 20, y: 20 }, // 工具对应的参数
    },
  ],
  attrs: {
    line: {
      stroke: 'rgba(139, 92, 246, 0.4)',
      strokeWidth: 2,
    },
  },
}
let graph: any

const initGraph = () => {
  Graph.registerPortLayout(
    'erPortPosition',
    (portsPositionArgs) => {
      return portsPositionArgs.map((_, index) => {
        return {
          position: {
            x: 0,
            y: (index + 1) * LINE_HEIGHT + 15,
          },
          angle: 0,
        }
      })
    },
    true
  )

  Graph.registerNode(
    'er-rect',
    {
      inherit: 'rect',
      markup: [
        {
          tagName: 'path',
          selector: 'top',
        },
        {
          tagName: 'rect',
          selector: 'body',
        },
        {
          tagName: 'text',
          selector: 'label',
        },
        {
          tagName: 'path',
          selector: 'div',
        },
      ],
      attrs: {
        top: {
          fill: '#7c3aed',
          refX: 0,
          refY: 0,
          d: 'M0 5C0 2.23858 2.23858 0 5 0H175C177.761 0 180 2.23858 180 5H0Z',
        },
        rect: {
          strokeWidth: 0.5,
          stroke: 'rgba(139, 92, 246, 0.3)',
          fill: '#1a1225',
          refY: 5,
        },
        div: {
          fillRule: 'evenodd',
          clipRule: 'evenodd',
          fill: '#a78bfa',
          refX: 12,
          refY: 21,
          fontSize: 14,
          d: 'M1.4773 1.47724C1.67618 1.27836 1.94592 1.16663 2.22719 1.16663H11.7729C12.0541 1.16663 12.3239 1.27836 12.5227 1.47724C12.7216 1.67612 12.8334 1.94586 12.8334 2.22713V11.7728C12.8334 12.0541 12.7216 12.3238 12.5227 12.5227C12.3239 12.7216 12.0541 12.8333 11.7729 12.8333H2.22719C1.64152 12.8333 1.16669 12.3585 1.16669 11.7728V2.22713C1.16669 1.94586 1.27842 1.67612 1.4773 1.47724ZM2.33335 5.83329V8.16662H4.66669V5.83329H2.33335ZM2.33335 9.33329V11.6666H4.66669V9.33329H2.33335ZM5.83335 11.6666H8.16669V9.33329H5.83335V11.6666ZM9.33335 11.6666H11.6667V9.33329H9.33335V11.6666ZM11.6667 8.16662V5.83329H9.33335V8.16662H11.6667ZM8.16669 5.83329H5.83335V8.16662H8.16669V5.83329ZM11.6667 2.33329H2.33335V4.66663H11.6667V2.33329Z',
        },
        label: {
          fill: 'rgba(255, 255, 255, 0.95)',
          fontSize: 14,
        },
      },
      ports: {
        groups: {
          list: {
            markup: [
              {
                tagName: 'rect',
                selector: 'portBody',
              },
              {
                tagName: 'text',
                selector: 'portNameLabel',
              },
            ],
            attrs: {
              portBody: {
                width: NODE_WIDTH,
                height: LINE_HEIGHT,
                stroke: 'rgba(139, 92, 246, 0.3)',
                strokeWidth: 0.5,
                fill: 'rgba(26, 18, 37, 0.95)',
                magnet: true,
              },
              portNameLabel: {
                ref: 'portBody',
                refX: 12,
                refY: 9.5,
                fontSize: 14,
                fill: 'rgba(196, 181, 253, 0.8)',
                textAnchor: 'left',
                textWrap: {
                  width: 150,
                  height: 24,
                  ellipsis: true,
                },
              },
            },
            position: 'erPortPosition',
          },
        },
      },
    },
    true
  )
  graph = new Graph({
    mousewheel: {
      enabled: true,
      modifiers: ['ctrl', 'meta'],
    },
    container: document.getElementById('container')!,
    autoResize: true,
    connecting: {
      allowBlank: false,
      router: {
        name: 'er',
        args: {
          offset: 25,
          direction: 'H',
        },
      },
      validateEdge({ edge }: any) {
        const obj = edge.store.data
        if (!obj.target.port || obj.target.cell === obj.source.cell) return false
        return true
      },
      createEdge() {
        return new Shape.Edge(edgeOPtion)
      },
    },
  })

  graph.on('edge:mouseenter', ({ e }: any) => {
    Array.from(document.querySelectorAll('.x6-edge-tool')).forEach((ele: any) => {
      if (ele.dataset.cellId === e.target.parentNode.dataset.cellId) {
        ele.style.display = 'block'
      }
    })
  })

  graph.on('edge:mouseleave', ({ e }: any) => {
    Array.from(document.querySelectorAll('.x6-edge-tool')).forEach((ele: any) => {
      if (ele.dataset.cellId === e.target.parentNode.dataset.cellId) {
        ele.style.display = 'none'
      }
    })
  })

  graph.on('node:mouseenter', ({ node }: any) => {
    node.addTools({
      name: 'button',
      args: {
        markup: [
          {
            tagName: 'circle',
            selector: 'button',
            attrs: {
              r: 7,
              cursor: 'pointer',
            },
          },
          {
            tagName: 'path',
            selector: 'icon',
            attrs: {
              d: 'M -3 -3 3 3 M -3 3 3 -3',
              stroke: 'white',
              'stroke-width': 2,
              cursor: 'pointer',
            },
          },
        ],
        x: 0,
        y: 0,
        offset: { x: 165, y: 28 },
        onClick({ view }: any) {
          graph.removeNode(view.cell.id)
          nodeIds.value = nodeIds.value.filter((ele) => ele !== view.cell.id)
          if (!nodeIds.value.length) {
            graph.dispose()
            graph = null
          }
          emits('getTableName', [...nodeIds.value])
        },
      },
    })
  })

  // 鼠标移开时删除按钮
  graph.on('node:mouseleave', ({ node }: any) => {
    node.removeTools() // 删除所有的工具
  })
}

const getTableData = () => {
  loading.value = true
  datasourceApi
    .relationGet(props.id)
    .then((data: any) => {
      if (!data.length) return
      nodeIds.value = data.filter((ele: any) => ele.shape === 'er-rect').map((ele: any) => ele.id)
      nextTick(() => {
        if (!graph) {
          initGraph()
        }
        data.forEach((item: any) => {
          if (item.shape === 'edge') {
            cells.value.push(graph.createEdge({ ...item, ...edgeOPtion }))
          } else {
            cells.value.push(
              graph.createNode({
                ...item,
                height: LINE_HEIGHT + 15,
                width: NODE_WIDTH,
              })
            )
          }
        })
        graph.resetCells(cells.value)
        graph.zoomToFit({ padding: 10, maxScale: 1 })
        emits('getTableName', [...nodeIds.value])
      })
    })
    .catch(() => {
      ElMessage.error(t('common.load_failed'))
    })
    .finally(() => {
      loading.value = false
    })
}
onMounted(() => {
  getTableData()
})
onBeforeUnmount(() => {
  // 正确清理 graph 资源，避免内存泄漏
  if (graph) {
    try {
      graph.dispose()
    } catch (e) {
      // 忽略清理时的错误
    }
    graph = null
  }
})
const dragover = () => {
  // do
}

const addNode = (node: any) => {
  if (!graph) {
    initGraph()
  }
  graph.addNode(
    graph.createNode({
      ...node,
      attrs: {
        label: {
          text: node.label,
          textAnchor: 'left',
          refX: 34,
          refY: 28,
          textWrap: {
            width: 120,
            height: 24,
            ellipsis: true,
          },
        },
      },
      height: LINE_HEIGHT + 15,
      width: NODE_WIDTH,
    })
  )
}

const clickTable = (table: any) => {
  loading.value = true
  datasourceApi
    .fieldList(table.id)
    .then((res: AnyColumn) => {
      const node = {
        id: table.id,
        shape: 'er-rect',
        label: table.table_name,
        width: 150,
        height: 24,
        position: {
          x: table.x,
          y: table.y,
        },
        ports: res.map((ele: any) => {
          return {
            id: ele.id,
            group: 'list',
            attrs: {
              portNameLabel: {
                text: ele.field_name,
              },
              portTypeLabel: {
                text: ele.field_type,
              },
            },
          }
        }),
      }
      nodeIds.value = [...nodeIds.value, table.id]
      nextTick(() => {
        addNode(node)
      })
      emits('getTableName', [...nodeIds.value])
    })
    .catch(() => {
      ElMessage.error(t('common.load_failed'))
    })
    .finally(() => {
      loading.value = false
    })
}

const drop = (e: any) => {
  const obj = JSON.parse(e.dataTransfer.getData('table') || '{}')
  if (!obj.id) return
  clickTable({ ...obj, x: e.layerX, y: e.layerY })
}
const saveLoading = ref(false)
const save = () => {
  saveLoading.value = true
  datasourceApi.relationSave(props.id, graph.toJSON().cells).then(() => {
    ElMessage({
      type: 'success',
      message: t('common.save_success'),
    })
  }).catch(() => {
    ElMessage.error(t('common.save_failed'))
  }).finally(() => {
    saveLoading.value = false
  })
}
</script>

<template>
  <svg style="position: fixed; top: -9999px" xmlns:xlink="http://www.w3.org/1999/xlink">
    <defs>
      <filter
        id="filter-dropShadow-v0-3329848037"
        x="-1"
        y="-1"
        width="3"
        height="3"
        filterUnits="objectBoundingBox"
      >
        <feDropShadow
          stdDeviation="4"
          dx="1"
          dy="2"
          flood-color="rgba(0,0,0,0.5)"
          flood-opacity="0.65"
        ></feDropShadow>
      </filter>
    </defs>
  </svg>
  <div v-if="!nodeIds.length" v-loading="loading" class="relationship-empty">
    {{ t('training.add_it_here') }}
  </div>
  <div v-else id="container" v-loading="loading"></div>
  <div
    v-show="dragging"
    class="drag-mask"
    @dragover.prevent.stop="dragover"
    @drop.prevent.stop="drop"
  ></div>
  <div class="save-btn">
    <el-button v-if="nodeIds.length" type="primary" :loading="saveLoading" @click="save">
      {{ t('common.save') }}
    </el-button>
  </div>
</template>

<style lang="less" scoped>
// ChatBI 表关系图 - 深色主题设计
@primary-400: #a78bfa;
@primary-500: #8b5cf6;
@primary-600: #7c3aed;
@dark-bg: #0f0a1a;
@dark-bg-secondary: #1a1225;
@dark-border: rgba(139, 92, 246, 0.2);
@dark-text: rgba(255, 255, 255, 0.95);
@dark-text-secondary: rgba(196, 181, 253, 0.8);
@dark-text-muted: rgba(196, 181, 253, 0.5);

.save-btn {
  position: absolute;
  right: 16px;
  bottom: 16px;

  :deep(.ed-button--primary) {
    background: linear-gradient(135deg, @primary-600 0%, @primary-500 100%) !important;
    border: none !important;
    border-radius: 10px;
    box-shadow: 0 4px 16px rgba(139, 92, 246, 0.35);

    &:hover {
      box-shadow: 0 6px 24px rgba(139, 92, 246, 0.45);
    }
  }
}

.drag-mask {
  width: 100%;
  height: 100%;
  position: absolute;
  left: 0;
  top: 56px;
  z-index: 10;
  background: rgba(139, 92, 246, 0.05);
  border: 2px dashed @dark-border;
}

.relationship-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  font-size: 16px;
  color: @dark-text-muted;
  background: @dark-bg-secondary;
}

#container {
  font-size: 14px;
  user-select: text;
  overflow: hidden;
  outline: none;
  touch-action: none;
  box-sizing: border-box;
  position: relative;
  min-width: 400px;
  min-height: 600px;
  width: 100%;
  height: 100%;
  background-color: @dark-bg-secondary;
  background-image: radial-gradient(circle, rgba(139, 92, 246, 0.08) 1px, transparent 1px);
  background-size: 20px 20px;

  :deep(.x6-edge-tool) {
    display: none;

    circle {
      fill: @primary-500 !important;
    }
  }

  :deep(.x6-node-tool) {
    circle {
      fill: @primary-500 !important;
    }
  }

  :deep(.x6-node) {
    filter: drop-shadow(0 4px 12px rgba(0, 0, 0, 0.4));
  }
}
</style>
