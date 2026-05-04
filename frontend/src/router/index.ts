import { createRouter, createWebHistory } from 'vue-router'

import AppLayout from '@/layouts/AppLayout.vue'
import StyleDetailView from '@/views/StyleDetailView.vue'
import StylesView from '@/views/StylesView.vue'
import WriteView from '@/views/WriteView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: AppLayout,
      redirect: '/styles',
      children: [
        { path: 'styles', name: 'styles', component: StylesView },
        { path: 'styles/:id', name: 'style-detail', component: StyleDetailView, props: true },
        { path: 'write', name: 'write', component: WriteView },
      ],
    },
  ],
})

export default router

