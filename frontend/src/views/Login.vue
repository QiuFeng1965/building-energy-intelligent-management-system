<template>
  <div class="login-container min-h-screen w-full flex items-center justify-center bg-[#f0f4f8] overflow-hidden relative font-sans text-slate-800"
       @mousedown="handleMouseDown" 
       @mouseup="handleMouseUp">
    
    <div ref="bgParallax" class="absolute inset-0 z-0 pointer-events-none transition-transform duration-1000 ease-out">
      <div class="absolute inset-0 dot-grid-pattern opacity-50"></div>
      <div class="absolute top-[10%] left-[20%] w-[500px] h-[500px] bg-blue-500/10 rounded-full blur-[120px] animate-breathe"></div>
      <div class="absolute bottom-[10%] right-[20%] w-[600px] h-[600px] bg-indigo-400/10 rounded-full blur-[150px] animate-breathe-delay"></div>
      <div class="absolute top-[40%] left-[50%] w-[400px] h-[400px] bg-cyan-400/10 rounded-full blur-[100px] animate-breathe"></div>
    </div>

    <div class="w-full max-w-7xl flex items-center justify-between p-4 md:p-10 z-10 relative">
      
      <div class="hidden md:flex flex-col items-center justify-center flex-1 pr-10 text-center relative h-[550px]">
        
        <div class="absolute right-[12%] top-[5%] z-20">
          <div ref="headShield" class="clay-body w-32 h-32 rounded-[2rem] bg-slate-800 flex flex-col items-center justify-center relative overflow-hidden border-4 border-slate-700">
            <div class="absolute top-2 w-16 h-2 bg-blue-500/50 rounded-full shadow-[0_0_10px_#3b82f6]"></div>
            <div class="w-[80%] h-12 flex items-center justify-center px-2 relative z-10 mt-4 bg-slate-900 rounded-xl border border-slate-600 shadow-inner">
              <div ref="eyeLShield" class="absolute left-3 z-10">
                <div class="eye-pupil bg-cyan-400 rounded-md shadow-[0_0_10px_#22d3ee]" :class="pupilStateClass('w-8 h-4', 'w-8 h-1', 'w-10 h-6')"></div>
              </div>
              <div ref="eyeRShield" class="absolute right-3 z-10">
                <div class="eye-pupil bg-cyan-400 rounded-md shadow-[0_0_10px_#22d3ee]" :class="pupilStateClass('w-8 h-4', 'w-8 h-1', 'w-10 h-6')"></div>
              </div>
            </div>
          </div>
          <div ref="shadowShield" class="absolute bottom-[-20px] left-1/2 -translate-x-1/2 w-20 h-5 bg-slate-900/20 rounded-full blur-md"></div>
        </div>

        <div class="absolute left-[12%] bottom-[5%] z-30">
          <div ref="headCloud" class="clay-body w-28 h-24 rounded-[40%_60%_70%_50%_/_50%_50%_60%_40%] bg-blue-100 border-2 border-white flex flex-col items-center justify-center backdrop-blur-sm">
            <div class="flex items-center justify-center gap-4 relative w-full h-8">
              <div ref="eyeLCloud" class="absolute left-6 z-10">
                <div class="eye-pupil bg-blue-500 rounded-full" :class="pupilStateClass('w-3 h-3', 'w-3 h-1', 'w-4 h-4')"></div>
              </div>
              <div ref="eyeRCloud" class="absolute right-6 z-10">
                <div class="eye-pupil bg-blue-500 rounded-full" :class="pupilStateClass('w-3 h-3', 'w-3 h-1', 'w-4 h-4')"></div>
              </div>
            </div>
          </div>
          <div ref="shadowCloud" class="absolute bottom-[-15px] left-1/2 -translate-x-1/2 w-20 h-4 bg-blue-500/10 rounded-full blur-md"></div>
        </div>

        <div class="absolute right-[5%] bottom-[15%] z-20">
          <div ref="headLens" class="clay-body w-28 h-28 rounded-full bg-slate-100 flex items-center justify-center relative overflow-hidden border-[6px] border-slate-300">
            <div class="w-full h-full flex items-center justify-center relative z-10 bg-slate-200 rounded-full">
              <div ref="eyeLens" class="absolute z-10">
                <div class="w-14 h-14 bg-slate-800 border-4 border-slate-600 rounded-full flex items-center justify-center shadow-[inset_0_0_15px_rgba(0,0,0,0.8)]">
                  <div class="w-6 h-6 rounded-full flex items-center justify-center transition-colors duration-300" :class="{'bg-blue-500 shadow-[0_0_15px_#3b82f6]': isMouseDown, 'bg-slate-700': isPasswordFocused, 'bg-slate-900': !isMouseDown && !isPasswordFocused}">
                     <div class="w-2 h-2 bg-white rounded-full absolute top-1 right-1 opacity-70"></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div ref="shadowLens" class="absolute bottom-[-20px] left-1/2 -translate-x-1/2 w-24 h-5 bg-slate-400/20 rounded-full blur-md"></div>
        </div>

        <div class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-10 scale-110">
          <div ref="headCore" class="clay-body w-56 h-60 rounded-[3rem_3rem_4rem_4rem] bg-white border border-slate-100 flex flex-col items-center justify-center relative">
            <div class="w-20 h-2 bg-blue-50 rounded-full absolute top-5 shadow-[inset_0_2px_4px_rgba(0,0,0,0.05)]"></div>
            
            <div class="w-[85%] h-24 bg-slate-900 rounded-3xl flex items-center justify-center gap-10 relative mt-4 shadow-[inset_0_0_20px_rgba(0,0,0,0.5)] border-4 border-slate-800 overflow-hidden">
              <div class="absolute -top-10 -right-10 w-32 h-32 bg-white/5 rounded-full blur-xl"></div>
              
              <div ref="eyeLCore" class="absolute z-10 left-6">
                <div class="eye-pupil bg-blue-400 rounded-[50%] flex items-center justify-center shadow-[0_0_15px_rgba(96,165,250,0.6)]" :class="pupilStateClass('w-12 h-12', 'w-10 h-2 !rounded-sm bg-blue-600', 'w-14 h-14 bg-cyan-300')">
                  <div class="w-4 h-4 bg-white rounded-full absolute top-2 left-2 shadow-[0_0_5px_#fff]"></div>
                </div>
              </div>
              <div ref="eyeRCore" class="absolute z-10 right-6">
                <div class="eye-pupil bg-blue-400 rounded-[50%] flex items-center justify-center shadow-[0_0_15px_rgba(96,165,250,0.6)]" :class="pupilStateClass('w-12 h-12', 'w-10 h-2 !rounded-sm bg-blue-600', 'w-14 h-14 bg-cyan-300')">
                  <div class="w-4 h-4 bg-white rounded-full absolute top-2 left-2 shadow-[0_0_5px_#fff]"></div>
                </div>
              </div>
            </div>

            <div class="w-full relative h-16 mt-4">
              <div class="absolute left-6 w-4 h-4 bg-blue-100 rounded-full shadow-inner transition-colors duration-300" :class="{'bg-blue-400 shadow-[0_0_10px_#60a5fa]': isLoggingIn}"></div>
              <div class="absolute right-6 w-4 h-4 bg-blue-100 rounded-full shadow-inner transition-colors duration-300" :class="{'bg-blue-400 shadow-[0_0_10px_#60a5fa]': isLoggingIn}"></div>
              <div class="absolute left-1/2 -translate-x-1/2 top-4 flex gap-1">
                <div class="w-1.5 h-1.5 bg-slate-300 rounded-full"></div>
                <div class="w-1.5 h-1.5 bg-slate-300 rounded-full"></div>
                <div class="w-1.5 h-1.5 bg-slate-300 rounded-full"></div>
              </div>
            </div>
          </div>
          <div ref="shadowCore" class="absolute bottom-[-35px] left-1/2 -translate-x-1/2 w-48 h-8 bg-slate-300/30 rounded-full blur-xl"></div>
        </div>

      </div>

      <div class="flex-1 flex justify-center md:justify-end relative" style="perspective: 1500px;">
        <div ref="loginCardRef" class="w-full max-w-[440px] p-10 bg-white/80 backdrop-blur-2xl rounded-[32px] shadow-[0_30px_80px_rgba(0,0,0,0.04),inset_0_0_0_1px_rgba(255,255,255,1)] border border-white relative z-20 transition-transform duration-100 ease-out" style="transform-style: preserve-3d;">
          
          <div class="flex items-center gap-4 mb-10 transform translate-z-10">
            <div class="w-14 h-14 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-2xl flex items-center justify-center shadow-[0_10px_20px_rgba(59,130,246,0.3),inset_0_2px_5px_rgba(255,255,255,0.4)]">
              <div class="w-6 h-6 border-2 border-white rounded-lg flex items-center justify-center relative">
                 <div class="w-2 h-2 bg-white rounded-sm absolute -top-1 -right-1"></div>
              </div>
            </div>
            <div>
              <h1 class="text-3xl font-black text-slate-800 tracking-tight">系统控制台</h1>
              <p class="text-slate-500 text-xs mt-1 font-bold tracking-widest uppercase">Admin Terminal</p>
            </div>
          </div>

          <form @submit.prevent="handleLogin" class="space-y-6 transform translate-z-10">
            
            <div class="space-y-2 group">
              <label for="username" class="flex items-center gap-2 text-sm font-bold text-slate-700 tracking-wide transition-colors group-focus-within:text-blue-500">
                管理账号
              </label>
              <div class="relative flex items-center w-full h-14 bg-slate-50/80 hover:bg-slate-50 rounded-2xl border-2 border-slate-200 focus-within:!bg-white focus-within:!border-blue-400 focus-within:shadow-[0_0_20px_rgba(59,130,246,0.15)] transition-all overflow-hidden">
                <div class="pl-4 pr-3 flex items-center h-full pointer-events-none">
                   <el-icon class="text-slate-400 text-xl transition-colors group-focus-within:text-blue-500"><User /></el-icon>
                </div>
                
                <input v-model="loginForm.username" type="text" id="username" 
                       ref="usernameInputRef"
                       @focus="isUsernameFocused = true" 
                       @blur="isUsernameFocused = false" 
                       placeholder="请输入系统分配的账号" 
                       class="w-full h-full pr-4 bg-transparent text-slate-800 text-base outline-none tracking-wide z-10 placeholder-slate-300 font-medium" required />
              </div>
            </div>
            
            <div class="space-y-2 group">
              <label for="password" class="flex items-center gap-2 text-sm font-bold text-slate-700 tracking-wide transition-colors group-focus-within:text-indigo-500">
                安全凭证
              </label>
              <div class="relative flex items-center w-full h-14 bg-slate-50/80 hover:bg-slate-50 rounded-2xl border-2 border-slate-200 focus-within:!bg-white focus-within:!border-indigo-400 focus-within:shadow-[0_0_20px_rgba(99,102,241,0.2)] transition-all overflow-hidden">
                <div class="pl-4 pr-3 flex items-center h-full pointer-events-none">
                   <el-icon class="text-slate-400 text-xl transition-colors group-focus-within:text-indigo-500"><Lock /></el-icon>
                </div>
                
                <input v-model="loginForm.password" type="password" id="password" 
                       ref="passwordInputRef"
                       @focus="isPasswordFocused = true" 
                       @blur="isPasswordFocused = false" 
                       placeholder="••••••••" 
                       class="w-full h-full pr-4 bg-transparent text-slate-800 text-base outline-none tracking-widest z-10 placeholder-slate-300" required />
              </div>
            </div>

            <button type="submit" :disabled="isLoggingIn" class="w-full h-16 mt-6 bg-slate-800 text-white rounded-2xl font-bold text-lg hover:bg-slate-900 active:scale-[0.97] transition-all duration-300 disabled:opacity-50 flex items-center justify-center gap-2 relative overflow-hidden group shadow-[0_10px_30px_rgba(15,23,42,0.2)] hover:shadow-[0_10px_30px_rgba(59,130,246,0.3)]">
              <div class="absolute inset-0 -translate-x-full group-hover:animate-[shimmer_1.5s_infinite] bg-gradient-to-r from-transparent via-white/20 to-transparent skew-x-12"></div>
              <el-icon v-if="isLoggingIn" class="animate-spin text-2xl relative z-10"><Loading /></el-icon>
              <span class="relative z-10 tracking-widest">{{ isLoggingIn ? '校验协议中...' : '登 录 系 统' }}</span>
            </button>
          </form>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login } from '../api/index.js'

