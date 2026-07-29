<template>
  <div class="w-full h-full relative bg-[#020617]">
    
    <TresCanvas shadows :shadow-map-type="1" alpha window-size clear-color="#020617">
      
      <TresPerspectiveCamera :position="[55, 50, 55]" :look-at="[0, 0, 0]" />
      <TresFog :args="['#020617', 100, 400]" />

      <TresHemisphereLight :intensity="0.4" />

      <TresAmbientLight :intensity="isHeatmapActive ? 0.1 : 0.4" color="#94a3b8" />

      <TresDirectionalLight :position="[60, 80, 40]" :intensity="isHeatmapActive ? 0.2 : 1.5" color="#ffffff" cast-shadow />

      <TresGridHelper :args="[300, 150, '#1e293b', '#0f172a']" :position="[0, -0.1, 0]" />

      <BuildingManager
        :buildingData="data"
        :selectedBuildingId="selectedBuildingId"
        :hoveredBuildingId="hoveredBuildingId"
        :buildingVisibilityMap="{ showDetail: true }"
        @building-click="onBuildingClick"
      />

      <TresGroup v-for="building in buildingHeatmapData" :key="'heat-' + building.id" :position="building.position">
        <TresMesh v-if="isHeatmapActive" :rotation="[-Math.PI / 2, 0, 0]" :position="[0, 0.1, 0]">
          <TresPlaneGeometry :args="[building.scale[0] * 3, building.scale[2] * 3]" />
          <TresShaderMaterial
            :transparent="true" :depthWrite="false" :blending="2"
            :vertexShader="vertexShader" :fragmentShader="fragmentShader"
            :uniforms="{ uColor: { value: building.cachedColor }, uIntensity: { value: building.intensity } }"
          />
        </TresMesh>
      </TresGroup>

      <OrbitControls :enable-damping="true" :auto-rotate="true" :auto-rotate-speed="0.5" :max-polar-angle="Math.PI / 2 - 0.05" />

    </TresCanvas>
  </div>
</template>

<script setup>
import * as THREE from 'three'
import { computed } from 'vue'
import { TresCanvas } from '@tresjs/core'
import { OrbitControls } from '@tresjs/cientos'
import { useDigitalTwin } from '../composables/useDigitalTwin.js'
import BuildingManager from './BuildingManager.vue'

const { selectedBuildingId, hoveredBuildingId, setSelectedBuilding, isHeatmapActive } = useDigitalTwin()

const vertexShader = `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`
const fragmentShader = `
  uniform vec3 uColor;
  uniform float uIntensity;
  varying vec2 vUv;
  void main() {
    float dist = distance(vUv, vec2(0.5));
    float alpha = smoothstep(0.5, 0.0, dist);
    alpha = pow(alpha, 1.5);
    gl_FragColor = vec4(uColor, alpha * uIntensity);
  }
`

const props = defineProps({
  data: {
    type: Array,
    default: () => []
  }
})

// 缓存 THREE.Color 实例，避免每次响应式更新都 new 一个新对象
const colorCache = new Map()
function getCachedColor(hex) {
  if (!colorCache.has(hex)) {
    colorCache.set(hex, new THREE.Color(hex))
  }
  return colorCache.get(hex)
}

// 用 computed 缓存 uniforms，避免模板内联每帧重建
const buildingHeatmapData = computed(() =>
  props.data.map(building => ({
    ...building,
    cachedColor: getCachedColor(building.color),
    intensity: building.status === '正常' ? 0.5 : 1.5
  }))
)

const onBuildingClick = (building) => {
  if(building && building.id) {
    setSelectedBuilding(building.id)
  }
}
</script>