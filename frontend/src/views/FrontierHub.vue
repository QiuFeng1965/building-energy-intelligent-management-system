<template>
  <div class="flex flex-col gap-4 pb-8 bg-slate-50/60 min-h-screen">

    <!-- 页头 -->
    <div class="bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-500 p-5 rounded-2xl shadow-lg text-white">
      <div class="flex items-center justify-between flex-wrap gap-4">
        <div class="flex items-center gap-4">
          <div class="w-12 h-12 rounded-xl bg-white/20 flex items-center justify-center backdrop-blur">
            <el-icon class="text-3xl"><Cpu /></el-icon>
          </div>
          <div>
            <h2 class="text-2xl font-bold">{{ categoryTitle }}</h2>
            <p class="text-indigo-100 mt-1 text-xs flex items-center gap-2 flex-wrap">
              <span>{{ categorySubtitle }}</span>
              <span class="opacity-50">·</span>
              <span class="inline-flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-emerald-300 animate-pulse"></span> 实时数据库驱动</span>
              <span class="opacity-50">·</span>
              <span>127 台设备 · 1.11M 条记录</span>
            </p>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <el-button type="primary" @click="refreshAll" :loading="refreshing" class="!bg-white/20 !border-white/30 !text-white hover:!bg-white/30">
            <el-icon class="mr-1"><Refresh /></el-icon> 刷新全部
          </el-button>
        </div>
      </div>
      <!-- 分类快速切换 -->
      <div class="mt-3 flex items-center gap-2 flex-wrap">
        <router-link to="/frontier/energy"
          :class="['px-3 py-1 rounded-full text-xs transition-all', category === 'energy' ? 'bg-white text-indigo-600 font-bold' : 'bg-white/15 text-white hover:bg-white/25']">
          ⚡ 能源智能分析
        </router-link>
        <router-link to="/frontier/ai"
          :class="['px-3 py-1 rounded-full text-xs transition-all', category === 'ai' ? 'bg-white text-indigo-600 font-bold' : 'bg-white/15 text-white hover:bg-white/25']">
          🤖 智能体与知识
        </router-link>
        <router-link to="/frontier/ops"
          :class="['px-3 py-1 rounded-full text-xs transition-all', category === 'ops' ? 'bg-white text-indigo-600 font-bold' : 'bg-white/15 text-white hover:bg-white/25']">
          🏢 数字孪生与运维
        </router-link>
      </div>
    </div>

    <!-- 功能切换 Tab（使用可滚动标签栏，避免布局拥挤）-->
    <el-tabs v-model="activeTab" type="border-card" class="!rounded-2xl !shadow-sm frontier-tabs">

      <!-- ========== 分类1-能源智能分析 ========== -->
      <!-- Tab 1: 异常检测 + 根因分析 -->
      <el-tab-pane v-if="category === 'energy'" label="🔍 异常检测 & 根因分析" name="anomaly">
        <div v-loading="anomalyLoading">
          <!-- KPI 卡片 -->
          <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <StatCard label="扫描样本数" :value="anomalyMeta.scanned || 0" color="indigo" />
            <StatCard label="异常事件数" :value="anomalyMeta.anomaly_count || 0" color="rose" />
            <StatCard label="异常率" :value="(anomalyMeta.anomaly_rate || 0) + '%'" color="amber" />
            <StatCard label="模型状态" :value="anomalyMeta.model_status || '-'" color="cyan" />
          </div>

          <!-- 控制栏 -->
          <div class="flex items-center gap-3 mb-4 flex-wrap">
            <el-select v-model="anomalyHours" placeholder="回看时长" style="width: 140px" @change="loadAnomaly">
              <el-option label="近 24 小时" :value="24" />
              <el-option label="近 3 天" :value="72" />
              <el-option label="近 7 天" :value="168" />
            </el-select>
            <DataSourceTag source="real" />
          </div>

          <!-- 异常列表 -->
          <el-empty v-if="!anomalyEvents.length" description="当前时段无异常事件" />
          <el-table v-else :data="anomalyEvents" stripe max-height="560">
            <el-table-column prop="device_name" label="设备名称" min-width="180" />
            <el-table-column prop="building_type" label="建筑类型" width="120" />
            <el-table-column prop="anomaly_score" label="异常分数" width="110" sortable>
              <template #default="{ row }">
                <el-tag :type="row.anomaly_score < -0.15 ? 'danger' : 'warning'" effect="dark" round>
                  {{ row.anomaly_score ?? '-' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="关键指标" min-width="180">
              <template #default="{ row }">
                <div class="text-xs space-y-1">
                  <div v-if="row.key_metrics.cop !== null">COP: <span class="font-bold text-cyan-600">{{ row.key_metrics.cop }}</span></div>
                  <div v-if="row.key_metrics.elec_consumption !== null">功率: <span class="font-bold text-rose-500">{{ row.key_metrics.elec_consumption }} kW</span></div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="根因链 (Top 3)" min-width="280">
              <template #default="{ row }">
                <div class="space-y-1">
                  <div v-for="(cause, idx) in row.root_causes" :key="idx" class="text-xs flex items-center gap-2">
                    <span class="w-5 h-5 rounded-full bg-slate-100 flex items-center justify-center font-bold text-slate-500">{{ idx + 1 }}</span>
                    <span class="font-medium text-slate-700">{{ cause.feature_cn }}</span>
                    <span class="text-slate-400">=</span>
                    <span class="font-mono text-indigo-600">{{ cause.current_value }}</span>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="suggestion" label="处置建议" min-width="240">
              <template #default="{ row }">
                <div class="text-xs text-slate-600 bg-amber-50 p-2 rounded-lg border border-amber-100">{{ row.suggestion }}</div>
              </template>
            </el-table-column>
            <el-table-column prop="monitor_time" label="监测时间" width="160" />
          </el-table>
        </div>
      </el-tab-pane>

      <!-- Tab 2: 碳中和路径推演 -->
      <el-tab-pane v-if="category === 'energy'" label="🌱 碳中和路径推演" name="carbon">
        <div v-loading="carbonLoading">
          <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <StatCard label="总排放量" :value="(carbonSummary.total_emission_t || 0) + ' tCO₂'" color="slate" />
            <StatCard label="Scope 2 间接排放" :value="(carbonSummary.scope2_emission_t || 0) + ' tCO₂'" color="blue" />
            <StatCard label="碳排放强度" :value="(carbonSummary.intensity_kg_per_kwh || 0) + ' kg/kWh'" color="amber" />
            <StatCard label="日配额使用率" :value="(carbonSummary.quota_usage_pct || 0) + '%'" :color="carbonSummary.quota_usage_pct > 100 ? 'rose' : 'emerald'" />
          </div>

          <div class="flex items-center gap-3 mb-4">
            <DataSourceTag source="real" />
            <span class="text-xs text-slate-500">电网因子：{{ carbonSummary.grid_factor || 0.5366 }} tCO₂/MWh（{{ carbonSummary.grid_region || '华东电网' }}）</span>
          </div>

          <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
              <h4 class="font-bold text-slate-700 mb-3">碳排放趋势（按日）</h4>
              <div ref="carbonTrendChartRef" class="w-full h-80"></div>
            </div>
            <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
              <h4 class="font-bold text-slate-700 mb-3">碳中和路径推演（3 场景对比）</h4>
              <div ref="carbonPathwayChartRef" class="w-full h-80"></div>
            </div>
          </div>

          <div class="mt-4 bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <h4 class="font-bold text-slate-700 mb-3">场景对比</h4>
            <el-table :data="carbonPathways" stripe size="small">
              <el-table-column prop="name" label="场景" width="120" />
              <el-table-column prop="description" label="说明" min-width="240" />
              <el-table-column prop="baseline_emission_t" label="基线排放 tCO₂" width="130" />
              <el-table-column prop="peak_year" label="达峰年份" width="100" />
              <el-table-column prop="neutral_year" label="碳中和年" width="100">
                <template #default="{ row }">
                  <span v-if="row.neutral_year" class="text-emerald-600 font-bold">{{ row.neutral_year }}</span>
                  <span v-else class="text-slate-400">未达成</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </el-tab-pane>

      <!-- Tab 3: 虚拟电厂需求响应 -->
      <el-tab-pane v-if="category === 'energy'" label="⚡ 虚拟电厂需求响应" name="vpp">
        <div v-loading="vppLoading">
          <!-- 当前状态 -->
          <div class="bg-gradient-to-br from-slate-900 to-indigo-900 p-6 rounded-2xl text-white mb-4 shadow-lg">
            <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <div>
                <div class="text-xs text-indigo-200 mb-1">当前时段</div>
                <div class="text-lg font-bold">{{ vppStatus.current?.period_name || '-' }}</div>
                <div class="text-xl font-black text-amber-400 mt-1">{{ vppStatus.current?.price || 0 }} <span class="text-sm">元/kWh</span></div>
              </div>
              <div>
                <div class="text-xs text-indigo-200 mb-1">当前负荷</div>
                <div class="text-xl font-bold">{{ vppStatus.current?.current_load || 0 }} <span class="text-sm">kW</span></div>
              </div>
              <div>
                <div class="text-xs text-indigo-200 mb-1">今日电费估算</div>
                <div class="text-xl font-bold text-rose-400">¥ {{ vppStatus.today_cost_estimate || 0 }}</div>
              </div>
              <div>
                <div class="text-xs text-indigo-200 mb-1">调度收益（月）</div>
                <div class="text-xl font-bold text-emerald-400">¥ {{ vppEconomy.potential_benefit?.total_annual || 0 }}</div>
              </div>
            </div>
            <div class="mt-4 bg-white/10 p-3 rounded-lg border border-white/20">
              <span class="text-sm font-medium">💡 智能调度建议：</span>
              <span class="text-sm">{{ vppStatus.current?.action || '-' }}</span>
            </div>
          </div>

          <div class="flex items-center gap-3 mb-4">
            <DataSourceTag source="real" />
            <span class="text-xs text-slate-500">基于近 7 天真实负荷曲线 + 福建省工商业分时电价</span>
          </div>

          <!-- 24h 调度策略 -->
          <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm mb-4">
            <h4 class="font-bold text-slate-700 mb-3">24h 储能调度策略（含 SOC 变化）</h4>
            <div ref="vppDispatchChartRef" class="w-full h-96"></div>
          </div>

          <!-- 经济性 -->
          <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <StatCard label="峰谷套利潜力" :value="'¥ ' + (vppEconomy.potential_benefit?.arbitrage || 0)" color="emerald" subtitle="月度估算" />
            <StatCard label="需求响应补贴" :value="'¥ ' + (vppEconomy.potential_benefit?.demand_response_subsidy || 0)" color="blue" subtitle="月度估算" />
            <StatCard label="年化总收益" :value="'¥ ' + (vppEconomy.potential_benefit?.total_annual || 0)" color="amber" subtitle="含需量管理" />
          </div>
        </div>
      </el-tab-pane>

      <!-- Tab 4: 光储充微电网 -->
      <el-tab-pane v-if="category === 'energy'" label="☀️ 光储充微电网" name="microgrid">
        <div v-loading="microgridLoading">
          <!-- KPI 卡片 -->
          <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <StatCard label="光伏当前功率" :value="(microgridOverview.pv?.current_power_kw || 0) + ' kW'" color="emerald" :subtitle="'装机 ' + (microgridOverview.config?.pv_capacity_kw || 100) + ' kW'" />
            <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
              <div class="text-xs text-slate-400 mb-2">储能 SOC</div>
              <div class="text-2xl font-black text-cyan-600">{{ microgridOverview.battery?.soc_pct || 0 }}%</div>
              <el-progress :percentage="microgridOverview.battery?.soc_pct || 0" :color="'#06b6d4'" :show-text="false" :stroke-width="6" class="mt-2" />
              <div class="text-xs text-slate-400 mt-1">{{ microgridOverview.battery?.action === 'charge' ? '充电中' : microgridOverview.battery?.action === 'discharge' ? '放电中' : '待机' }}</div>
            </div>
            <StatCard label="充电桩占用" :value="(microgridOverview.ev_chargers?.busy || 0) + ' / ' + (microgridOverview.ev_chargers?.total || 0)" color="amber" :subtitle="'总功率 ' + (microgridOverview.ev_chargers?.total_power_kw || 0) + ' kW'" />
            <StatCard label="建筑当前负荷" :value="(microgridOverview.grid?.building_load_kw || 0) + ' kW'" color="rose" :subtitle="'上网 ' + (microgridOverview.grid?.grid_export_kw || 0) + ' kW'" />
          </div>

          <div class="flex items-center gap-3 mb-4">
            <DataSourceTag source="real" />
            <span class="text-xs text-slate-500">天气：辐照 {{ microgridOverview.pv?.weather?.radiation_w_m2 || 0 }} W/m² · 温度 {{ microgridOverview.pv?.weather?.temp_c || 25 }}℃ · 云量 {{ microgridOverview.pv?.weather?.cloud_pct || 0 }}%</span>
          </div>

          <!-- 光伏预测曲线 -->
          <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm mb-4">
            <h4 class="font-bold text-slate-700 mb-3">光伏发电预测曲线（24h）</h4>
            <div ref="pvForecastChartRef" class="w-full h-96"></div>
          </div>

          <!-- 充电桩详情 -->
          <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm mb-4">
            <h4 class="font-bold text-slate-700 mb-3">充电桩实时状态</h4>
            <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
              <div v-for="c in (microgridOverview.ev_chargers?.chargers || [])" :key="c.id"
                   class="p-3 rounded-lg border" :class="c.status === 'charging' ? 'bg-emerald-50 border-emerald-200' : 'bg-slate-50 border-slate-200'">
                <div class="text-xs font-bold text-slate-700">{{ c.name }}</div>
                <div class="text-xs mt-1" :class="c.status === 'charging' ? 'text-emerald-600' : 'text-slate-400'">
                  {{ c.status === 'charging' ? '充电中 ' + c.power_kw + ' kW' : '空闲' }}
                </div>
              </div>
            </div>
          </div>

          <!-- 微电网调度建议 -->
          <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <h4 class="font-bold text-slate-700 mb-3">微电网调度建议（24h）</h4>
            <el-table :data="microgridScheduleData" stripe size="small" max-height="360">
              <el-table-column prop="hour" label="时段" width="80">
                <template #default="{ row }">{{ row.hour }}:00</template>
              </el-table-column>
              <el-table-column prop="action" label="调度动作" min-width="140" />
              <el-table-column prop="reason" label="决策依据" min-width="240" />
              <el-table-column prop="expected_power_kw" label="预期功率 kW" width="120" />
            </el-table>
          </div>
        </div>
      </el-tab-pane>

      <!-- ========== 分类2-智能体与知识 ========== -->
      <!-- Tab 5: 多智能体协作 -->
      <el-tab-pane v-if="category === 'ai'" label="🤖 多智能体协作" name="agents">
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
          <div class="lg:col-span-2 bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <h4 class="font-bold text-slate-700 mb-3">智能体工作流（DAG 编排）</h4>
            <div class="flex items-center gap-2 flex-wrap">
              <div v-for="(agent, idx) in agentsList" :key="agent.id" class="flex items-center gap-2">
                <div :class="['p-3 rounded-xl border-2 transition-all', agent.active ? 'bg-indigo-50 border-indigo-400 shadow-md' : 'bg-slate-50 border-slate-200']">
                  <div class="text-2xl">{{ agent.icon }}</div>
                  <div class="text-xs font-bold text-slate-700 mt-1">{{ agent.name }}</div>
                </div>
                <el-icon v-if="idx < agentsList.length - 1" class="text-slate-300 text-xl"><ArrowRight /></el-icon>
              </div>
            </div>
            <div class="mt-4">
              <el-input v-model="agentTask" placeholder="输入任务，如：诊断并处理近期异常设备">
                <template #append>
                  <el-button type="primary" @click="runWorkflow" :loading="workflowRunning">
                    <el-icon class="mr-1"><VideoPlay /></el-icon> 执行工作流
                  </el-button>
                </template>
              </el-input>
            </div>
          </div>
          <div class="bg-slate-900 p-4 rounded-xl border border-slate-700 text-white">
            <h4 class="font-bold mb-3 flex items-center gap-2">
              <el-icon class="text-emerald-400"><Monitor /></el-icon> 执行日志
            </h4>
            <div class="space-y-2 max-h-64 overflow-auto">
              <div v-for="(log, idx) in workflowLogs" :key="idx" class="text-xs">
                <span class="text-emerald-400 font-mono">[{{ log.time }}]</span>
                <span :class="log.type === 'start' ? 'text-blue-300' : log.type === 'complete' ? 'text-emerald-300' : 'text-slate-300'"> {{ log.message }}</span>
              </div>
              <div v-if="workflowLogs.length === 0" class="text-slate-500 text-xs">等待执行...</div>
            </div>
          </div>
        </div>

        <div class="space-y-3">
          <div v-for="(result, idx) in workflowResults" :key="idx" class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <div class="flex items-center gap-2 mb-2">
              <span class="text-2xl">{{ result.icon }}</span>
              <span class="font-bold text-slate-700">{{ result.agent_name }}</span>
              <el-tag type="success" size="small" effect="plain">完成</el-tag>
            </div>
            <div class="text-sm text-slate-600 bg-slate-50 p-3 rounded-lg whitespace-pre-wrap max-h-60 overflow-auto">{{ result.output }}</div>
          </div>
        </div>
      </el-tab-pane>

      <!-- Tab 6: 知识图谱 -->
      <el-tab-pane v-if="category === 'ai'" label="🧠 知识图谱" name="knowledge">
        <div v-loading="knowledgeLoading" class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div class="flex items-center justify-between mb-4 flex-wrap gap-2">
            <h4 class="font-bold text-slate-700">设备-故障-部件-维保 关系图谱</h4>
            <div class="flex items-center gap-2">
              <DataSourceTag source="real" />
              <el-select v-model="knowledgeFilter" placeholder="节点类型" style="width: 140px" @change="loadKnowledge">
                <el-option label="全部" value="" />
                <el-option label="设备" value="device" />
                <el-option label="故障" value="fault" />
                <el-option label="部件" value="part" />
                <el-option label="维保动作" value="action" />
              </el-select>
            </div>
          </div>
          <div class="mb-3 flex gap-2 flex-wrap">
            <el-tag v-for="t in knowledgeStats.types" :key="t" type="info" size="small">{{ typeLabelMap[t] || t }}</el-tag>
            <el-tag type="success" size="small">节点 {{ knowledgeStats.node_count }}</el-tag>
            <el-tag type="warning" size="small">边 {{ knowledgeStats.edge_count }}</el-tag>
          </div>
          <div ref="knowledgeGraphRef" class="w-full h-[500px] bg-slate-50 rounded-xl border border-slate-100"></div>
        </div>
      </el-tab-pane>

      <!-- ========== 分类3-数字孪生与运维 ========== -->
      <!-- Tab 7: 3D 实时数字孪生 -->
      <el-tab-pane v-if="category === 'ops'" label="🏢 3D 实时数字孪生" name="twin3d">
        <div v-loading="twinLoading">
          <!-- 统计卡片 -->
          <div class="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-4">
            <StatCard label="设备总数" :value="twinStats.total_devices || 0" color="indigo" />
            <StatCard label="在线设备" :value="twinStats.online || 0" color="emerald" />
            <StatCard label="正常" :value="twinStats.normal || 0" color="emerald" />
            <StatCard label="告警" :value="(twinStats.warning || 0) + (twinStats.abnormal || 0)" color="amber" />
            <StatCard label="实时告警" :value="twinStats.total_alerts || 0" color="rose" />
          </div>

          <div class="flex items-center gap-3 mb-4">
            <DataSourceTag source="real" />
            <span class="text-xs text-slate-500">校园 → 建筑 → 空间（机房/场景） → 设备 四级层级钻取</span>
          </div>

          <!-- 层级钻取：校园概览 -->
          <div v-if="twinHierarchy" class="bg-gradient-to-r from-indigo-50 to-blue-50 p-4 rounded-xl border border-indigo-200 mb-4">
            <div class="flex items-center gap-3 flex-wrap">
              <el-icon class="text-2xl text-indigo-600"><Cpu /></el-icon>
              <div>
                <div class="font-bold text-indigo-700">{{ twinHierarchy.campus_name }}</div>
                <div class="text-xs text-slate-500">
                  {{ twinHierarchy.total_buildings }} 栋建筑 · {{ twinHierarchy.total_spaces }} 个空间 · {{ twinHierarchy.total_devices }} 台设备 · {{ twinHierarchy.location }}
                </div>
              </div>
            </div>
          </div>

          <!-- 左右布局：左侧建筑+空间树，右侧设备详情 -->
          <div class="grid grid-cols-1 lg:grid-cols-12 gap-4 mb-4">
            <!-- 左侧：建筑→空间树 -->
            <div class="lg:col-span-5 bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
              <h4 class="font-bold text-slate-700 mb-3">建筑 / 空间导航</h4>
              <el-empty v-if="!twinHierarchy?.buildings?.length" description="暂无层级数据" :image-size="60" />
              <el-collapse v-else v-model="expandedBuildings" accordion>
                <el-collapse-item
                  v-for="bld in twinHierarchy.buildings"
                  :key="bld.building_id"
                  :name="bld.building_id"
                >
                  <template #title>
                    <div class="flex items-center justify-between w-full pr-3" @click="selectedBuildingId = bld.building_id">
                      <div class="flex items-center gap-2">
                        <span class="text-base">🏢</span>
                        <span class="font-medium text-slate-700">{{ bld.building_name }}</span>
                        <el-tag size="small" type="info">{{ bld.building_type }}</el-tag>
                      </div>
                      <div class="flex items-center gap-2 text-xs text-slate-400">
                        <span>{{ bld.device_count }} 设备</span>
                        <span>·</span>
                        <span>{{ bld.total_power_kw }} kW</span>
                        <el-tag v-if="bld.status_distribution.abnormal > 0" size="small" type="danger">{{ bld.status_distribution.abnormal }}异常</el-tag>
                      </div>
                    </div>
                  </template>

                  <!-- 建筑概览 -->
                  <div class="grid grid-cols-3 gap-2 mb-3 p-2 bg-slate-50 rounded-lg text-xs">
                    <div class="text-center">
                      <div class="text-slate-400">面积</div>
                      <div class="font-bold text-slate-700">{{ bld.total_area_m2 }} ㎡</div>
                    </div>
                    <div class="text-center">
                      <div class="text-slate-400">空间数</div>
                      <div class="font-bold text-slate-700">{{ bld.space_count }}</div>
                    </div>
                    <div class="text-center">
                      <div class="text-slate-400">功率密度</div>
                      <div class="font-bold text-slate-700">{{ bld.avg_power_density_w_m2 }} W/㎡</div>
                    </div>
                  </div>

                  <!-- 空间列表 -->
                  <div class="space-y-2">
                    <div
                      v-for="sp in bld.spaces"
                      :key="sp.space_id"
                      @click="selectedSpaceId = sp.space_id; selectedBuildingId = bld.building_id"
                      :class="['p-3 rounded-lg border cursor-pointer transition-all', selectedSpaceId === sp.space_id ? 'border-indigo-400 bg-indigo-50 shadow-sm' : 'border-slate-200 hover:border-indigo-200 hover:bg-slate-50']"
                    >
                      <div class="flex items-center justify-between mb-1">
                        <div class="flex items-center gap-2">
                          <span class="text-sm">📍</span>
                          <span class="font-medium text-sm text-slate-700">{{ sp.space_name }}</span>
                          <el-tag size="small" :type="sp.orientation === 'CORE' ? 'warning' : 'info'">{{ sp.orientation }}</el-tag>
                        </div>
                        <span class="text-xs text-slate-400">{{ sp.device_count }} 设备</span>
                      </div>
                      <div class="flex items-center gap-3 text-xs text-slate-500">
                        <span>{{ sp.area_m2 }} ㎡</span>
                        <span>·</span>
                        <span>{{ sp.total_power_kw }} kW</span>
                        <span>·</span>
                        <span>{{ sp.power_density_w_m2 }} W/㎡</span>
                        <span v-if="sp.status_distribution.abnormal > 0" class="text-rose-500">⚠ {{ sp.status_distribution.abnormal }}异常</span>
                      </div>
                    </div>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </div>

            <!-- 右侧：空间设备详情 -->
            <div class="lg:col-span-7 bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
              <div v-if="!selectedSpace">
                <el-empty description="请从左侧选择空间查看设备详情" :image-size="80" />
              </div>
              <template v-else>
                <!-- 空间信息头 -->
                <div class="flex items-center justify-between mb-3 pb-3 border-b border-slate-100">
                  <div>
                    <h4 class="font-bold text-slate-700">{{ selectedSpace.space_name }}</h4>
                    <div class="text-xs text-slate-500 mt-1">
                      朝向 {{ selectedSpace.orientation }} · 面积 {{ selectedSpace.area_m2 }}㎡ · 层高 {{ selectedSpace.clear_height_m }}m · 最大容纳 {{ selectedSpace.max_occupancy }} 人 · 窗墙比 {{ selectedSpace.window_wall_ratio }}
                    </div>
                  </div>
                  <el-tag type="success">{{ selectedSpace.device_count }} 台设备</el-tag>
                </div>

                <!-- 空间统计 -->
                <div class="grid grid-cols-4 gap-2 mb-3">
                  <div class="p-2 bg-emerald-50 rounded-lg text-center">
                    <div class="text-xs text-slate-400">正常</div>
                    <div class="font-bold text-emerald-600">{{ selectedSpace.status_distribution.normal }}</div>
                  </div>
                  <div class="p-2 bg-amber-50 rounded-lg text-center">
                    <div class="text-xs text-slate-400">警告</div>
                    <div class="font-bold text-amber-600">{{ selectedSpace.status_distribution.warning }}</div>
                  </div>
                  <div class="p-2 bg-rose-50 rounded-lg text-center">
                    <div class="text-xs text-slate-400">异常</div>
                    <div class="font-bold text-rose-500">{{ selectedSpace.status_distribution.abnormal }}</div>
                  </div>
                  <div class="p-2 bg-slate-50 rounded-lg text-center">
                    <div class="text-xs text-slate-400">离线</div>
                    <div class="font-bold text-slate-500">{{ selectedSpace.status_distribution.offline }}</div>
                  </div>
                </div>

                <!-- 设备列表 -->
                <el-table :data="selectedSpace.devices" stripe size="small" max-height="360">
                  <el-table-column prop="device_name" label="设备名称" min-width="160" />
                  <el-table-column prop="device_type" label="类型" width="110" />
                  <el-table-column label="状态" width="90">
                    <template #default="{ row }">
                      <el-tag :type="row.status === 'NORMAL' ? 'success' : row.status === 'OFFLINE' ? 'info' : 'danger'" size="small">{{ row.status }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="功率 kW" width="90">
                    <template #default="{ row }">{{ row.realtime?.power_kw ?? '-' }}</template>
                  </el-table-column>
                  <el-table-column label="COP" width="70">
                    <template #default="{ row }">{{ row.realtime?.cop ?? '-' }}</template>
                  </el-table-column>
                  <el-table-column label="供水温度" width="90">
                    <template #default="{ row }">{{ row.realtime?.supply_temp != null ? row.realtime.supply_temp + '℃' : '-' }}</template>
                  </el-table-column>
                  <el-table-column label="额定功率" width="90">
                    <template #default="{ row }">{{ row.rated_power ? row.rated_power + ' kW' : '-' }}</template>
                  </el-table-column>
                </el-table>
              </template>
            </div>
          </div>

          <!-- 实时告警列表 -->
          <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <h4 class="font-bold text-slate-700 mb-3">实时告警列表</h4>
            <el-empty v-if="!twinAlerts.length" description="当前无告警" />
            <el-table v-else :data="twinAlerts" stripe size="small" max-height="300">
              <el-table-column prop="alert_id" label="告警 ID" width="120" />
              <el-table-column prop="device_id" label="设备 ID" width="200" />
              <el-table-column prop="device_name" label="设备名称" min-width="160" />
              <el-table-column prop="level" label="级别" width="100">
                <template #default="{ row }">
                  <el-tag :type="row.level === 'critical' ? 'danger' : 'warning'" size="small">{{ row.level }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="message" label="告警信息" min-width="240" />
              <el-table-column prop="timestamp" label="时间" width="180" />
            </el-table>
          </div>
        </div>
      </el-tab-pane>

      <!-- Tab 8: AR 远程运维 -->
      <el-tab-pane v-if="category === 'ops'" label="📱 AR 远程运维" name="ar">
        <div v-loading="arLoading">
          <!-- 设备选择 -->
          <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm mb-4">
            <div class="flex items-center gap-3 flex-wrap">
              <span class="text-sm font-medium text-slate-600">选择设备：</span>
              <el-select v-model="arDeviceId" placeholder="请选择设备" filterable style="width: 360px" @change="loadAr">
                <el-option
                  v-for="d in arDeviceOptions"
                  :key="d.device_id"
                  :label="d.label"
                  :value="d.device_id"
                />
              </el-select>
              <el-button type="primary" @click="loadAr">
                <el-icon class="mr-1"><Refresh /></el-icon> 重新加载
              </el-button>
              <DataSourceTag source="real" />
            </div>
          </div>

          <el-empty v-if="!arDeviceId" description="请选择设备查看 AR 叠加层数据" />

          <template v-else>
            <!-- 设备基础信息 -->
            <div class="grid grid-cols-1 lg:grid-cols-4 gap-3 mb-4">
              <StatCard label="设备名称" :value="arDeviceInfo.name || '-'" color="slate" />
              <StatCard label="设备类型" :value="arDeviceInfo.type || '-'" color="indigo" />
              <StatCard label="位置" :value="arDeviceInfo.location || '-'" color="blue" />
              <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
                <div class="text-xs text-slate-400 mb-2">运行状态</div>
                <div class="text-lg font-bold" :class="arDeviceStatus.run_status === 'NORMAL' ? 'text-emerald-600' : 'text-rose-500'">
                  {{ arDeviceStatus.run_status || '-' }}
                </div>
                <div v-if="arDeviceStatus.fault_code" class="text-xs text-rose-500 mt-1">故障码：{{ arDeviceStatus.fault_code }}</div>
              </div>
            </div>

            <!-- 实时指标 -->
            <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm mb-4">
              <h4 class="font-bold text-slate-700 mb-3">实时运行指标（AR 叠加层）</h4>
              <div v-if="arRealtimeMetrics.length" class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                <div v-for="m in arRealtimeMetrics" :key="m.label"
                     class="p-3 rounded-lg border" :class="m.status === 'warning' ? 'bg-amber-50 border-amber-200' : 'bg-slate-50 border-slate-200'">
                  <div class="text-xs text-slate-400">{{ m.label }}</div>
                  <div class="text-lg font-bold mt-1" :class="m.status === 'warning' ? 'text-amber-600' : 'text-slate-700'">
                    {{ m.value ?? '-' }} <span class="text-xs">{{ m.unit }}</span>
                  </div>
                </div>
              </div>
              <el-empty v-else description="暂无实时指标数据" :image-size="60" />
            </div>

            <!-- 最近工单 -->
            <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm mb-4">
              <h4 class="font-bold text-slate-700 mb-3">最近工单</h4>
              <el-empty v-if="!arWorkOrders.length" description="该设备暂无工单" :image-size="60" />
              <el-table v-else :data="arWorkOrders" stripe size="small">
                <el-table-column prop="order_id" label="工单 ID" width="200" />
                <el-table-column prop="diagnosis_title" label="诊断标题" min-width="180" />
                <el-table-column prop="status" label="状态" width="100">
                  <template #default="{ row }">
                    <el-tag :type="row.status === 'closed' ? 'success' : row.status === 'in_progress' ? 'warning' : 'info'" size="small">{{ row.status }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="created_at" label="创建时间" width="180" />
                <el-table-column prop="maintenance_action" label="维保动作" min-width="180" />
              </el-table>
            </div>

            <!-- 设备手册要点 -->
            <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm mb-4">
              <h4 class="font-bold text-slate-700 mb-3">设备手册要点 <el-tag v-if="arManualDeviceType" size="small" type="info">{{ arManualDeviceType }}</el-tag></h4>
              <div v-if="arManual.steps && arManual.steps.length" class="space-y-2">
                <div v-for="(point, idx) in arManual.steps" :key="idx" class="flex items-start gap-2 p-2 rounded-lg bg-amber-50 border border-amber-100">
                  <span class="w-6 h-6 rounded-full bg-amber-400 text-white flex items-center justify-center font-bold text-xs flex-shrink-0">{{ idx + 1 }}</span>
                  <span class="text-sm text-slate-700">{{ point }}</span>
                </div>
                <div v-if="arManual.warning" class="text-sm text-rose-600 font-medium mt-2">{{ arManual.warning }}</div>
              </div>
              <div v-else class="text-sm text-slate-400">{{ arManual.summary || '暂无手册信息' }}</div>
            </div>

            <!-- AR 标注 -->
            <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
              <div class="flex items-center justify-between mb-3">
                <h4 class="font-bold text-slate-700">现场标注（持久化到数据库）</h4>
                <el-button type="primary" size="small" @click="showAnnotDialog = true">
                  <el-icon class="mr-1"><EditPen /></el-icon> 新增标注
                </el-button>
              </div>
              <el-empty v-if="!arAnnotations.length" description="暂无标注" :image-size="60" />
              <el-table v-else :data="arAnnotations" stripe size="small">
                <el-table-column prop="operator" label="标注人" width="100" />
                <el-table-column prop="note" label="标注内容" min-width="240" />
                <el-table-column prop="created_at" label="时间" width="180" />
              </el-table>
            </div>
          </template>
        </div>
      </el-tab-pane>

      <!-- Tab 9: 全链路可观测性 -->
      <el-tab-pane v-if="category === 'ops'" label="📡 全链路可观测性" name="observability">
        <!-- 组件健康状态 -->
        <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm mb-4">
          <h4 class="font-bold text-slate-700 mb-3">组件健康状态</h4>
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            <div v-for="comp in healthComponents" :key="comp.name"
                 class="p-3 rounded-lg border flex items-center justify-between"
                 :class="comp.status === 'healthy' ? 'bg-emerald-50 border-emerald-200' : comp.status === 'warning' ? 'bg-amber-50 border-amber-200' : comp.status === 'unhealthy' ? 'bg-rose-50 border-rose-200' : 'bg-slate-50 border-slate-200'">
              <div>
                <div class="text-sm font-medium capitalize">{{ comp.name }}</div>
                <div v-if="comp.cpu_pct !== undefined" class="text-xs text-slate-500 mt-1">
                  CPU {{ comp.cpu_pct?.toFixed(1) }}% · 内存 {{ comp.memory_pct?.toFixed(1) }}% · 磁盘 {{ comp.disk_pct?.toFixed(1) }}%
                </div>
              </div>
              <el-tag :type="comp.status === 'healthy' ? 'success' : comp.status === 'warning' ? 'warning' : 'danger'" size="small" effect="dark">
                {{ comp.status }}
              </el-tag>
            </div>
          </div>
        </div>

        <div class="flex items-center gap-3 mb-4">
          <DataSourceTag source="real" />
          <span class="text-xs text-slate-500">基于 OpenTelemetry 风格的内存滑动窗口指标</span>
        </div>

        <!-- 指标时序图 -->
        <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <h4 class="font-bold text-slate-700 mb-3">请求指标（近 1 小时）</h4>
          <el-empty v-if="!metricsTimeline.length" description="暂无请求指标数据（需有流量产生）" :image-size="80" />
          <div v-else ref="metricsChartRef" class="w-full h-72"></div>
        </div>
      </el-tab-pane>

      <!-- Tab 10: 边缘计算网关 -->
      <el-tab-pane v-if="category === 'ops'" label="🌐 边缘计算网关" name="edge">
        <!-- 边缘网关状态 -->
        <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm mb-4">
          <div class="flex items-center justify-between mb-3">
            <h4 class="font-bold text-slate-700">边缘网关状态</h4>
            <DataSourceTag source="real" />
          </div>
          <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
            <div class="bg-slate-50 p-3 rounded-lg">
              <div class="text-xs text-slate-400">运行状态</div>
              <div class="font-bold" :class="edgeStatus.is_running ? 'text-emerald-600' : 'text-slate-400'">
                {{ edgeStatus.is_running ? '运行中' : '已停止' }}
              </div>
            </div>
            <div class="bg-slate-50 p-3 rounded-lg">
              <div class="text-xs text-slate-400">已发送消息</div>
              <div class="font-bold text-indigo-600">{{ edgeStatus.messages_sent || 0 }}</div>
            </div>
            <div class="bg-slate-50 p-3 rounded-lg">
              <div class="text-xs text-slate-400">活跃设备</div>
              <div class="font-bold text-blue-600">{{ edgeStatus.active_devices || 0 }}</div>
            </div>
            <div class="bg-slate-50 p-3 rounded-lg">
              <div class="text-xs text-slate-400">异常注入</div>
              <div class="font-bold" :class="edgeStatus.anomaly_injection ? 'text-rose-500' : 'text-slate-400'">
                {{ edgeStatus.anomaly_injection ? edgeStatus.anomaly_injection.type : '无' }}
              </div>
            </div>
          </div>
          <div class="flex gap-2 flex-wrap">
            <el-button size="small" type="warning" @click="injectAnomaly('cop_drop')">注入 COP 异常</el-button>
            <el-button size="small" type="danger" @click="injectAnomaly('overheat')">注入过热</el-button>
            <el-button size="small" @click="injectAnomaly('clear')">清除异常</el-button>
          </div>
        </div>

        <!-- 边缘设备实时快照 -->
        <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <h4 class="font-bold text-slate-700 mb-3">边缘设备实时快照（从 fact_energy_records 最新记录）</h4>
          <el-table :data="edgeSnapshot" stripe size="small" max-height="500">
            <el-table-column prop="building_name" label="建筑" width="120" />
            <el-table-column prop="space_name" label="空间" width="140" />
            <el-table-column prop="device_name" label="设备名称" min-width="160" />
            <el-table-column prop="protocol" label="协议" width="100" />
            <el-table-column prop="run_status" label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.run_status === 'NORMAL' ? 'success' : 'warning'" size="small">{{ row.run_status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="elec_consumption" label="功率 kW" width="100" />
            <el-table-column prop="cop" label="COP" width="80" />
            <el-table-column prop="supply_temp" label="供水温度" width="100" />
            <el-table-column prop="return_temp" label="回水温度" width="100" />
          </el-table>
        </div>
      </el-tab-pane>

    </el-tabs>

    <!-- AR 标注新增对话框 -->
    <el-dialog v-model="showAnnotDialog" title="新增现场标注" width="500px">
      <el-form :model="annotForm" label-width="80px">
        <el-form-item label="设备 ID">
          <el-input :value="arDeviceId" disabled />
        </el-form-item>
        <el-form-item label="标注人">
          <el-input v-model="annotForm.operator" placeholder="请输入标注人姓名" />
        </el-form-item>
        <el-form-item label="标注内容">
          <el-input v-model="annotForm.note" type="textarea" :rows="4" placeholder="请输入现场观察内容" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAnnotDialog = false">取消</el-button>
        <el-button type="primary" @click="submitAnnotation" :loading="annotSubmitting">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, shallowRef, watch, computed, h, defineComponent } from 'vue'
import * as echarts from 'echarts'
import { Cpu, Refresh, ArrowRight, VideoPlay, Monitor, EditPen } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import {
  fetchAnomalyDetect, fetchCarbonOverview, fetchCarbonPathway,
  fetchVppStatus, fetchVppDispatch, fetchVppEconomy, fetchMicrogridOverview,
  fetchPvForecast, fetchMicrogridSchedule,
  fetchAgentsList, executeAgentWorkflow, fetchKnowledgeGraph,
  fetchTwinRealtime, fetchTwinDevices3D, fetchTwinHierarchy,
  fetchArDevice, fetchArWorkOrders, fetchArManual, fetchArDevices, fetchArAnnotations, saveArAnnotation,
  fetchObservabilityHealth, fetchObservabilityDashboard, fetchEdgeStatus, fetchEdgeSnapshot, injectEdgeAnomaly
} from '../api/index.js'

// ===== 路由 props：分类（energy / ai / ops）=====
const props = defineProps({
  category: {
    type: String,
    default: 'energy',
    validator: (v) => ['energy', 'ai', 'ops'].includes(v)
  }
})

// 各分类配置
const CATEGORY_CONFIG = {
  energy: {
    title: '能源智能分析',
    subtitle: '4 大能源前沿能力：异常检测 · 碳中和 · 虚拟电厂 · 微电网',
    tabs: ['anomaly', 'carbon', 'vpp', 'microgrid'],
    defaultTab: 'anomaly'
  },
  ai: {
    title: '智能体与知识',
    subtitle: '2 大 AI 前沿能力：多智能体协作 · 知识图谱',
    tabs: ['agents', 'knowledge'],
    defaultTab: 'agents'
  },
  ops: {
    title: '数字孪生与运维',
    subtitle: '4 大运维前沿能力：3D 孪生 · AR 运维 · 可观测性 · 边缘网关',
    tabs: ['twin3d', 'ar', 'observability', 'edge'],
    defaultTab: 'twin3d'
  }
}

const categoryTitle = computed(() => CATEGORY_CONFIG[props.category]?.title || '前沿功能创新中心')
const categorySubtitle = computed(() => CATEGORY_CONFIG[props.category]?.subtitle || '')

const activeTab = ref(CATEGORY_CONFIG[props.category]?.defaultTab || 'anomaly')
const refreshing = ref(false)

// 监听 category 变化（路由切换时），重置 activeTab 并重新加载该分类数据
watch(() => props.category, async (newCat) => {
  activeTab.value = CATEGORY_CONFIG[newCat]?.defaultTab || 'anomaly'
  // 路由切换时重新加载该分类的数据
  await nextTick()
  refreshAll()
})

// ===== 通用统计卡片组件（修复：使用正确的渲染函数）=====
const StatCard = defineComponent({
  name: 'StatCard',
  props: {
    label: { type: String, default: '' },
    value: { type: [String, Number], default: '-' },
    color: { type: String, default: 'slate' },
    subtitle: { type: String, default: '' }
  },
  setup(props) {
    const colorMap = {
      slate: 'text-slate-700', indigo: 'text-indigo-600', blue: 'text-blue-600',
      cyan: 'text-cyan-600', emerald: 'text-emerald-600', amber: 'text-amber-600',
      rose: 'text-rose-500', pink: 'text-pink-500'
    }
    return () => h('div', { class: 'bg-white p-4 rounded-xl border border-slate-200 shadow-sm' }, [
      h('div', { class: 'text-xs text-slate-400 mb-2' }, props.label),
      h('div', { class: ['text-2xl font-black', colorMap[props.color] || colorMap.slate] }, String(props.value)),
      props.subtitle ? h('div', { class: 'text-xs text-slate-400 mt-1' }, props.subtitle) : null
    ])
  }
})

// 数据源标签
const DataSourceTag = defineComponent({
  name: 'DataSourceTag',
  props: { source: { type: String, default: 'real' } },
  setup(props) {
    return () => props.source === 'real'
      ? h('span', { class: 'inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-600 border border-emerald-200' }, '✓ 真实数据')
      : h('span', { class: 'inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-600 border border-amber-200' }, '⚠ 模拟数据')
  }
})

const typeLabelMap = {
  building: '建筑', space: '空间', device: '设备', part: '部件',
  fault: '故障', action: '维保动作', workorder: '工单'
}

// ===== 异常检测 =====
const anomalyLoading = ref(false)
const anomalyHours = ref(168)
const anomalyEvents = ref([])
const anomalyMeta = ref({})

const loadAnomaly = async () => {
  anomalyLoading.value = true
  try {
    const res = await fetchAnomalyDetect({ hours: anomalyHours.value })
    if (res.status === 'success') {
      anomalyEvents.value = res.data || []
      anomalyMeta.value = res.meta || {}
    }
  } catch (e) {
    ElMessage.error('异常检测加载失败')
  } finally {
    anomalyLoading.value = false
  }
}

// ===== 碳排放 =====
const carbonLoading = ref(false)
const carbonSummary = ref({})
const carbonTrend = ref([])
const carbonPathways = ref([])
const carbonTrendChartRef = ref(null)
const carbonPathwayChartRef = ref(null)
const carbonTrendChart = shallowRef(null)
const carbonPathwayChart = shallowRef(null)

const loadCarbon = async () => {
  carbonLoading.value = true
  try {
    const [overviewRes, pathwayRes] = await Promise.all([
      fetchCarbonOverview(30),
      fetchCarbonPathway(2030)
    ])
    if (overviewRes.status === 'success' && overviewRes.data) {
      carbonSummary.value = overviewRes.data.summary || {}
      carbonTrend.value = overviewRes.data.trend || []
    }
    if (pathwayRes.status === 'success' && pathwayRes.data) {
      carbonPathways.value = pathwayRes.data.scenarios || []
    }
    // 渲染延迟到 Tab 切换时执行（避免容器尺寸为 0）
    if (activeTab.value === 'carbon') {
      nextTick(() => {
        renderCarbonTrend()
        renderCarbonPathway()
      })
    }
  } catch (e) {
    ElMessage.error('碳排放数据加载失败')
  } finally {
    carbonLoading.value = false
  }
}

const renderCarbonTrend = () => {
  if (!carbonTrendChartRef.value) return
  if (!carbonTrendChart.value) carbonTrendChart.value = echarts.init(carbonTrendChartRef.value)
  carbonTrendChart.value.resize()
  carbonTrendChart.value.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['Scope 1', 'Scope 2', '总计'], top: 0 },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: carbonTrend.value.map(t => (t.day || '').substring(5)) },
    yAxis: { type: 'value', name: 'tCO₂' },
    series: [
      { name: 'Scope 1', type: 'bar', stack: 'a', data: carbonTrend.value.map(t => t.scope1_t), itemStyle: { color: '#f59e0b' } },
      { name: 'Scope 2', type: 'bar', stack: 'a', data: carbonTrend.value.map(t => t.scope2_t), itemStyle: { color: '#3b82f6' } },
      { name: '总计', type: 'line', data: carbonTrend.value.map(t => t.total_t), itemStyle: { color: '#ef4444' }, lineStyle: { width: 2 } },
    ]
  })
}