const emit = defineEmits(['login-success'])
const router = useRouter()

const isLoggingIn = ref(false)
const loginForm = reactive({ username: '', password: '' })

// ================= 🧠 交互状态核心 =================
const isUsernameFocused = ref(false)
const isPasswordFocused = ref(false)
const isMouseDown = ref(false)

const handleMouseDown = () => { isMouseDown.value = true }
const handleMouseUp = () => { isMouseDown.value = false }

const usernameInputRef = ref(null)
const passwordInputRef = ref(null)

// 动态样式计算（仅控制颜色和形状，不控制transform）
const pupilStateClass = (normalClass, hideClass, shockClass) => {
  if (isMouseDown.value) return `${shockClass} !duration-75` 
  if (isPasswordFocused.value) return `${hideClass} !duration-300` 
  return `${normalClass} animate-blink` 
}

// ================= 🧠 DOM 引用 =================
const bgParallax = ref(null)
const headCore = ref(null), eyeLCore = ref(null), eyeRCore = ref(null), shadowCore = ref(null)
const headShield = ref(null), eyeLShield = ref(null), eyeRShield = ref(null), shadowShield = ref(null)
const headLens = ref(null), eyeLens = ref(null), shadowLens = ref(null)
const headCloud = ref(null), eyeLCloud = ref(null), eyeRCloud = ref(null), shadowCloud = ref(null)
const loginCardRef = ref(null)

