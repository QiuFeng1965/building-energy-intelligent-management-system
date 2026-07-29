# 前端模块说明

## 技术栈

Vue3 + Vite + Three.js + TresJS + ECharts + TailwindCSS + ElementPlus + DOMPurify

## 启动命令

```bash
cd frontend
npm run dev      # 开发模式（热更新）
npm run build    # 生产构建
```

## 目录结构

```
src/
├── api/                 # 统一 API 调用层
│   └── index.js         # 12 个 API 函数，基于 utils/request.js 的 safeFetch
├── config/              # 配置/常量目录
│   └── BuildingLibrary.js   # 建筑模型定义库（墙体/玻璃/草地/跑道/地面）
├── components/          # 3D 可视化组件
│   ├── Campus3DCanvas.vue   # 原生 Three.js 南京城市白模场景
│   ├── SpatialCanvas.vue    # TresJS Canvas 容器（相机/雾/光照/Bloom）
│   ├── BuildingManager.vue  # TresJS 声明式建筑群渲染
│   └── MapBase.vue          # TresJS 地图底板（地面/道路/水体/树木）
├── views/               # 页面视图
│   ├── Login.vue            # 登录页（物理引擎驱动机器人交互）
│   ├── Dashboard.vue        # 能源态势总览（KPI + ECharts）
│   ├── EnergyAnalysis.vue   # 能耗分析
│   ├── DeviceMonitor.vue    # 设备监控
│   ├── SpatialTwin.vue      # 空间孪生（混沌工程控制台 + 3D + 容灾日志）
│   ├── AiAgent.vue          # AI 智慧决策（流式对话 + 雷达图 + 图片上传）
│   ├── AdminDashboard.vue   # 管理后台仪表盘
│   └── HelloWorld.vue       # 默认示例
├── composables/         # 组合式函数
│   └── useDigitalTwin.js    # 全局单例（建筑 ID、hover、LOD、热力图开关）
├── utils/               # 工具函数
│   └── request.js           # 统一请求工具（超时 + JWT + AbortController）
├── assets/              # 静态资源
├── App.vue              # 根组件
├── main.js              # 应用入口
└── style.css            # 全局样式
```

## 代理配置

`vite.config.js` 已配置 `/api` 和 `/ws` 代理到 `http://127.0.0.1:8000`，前端请求无需写绝对地址。

## 依赖说明

| 依赖 | 用途 |
|------|------|
| three | 3D 渲染引擎 |
| @tresjs/core | Vue3 声明式 Three.js 封装 |
| echarts | 数据可视化图表 |
| element-plus | UI 组件库 |
| dompurify | XSS 防护（v-html 消毒） |