const renderCarbonPathway = () => {
  if (!carbonPathwayChartRef.value) return
  if (!carbonPathwayChart.value) carbonPathwayChart.value = echarts.init(carbonPathwayChartRef.value)
  carbonPathwayChart.value.resize()
  const colors = ['#94a3b8', '#f59e0b', '#10b981']
  const years = carbonPathways.value[0]?.pathway?.map(p => p.year) || []
  carbonPathwayChart.value.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: carbonPathways.value.map(s => s.name), top: 0 },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: years },
    yAxis: { type: 'value', name: 'tCO₂' },
    series: carbonPathways.value.map((s, idx) => ({
      name: s.name,
      type: 'line',
      data: (s.pathway || []).map(p => p.emission_t),
      lineStyle: { width: 3, color: colors[idx] },
      itemStyle: { color: colors[idx] },
      smooth: true,
    }))
  })
}

// ===== VPP =====
const vppLoading = ref(false)
const vppStatus = ref({})
const vppEconomy = ref({})
const vppDispatchChartRef = ref(null)
const vppDispatchChart = shallowRef(null)
let vppDispatchData = []

const loadVpp = async () => {
  vppLoading.value = true
  try {
    const [status, economy, dispatch] = await Promise.all([
      fetchVppStatus(), fetchVppEconomy(30), fetchVppDispatch()
    ])
    if (status.status === 'success') vppStatus.value = status.data || {}
    if (economy.status === 'success') vppEconomy.value = economy.data || {}
    if (dispatch.status === 'success' && dispatch.data) vppDispatchData = dispatch.data.schedule || []
    // 渲染延迟到 Tab 切换时执行（避免容器尺寸为 0）
    if (activeTab.value === 'vpp') {
      nextTick(() => renderVppDispatch())
    }
  } catch (e) {
    ElMessage.error('VPP 数据加载失败')
  } finally {
    vppLoading.value = false
  }
}