// ================= 🚀 顶级物理引擎 (Awwwards 级别) =================
let mouseX = window.innerWidth / 2
let mouseY = window.innerHeight / 2
let animationFrameId = null

// 用于计算移动速度的变量 (挤压与拉伸效应用)
let lastMouseX = mouseX
let lastMouseY = mouseY
let mouseVelocity = 0

// 为每一个机器人实例创建一个独立的物理状态
class RobotPhysics {
  constructor(headRef, eyeRefs, shadowRef, config) {
    this.headRef = headRef;
    this.eyeRefs = eyeRefs;
    this.shadowRef = shadowRef;
    this.config = config;
    
    // 头部当前位置
    this.headX = 0; this.headY = 0;
    // 眼睛当前位置 (滞后于头部)
    this.eyeX = 0; this.eyeY = 0;
    
    // 随机的呼吸初始相位，让每个机器人浮动频率不同
    this.breathPhase = Math.random() * Math.PI * 2;
  }

  update(targetX, targetY, isAvoiding, isTrackingCaret, centerX, centerY, time) {
    if (!this.headRef.value) return;

    // 1. 计算有机呼吸 (Idle Hover) 
    // 哪怕鼠标不动，机器人也会在空中轻微画8字游动
    const idleX = Math.sin(time * 0.002 + this.breathPhase) * 15;
    const idleY = Math.cos(time * 0.003 + this.breathPhase) * 10;

    let finalTargetX = targetX;
    let finalTargetY = targetY;

    // 2. 状态覆写：密码非礼勿视
    if (isAvoiding) {
      finalTargetX = centerX + 800 * Math.cos(this.breathPhase); 
      finalTargetY = centerY - 600; 
    }

    // 向量计算
    const dx = (finalTargetX - centerX) + idleX;
    const dy = (finalTargetY - centerY) + idleY;
    const distance = Math.sqrt(dx * dx + dy * dy);
    const angle = Math.atan2(dy, dx);

    // 3. 头部物理 (平滑 Lerp 跟随)
    const maxHeadMove = this.config.headRadius * (isAvoiding ? 0.3 : 1);
    const distanceRatio = Math.min(distance / 600, 1);
    
    const targetHeadX = Math.cos(angle) * maxHeadMove * distanceRatio + idleX;
    let targetHeadY = Math.sin(angle) * maxHeadMove * distanceRatio + idleY;
    
    if (isAvoiding) targetHeadY += 20; // 眯眼时头部低垂

    // Lerp (线性插值)：当前位置 = 当前位置 + (目标 - 当前) * 缓动系数
    this.headX += (targetHeadX - this.headX) * 0.1;
    this.headY += (targetHeadY - this.headY) * 0.1;

    // 4. 挤压与拉伸 (Squash & Stretch)
    // 根据鼠标滑动速度拉伸变形，极具生命力
    let stretch = 1 + Math.min(mouseVelocity * 0.005, 0.15);
    let squash = 1 - Math.min(mouseVelocity * 0.002, 0.1);
    if (isMouseDown.value) { stretch = 1.1; squash = 0.9; } // 点击时 Q弹压扁

    this.headRef.value.style.transform = `
      translate(${this.headX}px, ${this.headY}px) 
      rotate(${angle * (180 / Math.PI)}deg) 
      scaleX(${stretch}) scaleY(${squash}) 
      rotate(${-angle * (180 / Math.PI)}deg)
    `;

    // 5. 底部阴影联动 (距离越远，阴影越小越淡)
    if (this.shadowRef.value) {
      const shadowScale = 1 - Math.min(Math.abs(this.headY) / 100, 0.5);
      this.shadowRef.value.style.transform = `translateX(${-this.headX * 0.2}px) scale(${shadowScale})`;
      this.shadowRef.value.style.opacity = shadowScale;
    }

    // 6. 眼睛物理 (延迟跟随头部，形成二次动态)
    const maxEyeDist = Math.min(distance * 0.06, this.config.maxEyeRadius);
    const targetEyeX = Math.cos(angle) * maxEyeDist;
    let targetEyeY = Math.sin(angle) * maxEyeDist;
    
    if (isAvoiding) targetEyeY += 12;

    // 眼睛的缓动系数比头部小，产生“滞后感”
    this.eyeX += (targetEyeX - this.eyeX) * 0.15;
    this.eyeY += (targetEyeY - this.eyeY) * 0.15;

    this.eyeRefs.forEach(eyeRef => {
      if (eyeRef.value) eyeRef.value.style.transform = `translate(${this.eyeX}px, ${this.eyeY}px)`;
    });
  }
}

