<template>
  <div class="w-full h-[calc(100vh-120px)] bg-[#020617] rounded-2xl shadow-2xl overflow-hidden relative font-sans border border-[#1e293b] flex" tabindex="0" @keydown="handleKeydown">
    
    <div v-if="!isSystemBooted" class="absolute inset-0 z-[999] bg-[#020617]/95 backdrop-blur-md flex flex-col items-center justify-center transition-opacity duration-500">
        <div class="text-indigo-400 font-mono text-xl mb-8 animate-pulse tracking-widest flex items-center gap-3">
            <el-icon class="is-loading"><Loading /></el-icon>
            > 正在初始化空间孪生基座 ...
        </div>
        <button @click="bootSystem" 
                class="px-8 py-4 bg-indigo-900/30 border border-indigo-500/50 text-indigo-300 font-bold tracking-[0.2em] rounded-xl hover:bg-indigo-600 hover:text-white transition-all shadow-[0_0_20px_rgba(79,70,229,0.2)] hover:shadow-[0_0_40px_rgba(79,70,229,0.6)]">
            启动数字孪生中枢
        </button>
    </div>

    <transition name="fade-slide-down">
        <div v-if="showChaosDashboard" class="absolute top-6 left-1/2 -translate-x-1/2 z-[100] bg-[#0f172a]/95 backdrop-blur-xl border border-red-900/50 p-6 rounded-2xl shadow-2xl w-96">
            <div class="flex items-center justify-between mb-4 border-b border-[#334155] pb-2">
                <h3 class="text-red-500 font-bold tracking-widest flex items-center gap-2">
                    <el-icon class="text-xl"><Warning /></el-icon> 混沌工程控制台
                </h3>
                <span class="text-[10px] bg-red-900/30 text-red-500 border border-red-800/50 px-2 py-1 rounded font-mono">GOD MODE</span>
            </div>
            <div class="space-y-5">
                <div class="flex justify-between items-center group">
                    <div>
                        <div class="text-sm text-slate-200 font-bold group-hover:text-red-400 transition-colors">Kill Primary Node</div>
                        <div class="text-[10px] text-slate-500">强制瘫痪 8000 端口，触发容灾</div>
                    </div>
                    <el-switch v-model="chaosOptions.killPrimary" style="--el-switch-on-color: #ef4444; --el-switch-off-color: #334155" />
                </div>
                <div class="flex justify-between items-center group">
                    <div>
                        <div class="text-sm text-slate-200 font-bold group-hover:text-yellow-400 transition-colors">Inject Network Latency</div>
                        <div class="text-[10px] text-slate-500">模拟全局 +2000ms 极度拥堵</div>
                    </div>
                    <el-switch v-model="chaosOptions.latency" style="--el-switch-on-color: #eab308; --el-switch-off-color: #334155" />
                </div>
                <div class="flex justify-between items-center group border-t border-[#334155] pt-3 mt-2">
                    <div>
                        <div class="text-sm text-red-500 font-black tracking-widest">KILL ALL (Total Outage)</div>
                        <div class="text-[10px] text-red-600/70">毁灭性打击：主备双线全断</div>
                    </div>
                    <el-switch v-model="chaosOptions.killAll" style="--el-switch-on-color: #dc2626; --el-switch-off-color: #334155" />
                </div>
            </div>
            <div class="mt-5 text-[10px] text-slate-500 text-center font-mono">Press Ctrl+Shift+K to hide</div>
        </div>
    </transition>

    <div class="flex-1 h-full relative overflow-hidden bg-[#020617]">
        
        <button @click="isSidebarOpen = !isSidebarOpen"
                class="absolute top-6 right-6 z-[60] p-2.5 bg-[#0f172a]/80 backdrop-blur-md border border-[#334155] rounded-xl text-slate-300 hover:text-white hover:bg-[#1e293b] hover:border-indigo-500/50 transition-all shadow-lg group">
            <el-icon class="text-xl transition-transform" :class="!isSidebarOpen ? 'rotate-180' : ''">
               <Fold v-if="isSidebarOpen" />
               <Expand v-else />
            </el-icon>
        </button>

        <div v-if="isSystemBooted" 
            class="absolute top-6 right-24 z-[60] flex items-center gap-3 px-4 py-2 bg-[#0f172a]/80 backdrop-blur-md border border-[#334155] rounded-xl text-slate-300 shadow-xl transition-all duration-300">
            
            <div class="flex items-center gap-2 border-r border-[#334155] pr-3">
                <el-icon class="text-indigo-400 text-lg"><Sunny /></el-icon>
                <span class="font-mono font-bold text-sm">{{ weatherData.temp }}°C</span>
            </div>

            <div class="flex items-center gap-2 border-r border-[#334155] pr-3">
                <span class="text-xs font-bold text-slate-400">{{ weatherData.condition }}</span>
            </div>

            <div class="flex flex-col gap-0.5 text-[10px] text-slate-400 leading-none">
                <div class="flex items-center gap-1">
                    <span class="opacity-70">湿:</span>
                    <span class="font-mono">{{ weatherData.humidity }}</span>
                </div>
                <div class="flex items-center gap-1">
                    <span class="opacity-70">风:</span>
                    <span class="font-mono">{{ weatherData.windSpeed }}</span>
                </div>
            </div>
        </div>

        <div class="w-full h-full transition-all duration-700"
             :class="{
                'grayscale contrast-125 opacity-60 crt-scanlines-light': systemState !== 'LIVE'
             }">
            <SpatialCanvas :data="campusData" />
        </div>

        <div v-if="systemState === 'SWITCHING'" 
             class="absolute inset-0 z-40 flex flex-col items-center justify-center bg-red-900/20 backdrop-blur-[4px] transition-all">
             <div class="text-red-500 font-black text-6xl md:text-7xl tracking-[0.3em] animate-pulse drop-shadow-xl">
                 SYSTEM OFFLINE
             </div>
             <div class="text-red-400 mt-6 font-mono text-xl md:text-2xl animate-bounce tracking-widest flex items-center gap-3">
                 <el-icon class="is-loading"><Loading /></el-icon>
                 REROUTING TO BACKUP NODE...
             </div>
        </div>

        <div v-if="systemState === 'SWITCHING'" 
             class="absolute bottom-6 left-6 z-50 bg-[#0f172a]/90 border border-[#334155] p-4 rounded-xl shadow-2xl font-mono text-sm w-[420px] overflow-hidden flex flex-col backdrop-blur-md">
            <div class="text-indigo-400 mb-3 border-b border-[#334155] pb-2 text-xs font-bold tracking-widest flex justify-between">
                <span>TERMINAL // SYS_OVERRIDE</span>
                <span class="text-slate-500 animate-pulse">REC ●</span>
            </div>
            <div class="flex flex-col gap-1.5 h-40 justify-end overflow-hidden text-xs">
                <div v-for="(log, idx) in terminalLogs" :key="idx"
                     class="animate-fade-in-up flex gap-2"
                     :class="{'text-red-400': log.includes('[WARN]') || log.includes('[FATAL]'), 
                              'text-emerald-400': log.includes('[OK]'), 
                              'text-slate-400': log.includes('[INFO]'), 
                              'text-indigo-400 font-bold': log.includes('[SYS]')}">
                    <span class="opacity-50 text-slate-500">></span> {{ log }}
                </div>
                <div class="text-indigo-500 animate-pulse mt-1">> _</div>
            </div>
        </div>

        <div v-if="mttrTime" 
             class="absolute top-8 left-1/2 -translate-x-1/2 z-50 px-8 py-5 bg-[#0f172a]/95 backdrop-blur-xl border border-emerald-900/50 rounded-2xl shadow-2xl flex items-center gap-6 cursor-pointer hover:scale-105 transition-transform animate-slide-down"
             @click="mttrTime = null">
            <div class="p-4 bg-emerald-900/30 rounded-full border border-emerald-800/50">
                <el-icon class="text-emerald-400 text-4xl animate-pulse"><Timer /></el-icon>
            </div>
            <div>
                <div class="text-emerald-400 text-sm font-bold tracking-widest mb-1 flex items-center gap-2">
                    <span class="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-ping"></span>
                    系统高可用容灾接管成功 (MTTR)
                </div>
                <div class="text-white font-mono font-black text-6xl tracking-tight">
                    {{ mttrTime }} <span class="text-2xl font-medium text-emerald-500">ms</span>
                </div>
            </div>
        </div>
    </div>

    <!-- <div v-if="isSystemBooted" class="absolute top-6 right-24 z-50 flex items-center gap-3 px-4 py-2 bg-[#0f172a]/80 backdrop-blur-md border border-[#334155] rounded-xl text-slate-300 shadow-xl">
    <div class="flex items-center gap-2 border-r border-[#334155] pr-3">
        <el-icon class="text-indigo-400 text-lg"><Sunny /></el-icon>
        <span class="font-mono font-bold text-sm">{{ weatherData.temp || '24' }}°C</span>
    </div>
    <div class="flex items-center gap-2">
        <span class="text-xs font-bold text-slate-400">{{ weatherData.condition || '晴' }}</span>
        <span class="text-[10px] text-slate-500">湿度: {{ weatherData.humidity || '45%' }}</span>
    </div>
    </div> -->
    
    <aside 
        class="h-full bg-[#0f172a]/80 backdrop-blur-xl border-l border-[#1e293b] flex flex-col z-10 shrink-0 shadow-[-10px_0_30px_rgba(0,0,0,0.5)] transition-all duration-500 ease-in-out overflow-hidden"
        :class="isSidebarOpen ? 'w-80 p-6 opacity-100' : 'w-0 p-0 opacity-0 border-none'"
    >
        <div class="w-[270px]" v-show="isSidebarOpen">
            <div class="flex items-center justify-between mb-6 pb-4 border-b border-[#334155]">
                <div class="flex items-center gap-3">
                    <div class="p-2 bg-indigo-900/30 text-indigo-400 rounded-xl border border-indigo-800/50 shadow-[0_0_15px_rgba(79,70,229,0.2)]">
                        <el-icon class="text-2xl"><OfficeBuilding /></el-icon>
                    </div>
                    <div class="flex items-center gap-2">
                        <h2 class="text-xl font-black text-white tracking-tight">
                            {{ campusName || '智慧孪生中枢' }}
                        </h2>
                    </div>
                </div>
            </div>
            
            <div class="p-4 bg-[#1e293b]/50 border border-[#334155] rounded-xl mb-6 flex items-center justify-between transition-all" :class="{'ring-1 ring-orange-500/50 bg-orange-900/10 border-orange-500/30': isHeatmapActive}">
                <div class="flex items-center gap-2">
                    <el-icon :class="isHeatmapActive ? 'text-orange-400' : 'text-slate-500'" class="text-xl transition-colors"><MagicStick /></el-icon>
                    <span :class="isHeatmapActive ? 'text-orange-400' : 'text-slate-300'" class="font-bold text-sm transition-colors">空间能效热力场</span>
                </div>
                <el-switch v-model="isHeatmapActive" style="--el-switch-on-color: #f97316; --el-switch-off-color: #334155"/>
            </div>

            <div class="flex items-center justify-between mb-2">
                <span class="text-xs text-slate-500 font-bold tracking-wider">NETWORK NODE</span>
                <div class="flex items-center gap-2">
                    <span class="text-xs text-indigo-400 font-mono font-bold">{{ API_NODES[currentNodeIndex].id }}</span>
                    <div class="flex items-center gap-1 bg-[#1e293b] px-2 py-1 rounded border" :class="getPingColor(currentPing)">
                        <span class="w-1.5 h-1.5 rounded-full" :class="getPingBg(currentPing) + ' animate-pulse'"></span>
                        <span class="text-[10px] font-mono font-bold">{{ currentPing }}</span>
                    </div>
                </div>
            </div>

            <div class="flex items-center justify-between mb-4">
                 <span class="text-xs text-slate-500 font-bold tracking-wider">SYSTEM STATUS</span>
                 <el-tag 
                    :type="systemState === 'OFFLINE' ? 'danger' : (systemState === 'SWITCHING' ? 'warning' : 'success')" 
                    effect="dark" size="small" class="font-bold transition-all border-none"
                    :class="{'animate-pulse': systemState !== 'LIVE'}"
                 >
                    {{ systemState === 'OFFLINE' ? 'OFFLINE (快照)' : (systemState === 'SWITCHING' ? 'FAILOVER...' : 'LIVE') }}
                 </el-tag>
            </div>
            
            <p class="text-xs text-slate-500 font-mono mb-4 text-right">{{ lastUpdate || 'TIME FROZEN' }}</p>

            <div v-if="error" class="mb-4 p-3 bg-red-900/20 border border-red-800/50 rounded-lg flex items-start gap-2 animate-fade-in">
                <el-icon class="text-red-400 mt-0.5"><Warning /></el-icon>
                <div class="text-xs text-red-400 leading-relaxed">{{ error }}</div>
            </div>
        </div>

        <div class="flex-grow overflow-y-auto space-y-3 pr-2 custom-scrollbar-dark overflow-x-hidden w-[270px]" v-show="isSidebarOpen">
            <transition name="fade-slide" mode="out-in">
                <div v-if="!selectedBuildingData" key="list">
                    <div class="p-3 mb-3 bg-[#1e293b]/50 border border-[#334155] rounded-lg flex justify-between items-center text-sm">
                       <span class="text-slate-400 font-bold">当前视角</span>
                       <span class="text-white font-black drop-shadow-md">全域总览</span>
                    </div>

                    <div v-for="building in campusData" :key="building.id" @click="setSelectedBuilding(building.id)" class="group relative bg-[#1e293b]/40 hover:bg-[#334155]/60 p-4 rounded-xl border border-[#334155] transition-all duration-300 hover:shadow-[0_0_15px_rgba(0,0,0,0.3)] cursor-pointer overflow-hidden mb-3">
                        <div class="absolute left-0 top-0 bottom-0 w-1 transition-all duration-300 group-hover:w-2" :style="{ backgroundColor: building.color, boxShadow: `0 0 10px ${building.color}` }"></div>
                        <div class="pl-2 flex justify-between items-start">
                            <div>
                                <div class="flex items-center gap-2 mb-1">
                                    <span class="text-sm font-bold text-slate-100">{{ building.name }}</span>
                                    <span class="text-[10px] px-1.5 py-0.5 rounded bg-[#0f172a] border border-[#334155] text-slate-400 font-mono">{{ building.id }}</span>
                                </div>
                                <p class="text-xs text-slate-500">{{ building.type }}</p>
                            </div>
                            <div class="flex flex-col items-end gap-1.5">
                                <span class="text-sm font-bold drop-shadow-md" :style="{ color: building.color }">
                                    {{ building.status }}
                                </span>
                                <div class="flex items-center gap-1 bg-[#0f172a]/80 px-2 py-0.5 rounded border border-[#334155]">
                                    <span class="text-yellow-400 text-[10px]">⚡</span>
                                    <span class="text-xs text-slate-300 font-mono font-bold">{{ building.power || (building.status === '正常' ? '124.5' : '850.2') }} kW</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div v-else key="detail" class="space-y-4">
                    <button @click="setSelectedBuilding(null)" class="w-full py-2.5 mb-2 bg-[#1e293b]/50 hover:bg-[#334155] text-slate-300 hover:text-white font-bold rounded-lg border border-[#334155] transition-colors text-sm shadow-sm">
                      ← 返回全域总览
                    </button>
                    <div class="p-5 bg-[#1e293b]/60 backdrop-blur-md border border-[#334155] border-l-4 rounded-xl shadow-[0_10px_30px_rgba(0,0,0,0.5)]" :style="{ borderLeftColor: selectedBuildingData.color }">
                        <h3 class="text-lg font-black text-white mb-3">{{ selectedBuildingData.name }}</h3>
                        <div class="flex items-center gap-2 mb-5 text-sm">
                            <span class="text-slate-400 font-bold">运行状态:</span>
                            <span class="font-black px-2 py-1 rounded bg-[#0f172a] border border-[#334155]" :style="{ color: selectedBuildingData.color, textShadow: `0 0 8px ${selectedBuildingData.color}80` }">{{ selectedBuildingData.status }}</span>
                        </div>
                        <div class="grid grid-cols-2 gap-3 mt-4">
                            <div class="bg-[#0f172a]/80 p-3 rounded-lg border border-[#334155]">
                                <div class="text-xs text-slate-500 font-bold mb-1">建筑类型</div>
                                <div class="text-sm font-bold text-slate-200">{{ selectedBuildingData.type }}</div>
                            </div>
                            <div class="bg-[#0f172a]/80 p-3 rounded-lg border border-[#334155]">
                                <div class="text-xs text-slate-500 font-bold mb-1">设备连通率</div>
                                <div class="text-sm font-bold text-slate-200 font-mono">{{ selectedBuildingData.status === '正常' ? '100%' : '82%' }}</div>
                            </div>
                        </div>
                    </div>
                </div>
            </transition>
        </div>
    </aside>

  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, onActivated, onDeactivated, computed } from 'vue'