const renderVppDispatch = () => {
  if (!vppDispatchChartRef.value) return
  if (!vppDispatchChart.value) vppDispatchChart.value = echarts.init(vppDispatchChartRef.value)
  vppDispatchChart.value.resize()
  vppDispatchChart.value.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['原始负荷', '净负荷', 'SOC'], top: 0 },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: vppDispatchData.map(s => s.hour + ':00') },
    yAxis: [
      { type: 'value', name: 'kW' },
      { type: 'value', name: 'SOC%', max: 100 },
    ],
    series: [
      { name: '原始负荷', type: 'bar', data: vppDispatchData.map(s => s.original_load), itemStyle: { color: '#94a3b8' } },
      { name: '净负荷', type: 'line', data: vppDispatchData.map(s => s.net_load), itemStyle: { color: '#3b82f6' }, lineStyle: { width: 3 } },
      { name: 'SOC', type: 'line', yAxisIndex: 1, data: vppDispatchData.map(s => s.soc_pct), itemStyle: { color: '#10b981' }, lineStyle: { width: 2, type: 'dashed' } },
    ]
  })
}

// ===== 光储充微电网 =====
const microgridLoading = ref(false)
const microgridOverview = ref({})
const pvForecastChartRef = ref(null)
const pvForecastChart = shallowRef(null)
let pvForecastData = []
const microgridScheduleData = ref([])

