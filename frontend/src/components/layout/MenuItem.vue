<script lang="ts">
import { h, defineComponent } from 'vue'
import { ElMenuItem, ElSubMenu, ElIcon } from 'element-plus-secondary'
import { useRouter, useRoute } from 'vue-router'
import chat from '@/assets/svg/menu/icon_chat_filled.svg'
import noChat from '@/assets/svg/menu/icon_chat_outlined.svg'
import dashboard from '@/assets/svg/menu/icon_dashboard_filled.svg'
import { useEmitt } from '@/utils/useEmitt'
import noDashboard from '@/assets/svg/menu/icon_dashboard_outlined.svg'
import ds from '@/assets/svg/menu/icon_database_filled.svg'
import noDs from '@/assets/svg/menu/icon_database_outlined.svg'
import model from '@/assets/svg/menu/icon_dataset_filled.svg'
import noModel from '@/assets/svg/menu/icon_dataset_outlined.svg'
import user from '@/assets/svg/menu/icon_member_filled.svg'
import noUser from '@/assets/svg/menu/icon_member_outlined.svg'
import workspace from '@/assets/svg/menu/icon_moments-categories_filled.svg'
import noWorkspace from '@/assets/svg/menu/icon_moments-categories_outlined.svg'
import set from '@/assets/svg/menu/icon_setting_filled.svg'
import noSet from '@/assets/svg/menu/icon-setting.svg'
import rag from '@/assets/svg/menu/icon_rag_filled.svg'
import noRag from '@/assets/svg/menu/icon_rag_outlined.svg'
import prompt from '@/assets/svg/menu/icon_prompt_filled.svg'
import noPrompt from '@/assets/svg/menu/icon_prompt_outlined.svg'
import book from '@/assets/svg/menu/icon_book_filled.svg'
import noBook from '@/assets/svg/menu/icon_book_outlined.svg'
import code from '@/assets/svg/menu/icon_code_filled.svg'
import noCode from '@/assets/svg/menu/icon_code_outlined.svg'

const iconMap = {
  chat,
  noChat,
  ds,
  noDs,
  dashboard,
  noDashboard,
  workspace,
  noWorkspace,
  set,
  noSet,
  user,
  noUser,
  model,
  noModel,
  rag,
  noRag,
  prompt,
  noPrompt,
  book,
  noBook,
  code,
  noCode,
} as { [key: string]: any }

const MenuItem = defineComponent({
  name: 'MenuItem',
  props: {
    menu: {
      type: Object,
      required: true,
    },
  },
  setup(props) {
    const router = useRouter()
    const route = useRoute()
    const titleWithIcon = (props: any) => {
      const { title, icon } = props
      return [
        h(ElIcon, { size: '18' }, { default: () => h(iconMap[icon]) }),
        h('span', null, { default: () => title }),
      ]
    }

    const handleMenuClick = (e: any) => {
      if (e.index === '/ds/index') {
        useEmitt().emitter.emit('ds-index-click')
      }
      if (e.index) {
        router.push(e.redirect || e.index)
      }
    }

    return () => {
      const { children, hidden, path } = props.menu
      if (hidden) {
        return null
      }

      if (children?.length) {
        const { title, iconDeActive, iconActive } = props.menu?.meta || {}
        const icon = route.path.startsWith(path) ? iconActive : iconDeActive
        return h(
          ElSubMenu,
          { index: path, onClick: () => handleMenuClick(props.menu) },
          {
            title: () => titleWithIcon({ title, icon }),
            default: () => [
              h(MenuItem, { menu: { meta: { title } }, class: 'subTitleMenu' }),
              children.map((ele: any) => h(MenuItem, { menu: ele })),
            ],
          }
        )
      }

      const { title, iconDeActive, iconActive } = props.menu?.meta || {}
      const icon = route.path === path ? iconActive : iconDeActive
      
      return h(
        ElMenuItem,
        { index: path, onClick: (e: any) => handleMenuClick(e) },
        {
          default: () => {
            const children = []
            if (icon && iconMap[icon]) {
              children.push(
                h(ElIcon, { size: 18 }, { default: () => h(iconMap[icon]) })
              )
            }
            children.push(h('span', null, { default: () => title }))
            return children
          },
        }
      )
    }
  },
})

export default MenuItem
</script>
