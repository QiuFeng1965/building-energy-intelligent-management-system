<template>
  <TresGroup :position="[0, -0.05, 0]" name="MapBaseLayer">
    
    <TresMesh rotation-x="-1.570796" receive-shadow>
      <TresPlaneGeometry :args="[500, 500]" />
      <TresMeshPhysicalMaterial 
        color="#0a122a" 
        :metalness="0.5"
        :roughness="0.8"
        :transmission="0.6"
        :thickness="5"
        :transparent="true"
        :opacity="0.95"
      />
    </TresMesh>

    <TresGroup name="RoadNetwork">
      <TresMesh v-for="(road, index) in roadData" :key="index" :position="road.position">
        <TresPlaneGeometry :args="road.args" />
        <TresMeshBasicMaterial color="#3b82f6" :transparent="true" :opacity="0.25" />
      </TresMesh>
    </TresGroup>

    <TresMesh :position="[45, 0.1, 45]" rotation-x="-1.570796" name="WaterBody">
      <TresCircleGeometry :args="[10, 32]" />
      <TresMeshPhysicalMaterial 
        color="#1d4ed8" 
        :metalness="0.1"
        :roughness="0.1"
        :transmission="0.95"
        :thickness="1"
        :transparent="true"
        :opacity="0.9"
      />
    </TresMesh>

    <TresGroup name="DigitalTrees">
       <TresMesh v-for="(tree, index) in treeData" :key="index" :position="tree.position">
         <TresConeGeometry :args="[1.2, 3, 4]" />
         <TresMeshBasicMaterial color="#059669" :wireframe="true" />
       </TresMesh>
    </TresGroup>

    <TresGridHelper :args="[300, 150, '#111827', '#030712']" :position="[0, 0, 0]" />

  </TresGroup>
</template>

<script setup>
// 这里定义一些静态的地图地貌数据
const roadData = [
  { position: [-25, 0.1, 0], args: [2, 100] }, // 主轴
  { position: [25, 0.1, 0], args: [2, 100] },
  { position: [0, 0.1, -25], args: [100, 2] },
  { position: [0, 0.1, 25], args: [100, 2] },
]

const treeData = []
for (let i = 0; i < 50; i++) {
  treeData.push({
    position: [
      (Math.random() - 0.5) * 120 + 30, // 避免挡住核心建筑区
      1.5,
      (Math.random() - 0.5) * 120 + 30
    ]
  })
}
</script>