const loadMicrogrid = async () => {
  microgridLoading.value = true
  try {
    const [overview, forecast, schedule] = await Promise.all([
      fetchMicrogridOverview(), fetchPvForecast(), fetchMicrogridSchedule()
    ])
    if (overview.status === 'success') microgridOverview.value = overview.data || {}
    if (forecast.status === 'success' && forecast.data) pvForecastData = forecast.data.forecast || []
    if (schedule.status === 'success' && schedule.data) microgridScheduleData.value = schedule.data.schedule || []
    // 渲染延迟到 Tab 切换时执行（避免容器尺寸为 0）
    if (activeTab.value === 'microgrid') {
      nextTick(() => renderPvForecast())
    }
  } catch (e) {
    ElMessage.error('微电网数据加载失败')
  } finally {
    microgridLoading.value = false
  }
}

const renderPvForecast = () => {
  if (!pvForecastChartRef.value) return
  if (!pvForecastChart.value) pvForecastChart.value = echarts.init(pvForecastChartRef.value)
  pvForecastChart.value.resize()
  // 后端字段：predicted_power_kw, radiation_w_m2（修正字段名）
  pvForecastChart.value.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['预测功率 (kW)', '辐照度 (W/m²)'], top: 0 },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: pvForecastData.map(p => (p.time || '').substring(11, 16) || (p.hour + ':00')),
    },
    yAxis: [
      { type: 'value', name: 'kW' },
      { type: 'value', name: 'W/m²' },
    ],
    series: [
      {
        name: '预测功率 (kW)',
        type: 'line',
        smooth: true,
        data: pvForecastData.map(p => p.predicted_power_kw ?? p.predicted_kw ?? 0),
        itemStyle: { color: '#f59e0b' },
        areaStyle: { opacity: 0.2 },
      },
      {
        name: '辐照度 (W/m²)',
        type: 'line',
        yAxisIndex: 1,
        data: pvForecastData.map(p => p.radiation_w_m2 ?? 0),
        itemStyle: { color: '#06b6d4' },
        lineStyle: { type: 'dashed' },
      },
    ]
  })
}

