// src/utils/TwinRenderer.js
// 3D 孪生时间引擎核心渲染器
// 职责：
//   1. 在 requestAnimationFrame 中监听时间戳变化并同步更新 3D 场景
//   2. 基于时间戳动态平滑修改设备材质（温度升高 → 发光红色）
//   3. 严格 dispose() 释放几何体/材质/纹理/ WebGL 上下文，杜绝显存泄漏
//
// 使用 THREE.MathUtils.lerp + Color.lerp 做帧率无关插值，快速拖拽不掉帧。

import * as THREE from 'three'

// 颜色常量（模块级单例，避免每帧 new Color 引发 GC Stutter）
const COLOR_NORMAL = new THREE.Color('#38bdf8')
const COLOR_WARN = new THREE.Color('#f59e0b')
const COLOR_CRITICAL = new THREE.Color('#ef4444')
const COLOR_GLOW = new THREE.Color('#450a0a')

// 设备状态阈值
const TEMP_WARN = 60      // °C
const TEMP_CRITICAL = 85  // °C

export class TwinRenderer {
  /**
   * @param {HTMLElement} container 渲染容器
   * @param {Object} options
   * @param {Function} [options.onDeviceClick] 设备点击回调 (deviceId, node) => void
   * @param {Function} [options.stateSampler] 自定义状态采样器 (ts) => Map<deviceId, {temp, power, status}>
   */
  constructor(container, options = {}) {
    this.container = container
    this.options = options
    this.disposed = false

    // 时间引擎状态
    this.currentTimestamp = Date.now()
    this._lastAppliedTs = 0  // 上次应用过的 ts，避免每帧重复采样

    // 设备节点集合（device_id → { mesh, material, baseColor, ...lerp 状态 }）
    this.deviceNodes = new Map()

    // 受管可释放资源池（dispose 时统一释放，防泄漏）
    this._disposableGeometries = []
    this._disposableMaterials = []
    this._disposableTextures = []

    this._initScene()
    this._initResizeObserver()
    this._startRenderLoop()
  }

