<template>
  <div ref="containerRef" class="w-full h-full relative outline-none">
    <div v-if="isLoading" class="absolute inset-0 z-50 flex flex-col items-center justify-center bg-slate-50/80 backdrop-blur-sm">
      <el-icon class="is-loading text-4xl text-indigo-500 mb-4"><Loading /></el-icon>
      <span class="text-slate-600 font-bold tracking-widest animate-pulse">正在加载南京真实空间孪生基座... {{ loadProgress }}%</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { CSS2DRenderer, CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer.js'

const props = defineProps({
  campusData: { type: Array, default: () => [] }
})
const emit = defineEmits(['building-click'])

const containerRef = ref(null)
const isLoading = ref(true)
const loadProgress = ref(0)

let scene, camera, renderer, labelRenderer, controls
let animationFrameId
let raycaster, mouse
let buildingMeshes = []
let gltfScene = null  // GLTF 模型根节点引用
let clickTimerId = null  // setTimeout 引用

const init3DEnvironment = () => {
  const container = containerRef.value
  const width = container.clientWidth
  const height = container.clientHeight

  // 1. 场景与柔和白模背景
  scene = new THREE.Scene()
  scene.background = new THREE.Color('#f1f5f9')
  scene.fog = new THREE.FogExp2('#f1f5f9', 0.001)

  // 2. 相机配置
  camera = new THREE.PerspectiveCamera(45, width / height, 1, 10000)
  camera.position.set(400, 300, 400) // 默认观测角度

  // 3. WebGL 渲染器
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false })
  renderer.setSize(width, height)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))  // 上限裁剪，防止高 DPR 设备爆显存
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  container.appendChild(renderer.domElement)

  // 4. CSS2D 渲染器 (用于悬浮数据标签)
  labelRenderer = new CSS2DRenderer()
  labelRenderer.setSize(width, height)
  labelRenderer.domElement.style.position = 'absolute'
  labelRenderer.domElement.style.top = '0px'
  labelRenderer.domElement.style.pointerEvents = 'none' 
  container.appendChild(labelRenderer.domElement)

  // 5. 高级柔和光影系统
  const ambientLight = new THREE.AmbientLight('#ffffff', 0.6)
  scene.add(ambientLight)

  const dirLight = new THREE.DirectionalLight('#ffffff', 0.8)
  dirLight.position.set(300, 500, 200)
  dirLight.castShadow = true
  dirLight.shadow.mapSize.width = 1024
  dirLight.shadow.mapSize.height = 1024
  scene.add(dirLight)

  // 6. 控制器与交互
  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.05
  controls.maxPolarAngle = Math.PI / 2.1 
  
  raycaster = new THREE.Raycaster()
  mouse = new THREE.Vector2()
  window.addEventListener('resize', onWindowResize)
  renderer.domElement.addEventListener('pointerdown', onMouseClick)
}

const loadWhiteBoxModel = () => {
  const loader = new GLTFLoader()
  // 注意这里：直接加载您刚才放入 public/models 的南京地图模型
  loader.load(
    '/models/cadmapper-nanjing-jiangsu-cn.glb',
    (gltf) => {
      const model = gltf.scene
      
      const whiteMaterial = new THREE.MeshStandardMaterial({
        color: '#ffffff', roughness: 0.8, metalness: 0.1,
      })

      model.traverse((child) => {
        if (child.isMesh) {
          child.castShadow = true
          child.receiveShadow = true
          child.material = whiteMaterial  // 共享材质，避免数千个 clone 爆显存
          buildingMeshes.push(child)
        }
      })

      // 核心：自动居中与缩放南京真实的地理数据
      const box = new THREE.Box3().setFromObject(model)
      const center = box.getCenter(new THREE.Vector3())
      const size = box.getSize(new THREE.Vector3())
      const maxDim = Math.max(size.x, size.y, size.z)

      const scale = 600 / maxDim
      model.scale.set(scale, scale, scale)
      model.position.sub(center.multiplyScalar(scale))

      gltfScene = model  // 保存引用以便卸载时 dispose
      scene.add(model)
      isLoading.value = false
      syncDataToScene()
    },
    (xhr) => { loadProgress.value = Math.round((xhr.loaded / xhr.total) * 100) },
    (error) => {
      console.error('模型加载失败', error)
      isLoading.value = false
    }
  )
}