// ===== 3D 实时数字孪生 =====
const twinLoading = ref(false)
const twinBuildings = ref([])
const twinDevices = ref([])
const twinAlerts = ref([])
const twinStats = ref({})

// 层级树状态
const twinHierarchy = ref(null)
const selectedBuildingId = ref('')
const selectedSpaceId = ref('')
// 当前展开的建筑（el-collapse）
const expandedBuildings = ref([])

const loadTwin3d = async () => {
  twinLoading.value = true
  try {
    const [realtime, hierarchy] = await Promise.all([
      fetchTwinRealtime(), fetchTwinHierarchy()
    ])
    if (realtime.status === 'success' && realtime.data) {
      twinBuildings.value = realtime.data.buildings || []
      twinAlerts.value = realtime.data.alerts || []
      twinStats.value = realtime.data.stats || {}
      twinDevices.value = realtime.data.devices || []
    }
    if (hierarchy.status === 'success' && hierarchy.data) {
      twinHierarchy.value = hierarchy.data
      // 默认展开第一个建筑
      if (hierarchy.data.buildings?.length && !expandedBuildings.value.length) {
        expandedBuildings.value = [hierarchy.data.buildings[0].building_id]
        selectedBuildingId.value = hierarchy.data.buildings[0].building_id
        // 默认选第一个空间
        if (hierarchy.data.buildings[0].spaces?.length) {
          selectedSpaceId.value = hierarchy.data.buildings[0].spaces[0].space_id
        }
      }
    }
  } catch (e) {
    ElMessage.error('3D 孪生数据加载失败')
  } finally {
    twinLoading.value = false
  }
}