import axios from 'axios'
import { ElMessage, ElNotification } from 'element-plus' 
// 🌟 引入折叠/展开图标
import { OfficeBuilding, MagicStick, Warning, Timer, Loading, Fold, Expand, Sunny, WindPower } from '@element-plus/icons-vue' 
import SpatialCanvas from '../components/SpatialCanvas.vue' 
import { useDigitalTwin } from '../composables/useDigitalTwin'

const { selectedBuildingId, setSelectedBuilding, isHeatmapActive } = useDigitalTwin() 

// 🌟 新增：侧边栏折叠状态控制
const isSidebarOpen = ref(true);

const isSystemBooted = ref(false); 
const campusName = ref('')
const campusData = ref([])
const lastUpdate = ref('')

const isLoading = ref(false) 
const error = ref(null)
const isRealData = ref(false) 

let pollTimer = null
let pingTimer = null
let hasPrompted = false 

let failoverStartTime = 0; 
const mttrTime = ref(null); 
const currentPing = ref('12ms'); 

let abortController = null;

const API_NODES = [
    { id: '主控节点 (Port 8000)', url: '' },           // 走 vite proxy
    { id: '容灾节点 (Port 8001)', url: 'http://127.0.0.1:8001' }
];
const currentNodeIndex = ref(0);
const systemState = ref('LIVE'); 