let robots = [];

const handleMouseMove = (e) => {
  mouseX = e.clientX
  mouseY = e.clientY
}

const animatePhysics = () => {
  const time = Date.now();
  let targetX = mouseX
  let targetY = mouseY

  // 计算鼠标滑动速度 (Squash & Stretch 动力源)
  const vX = mouseX - lastMouseX;
  const vY = mouseY - lastMouseY;
  mouseVelocity = mouseVelocity * 0.8 + Math.sqrt(vX * vX + vY * vY) * 0.2;
  lastMouseX = mouseX;
  lastMouseY = mouseY;

  // 视差背景联动
  if (bgParallax.value) {
    const bgX = (window.innerWidth / 2 - mouseX) * 0.02;
    const bgY = (window.innerHeight / 2 - mouseY) * 0.02;
    bgParallax.value.style.transform = `translate(${bgX}px, ${bgY}px)`;
  }

  // 获取系统的绝对物理中心点
  let centerX = window.innerWidth / 2;
  let centerY = window.innerHeight / 2;
  if (headCore.value) {
    const rect = headCore.value.getBoundingClientRect();
    centerX = rect.left + rect.width / 2;
    centerY = rect.top + rect.height / 2;
  }

  // 📝 光标追踪逻辑
  let isTrackingCaret = false;
  if (isUsernameFocused.value && usernameInputRef.value) {
    const rect = usernameInputRef.value.getBoundingClientRect();
    const textWidth = loginForm.username.length * 9.5; // 字体等效宽度
    targetX = rect.left + 45 + textWidth; 
    targetY = rect.top + rect.height / 2;
    isTrackingCaret = true;
  } 

  // 更新所有机器人
  robots.forEach(robot => {
    robot.update(targetX, targetY, isPasswordFocused.value, isTrackingCaret, centerX, centerY, time);
  });

  // 登录框微弱的3D陀螺仪悬浮
  if (loginCardRef.value) {
    const cardRotX = ((centerY - targetY) / window.innerHeight) * 8;
    const cardRotY = ((targetX - centerX) / window.innerWidth) * 8;
    // 使用 lerp 让卡片旋转也极度丝滑
    loginCardRef.value.style.transform = `rotateX(${cardRotX}deg) rotateY(${cardRotY}deg) translateZ(0px)`;
  }

  animationFrameId = requestAnimationFrame(animatePhysics)
}