const syncDataToScene = () => {
  buildingMeshes.forEach(mesh => {
    mesh.children = mesh.children.filter(c => !c.isCSS2DObject)
  })

  // 演示：在几栋大楼顶上随机挂载告警标签
  const mockData = [
    { name: '业务中心 A座', power: 345, status: '正常' },
    { name: '核心机房', power: 890, status: '告警' },
    { name: '研发大楼', power: 120, status: '正常' }
  ]

  mockData.forEach((data, index) => {
    const targetMesh = buildingMeshes[index * 5] 
    if (targetMesh) {
      targetMesh.userData = { id: `B-${index}`, ...data }
      
      if (data.status === '告警') {
        // 🌟 修复：先 clone 材质，避免直接修改共享材质导致全局污染（其他建筑也会变红）
        targetMesh.material = targetMesh.material.clone()
        targetMesh.material.color.set('#fee2e2')
        targetMesh.material.emissive = new THREE.Color('#ef4444')
        targetMesh.material.emissiveIntensity = 0.2
      }

      const div = document.createElement('div')
      div.className = `px-3 py-1.5 backdrop-blur-md border rounded-lg shadow-lg flex flex-col items-center cursor-pointer transition-transform hover:scale-110 ${data.status === '正常' ? 'bg-white/80 border-slate-200' : 'bg-red-500/90 border-red-400 text-white'}`

      // 安全的 DOM API 替代 innerHTML 拼接，防止 XSS
      const span1 = document.createElement('span')
      span1.className = `text-xs font-bold ${data.status === '正常' ? 'text-slate-800' : 'text-white'}`
      span1.textContent = data.name
      const span2 = document.createElement('span')
      span2.className = `text-[10px] font-mono mt-0.5 ${data.status === '正常' ? 'text-indigo-600' : 'text-red-100'}`
      span2.textContent = `${data.power} kW`
      div.appendChild(span1)
      div.appendChild(span2)
      
      const label = new CSS2DObject(div)
      const box = new THREE.Box3().setFromObject(targetMesh)
      label.position.set(0, (box.max.y - box.min.y) / 2 + 5, 0)
      targetMesh.add(label)
    }
  })
}

const onMouseClick = (event) => {
  const container = containerRef.value
  const rect = container.getBoundingClientRect()
  mouse.x = ((event.clientX - rect.left) / container.clientWidth) * 2 - 1
  mouse.y = -((event.clientY - rect.top) / container.clientHeight) * 2 + 1

  raycaster.setFromCamera(mouse, camera)
  const intersects = raycaster.intersectObjects(buildingMeshes, false)

  if (intersects.length > 0) {
    const clickedMesh = intersects[0].object
    const buildingData = clickedMesh.userData
    if (buildingData && buildingData.name) {
      const originalY = clickedMesh.position.y
      clickedMesh.position.y += 2
      clickTimerId = setTimeout(() => { clickedMesh.position.y = originalY; clickTimerId = null }, 150)
      emit('building-click', buildingData.id)
    }
  }
}

const onWindowResize = () => {
  if (!containerRef.value || !camera || !renderer) return
  const width = containerRef.value.clientWidth
  const height = containerRef.value.clientHeight
  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
  labelRenderer.setSize(width, height)
}

const animate = () => {
  animationFrameId = requestAnimationFrame(animate)
  if (controls) controls.update()
  if (renderer && scene && camera) renderer.render(scene, camera)
  if (labelRenderer && scene && camera) labelRenderer.render(scene, camera)
}

onMounted(() => {
  init3DEnvironment()
  loadWhiteBoxModel()
  animate()
})

// 完整的资源释放函数：遍历场景树 dispose geometry/material
function disposeNode(node) {
  if (node.isMesh) {
    node.geometry?.dispose()
    const mat = node.material
    if (Array.isArray(mat)) mat.forEach(m => m.dispose())
    else mat?.dispose()
  }
  node.children?.slice().forEach(disposeNode)
}

function dispose3DResources() {
  if (clickTimerId) { clearTimeout(clickTimerId); clickTimerId = null }
  if (animationFrameId) { cancelAnimationFrame(animationFrameId); animationFrameId = null }

  // 1. GLTF 整树 dispose
  if (gltfScene) {
    disposeNode(gltfScene)
    scene?.remove(gltfScene)
    gltfScene = null
  }
  // 2. 显式 dispose 建筑列表
  buildingMeshes.forEach(m => {
    m.geometry?.dispose()
    // 材质是共享的，只需 dispose 一次（由 gltfScene traverse 处理）
  })
  buildingMeshes.length = 0

  // 3. OrbitControls 内部监听了多个 pointer 事件
  controls?.dispose()
  controls = null

  // 4. CSS2DRenderer 的 DOM 节点
  if (labelRenderer) {
    labelRenderer.domElement.remove()
    labelRenderer = null
  }

  // 5. WebGLRenderer
  if (renderer) {
    renderer.dispose()
    renderer.forceContextLoss()
    renderer.domElement.remove()
    renderer = null
  }

  // 6. 场景残留光源等
  if (scene) {
    scene.traverse(disposeNode)
    scene = null
  }
  camera = null
}

onBeforeUnmount(() => {
  window.removeEventListener('resize', onWindowResize)
  if (renderer) renderer.domElement.removeEventListener('pointerdown', onMouseClick)
  dispose3DResources()
})
</script>