const showChaosDashboard = ref(false);
const chaosOptions = ref({
    killPrimary: false,
    latency: false,
    killAll: false
});
const handleKeydown = (e) => {
    if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        showChaosDashboard.value = !showChaosDashboard.value;
    }
};

const terminalLogs = ref([]);
let logInterval = null;
const logSequence = [
    "[WARN] Node:8000 Connection timeout (1502ms)",
    "[SYS] TCP Reset received. Target unreachable.",
    "[SYS] Initiating High-Availability Failover Protocol v2.4...",
    "[INFO] DNS BGP Route flushing & Rerouting...",
    "[INFO] Pinging DR-Node:8001... [Timeout]",
    "[INFO] Re-pinging DR-Node:8001... [Success: 84ms]",
    "[SYS] DR-Node Handshake established.",
    "[INFO] Synchronizing encrypted state vectors...",
    "[INFO] Decrypting payload stream...",
    "[OK] Data sync 100% completed. Ready."
];

const startTerminalLogs = () => {
    terminalLogs.value = [];
    if (logInterval) clearInterval(logInterval);
    let i = 0;
    logInterval = setInterval(() => {
        if (i < logSequence.length) {
            terminalLogs.value.push(logSequence[i]);
            if (terminalLogs.value.length > 5) terminalLogs.value.shift();
            i++;
        } else {
            clearInterval(logInterval);
        }
    }, 500);
};

