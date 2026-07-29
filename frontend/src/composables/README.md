# 组合式函数目录

本目录存放 Vue3 组合式函数（Composables），用于跨组件复用有状态的逻辑。

## 函数清单

- **useDigitalTwin.js**
  模块级单例 composable，集中存储数字孪生场景的全局状态，包括当前选中的建筑 ID、鼠标 hover 建筑ID、LOD（细节层次）等级，以及热力图显示开关等关键状态，供多个组件共享读写。
