// filepath: C:\Users\Administrator\Desktop\Building Energy Intelligent Management System2\frontend\src\main.js
import { createApp } from 'vue'
import App from './App.vue'
import './style.css' // 如果有
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
// Element Plus 官方深色模式 CSS 变量（html.dark 类生效）
import 'element-plus/theme-chalk/dark/css-vars.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

// 🌟 1. 致命修复：引入 TresJS 插件
import Tres from '@tresjs/core'

// 路由
import router from './router'

const app = createApp(App)

// 注册 ElementPlus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(ElementPlus)

// 🌟 2. 致命修复：全局注册 TresJS 插件
app.use(Tres)

// 注册路由
app.use(router)

app.mount('#app')