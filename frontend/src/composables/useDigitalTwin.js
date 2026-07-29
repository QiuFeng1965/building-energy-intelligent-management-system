// frontend/src/composables/useDigitalTwin.js
import { ref, computed } from 'vue'

const selectedBuildingId = ref(null)
const hoveredBuildingId = ref(null)
const globalLODLevel = ref(0) // 0: 全高清, 1: 中等, 2: 极低(方块)
// 🌟 新增：热力图开关状态
const isHeatmapActive = ref(false)
// 🌟 核心优化：定义不同 LOD 下的显示策略
// 确保即使在极低 LOD 下，核心楼宇依然显示，而不是消失。
// TODO: LOD 基于镜头距离的动态切换逻辑尚未接入：
//   - setGlobalLOD 在整个项目中从未被调用
//   - globalLODLevel 当前存储的是 LOD 等级 (0/1/2)，并非镜头距离
//   - 待补：在 SpatialCanvas.vue 等场景中监听相机位置变化，按距离阈值
//     (近 <80 / 中 80~200 / 远 >=200) 调用 setGlobalLOD 或直接更新 globalLODLevel
//   一旦上述接入完成，可将下方 computed 替换为基于镜头距离的分支：
//     const dist = globalLODLevel.value
//     return {
//       showDetail: dist < 80,
//       showWireframe: dist >= 80 && dist < 200,
//       showOutline: dist >= 200,
//     }
const buildingVisibilityMap = computed(() => {
  // 屏蔽 LOD 隐藏机制，不管镜头拉多远，老老实实显示大楼实体和线框细节
  return { showDetail: true, showWireframe: true, showOutline: false };
})

export function useDigitalTwin() {
  const setSelectedBuilding = (id) => {
    selectedBuildingId.value = id
  }
  
  const setHoveredBuilding = (id) => {
    hoveredBuildingId.value = id
  }

  const setGlobalLOD = (level) => {
    globalLODLevel.value = level
  }

  return {
    selectedBuildingId,
    hoveredBuildingId,
    globalLODLevel,
    buildingVisibilityMap,
    isHeatmapActive, // 🌟 记得在这里导出它
    setSelectedBuilding,
    setHoveredBuilding,
    setGlobalLOD,
  }
}