import { createPinia } from 'pinia';
import { createApp } from 'vue';

import App from '@/App.vue';
import { buildRouter } from '@/router';
import '@/styles/main.css';

const app = createApp(App);

app.use(createPinia());
app.use(buildRouter());
app.mount('#app');