const handleLogin = async () => {
  isLoggingIn.value = true
  try {
    const data = await login(loginForm.username, loginForm.password)
    if (data.status === 'success') {
      // 存储 token 到 localStorage
      if (data.token) {
        localStorage.setItem('token', data.token)
        localStorage.setItem('username', data.username || 'admin')
      }
      ElMessage.success('授权通过，正在初始化控制台。')
      emit('login-success', data)  // 兼容旧的 emit 方式（若父组件监听）
      // 直接路由跳转（不依赖父组件事件，因为 router-view 不会转发 emit）
      router.push('/spatial-twin')
    } else {
      ElMessage.error(data.message)
    }
  } catch (error) {
    ElMessage.error('无法连接到网关，请检查网络配置。')
  } finally {
    isLoggingIn.value = false
  }
}

onMounted(() => {
  // 初始化机器人矩阵，赋予不同的骨骼限制属性
  robots = [
    new RobotPhysics(headCore, [eyeLCore, eyeRCore], shadowCore, { headRadius: 45, maxEyeRadius: 26 }),
    new RobotPhysics(headShield, [eyeLShield, eyeRShield], shadowShield, { headRadius: 60, maxEyeRadius: 20 }),
    new RobotPhysics(headLens, [eyeLens], shadowLens, { headRadius: 35, maxEyeRadius: 16 }),
    new RobotPhysics(headCloud, [eyeLCloud, eyeRCloud], shadowCloud, { headRadius: 50, maxEyeRadius: 14 })
  ];

  window.addEventListener('mousemove', handleMouseMove)
  animatePhysics()
})