// 当前选中的空间对象
const selectedSpace = computed(() => {
  if (!twinHierarchy.value || !selectedSpaceId.value) return null
  for (const bld of twinHierarchy.value.buildings || []) {
    for (const sp of bld.spaces || []) {
      if (sp.space_id === selectedSpaceId.value) return sp
    }
  }
  return null
})

// 当前选中的建筑对象
const selectedBuilding = computed(() => {
  if (!twinHierarchy.value || !selectedBuildingId.value) return null
  return (twinHierarchy.value.buildings || []).find(b => b.building_id === selectedBuildingId.value) || null
})

// ===== AR 远程运维 =====
const arLoading = ref(false)
const arDeviceId = ref('')
const arDeviceOptions = ref([])
const arDeviceInfo = ref({})
const arDeviceStatus = ref({})
const arRealtimeMetrics = ref([])
const arWorkOrders = ref([])
const arManual = ref({})
const arManualDeviceType = ref('')
const arAnnotations = ref([])

// 标注对话框
const showAnnotDialog = ref(false)
const annotSubmitting = ref(false)
const annotForm = ref({ operator: '', note: '' })

const loadArDevices = async () => {
  try {
    const res = await fetchArDevices()
    if (res.status === 'success') {
      arDeviceOptions.value = res.data || []
      // 默认选第一个设备
      if (arDeviceOptions.value.length && !arDeviceId.value) {
        arDeviceId.value = arDeviceOptions.value[0].device_id
        await loadAr()
      }
    }
  } catch (e) {
    console.error('加载 AR 设备清单失败', e)
  }
}

