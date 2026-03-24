import { createRouter, createWebHashHistory } from 'vue-router'
// Layout is available for future use
import LayoutDsl from '@/components/layout/LayoutDsl.vue'
import SinglePage from '@/components/layout/SinglePage.vue'
import login from '@/views/login/index.vue'
import chat from '@/views/chat/index.vue'
import Datasource from '@/views/ds/Datasource.vue'
import Dashboard from '@/views/dashboard/index.vue'
import DashboardCanvas from '@/views/dashboard/canvas/index.vue'
import Model from '@/views/system/model/Model.vue'
import Prompt from '@/views/system/prompt/index.vue'
import SqlExample from '@/views/system/sql-example/index.vue'
import Terminology from '@/views/system/terminology/index.vue'
import User from '@/views/system/user/index.vue'
import Page401 from '@/views/error/index.vue'
import { i18n } from '@/i18n'
import { watchRouter } from './watch'

const t = i18n.global.t
export const routes = [
  {
    path: '/',
    redirect: '/login',
  },
  {
    path: '/login',
    name: 'login',
    component: login,
  },
  {
    path: '/chat',
    component: LayoutDsl,
    redirect: '/chat/index',
    children: [
      {
        path: 'index',
        name: 'chat',
        component: chat,
        props: (route: any) => {
          return { startChatDsId: route.query.start_chat }
        },
        meta: { title: t('menu.Data Q&A'), iconActive: 'chat', iconDeActive: 'noChat' },
      },
    ],
  },
  {
    path: '/dsTable',
    component: SinglePage,
    children: [
      {
        path: ':dsId/:dsName',
        name: 'dsTable',
        component: () => import('@/views/ds/TableList.vue'),
        props: true,
      },
    ],
  },
  {
    path: '/dashboard',
    component: LayoutDsl,
    redirect: '/dashboard/index',
    children: [
      {
        path: 'index',
        name: 'dashboard',
        component: Dashboard,
        meta: {
          title: t('dashboard.dashboard'),
          iconActive: 'dashboard',
          iconDeActive: 'noDashboard',
        },
      },
    ],
  },
  {
    path: '/ds',
    component: LayoutDsl,
    redirect: '/ds/index',
    children: [
      {
        path: 'index',
        name: 'ds',
        component: Datasource,
        meta: { title: t('menu.Data Connections'), iconActive: 'ds', iconDeActive: 'noDs' },
      },
    ],
  },
  {
    path: '/canvas',
    name: 'canvas',
    component: DashboardCanvas,
    meta: { title: 'Canvas', hidden: true },
  },
  {
    path: '/model',
    component: LayoutDsl,
    redirect: '/model/index',
    children: [
      {
        path: 'index',
        name: 'model',
        component: Model,
        meta: {
          title: t('model.ai_model_configuration'),
          iconActive: 'model',
          iconDeActive: 'noModel',
        },
      },
    ],
  },

  {
    path: '/system',
    component: LayoutDsl,
    redirect: '/system/user',
    meta: { hidden: true },
    children: [
      {
        path: 'user',
        name: 'user',
        component: User,
        meta: { title: t('user.user_management'), iconActive: 'user', iconDeActive: 'noUser' },
      },
      {
        path: 'model',
        name: 'sysModel',
        component: Model,
        meta: {
          title: t('model.ai_model_configuration'),
          iconActive: 'model',
          iconDeActive: 'noModel',
        },
        hidden: true,
      },
      // professional 和 training 已从 RAG 模块独立为单独菜单
      {
        path: 'prompt',
        name: 'prompt',
        component: Prompt,
        meta: { 
          title: t('prompt.customize_prompt_words'), 
          iconActive: 'prompt', 
          iconDeActive: 'noPrompt' 
        },
      },
      {
        path: 'sql-example',
        name: 'sqlExample',
        component: SqlExample,
        meta: { 
          title: t('training.data_training'), 
          iconActive: 'code', 
          iconDeActive: 'noCode' 
        },
      },
      {
        path: 'terminology',
        name: 'terminology',
        component: Terminology,
        meta: { 
          title: t('professional.professional_terminology'), 
          iconActive: 'book', 
          iconDeActive: 'noBook' 
        },
      },
    ],
  },
  {
    path: '/401',
    name: '401',
    hidden: true,
    meta: { hidden: true },
    component: Page401,
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    redirect: '/401',
    meta: { hidden: true },
  },
]
const router = createRouter({
  history: createWebHashHistory(),
  routes,
})
watchRouter(router)
export default router
