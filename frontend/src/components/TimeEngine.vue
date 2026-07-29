<template>
  <div class="time-engine-panel">
    <!-- 顶部模式切换 -->
    <div class="engine-header">
      <div class="mode-tabs">
        <button
          v-for="m in MODES"
          :key="m.key"
          :class="['mode-btn', { active: mode === m.key }]"
          @click="setMode(m.key)"
        >
          <span class="mode-icon">{{ m.icon }}</span>
          <span>{{ m.label }}</span>
        </button>
      </div>
      <div class="current-ts">
        <span class="ts-label">当前时刻</span>
        <span class="ts-value">{{ formattedTimestamp }}</span>
      </div>
    </div>

    <!-- 主时间轴 -->
    <div class="timeline-track" ref="trackRef">
      <!-- 区间刻度 -->
      <div class="timeline-ticks">
        <div
          v-for="tick in ticks"
          :key="tick.value"
          class="tick"
          :style="{ left: tick.pct + '%' }"
        >
          <span class="tick-label">{{ tick.label }}</span>
        </div>
      </div>

      <!-- 可拖拽游标 -->
      <div
        class="timeline-cursor"
        :style="{ left: cursorPct + '%' }"
        @pointerdown="onPointerDown"
      >
        <div class="cursor-handle"></div>
      </div>

      <!-- 故障事件锚点 -->
      <div
        v-for="event in eventsInRange"
        :key="event.id"
        class="event-marker"
        :class="{ critical: event.severity === 'critical' }"
        :style="{ left: eventPct(event) + '%' }"
        :title="event.title"
        @click="$emit('event-click', event)"
      ></div>
    </div>

    <!-- 底部控制 -->
    <div class="engine-footer">
      <button class="ctrl-btn" @click="togglePlay" :title="isPlaying ? '暂停' : '播放'">
        {{ isPlaying ? '⏸' : '▶' }}
      </button>
      <button class="ctrl-btn" @click="stepBackward" title="后退">⏮</button>
      <button class="ctrl-btn" @click="stepForward" title="前进">⏭</button>

      <div class="speed-control">
        <span class="speed-label">倍速</span>
        <select v-model="playbackSpeed" class="speed-select">
          <option v-for="s in SPEEDS" :key="s" :value="s">{{ s }}x</option>
        </select>
      </div>

      <div class="range-info">
        <span>{{ formatTs(rangeStart) }}</span>
        <span class="sep">→</span>
        <span>{{ formatTs(rangeEnd) }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  // v-model: 当前时间戳（毫秒）
  modelValue: { type: Number, default: Date.now() },
  // 时间轴区间
  rangeStart: { type: Number, default: () => Date.now() - 7 * 24 * 3600 * 1000 },
  rangeEnd: { type: Number, default: () => Date.now() + 7 * 24 * 3600 * 1000 },
  // 故障/告警事件锚点 [{id, ts, title, severity}]
  events: { type: Array, default: () => [] },
  autoPlay: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue', 'mode-change', 'event-click'])

const MODES = [
  { key: 'history', label: '历史回溯', icon: '⏪' },
  { key: 'live', label: '实时直播', icon: '📡' },
  { key: 'forecast', label: '未来推演', icon: '🔮' }
]
const SPEEDS = [0.5, 1, 2, 4, 8, 16]

const mode = ref('live')
const isPlaying = ref(props.autoPlay)
const playbackSpeed = ref(1)
const trackRef = ref(null)

// currentTimestamp 是单一事实源，驱动 3D 场景
const currentTimestamp = ref(props.modelValue)

// 同步外部 v-model
watch(() => props.modelValue, (v) => {
  if (v !== currentTimestamp.value) currentTimestamp.value = v
})
watch(currentTimestamp, (v) => emit('update:modelValue', v))

const formattedTimestamp = computed(() => formatTs(currentTimestamp.value))
const cursorPct = computed(() => tsToPct(currentTimestamp.value))

const eventsInRange = computed(() =>
  props.events.filter(e => e.ts >= props.rangeStart && e.ts <= props.rangeEnd)
)

const ticks = computed(() => {
  const span = props.rangeEnd - props.rangeStart
  const n = 7
  const arr = []
  for (let i = 0; i <= n; i++) {
    const ts = props.rangeStart + (span * i) / n
    arr.push({ value: ts, pct: (i / n) * 100, label: formatTs(ts) })
  }
  return arr
})

function tsToPct(ts) {
  const span = props.rangeEnd - props.rangeStart
  if (span <= 0) return 0
  return Math.max(0, Math.min(100, ((ts - props.rangeStart) / span) * 100))
}
function eventPct(e) { return tsToPct(e.ts) }

function formatTs(ts) {
  const d = new Date(ts)
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function setMode(m) {
  mode.value = m
  emit('mode-change', m)
  // 模式切换时定位游标
  if (m === 'history') {
    currentTimestamp.value = props.rangeStart + (props.rangeEnd - props.rangeStart) * 0.2
  } else if (m === 'live') {
    currentTimestamp.value = Date.now()
  } else if (m === 'forecast') {
    currentTimestamp.value = props.rangeStart + (props.rangeEnd - props.rangeStart) * 0.8
  }
}

// 拖拽游标
let dragging = false
function onPointerDown(e) {
  dragging = true
  e.target.setPointerCapture(e.pointerId)
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', onPointerUp)
}
function onPointerMove(e) {
  if (!dragging || !trackRef.value) return
  const rect = trackRef.value.getBoundingClientRect()
  const pct = Math.max(0, Math.min(100, ((e.clientX - rect.left) / rect.width) * 100))
  const span = props.rangeEnd - props.rangeStart
  currentTimestamp.value = props.rangeStart + (span * pct) / 100
}
function onPointerUp() {
  dragging = false
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
}

// 播放循环（rAF 驱动，倍速可控）
let rafId = null
let lastFrameTs = 0
function playLoop(now) {
  if (!isPlaying.value) return
  if (!lastFrameTs) lastFrameTs = now
  const deltaMs = (now - lastFrameTs) * playbackSpeed.value
  lastFrameTs = now
  let next = currentTimestamp.value + deltaMs
  if (next >= props.rangeEnd) {
    next = props.rangeEnd
    isPlaying.value = false
  }
  currentTimestamp.value = next
  rafId = requestAnimationFrame(playLoop)
}
function togglePlay() {
  isPlaying.value = !isPlaying.value
  if (isPlaying.value) {
    lastFrameTs = 0
    rafId = requestAnimationFrame(playLoop)
  } else if (rafId) {
    cancelAnimationFrame(rafId)
    rafId = null
  }
}
function stepForward() {
  const span = props.rangeEnd - props.rangeStart
  currentTimestamp.value = Math.min(props.rangeEnd, currentTimestamp.value + span * 0.01)
}
function stepBackward() {
  const span = props.rangeEnd - props.rangeStart
  currentTimestamp.value = Math.max(props.rangeStart, currentTimestamp.value - span * 0.01)
}

watch(isPlaying, (v) => {
  if (v && !rafId) {
    lastFrameTs = 0
    rafId = requestAnimationFrame(playLoop)
  } else if (!v && rafId) {
    cancelAnimationFrame(rafId)
    rafId = null
  }
})

onMounted(() => {
  if (props.autoPlay) {
    isPlaying.value = true
    rafId = requestAnimationFrame(playLoop)
  }
})
onBeforeUnmount(() => {
  if (rafId) cancelAnimationFrame(rafId)
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
})
</script>

<style scoped>
.time-engine-panel {
  background: rgba(15, 23, 42, 0.92);
  backdrop-filter: blur(12px);
  border-top: 1px solid rgba(51, 65, 85, 0.6);
  padding: 12px 20px 14px;
  color: #e2e8f0;
  font-family: ui-monospace, monospace;
  user-select: none;
}
.engine-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.mode-tabs { display: flex; gap: 6px; }
.mode-btn {
  display: flex; align-items: center; gap: 4px;
  padding: 4px 12px; border-radius: 6px;
  background: rgba(51, 65, 85, 0.4); border: 1px solid transparent;
  color: #94a3b8; cursor: pointer; font-size: 12px; transition: all .2s;
}
.mode-btn:hover { color: #e2e8f0; background: rgba(51, 65, 85, 0.7); }
.mode-btn.active { color: #38bdf8; border-color: rgba(56, 189, 248, 0.6); background: rgba(56, 189, 248, 0.1); }
.mode-icon { font-size: 14px; }
.current-ts { display: flex; align-items: baseline; gap: 8px; }
.ts-label { font-size: 11px; color: #64748b; }
.ts-value { font-size: 14px; color: #38bdf8; font-weight: 600; letter-spacing: 0.5px; }

.timeline-track {
  position: relative; height: 36px; margin: 6px 8px 10px;
  background: linear-gradient(90deg, rgba(56, 189, 248, 0.05), rgba(239, 68, 68, 0.05));
  border-radius: 6px; border: 1px solid rgba(51, 65, 85, 0.5);
}
.timeline-ticks { position: absolute; inset: 0; }
.tick { position: absolute; top: 0; bottom: 0; width: 1px; background: rgba(148, 163, 184, 0.2); }
.tick-label { position: absolute; top: 2px; left: 4px; font-size: 9px; color: #64748b; white-space: nowrap; }
.timeline-cursor {
  position: absolute; top: -2px; bottom: -2px; width: 2px;
  background: #38bdf8; box-shadow: 0 0 8px rgba(56, 189, 248, 0.8);
  cursor: ew-resize; z-index: 2;
}
.cursor-handle {
  position: absolute; top: -6px; left: -5px;
  width: 12px; height: 12px; border-radius: 50%;
  background: #38bdf8; border: 2px solid #0f172a;
  box-shadow: 0 0 10px rgba(56, 189, 248, 1);
}
.event-marker {
  position: absolute; top: 50%; width: 8px; height: 8px;
  border-radius: 50%; background: #f59e0b;
  transform: translate(-50%, -50%); cursor: pointer;
  box-shadow: 0 0 6px rgba(245, 158, 11, 0.8);
}
.event-marker.critical { background: #ef4444; box-shadow: 0 0 8px rgba(239, 68, 68, 1); }

.engine-footer { display: flex; align-items: center; gap: 12px; }
.ctrl-btn {
  width: 28px; height: 28px; border-radius: 6px;
  background: rgba(51, 65, 85, 0.5); border: 1px solid rgba(71, 85, 105, 0.6);
  color: #e2e8f0; cursor: pointer; font-size: 14px; transition: all .15s;
}
.ctrl-btn:hover { background: rgba(56, 189, 248, 0.2); border-color: #38bdf8; }
.speed-control { display: flex; align-items: center; gap: 6px; }
.speed-label { font-size: 11px; color: #64748b; }
.speed-select {
  background: rgba(15, 23, 42, 0.8); color: #38bdf8;
  border: 1px solid rgba(56, 189, 248, 0.4); border-radius: 4px;
  padding: 2px 6px; font-size: 12px; font-family: inherit;
}
.range-info { margin-left: auto; font-size: 11px; color: #64748b; display: flex; gap: 6px; }
.range-info .sep { color: #475569; }
</style>