const loadAr = async () => {
  if (!arDeviceId.value) return
  arLoading.value = true
  try {
    const [device, orders, manual, annotations] = await Promise.all([
      fetchArDevice(arDeviceId.value),
      fetchArWorkOrders(arDeviceId.value, 5),
      fetchArManual(arDeviceId.value),
      fetchArAnnotations(arDeviceId.value, 20)
    ])
    if (device.status === 'success' && device.data) {
      arDeviceInfo.value = device.data.device_info || {}
      arDeviceStatus.value = device.data.status || {}
      arRealtimeMetrics.value = device.data.realtime_metrics || []
    } else {
      arDeviceInfo.value = {}
      arDeviceStatus.value = {}
      arRealtimeMetrics.value = []
    }
    if (orders.status === 'success') {
      arWorkOrders.value = orders.data || []
    }
    if (manual.status === 'success' && manual.data) {
      arManual.value = manual.data
      arManualDeviceType.value = manual.device_type || ''
    }
    if (annotations.status === 'success') {
      arAnnotations.value = annotations.data || []
    }
  } catch (e) {
    ElMessage.error('AR 数据加载失败')
  } finally {
    arLoading.value = false
  }
}

const submitAnnotation = async () => {
  if (!annotForm.value.note.trim()) {
    ElMessage.warning('请输入标注内容')
    return
  }
  annotSubmitting.value = true
  try {
    const res = await saveArAnnotation({
      device_id: arDeviceId.value,
      operator: annotForm.value.operator || 'anonymous',
      note: annotForm.value.note
    })
    if (res.status === 'success') {
      ElMessage.success('标注已保存')
      showAnnotDialog.value = false
      annotForm.value = { operator: '', note: '' }
      // 重新加载标注
      const annoRes = await fetchArAnnotations(arDeviceId.value, 20)
      if (annoRes.status === 'success') arAnnotations.value = annoRes.data || []
    } else {
      ElMessage.error(res.message || '保存失败')
    }
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    annotSubmitting.value = false
  }
}

// ===== 多智能体 =====
const agentsList = ref([])
const agentTask = ref('诊断并处理近期异常设备')
const workflowRunning = ref(false)
const workflowLogs = ref([])
const workflowResults = ref([])

const loadAgents = async () => {
  try {
    const res = await fetchAgentsList()
    if (res.status === 'success' && res.data) {
      agentsList.value = (res.data.agents || []).map(a => ({ ...a, active: false }))
    }
  } catch (e) {}
}

const runWorkflow = async () => {
  if (!agentTask.value.trim() || workflowRunning.value) return
  workflowRunning.value = true
  workflowLogs.value = []
  workflowResults.value = []
  agentsList.value.forEach(a => a.active = false)

  await executeAgentWorkflow(
    { task: agentTask.value },
    {
      onAgentStart: (data) => {
        const agent = agentsList.value.find(a => a.id === data.agent_id)
        if (agent) agent.active = true
        workflowLogs.value.push({
          time: new Date().toLocaleTimeString(),
          type: 'start',
          message: `▶ ${data.agent_name} 开始执行...`
        })
      },
      onAgentComplete: (data) => {
        workflowLogs.value.push({
          time: new Date().toLocaleTimeString(),
          type: 'complete',
          message: `✓ ${data.agent_name} 完成`
        })
        workflowResults.value.push({
          agent_name: data.agent_name,
          icon: agentsList.value.find(a => a.id === data.agent_id)?.icon || '🤖',
          output: data.output
        })
      },
      onWorkflowComplete: () => {
        workflowLogs.value.push({
          time: new Date().toLocaleTimeString(),
          type: 'complete',
          message: '🎉 工作流全部完成'
        })
        workflowRunning.value = false
      },
      onError: () => {
        workflowRunning.value = false
        ElMessage.error('工作流执行失败')
      }
    }
  )
}

// ===== 知识图谱 =====
const knowledgeLoading = ref(false)
const knowledgeFilter = ref('')
const knowledgeGraphRef = ref(null)
const knowledgeStats = ref({})
let knowledgeChart = null

const loadKnowledge = async () => {
  knowledgeLoading.value = true
  try {
    const res = await fetchKnowledgeGraph(knowledgeFilter.value)
    if (res.status === 'success' && res.data) {
      knowledgeStats.value = res.data.stats || {}
      nextTick(() => renderKnowledgeGraph(res.data))
    }
  } catch (e) {
    ElMessage.error('知识图谱加载失败')
  } finally {
    knowledgeLoading.value = false
  }
}