  // ============= 场景初始化 =============
  _initScene() {
    const w = this.container.clientWidth
    const h = this.container.clientHeight

    this.scene = new THREE.Scene()
    this.scene.background = new THREE.Color('#0f172a')
    this.scene.fog = new THREE.FogExp2('#0f172a', 0.0015)

    this.camera = new THREE.PerspectiveCamera(45, w / h, 1, 5000)
    this.camera.position.set(200, 180, 200)

    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: false,
      powerPreference: 'high-performance'
    })
    this.renderer.setSize(w, h)
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))  // 上限裁剪防高 DPR 爆显存
    this.renderer.shadowMap.enabled = true
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap
    this.container.appendChild(this.renderer.domElement)

    // 光源精简：1 环境 + 1 方向（性能优先，避免多光源成倍增加 draw call）
    this.ambientLight = new THREE.AmbientLight('#ffffff', 0.55)
    this.scene.add(this.ambientLight)

    this.dirLight = new THREE.DirectionalLight('#ffffff', 0.85)
    this.dirLight.position.set(150, 300, 120)
    this.dirLight.castShadow = true
    this.dirLight.shadow.mapSize.set(1024, 1024)
    this.dirLight.shadow.camera.left = -300
    this.dirLight.shadow.camera.right = 300
    this.dirLight.shadow.camera.top = 300
    this.dirLight.shadow.camera.bottom = -300
    this.scene.add(this.dirLight)

    // 外部按需注入 OrbitControls
    this.controls = null

    // 网格地面
    const gridGeo = new THREE.PlaneGeometry(800, 800)
    const gridMat = new THREE.MeshStandardMaterial({
      color: '#1e293b', roughness: 0.9, metalness: 0.1
    })
    this._disposableGeometries.push(gridGeo)
    this._disposableMaterials.push(gridMat)
    this.ground = new THREE.Mesh(gridGeo, gridMat)
    this.ground.rotation.x = -Math.PI / 2
    this.ground.receiveShadow = true
    this.scene.add(this.ground)

    // 射线投射（点击拾取）
    this.raycaster = new THREE.Raycaster()
    this._pointer = new THREE.Vector2()
    this._onPointerDown = this._onPointerDown.bind(this)
    this.renderer.domElement.addEventListener('pointerdown', this._onPointerDown)
  }

  _initResizeObserver() {
    this._resizeObserver = new ResizeObserver(() => this._onResize())
    this._resizeObserver.observe(this.container)
  }

  _onResize() {
    if (this.disposed) return
    const w = this.container.clientWidth
    const h = this.container.clientHeight
    if (w === 0 || h === 0) return  // 隐藏 tab 容器为 0，跳过避免矩阵退化
    this.camera.aspect = w / h
    this.camera.updateProjectionMatrix()
    this.renderer.setSize(w, h)
  }

  // ============= 设备节点管理 =============

  /**
   * 注册一个设备孪生节点
   * @param {string} deviceId
   * @param {THREE.Mesh} mesh
   * @param {Object} baseStyle 基础样式 { wall, emissive }
   */
  registerDevice(deviceId, mesh, baseStyle = {}) {
    // 克隆材质，避免共享材质被多设备互相污染
    const baseMat = mesh.material
    let ownedMaterial = baseMat
    if (!baseMat._ownedByRenderer) {
      ownedMaterial = baseMat.clone()
      ownedMaterial._ownedByRenderer = true
      this._disposableMaterials.push(ownedMaterial)
      mesh.material = ownedMaterial
    }

    const baseColor = new THREE.Color(baseStyle.wall || '#475569')
    const baseEmissive = new THREE.Color(baseStyle.emissive || '#000000')

    this.deviceNodes.set(deviceId, {
      mesh,
      material: ownedMaterial,
      baseColor,
      baseEmissive,
      baseEmissiveIntensity: 0,
      // 当前渲染状态（lerp 起点，每帧更新）
      _currentColor: baseColor.clone(),
      _currentEmissive: baseEmissive.clone(),
      _currentEmissiveIntensity: 0,
      // 目标状态（lerp 终点，时间戳变化时设置）
      _targetColor: baseColor.clone(),
      _targetEmissive: baseEmissive.clone(),
      _targetEmissiveIntensity: 0,
    })
  }

  /**
   * 基于时间戳采样设备状态
   * 真实场景应从后端拉历史/预测数据；默认提供正弦模拟采样器
   * @param {number} ts
   * @returns {Map<string, {temp:number, power:number, status:string}>}
   */
  _sampleDeviceStateAt(ts) {
    // 优先使用外部注入的采样器
    if (this.options.stateSampler) {
      return this.options.stateSampler(ts)
    }
    // 桩实现：根据 ts 在 0-24h 内正弦模拟温度
    const states = new Map()
    const date = new Date(ts)
    const hourOfDay = date.getHours() + date.getMinutes() / 60
    for (const deviceId of this.deviceNodes.keys()) {
      // 白天高负荷，夜间低负荷
      const load = Math.sin((hourOfDay - 6) / 24 * Math.PI * 2) * 0.5 + 0.5
      const temp = 35 + load * 50 + (deviceId.charCodeAt(0) % 7) * 2
      states.set(deviceId, {
        temp,
        power: 30 + load * 60,
        status: temp >= TEMP_CRITICAL ? 'critical' : temp >= TEMP_WARN ? 'warn' : 'normal'
      })
    }
    return states
  }

  /**
   * 核心：时间戳变更 → 采样状态 → 计算目标材质参数
   * 仅在 ts 变化时触发，避免每帧重复采样
   */
  _applyTimestamp(ts) {
    if (ts === this._lastAppliedTs) return
    this._lastAppliedTs = ts

    const states = this._sampleDeviceStateAt(ts)
    for (const [deviceId, node] of this.deviceNodes.entries()) {
      const s = states.get(deviceId)
      if (!s) continue

      // 根据温度计算目标颜色（lerp 终点）
      let targetColor, targetEmissive, targetIntensity
      if (s.status === 'critical') {
        targetColor = COLOR_CRITICAL.clone().lerp(COLOR_GLOW, 0.3)
        targetEmissive = COLOR_CRITICAL.clone()
        targetIntensity = 1.8
      } else if (s.status === 'warn') {
        targetColor = COLOR_WARN.clone()
        targetEmissive = COLOR_WARN.clone()
        targetIntensity = 0.9
      } else {
        targetColor = node.baseColor.clone()
        targetEmissive = node.baseEmissive.clone()
        targetIntensity = node.baseEmissiveIntensity
      }

      node._targetColor.copy(targetColor)
      node._targetEmissive.copy(targetEmissive)
      node._targetEmissiveIntensity = targetIntensity
    }
  }

  /**
   * 核心：每帧 lerp 平滑插值材质参数
   * 使用帧率无关的指数衰减：k = 1 - pow(0.2, deltaTime)
   * 保证快速拖拽时间轴时材质过渡平滑不掉帧
   */
  _lerpMaterials(deltaTime) {
    // 每秒完成 80% 过渡，帧率无关
    const k = 1 - Math.pow(0.2, deltaTime)
    for (const node of this.deviceNodes.values()) {
      node._currentColor.lerp(node._targetColor, k)
      node._currentEmissive.lerp(node._targetEmissive, k)
      node._currentEmissiveIntensity = THREE.MathUtils.lerp(
        node._currentEmissiveIntensity,
        node._targetEmissiveIntensity,
        k
      )

      // 直接 .copy 写入材质，避免每帧 new Color 引发 GC
      node.material.color.copy(node._currentColor)
      if (node.material.emissive) {
        node.material.emissive.copy(node._currentEmissive)
        node.material.emissiveIntensity = node._currentEmissiveIntensity
      }
      node.material.needsUpdate = true
    }
  }

  // ============= 时间戳外部接口 =============

  /**
   * 由 TimeEngine.vue 调用，更新当前时间戳
   * @param {number} ts 毫秒时间戳
   */
  setTimestamp(ts) {
    this.currentTimestamp = ts
    this._applyTimestamp(ts)
  }

  // ============= 渲染循环 =============

  _startRenderLoop() {
    this._clock = new THREE.Clock()
    this._renderBound = this._render.bind(this)
    this._rafId = requestAnimationFrame(this._renderBound)
  }

  _render() {
    if (this.disposed) return
    this._rafId = requestAnimationFrame(this._renderBound)

    const delta = this._clock.getDelta()

    // 即使 ts 未变，也持续 lerp，保证平滑过渡完成
    this._lerpMaterials(delta)

    if (this.controls) this.controls.update()
    this.renderer.render(this.scene, this.camera)
  }

  // ============= 交互 =============

  _onPointerDown(event) {
    const rect = this.renderer.domElement.getBoundingClientRect()
    this._pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
    this._pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
    this.raycaster.setFromCamera(this._pointer, this.camera)
    const meshes = [...this.deviceNodes.values()].map(n => n.mesh)
    const hits = this.raycaster.intersectObjects(meshes, false)
    if (hits.length > 0) {
      const entry = [...this.deviceNodes.entries()].find(([, n]) => n.mesh === hits[0].object)
      if (entry && this.options.onDeviceClick) {
        this.options.onDeviceClick(entry[0], entry[1])
      }
    }
  }

  // ============= dispose（强制释放，防显存泄漏） =============

  dispose() {
    if (this.disposed) return
    this.disposed = true

    // 1. 停止渲染循环
    if (this._rafId) {
      cancelAnimationFrame(this._rafId)
      this._rafId = null
    }

    // 2. 移除事件监听
    if (this.renderer) {
      this.renderer.domElement.removeEventListener('pointerdown', this._onPointerDown)
    }
    if (this._resizeObserver) {
      this._resizeObserver.disconnect()
      this._resizeObserver = null
    }
    if (this.controls && this.controls.dispose) {
      this.controls.dispose()
      this.controls = null
    }

    // 3. 清空设备节点引用（geometry/material 由共享池统一释放）
    this.deviceNodes.clear()

    // 4. 强制 dispose 所有受管几何体
    for (const geo of this._disposableGeometries) {
      if (geo && geo.dispose) geo.dispose()
    }
    this._disposableGeometries = []

    // 5. 强制 dispose 所有受管材质
    for (const mat of this._disposableMaterials) {
      if (mat && mat.dispose) mat.dispose()
    }
    this._disposableMaterials = []

    // 6. 强制 dispose 所有受管纹理
    for (const tex of this._disposableTextures) {
      if (tex && tex.dispose) tex.dispose()
    }
    this._disposableTextures = []

    // 7. 释放 WebGL 上下文（最关键，防止 GPU 显存残留）
    if (this.renderer) {
      this.renderer.dispose()
      if (this.renderer.forceContextLoss) this.renderer.forceContextLoss()
      if (this.renderer.domElement && this.renderer.domElement.parentNode) {
        this.renderer.domElement.parentNode.removeChild(this.renderer.domElement)
      }
      this.renderer = null
    }

    // 8. 清空场景图
    if (this.scene) {
      this.scene.clear()
      this.scene = null
    }

    this.camera = null
    this.raycaster = null
  }
}