let audioCtx = null;
let sirenInterval = null;

const initAudio = () => {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === 'suspended') audioCtx.resume();
};

// 2. 在 bootSystem 函数附近添加 weatherData 和 fetchWeather
const weatherData = ref({
    temp: '--',
    condition: '获取中',
    humidity: '--',
    windSpeed: '--' // 🌟 新增字段
})

const fetchWeather = async () => {
    try {
        // 模拟数据接口调用
        weatherData.value = {
            temp: '26',
            condition: '晴朗',
            humidity: '45%',
            windSpeed: '3.2 m/s' // 🌟 新增数据
        }
    } catch (e) {
        console.error("天气获取失败", e)
    }
}

const bootSystem = () => {
    initAudio(); 
    isSystemBooted.value = true;
    
    currentNodeIndex.value = 0;
    systemState.value = 'LIVE';
    
    fetchWeather(); // 启动时获取天气数据

    fetchSpatialData();
    pollTimer = setInterval(() => fetchSpatialData(false), 3000); 

    pingTimer = setInterval(() => {
        if (systemState.value === 'SWITCHING') {
            currentPing.value = 'TIMEOUT';
        } else if (systemState.value === 'OFFLINE') {
            currentPing.value = 'ERR';
        } else {
            let basePing = currentNodeIndex.value === 0 ? 12 : 75;
            let variance = currentNodeIndex.value === 0 ? 10 : 35;
            let pingVal = Math.floor(Math.random() * variance + basePing);
            
            if (chaosOptions.value.latency) pingVal += 2000; 
            
            currentPing.value = pingVal + 'ms';
        }
    }, 1500);
};

