import { createApp } from 'vue'
import { createPinia } from 'pinia'
// 视觉基线：直接复用原型的 theme.css（三人共用一套 class，保证页面一致）
import './styles/theme.css'
import App from './App.vue'
import router from './router'

createApp(App).use(createPinia()).use(router).mount('#app')
