<template>
  <TresGroup name="BuildingLayer">
    <TresGroup v-for="b in mergedBuildings" :key="b.id" :position="b.position">
      
      <Html v-if="hoveredBuildingId === b.id || selectedBuildingId === b.id" :position="[0, (b.scale?.[1] || 15) / 2 + 8, 0]" center>
        <div class="glass-label-dark" :style="{'--status-color': b.color}">
          <div class="font-bold text-lg mb-1 text-white">{{ b.name }}</div>
          <div class="text-sm flex justify-between gap-4">
            <span class="text-slate-400">{{ b.type || '建筑' }}</span>
            <span class="font-bold tracking-widest" :style="{ color: b.color, textShadow: `0 0 8px ${b.color}80` }">{{ b.status }}</span>
          </div>
        </div>
      </Html>

      <TresGroup v-if="buildingVisibilityMap.showDetail" name="DetailedGeometry">
        <TresGroup v-if="b.group && b.group.length > 0">
          <TresGroup v-for="(sub, sidx) in b.group" :key="sidx" :position="sub.position">
             
             <TresMesh cast-shadow receive-shadow @pointer-enter="(e) => onPointerEnter(e, b)" @pointer-leave="(e) => onPointerLeave(e, b)" @click="(e) => onClick(e, b)">
                
                <TresBoxGeometry v-if="sub.type === 'TresBoxGeometry' || !sub.type" :args="sub.args || sub.scale" />
                <TresCylinderGeometry v-else-if="sub.type === 'TresCylinderGeometry'" :args="sub.args" />
                <TresSphereGeometry v-else-if="sub.type === 'TresSphereGeometry'" :args="sub.args" />
                <TresPlaneGeometry v-else-if="sub.type === 'TresPlaneGeometry'" :args="sub.args" />
                
                <TresMeshStandardMaterial 
                  v-if="sub.isWindow || sub.isGlass"
                  :color="b.style.glass" 
                  :roughness="0.1" 
                  :metalness="0.9"
                  :emissive="b.style.glass" 
                  :emissiveIntensity="hoveredBuildingId === b.id ? 2.5 : 1.2" 
                />

                <TresMeshStandardMaterial v-else-if="sub.isGrass" color="#064e3b" :roughness="0.9" :metalness="0.1" /> <TresMeshStandardMaterial v-else-if="sub.isTrack" color="#0f172a" :roughness="0.8" :metalness="0.2" /> <TresMeshStandardMaterial v-else-if="sub.isGround" color="#1e293b" :roughness="0.8" :metalness="0.1" /> <TresMeshStandardMaterial 
                  v-else
                  :color="b.style.wall" 
                  :roughness="0.45"   
                  :metalness="0.35"   
                  :emissive="b.style.emissive" 
                  :emissiveIntensity="hoveredBuildingId === b.id ? 0.3 : 0.0" 
                />
             </TresMesh>
             
          </TresGroup>
        </TresGroup>
        
        <TresGroup v-else>
           <TresMesh cast-shadow receive-shadow @pointer-enter="(e) => onPointerEnter(e, b)" @pointer-leave="(e) => onPointerLeave(e, b)" @click="(e) => onClick(e, b)">
              <TresBoxGeometry :args="b.geometry?.args || b.scale" />
              <TresMeshStandardMaterial :color="b.style.wall" :roughness="0.45" :metalness="0.35" />
           </TresMesh>
        </TresGroup>

      </TresGroup>
    </TresGroup>
  </TresGroup>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Html } from '@tresjs/cientos' // ✅ 核心修复：把 3D HTML 浮空标签组件引入进来！
import { defineBuildings } from '../config/BuildingLibrary'

const props = defineProps({
  buildingData: { type: Array, default: () => [] },
  buildingVisibilityMap: { type: Object, default: () => ({ showDetail: true }) },
  hoveredBuildingId: { type: String, default: null },
  selectedBuildingId: { type: String, default: null }
})

const emit = defineEmits(['building-click', 'building-pointer-enter', 'building-pointer-leave'])

const mergedBuildings = computed(() => {
  const localModels = defineBuildings()
  return localModels.map(localModel => {
    const backendData = props.buildingData.find(apiItem => apiItem.id === localModel.id) || {}
    const status = backendData.status || localModel.status
    
    // 🌟 全局墙体采用深空钛灰，绝不大面积涂色；发光全部交给玻璃
    let style = { wall: '#475569', glass: '#0ea5e9', emissive: '#000000' } // 基础玻璃为科技亮蓝
    let color = '#0ea5e9'
    
    if (status === '故障' || backendData.color === '#ef4444') {
      // 故障：墙依旧保持金属灰，但窗户透出刺眼的红色红光
      style = { wall: '#334155', glass: '#ef4444', emissive: '#450a0a' }
      color = '#ef4444'
    } else if (status === '警告' || backendData.color === '#f59e0b') {
      // 警告：墙依旧保持金属灰，窗户透出警戒橙光
      style = { wall: '#334155', glass: '#f59e0b', emissive: '#451a03' }
      color = '#f59e0b'
    } else {
      switch (localModel.type) {
        case '实验': 
          // 实验楼使用更亮的冰蓝色玻璃
          style = { wall: '#334155', glass: '#38bdf8', emissive: '#000000' }; 
          color = '#38bdf8'; break;
        default: 
          style = { wall: '#475569', glass: '#0ea5e9', emissive: '#000000' }; 
          color = '#0ea5e9'; break;
      }
    }
    return { ...localModel, status, color, power: backendData.power || localModel.power, name: backendData.name || localModel.name, style }
  })
})

// ✅ 严谨的防御性写法（检查函数是否存在）
const onClick = (e, b) => { if (e && typeof e.stopPropagation === 'function') e.stopPropagation(); emit('building-click', b) }
const onPointerEnter = (e, b) => { if (e && typeof e.stopPropagation === 'function') e.stopPropagation(); emit('building-pointer-enter', b) }
const onPointerLeave = (e, b) => { if (e && typeof e.stopPropagation === 'function') e.stopPropagation(); emit('building-pointer-leave', b) }
</script>

<style scoped>
/* 🌟 配合暗黑科技风的深色毛玻璃标签 */
.glass-label-dark {
  background: rgba(15, 23, 42, 0.85); /* 极深的藏青蓝底色 */
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(51, 65, 85, 0.8); /* 微微发亮的边框 */
  border-top: 4px solid var(--status-color);
  padding: 12px 20px;
  border-radius: 12px;
  min-width: 160px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5); /* 更深的阴影 */
  user-select: none;
  pointer-events: none;
  transition: all 0.3s ease;
}
</style>