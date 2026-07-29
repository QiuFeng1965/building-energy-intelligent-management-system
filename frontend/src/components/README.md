# 3D 可视化组件目录

本目录存放建筑能源智能管理系统的三维可视化与场景渲染组件，基于原生 Three.js 与 TresJS（Vue3 声明式 Three.js 封装）实现。

## 组件清单与分类

> 注：原 `BuildingLibrary.js`（建筑模型定义库）已迁移至 `src/config/BuildingLibrary.js`，由配置目录统一管理。本目录仅保留与 UI 渲染强相关的 .vue 组件。

### 原生 Three.js 场景

- **Campus3DCanvas.vue**
  原生 Three.js 实现的南京城市白模场景，负责加载 GLB 模型并挂载告警标签，用于城市级宏观态势展示。

### TresJS（声明式 Three.js）组件

- **SpatialCanvas.vue**
  TresJS 顶层 Canvas 容器，统一配置相机、雾效、光照与后处理 Bloom 效果，并集成建筑能效热力图渲染逻辑。
- **BuildingManager.vue**
  基于 TresJS 声明式渲染建筑群，包含墙体、玻璃幕墙、草地、跑道、地面等子部件的组装与组织。建筑模型数据来源 `src/config/BuildingLibrary.js`。
- **MapBase.vue**
  声明式渲染地图底板，包括地面、道路、水体、树木以及参考网格，作为建筑群的承载基底。

## 目录组织说明

- 当前 .vue 组件仍直接放在 `src/components/` 下，未按 `three/` 子目录进一步细分，避免现有 import 路径被打断。
- 如未来原生 Three.js 组件增多、需要单独管理，可创建 `src/components/three/` 子目录，将 `Campus3DCanvas.vue` 等原生 Three.js 组件迁入；TresJS 组件保持原位即可。迁移时需同步更新 `src/views/SpatialTwin.vue` 等引用方的 import 路径。