const startSiren = () => {
    if (sirenInterval) return;
    initAudio();
    const play = () => {
        try {
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.type = 'square';
            osc.frequency.setValueAtTime(400, audioCtx.currentTime);
            osc.frequency.linearRampToValueAtTime(800, audioCtx.currentTime + 0.5);
            gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.5);
            osc.connect(gain);
            gain.connect(audioCtx.destination);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.5);
        } catch(e){}
    };
    play();
    sirenInterval = setInterval(play, 600); 
};

const stopSiren = () => {
    if (sirenInterval) {
        clearInterval(sirenInterval);
        sirenInterval = null;
    }
};

const playSuccessPing = () => {
    try {
        if (!audioCtx) initAudio();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(1200, audioCtx.currentTime);
        gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.5);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.5);
    } catch(e) {}
};

const selectedBuildingData = computed(() => {
    if (!selectedBuildingId.value || !campusData.value.length) return null;
    return campusData.value.find(b => b.id === selectedBuildingId.value);
})

const getPingColor = (val) => {
    if (val === 'ERR' || val === 'TIMEOUT') return 'border-red-900/50 text-red-500 bg-red-900/20';
    if (val.includes('ms')) {
        const num = parseInt(val);
        if (num > 60) return 'border-yellow-900/50 text-yellow-500 bg-yellow-900/20';
        return 'border-emerald-900/50 text-emerald-400 bg-emerald-900/20';
    }
    return 'border-[#334155] text-slate-500';
};
const getPingBg = (val) => {
    if (val === 'ERR' || val === 'TIMEOUT') return 'bg-red-500';
    if (val.includes('ms')) {
        const num = parseInt(val);
        if (num > 60) return 'bg-yellow-500';
        return 'bg-emerald-500';
    }
    return 'bg-slate-500';
};

