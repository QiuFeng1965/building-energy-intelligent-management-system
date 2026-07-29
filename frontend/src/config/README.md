# 配置 / 常量目录

本目录集中存放项目的静态配置、常量字典与数据模型定义，供业务组件统一引用，避免在 .vue 文件中硬编码散落。

## 当前内容

- **BuildingLibrary.js**
  智慧校园建筑几何体库。集中维护各建筑模型的几何参数、材质、位置与业务属性，以及路网、树木、路灯等场景元素的生成器。供 `src/components/BuildingManager.vue`、`SpatialCanvas.vue` 等 3D 场景组件统一调用。

  > 该文件原位于 `src/components/BuildingLibrary.js`，已迁移至本目录，由配置层统一管理。引用方式：`import { defineBuildings } from '@/config/BuildingLibrary'`。

## 设计原则

- 与 UI 渲染无关的静态数据（建筑模型定义、字典映射、固定常量等）应放入本目录。
- 业务组件通过 `import { ... } from '@/config/xxx'` 引用，便于统一维护与查找。
- 配置文件只导出数据与纯函数，不引入 Vue 运行时依赖，保证可被任意模块安全引用。
