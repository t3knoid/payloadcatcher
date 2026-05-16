import { createRouter, createWebHistory } from 'vue-router';

import HomeView from '@/views/HomeView.vue';
import InboxView from '@/views/InboxView.vue';
import PrivacyView from '@/views/PrivacyView.vue';

export const buildRouter = () => {
  return createRouter({
    history: createWebHistory(),
    routes: [
      {
        path: '/',
        name: 'home',
        component: HomeView,
      },
      {
        path: '/inbox/:clsid',
        name: 'inbox',
        component: InboxView,
        props: true,
      },
      {
        path: '/privacy',
        name: 'privacy',
        component: PrivacyView,
      },
    ],
    scrollBehavior() {
      return { top: 0 };
    },
  });
};