const fetchSpatialData = async (isRetry = false) => {
    if (isLoading.value && !isRetry) return;

    if (abortController && !isRetry) {
        abortController.abort();
    }
    abortController = new AbortController();

    if (currentNodeIndex.value === 1 && !isRetry) {
        let isPrimaryAlive = false;
        if (!chaosOptions.value.killPrimary && !chaosOptions.value.killAll) {
            try {
                const probeRes = await axios.get(`${API_NODES[0].url}/api/spatial-twin/campus-data`, { timeout: 2000 });
                if (probeRes.data.status === 'success') isPrimaryAlive = true;
            } catch (e) {}
        }
        if (isPrimaryAlive) {
            currentNodeIndex.value = 0;
            systemState.value = 'LIVE';
            error.value = null;
            playSuccessPing(); 
            ElNotification({ 
                title: '🔄 系统平滑回切',
                message: '检测到主服务器已恢复，前端已自动将流量切回主控节点！', 
                type: 'success',
                position: 'bottom-right'
            });
        }
    }

    let targetUrl = API_NODES[currentNodeIndex.value].url;
    
    if (chaosOptions.value.killPrimary && currentNodeIndex.value === 0) {
        targetUrl = 'http://127.0.0.1:9999'; // 混沌工程：模拟主节点不可达
    }

    try {
        isLoading.value = true;
        
        if (chaosOptions.value.latency) {
            await new Promise(r => setTimeout(r, 2000));
        }

        let response;
        
        if (currentNodeIndex.value === 1) {
            if (chaosOptions.value.killAll) {
                throw new Error("KILL ALL OPTION ACTIVE");
            }
            if (systemState.value === 'SWITCHING') {
                await new Promise(resolve => setTimeout(resolve, 5500));
            } else {
                await new Promise(resolve => setTimeout(resolve, 200)); 
            }
            response = {
                data: {
                    status: 'success',
                    campus_name: '智慧孪生中枢 (异地灾备)',
                    is_real_data: false,
                    last_update: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
                    data: campusData.value.map(building => ({
                        ...building,
                        status: '容灾降级运行',
                        color: '#94a3b8' 
                    }))
                }
            };
        } else {
            response = await axios.get(`${targetUrl}/api/spatial-twin/campus-data`, { 
                timeout: 3000, 
                signal: abortController.signal 
            });
        }
        
        if(response.data.status === 'success') {
            
            if (systemState.value === 'SWITCHING') {
                const failoverEndTime = performance.now();
                const mttr = (failoverEndTime - failoverStartTime).toFixed(2);
                mttrTime.value = mttr;
                
                stopSiren(); 
                if(logInterval) clearInterval(logInterval);
                playSuccessPing(); 
                
                ElNotification({ 
                    title: '✅ 故障转移与系统自愈完成',
                    message: `核心网络已在 ${mttr} 毫秒内完成容灾自愈。`, 
                    type: 'success',
                    duration: 8000,
                    position: 'bottom-right'
                });
                failoverStartTime = 0; 
            }
            
            systemState.value = 'LIVE';
            error.value = null;

            campusName.value = response.data.campus_name;
            campusData.value = response.data.data || []; 
            lastUpdate.value = response.data.last_update;
            isRealData.value = response.data.is_real_data; 
            
            if (currentNodeIndex.value === 0) {
                localStorage.setItem('spatial_twin_snapshot', JSON.stringify(campusData.value));
                localStorage.setItem('spatial_twin_last_update', lastUpdate.value);
            }
            
            if (!hasPrompted) {
                if (isRealData.value) {
                    ElMessage.success({ message: '数据库连接成功，已接入真实能耗数据！', duration: 4000 });
                } else {
                    ElMessage.warning({ message: '未检测到真实数据表，已切换为演示数据。', duration: 4000 });
                }
                hasPrompted = true;
            }
        } else {
            throw new Error(response.data.message || '获取数据失败');
        }
    } catch (e) {
        if (axios.isCancel(e)) return; 

        if (currentNodeIndex.value < API_NODES.length - 1 && !chaosOptions.value.killAll) {
            if (failoverStartTime === 0) {
                failoverStartTime = performance.now();
            }
            systemState.value = 'SWITCHING';
            error.value = `主节点异常宕机，正在向容灾节点转移流量...`;
            currentNodeIndex.value++; 
            startSiren(); 
            startTerminalLogs(); 
            
            if (campusData.value.length > 0) {
                campusData.value = campusData.value.map(building => ({
                    ...building,
                    status: '寻址容灾节点...',
                    color: '#475569' 
                }));
            }
            ElMessage.warning({ message: '⚠️ 检测到主服务器(8000)宕机，触发主备切换...', duration: 2000 });
            await fetchSpatialData(true); 
            return; 
        } else {
            systemState.value = 'OFFLINE';
            stopSiren(); 
            if(logInterval) clearInterval(logInterval);
            error.value = "全网通信彻底中断，已降级至本地快照呈现。";

            if (campusData.value.length > 0) {
                campusData.value = campusData.value.map(building => ({
                    ...building,
                    status: '全网瘫痪(本地快照)',
                    color: '#475569' 
                }));
            }
        }
    } finally {
        isLoading.value = false;
    }
}

