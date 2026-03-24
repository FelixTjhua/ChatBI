// SVG 文件导入类型声明
// vite-svg-loader 默认导入为组件
declare module '*.svg' {
  import type { FunctionalComponent, SVGAttributes } from 'vue'
  const component: FunctionalComponent<SVGAttributes>
  export default component
}

declare module '*.svg?component' {
  import type { FunctionalComponent, SVGAttributes } from 'vue'
  const component: FunctionalComponent<SVGAttributes>
  export default component
}

declare module '*.svg?url' {
  const content: string
  export default content
}

declare module '*.svg?raw' {
  const content: string
  export default content
}