onUnmounted(() => {
  window.removeEventListener('mousemove', handleMouseMove)
  if (animationFrameId) cancelAnimationFrame(animationFrameId)
})
</script>

<style scoped>
.dot-grid-pattern {
  background-image: radial-gradient(#cbd5e1 2px, transparent 2px);
  background-size: 40px 40px;
}

.clay-body {
  box-shadow: 
    0 30px 60px rgba(0,0,0,0.08),
    inset 10px 10px 20px rgba(255,255,255,0.7),
    inset -10px -10px 20px rgba(0,0,0,0.05);
  backface-visibility: hidden;
  transform-origin: center center;
  /* 移除 CSS transition 以免与 JS 打架，强制开启 GPU 加速 */
  will-change: transform;
}

.eye-pupil {
  /* 🔥 核心细节：只保留颜色和形状的渐变，坚决不让 CSS 干涉 Transform 位置变换！ */
  transition: background-color 0.3s ease, border-radius 0.3s ease, box-shadow 0.3s ease, height 0.3s cubic-bezier(0.68, -0.55, 0.27, 1.55), width 0.3s cubic-bezier(0.68, -0.55, 0.27, 1.55);
  will-change: transform;
}

.animate-blink { animation: blink 6s infinite; }
.animate-blink:nth-child(odd) { animation: blink 5s infinite 2s; }

@keyframes blink {
  0%, 9%, 11%, 19%, 21%, 69%, 71%, 100% { transform: scaleY(1); }
  10%, 20%, 70% { transform: scaleY(0.1); } 
}

.animate-breathe { animation: breathe 8s ease-in-out infinite; }
.animate-breathe-delay { animation: breathe 8s ease-in-out infinite 4s; }
@keyframes breathe {
  0%, 100% { transform: scale(1); opacity: 0.15; }
  50% { transform: scale(1.1); opacity: 0.3; }
}

@keyframes shimmer { 100% { transform: translateX(100%) skewX(12deg); } }
.translate-z-10 { transform: translateZ(40px); }

/* 深度优化自动填充的底色 */
input:-webkit-autofill,
input:-webkit-autofill:hover, 
input:-webkit-autofill:focus, 
input:-webkit-autofill:active{
  -webkit-box-shadow: 0 0 0 30px #ffffff inset !important;
  -webkit-text-fill-color: #1e293b !important;
  transition: background-color 5000s ease-in-out 0s;
  font-weight: 500;
}
</style>