const renderKnowledgeGraph = (data) => {
  if (!knowledgeGraphRef.value) return
  // 容器尺寸为 0 时延迟重试
  if (knowledgeGraphRef.value.offsetWidth === 0 || knowledgeGraphRef.value.offsetHeight === 0) {
    setTimeout(() => renderKnowledgeGraph(data), 300)
    return
  }
  if (!knowledgeChart) knowledgeChart = echarts.init(knowledgeGraphRef.value)

  // 节点类型 → 颜色与中文标签映射（覆盖所有数据库真实类型）
  const typeColors = {
    building: '#8b5cf6', space: '#a78bfa', device: '#3b82f6', part: '#10b981',
    fault: '#ef4444', action: '#f59e0b', workorder: '#06b6d4'
  }
  const typeSizes = {
    building: 45, space: 32, device: 40, part: 28, fault: 35, action: 26, workorder: 30
  }
  const typeCnLabel = {
    building: '建筑', space: '空间', device: '设备', part: '部件',
    fault: '故障', action: '维保动作', workorder: '工单'
  }

  knowledgeChart.setOption({
    tooltip: {
      formatter: p => p.dataType === 'node'
        ? `${typeCnLabel[p.data.type] || p.data.type}：${p.data.label || p.data.name}`
        : `${p.data.source} → ${p.data.target}（${p.data.value || p.data.relation}）`
    },
    legend: {
      data: Object.values(typeCnLabel),
      top: 10, textStyle: { fontSize: 11 }
    },
    series: [{
      type: 'graph',
      layout: 'force',
      roam: true,
      label: { show: true, position: 'right', fontSize: 11 },
      force: { repulsion: 220, edgeLength: 100, gravity: 0.1 },
      categories: Object.keys(typeCnLabel).map(k => ({ name: typeCnLabel[k] })),
      data: (data.nodes || []).map(n => {
        const typeIdx = Object.keys(typeCnLabel).indexOf(n.type)
        return {
          id: n.id,
          name: n.label,
          label: n.label,
          category: typeIdx >= 0 ? typeIdx : 0,
          symbolSize: typeSizes[n.type] || 25,
          itemStyle: { color: typeColors[n.type] || '#64748b' },
          type: n.type,
        }
      }),
      links: (data.edges || []).map(e => ({
        source: e.source,
        target: e.target,
        value: e.relation,
        lineStyle: { color: '#cbd5e1', width: 1.5 },
      })),
      lineStyle: { color: '#cbd5e1', curveness: 0.1 },
    }]
  })
}

// ===== 可观测性 + 边缘网关 =====
const healthComponents = ref([])
const edgeStatus = ref({})
const edgeSnapshot = ref([])
const metricsChartRef = ref(null)
const metricsChart = shallowRef(null)
const metricsTimeline = ref([])

const loadObservability = async () => {
  try {
    const [health, dash, edge, snap] = await Promise.all([
      fetchObservabilityHealth(), fetchObservabilityDashboard(),
      fetchEdgeStatus(), fetchEdgeSnapshot()
    ])
    if (health.status === 'success' && health.data) healthComponents.value = health.data.components || []
    if (edge.status === 'success' && edge.data) edgeStatus.value = edge.data
    if (snap.status === 'success' && snap.data) edgeSnapshot.value = snap.data.snapshot || []
    if (dash.status === 'success' && dash.data) {
      metricsTimeline.value = dash.data.timeline || []
      nextTick(() => renderMetrics(metricsTimeline.value))
    }
  } catch (e) {
    ElMessage.error('可观测性数据加载失败')
  }
}

const renderMetrics = (timeline) => {
  if (!metricsChartRef.value) return
  if (!timeline || !timeline.length) return
  if (!metricsChart.value) metricsChart.value = echarts.init(metricsChartRef.value)
  metricsChart.value.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['请求数', '错误数', 'DB 查询数'], top: 0 },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: timeline.map(t => t.time) },
    yAxis: { type: 'value' },
    series: [
      { name: '请求数', type: 'line', smooth: true, data: timeline.map(t => t.requests), itemStyle: { color: '#3b82f6' } },
      { name: '错误数', type: 'line', data: timeline.map(t => t.errors), itemStyle: { color: '#ef4444' } },
      { name: 'DB 查询数', type: 'line', smooth: true, data: timeline.map(t => t.db_queries), itemStyle: { color: '#10b981' } },
    ]
  })
}

const injectAnomaly = async (type) => {
  try {
    const payload = type === 'clear'
      ? { type: 'clear' }
      : { type, device_id: edgeSnapshot.value[0]?.device_id, duration_seconds: 60 }
    await injectEdgeAnomaly(payload)
    ElMessage.success(type === 'clear' ? '已清除异常' : `已注入 ${type} 异常`)
    setTimeout(() => loadObservability(), 1000)
  } catch (e) {
    ElMessage.error('注入失败')
  }
}

// ===== 刷新全部 =====
const refreshAll = async () => {
  refreshing.value = true
  const cat = props.category
  const loaders = []
  if (cat === 'energy') {
    loaders.push(loadAnomaly(), loadCarbon(), loadVpp(), loadMicrogrid())
  } else if (cat === 'ai') {
    loaders.push(loadAgents(), loadKnowledge())
  } else if (cat === 'ops') {
    loaders.push(loadTwin3d(), loadArDevices(), loadObservability())
  }
  await Promise.allSettled(loaders)
  refreshing.value = false
  ElMessage.success('刷新完成')
}

const handleResize = () => {
  carbonTrendChart.value?.resize()
  carbonPathwayChart.value?.resize()
  vppDispatchChart.value?.resize()
  pvForecastChart.value?.resize()
  knowledgeChart?.resize()
  metricsChart.value?.resize()
}

// 通用：等待容器尺寸就绪后执行渲染（解决 el-tab-pane display:none 导致的 0 尺寸问题）
const waitForContainerAndRender = (refObj, renderFn, maxAttempts = 10) => {
  let attempts = 0
  const check = () => {
    attempts++
    if (refObj.value && refObj.value.offsetWidth > 0 && refObj.value.offsetHeight > 0) {
      renderFn()
    } else if (attempts < maxAttempts) {
      setTimeout(check, 100)
    }
  }
  check()
}

// Tab 切换时懒加载图表
watch(activeTab, async (newTab) => {
  await nextTick()
  setTimeout(async () => {
    await nextTick()
    if (newTab === 'carbon') {
      waitForContainerAndRender(carbonTrendChartRef, renderCarbonTrend)
      waitForContainerAndRender(carbonPathwayChartRef, renderCarbonPathway)
    } else if (newTab === 'vpp') {
      waitForContainerAndRender(vppDispatchChartRef, renderVppDispatch)
    } else if (newTab === 'microgrid') {
      waitForContainerAndRender(pvForecastChartRef, renderPvForecast)
    } else if (newTab === 'knowledge') {
      if (knowledgeChart) {
        knowledgeChart.resize()
      } else if (knowledgeGraphRef.value && knowledgeGraphRef.value.offsetWidth > 0) {
        loadKnowledge()
      } else {
        waitForContainerAndRender(knowledgeGraphRef, () => loadKnowledge())
      }
    } else if (newTab === 'observability') {
      if (metricsChart.value) metricsChart.value.resize()
      else if (metricsTimeline.value.length) renderMetrics(metricsTimeline.value)
    }
  }, 200)
})

onMounted(() => {
  refreshAll()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  carbonTrendChart.value?.dispose()
  carbonPathwayChart.value?.dispose()
  vppDispatchChart.value?.dispose()
  pvForecastChart.value?.dispose()
  knowledgeChart?.dispose()
  metricsChart.value?.dispose()
})
</script>

<style>
.frontier-tabs .el-tabs__header {
  background: linear-gradient(to right, #f8fafc, #f1f5f9);
  border-radius: 16px 16px 0 0;
}
.frontier-tabs .el-tabs__nav-wrap::after {
  display: none;
}
.frontier-tabs .el-tabs__item {
  font-weight: 500;
  height: 44px;
  line-height: 44px;
  padding: 0 16px !important;
  font-size: 13px;
  transition: all 0.2s;
}
.frontier-tabs .el-tabs__item:hover {
  color: #6366f1;
}
.frontier-tabs .el-tabs__item.is-active {
  font-weight: 700;
  color: #4f46e5;
}
.frontier-tabs .el-tabs__content {
  padding: 16px;
}
/* 标签栏横向滚动（10 个标签在窄屏不挤） */
.frontier-tabs .el-tabs__nav {
  flex-wrap: wrap;
}
</style>