onMounted(() => {
    const cachedData = localStorage.getItem('spatial_twin_snapshot');
    if (cachedData) {
        if (cachedData.includes('#94a3b8') || cachedData.includes('#64748b')) {
            localStorage.removeItem('spatial_twin_snapshot');
        } else {
            campusData.value = JSON.parse(cachedData);
            lastUpdate.value = localStorage.getItem('spatial_twin_last_update') || '离线历史快照';
        }
    }
    document.querySelector('div[tabindex="0"]')?.focus();
})

// KeepAlive 缓存时暂停定时器，避免后台空转消耗网络与 CPU
function stopAllTimers() {
    if(pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    if(pingTimer) { clearInterval(pingTimer); pingTimer = null; }
    if(logInterval) { clearInterval(logInterval); logInterval = null; }
}

onDeactivated(() => {
    stopAllTimers();
    stopSiren();
    if(audioCtx) { audioCtx.close().catch(() => {}); audioCtx = null; }
})

onActivated(() => {
    // 重新激活时按需重启轮询
    if(isSystemBooted.value) {
        pollTimer = setInterval(() => fetchSpatialData(false), 3000);
        pingTimer = setInterval(() => {
            if (systemState.value === 'SWITCHING') {
                currentPing.value = 'TIMEOUT';
            } else if (systemState.value === 'OFFLINE') {
                currentPing.value = 'ERR';
            } else {
                let basePing = currentNodeIndex.value === 0 ? 12 : 75;
                let variance = currentNodeIndex.value === 0 ? 10 : 35;
                let pingVal = Math.floor(Math.random() * variance + basePing);
                if (chaosOptions.value.latency) pingVal += 2000;
                currentPing.value = pingVal + 'ms';
            }
        }, 1500);
    }
})

onUnmounted(() => {
    stopAllTimers();
    if(abortController) abortController.abort();
    stopSiren();
    if(audioCtx) { audioCtx.close().catch(() => {}); audioCtx = null; }
})
</script>

<style scoped>
/* 🌟 滚动条暗黑模式 */
.custom-scrollbar-dark::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar-dark::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar-dark::-webkit-scrollbar-thumb {
  background: #334155;
  border-radius: 4px;
}
.custom-scrollbar-dark::-webkit-scrollbar-thumb:hover {
  background: #475569;
}

.animate-fade-in { animation: fadeIn 0.3s ease-in-out; }
.animate-fade-in-up { animation: fadeInUp 0.3s ease-out forwards; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(-5px); } to { opacity: 1; transform: translateY(0); } }
@keyframes fadeInUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
.animate-slide-down { animation: slideDown 0.6s cubic-bezier(0.175, 0.885, 0.32, 1.275); }
@keyframes slideDown { from { opacity: 0; transform: translate(-50%, -60px); } to { opacity: 1; transform: translate(-50%, 0); } }

/* 暗黑离线状态下的红色警报扫描线 */
.crt-scanlines-light {
    position: relative;
}
.crt-scanlines-light::after {
    content: " ";
    display: block;
    position: absolute;
    top: 0;
    left: 0;
    bottom: 0;
    right: 0;
    background: linear-gradient(rgba(0, 0, 0, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
    z-index: 20;
    background-size: 100% 2px, 3px 100%;
    pointer-events: none;
}

.fade-slide-enter-active, .fade-slide-leave-active { transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
.fade-slide-enter-from { opacity: 0; transform: translateX(30px); }
.fade-slide-leave-to { opacity: 0; transform: translateX(-30px); }
.fade-slide-down-enter-active, .fade-slide-down-leave-active { transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275); }
.fade-slide-down-enter-from, .fade-slide-down-leave-to { opacity: 0; transform: translate(-50%, -40px) scale(0.95); }
</style>