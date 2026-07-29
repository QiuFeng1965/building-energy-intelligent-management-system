<template>
  <div class="flex flex-col gap-4 pb-8 bg-slate-50/60 min-h-screen">

    <!-- 页头 -->
    <div class="bg-gradient-to-r from-emerald-600 via-teal-600 to-cyan-600 p-5 rounded-2xl shadow-lg text-white">
      <div class="flex items-center justify-between flex-wrap gap-4">
        <div class="flex items-center gap-4">
          <div class="w-12 h-12 rounded-xl bg-white/20 flex items-center justify-center backdrop-blur">
            <el-icon class="text-3xl"><Promotion /></el-icon>
          </div>
          <div>
            <h2 class="text-2xl font-bold">进阶能力中心</h2>
            <p class="text-emerald-100 mt-1 text-xs flex items-center gap-2 flex-wrap">
              <span>9 大进阶能力 · 全栈实战</span>
              <span class="opacity-50">·</span>
              <span class="inline-flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-emerald-300 animate-pulse"></span> 真实数据驱动</span>
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
        <router-link v-for="cat in categories" :key="cat.value" :to="`/advanced/${cat.value}`"
          :class="['px-3 py-1 rounded-full text-xs transition-all', category === cat.value ? 'bg-white text-emerald-600 font-bold' : 'bg-white/15 text-white hover:bg-white/25']">
          {{ cat.icon }} {{ cat.label }}
        </router-link>
      </div>
    </div>

    <!-- 功能切换 Tab -->
    <el-tabs v-model="activeTab" type="border-card" class="!rounded-2xl !shadow-sm advanced-tabs">

      <!-- ========== 分类1-能源诊断与优化 ========== -->
      <!-- Tab 1: 设备健康度 & RUL 预测 -->
      <el-tab-pane v-if="category === 'diagnose'" label="🩺 设备健康度 & RUL 预测" name="rul">
        <div v-loading="rulLoading">
          <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <StatCard label="可评分设备数" :value="rulSummary.total_devices || 0" color="indigo" />
            <StatCard label="平均健康度" :value="(rulSummary.avg_score || 0) + ' 分'" :color="healthColor(rulSummary.avg_score)" />
            <StatCard label="预警设备" :value="(rulSummary.grade_counts?.warning || 0) + ' 台'" color="rose" />
            <StatCard label="优秀设备" :value="(rulSummary.grade_counts?.excellent || 0) + ' 台'" color="emerald" />
          </div>

          <!-- 分级分布 -->
          <div v-if="rulGrades.length" class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <div v-for="g in rulGrades" :key="g.key" class="bg-white rounded-xl p-3 border border-slate-100 shadow-sm flex items-center gap-3">
              <div class="w-3 h-12 rounded-full" :style="{ background: g.color }"></div>
              <div>
                <div class="text-xs text-slate-400">{{ g.name }}（{{ g.range }}）</div>
                <div class="text-xl font-bold" :style="{ color: g.color }">{{ g.count }} 台</div>
              </div>
            </div>
          </div>

          <div class="text-sm text-slate-500 mb-2 flex items-center gap-2">
            <el-icon><Warning /></el-icon> 健康度排名最差 Top 10 设备（建议优先维保）
          </div>
          <el-empty v-if="!rulRanking.length" description="暂无可评分设备" />
          <el-table v-else :data="rulRanking" stripe max-height="560">
            <el-table-column prop="rank" label="排名" width="70" align="center">
              <template #default="{ row }">
                <el-tag :type="row.rank <= 3 ? 'danger' : 'info'" effect="dark" round>{{ row.rank }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="device_name" label="设备名称" min-width="180" />
            <el-table-column prop="building_name" label="所属建筑" width="140" />
            <el-table-column prop="health_score" label="健康度" width="120" sortable>
              <template #default="{ row }">
                <el-progress :percentage="row.health_score" :color="row.color" :stroke-width="10" :text-inside="true" />
              </template>
            </el-table-column>
            <el-table-column prop="grade_name" label="分级" width="90">
              <template #default="{ row }">
                <el-tag :style="{ background: row.color, color: '#fff', border: 'none' }" effect="dark" round>{{ row.grade_name }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="COP" width="100">
              <template #default="{ row }">
                <span class="font-mono">{{ row.current_cop ?? '-' }} / {{ row.nominal_cop }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="fault_count_30d" label="30天故障" width="90" align="center" />
            <el-table-column prop="worst_dimension" label="主要扣分项" width="120">
              <template #default="{ row }">
                <el-tag size="small" type="warning">{{ dimensionName(row.worst_dimension) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="primary" link @click="viewRulDetail(row.device_id)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- Tab 2: 能耗基准对标 -->
      <el-tab-pane v-if="category === 'diagnose'" label="📊 能耗基准对标" name="benchmark">
        <div v-loading="benchmarkLoading">
          <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <StatCard label="建筑总数" :value="benchmarkSummary.total_buildings || 0" color="indigo" />
            <StatCard label="平均能耗强度" :value="(benchmarkSummary.avg_intensity || 0) + ' kWh/㎡·年'" color="amber" />
            <StatCard label="年化总能耗" :value="formatKwh(benchmarkSummary.total_annual_kwh)" color="rose" />
            <StatCard label="总节能潜力" :value="formatKwh(benchmarkSummary.total_saving_potential_kwh)" color="emerald" />
          </div>

          <!-- 评级分布 -->
          <div v-if="benchmarkGrades.length" class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <div v-for="g in benchmarkGrades" :key="g.grade" class="bg-white rounded-xl p-3 border border-slate-100 shadow-sm flex items-center gap-3">
              <div class="w-3 h-12 rounded-full" :style="{ background: g.color }"></div>
              <div>
                <div class="text-xs text-slate-400">{{ g.name }}（{{ g.grade }}）</div>
                <div class="text-xl font-bold" :style="{ color: g.color }">{{ g.count }} 栋</div>
              </div>
            </div>
          </div>

          <div ref="benchmarkChartRef" class="w-full h-80 bg-white rounded-xl border border-slate-100 p-3 mb-4"></div>

          <el-empty v-if="!benchmarkBuildings.length" description="暂无对标数据" />
          <el-table v-else :data="benchmarkBuildings" stripe max-height="500">
            <el-table-column prop="building_name" label="建筑名称" min-width="160" />
            <el-table-column prop="building_type_name" label="类型" width="100" />
            <el-table-column prop="total_area" label="面积(㎡)" width="100" align="right" />
            <el-table-column prop="annual_kwh" label="年能耗(kWh)" width="130" align="right" sortable />
            <el-table-column prop="intensity" label="强度(kWh/㎡·年)" width="150" align="right" sortable>
              <template #default="{ row }">
                <span :class="['font-bold', row.intensity > row.standard?.limit ? 'text-rose-500' : 'text-emerald-600']">{{ row.intensity }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="grade_name" label="评级" width="90">
              <template #default="{ row }">
                <el-tag :style="{ background: row.color, color: '#fff', border: 'none' }" effect="dark" round>{{ row.grade }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="saving_potential_kwh" label="节能潜力(kWh/年)" width="150" align="right" sortable>
              <template #default="{ row }">
                <span class="text-cyan-600 font-medium">{{ row.saving_potential_kwh?.toLocaleString() }}</span>
              </template>
            </el-table-column>
            <el-table-column label="基准标准" min-width="180">
              <template #default="{ row }">
                <span class="text-xs text-slate-500">限额{{ row.standard?.limit }} / 先进{{ row.standard?.advanced }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- Tab 3: 多能耦合优化 -->
      <el-tab-pane v-if="category === 'diagnose'" label="⚡ 多能耦合优化" name="multi_energy">
        <div v-loading="multiEnergyLoading">
          <!-- 实时概览 -->
          <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <StatCard label="当前时段" :value="multiEnergyOverview.period_name || '-'" color="indigo" />
            <StatCard label="电价" :value="(multiEnergyOverview.price || 0) + ' 元/kWh'" color="amber" />
            <StatCard label="当前负荷" :value="((multiEnergyOverview.energy_flow?.electricity?.total_load_kw) || 0) + ' kW'" color="rose" />
            <StatCard label="光伏出力" :value="((multiEnergyOverview.energy_flow?.electricity?.pv_generation_kw) || 0) + ' kW'" color="emerald" />
          </div>

          <!-- 能源耦合流向 -->
          <div v-if="multiEnergyOverview.coupling_efficiency" class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <div class="bg-white rounded-xl p-3 border border-slate-100 shadow-sm">
              <div class="text-xs text-slate-400">制冷 COP</div>
              <div class="text-lg font-bold text-cyan-600">{{ multiEnergyOverview.coupling_efficiency.cooling_cop }}</div>
            </div>
            <div class="bg-white rounded-xl p-3 border border-slate-100 shadow-sm">
              <div class="text-xs text-slate-400">制热效率</div>
              <div class="text-lg font-bold text-orange-500">{{ multiEnergyOverview.coupling_efficiency.heating_efficiency }}</div>
            </div>
            <div class="bg-white rounded-xl p-3 border border-slate-100 shadow-sm">
              <div class="text-xs text-slate-400">光伏自用率</div>
              <div class="text-lg font-bold text-emerald-600">{{ multiEnergyOverview.coupling_efficiency.pv_utilization_pct }}%</div>
            </div>
            <div class="bg-white rounded-xl p-3 border border-slate-100 shadow-sm">
              <div class="text-xs text-slate-400">可再生能源占比</div>
              <div class="text-lg font-bold text-indigo-600">{{ multiEnergyOverview.coupling_efficiency.renewable_ratio_pct }}%</div>
            </div>
          </div>

          <!-- 调度方案图表 -->
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
            <div ref="multiEnergyScheduleRef" class="w-full h-80 bg-white rounded-xl border border-slate-100 p-3"></div>
            <div ref="multiEnergyComparisonRef" class="w-full h-80 bg-white rounded-xl border border-slate-100 p-3"></div>
          </div>

          <!-- 优化对比摘要 -->
          <div v-if="multiEnergyComparison.comparison" class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <StatCard label="日节省电费" :value="(multiEnergyComparison.comparison.cost_saving_yuan || 0) + ' 元'" color="emerald" />
            <StatCard label="节省比例" :value="(multiEnergyComparison.comparison.cost_saving_rate_pct || 0) + '%'" color="indigo" />
            <StatCard label="日减排 CO₂" :value="(multiEnergyComparison.comparison.carbon_reduction_t || 0) + ' t'" color="cyan" />
            <StatCard label="削峰能力" :value="(multiEnergyComparison.comparison.peak_shaving_kw || 0) + ' kW'" color="rose" />
          </div>

          <div v-if="multiEnergyComparison.conclusion" class="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-sm text-emerald-800">
            <el-icon class="mr-1"><CircleCheckFilled /></el-icon>{{ multiEnergyComparison.conclusion }}
          </div>
        </div>
      </el-tab-pane>

      <!-- ========== 分类2-运营管理 ========== -->
      <!-- Tab 4: 智能告警中心 -->
      <el-tab-pane v-if="category === 'ops'" label="🚨 智能告警中心" name="alert">
        <div v-loading="alertLoading">
          <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <StatCard label="活跃告警" :value="alertStats.active_count || 0" color="rose" />
            <StatCard label="紧急告警" :value="alertStats.critical_count || 0" color="rose" />
            <StatCard label="今日新增" :value="alertStats.today_count || 0" color="amber" />
            <StatCard label="已恢复" :value="alertStats.resolved_count || 0" color="emerald" />
          </div>

          <!-- 推送渠道配置 -->
          <div class="bg-white rounded-xl border border-slate-100 p-4 mb-4">
            <div class="flex items-center justify-between mb-3">
              <span class="font-bold text-slate-700 flex items-center gap-2"><el-icon><Bell /></el-icon> 推送渠道</span>
              <el-button size="small" type="primary" @click="testPush" :loading="pushTesting">发送测试推送</el-button>
            </div>
            <div class="flex items-center gap-4 flex-wrap">
              <el-switch v-model="alertChannels.sms_enabled" active-text="短信" @change="saveChannels" />
              <el-switch v-model="alertChannels.email_enabled" active-text="邮件" @change="saveChannels" />
              <el-switch v-model="alertChannels.inapp_enabled" active-text="站内信" @change="saveChannels" />
            </div>
          </div>

          <!-- 筛选 -->
          <div class="flex items-center gap-3 mb-4 flex-wrap">
            <el-select v-model="alertFilter.level" placeholder="级别" clearable style="width: 120px" @change="loadAlerts">
              <el-option label="紧急" value="critical" />
              <el-option label="重要" value="important" />
              <el-option label="普通" value="normal" />
            </el-select>
            <el-select v-model="alertFilter.status" placeholder="状态" clearable style="width: 120px" @change="loadAlerts">
              <el-option label="活跃" value="active" />
              <el-option label="已确认" value="acknowledged" />
              <el-option label="已静默" value="silenced" />
              <el-option label="已恢复" value="resolved" />
            </el-select>
          </div>

          <el-empty v-if="!alertList.length" description="暂无告警" />
          <el-table v-else :data="alertList" stripe max-height="500">
            <el-table-column prop="level" label="级别" width="90">
              <template #default="{ row }">
                <el-tag :type="row.level === 'critical' ? 'danger' : row.level === 'important' ? 'warning' : 'info'" effect="dark" round>{{ levelLabel(row.level) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="title" label="告警标题" min-width="200" show-overflow-tooltip />
            <el-table-column prop="device_name" label="设备" min-width="150" show-overflow-tooltip />
            <el-table-column prop="source" label="来源" width="110">
              <template #default="{ row }">
                <el-tag size="small" type="info">{{ sourceLabel(row.source) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="触发时间" width="160" />
            <el-table-column label="操作" width="180" fixed="right">
              <template #default="{ row }">
                <el-button v-if="row.status === 'active'" size="small" type="primary" link @click="ackAlert(row.id)">确认</el-button>
                <el-button v-if="row.status !== 'silenced' && row.status !== 'resolved'" size="small" type="warning" link @click="silenceAlertRow(row.id)">静默1h</el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="flex justify-end mt-3">
            <el-pagination v-model:current-page="alertFilter.page" :page-size="20" :total="alertTotal" layout="prev, pager, next" @current-change="loadAlerts" />
          </div>
        </div>
      </el-tab-pane>

      <!-- Tab 5: 能源审计报告 -->
      <el-tab-pane v-if="category === 'ops'" label="📝 能源审计报告" name="audit">
        <div v-loading="auditLoading">
          <div class="flex items-center gap-3 mb-4 flex-wrap">
            <el-select v-model="auditBuildingId" placeholder="选择建筑" style="width: 280px" @change="loadAuditReport">
              <el-option v-for="b in auditBuildings" :key="b.building_id" :label="b.building_name" :value="b.building_id" />
            </el-select>
            <el-button type="success" @click="exportAudit" :loading="auditExporting" :disabled="!auditBuildingId">
              <el-icon class="mr-1"><Download /></el-icon> 导出 Word 报告
            </el-button>
          </div>

          <el-empty v-if="!auditReport" description="请选择建筑生成审计报告" />
          <template v-else>
            <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
              <StatCard label="审计期间" :value="auditReport.audit_period?.days + ' 天'" color="indigo" />
              <StatCard label="总能耗" :value="formatKwh(auditReport.energy_overview?.total_kwh)" color="rose" />
              <StatCard label="能耗强度" :value="(auditReport.energy_overview?.energy_intensity_kwh_per_m2 || 0) + ' kWh/㎡'" color="amber" />
              <StatCard label="评级" :value="auditReport.energy_overview?.comparison?.rating_name || '-'" color="emerald" />
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
              <div ref="auditTrendRef" class="w-full h-80 bg-white rounded-xl border border-slate-100 p-3"></div>
              <div ref="auditBreakdownRef" class="w-full h-80 bg-white rounded-xl border border-slate-100 p-3"></div>
            </div>

            <div v-if="auditReport.suggestions?.length" class="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <div class="font-bold text-amber-800 mb-2 flex items-center gap-2"><el-icon><MagicStick /></el-icon> 节能改造建议</div>
              <ul class="text-sm text-amber-700 space-y-1 list-disc list-inside">
                <li v-for="(s, i) in auditReport.suggestions" :key="i">{{ s }}</li>
              </ul>
            </div>
          </template>
        </div>
      </el-tab-pane>

      <!-- Tab 6: 工单全生命周期增强 -->
      <el-tab-pane v-if="category === 'ops'" label="🔧 工单全生命周期" name="workorder">
        <div v-loading="workorderLoading">
          <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <StatCard label="活跃工单" :value="slaStats.active_count || 0" color="indigo" />
            <StatCard label="按时完成率" :value="(slaStats.on_time_rate || 0) + '%'" :color="(slaStats.on_time_rate || 0) >= 90 ? 'emerald' : 'rose'" />
            <StatCard label="超时工单" :value="slaStats.overdue_count || 0" color="rose" />
            <StatCard label="平均处理时长" :value="(slaStats.avg_handle_hours || 0) + ' h'" color="amber" />
          </div>

          <el-tabs v-model="workorderSubTab" class="mb-4">
            <el-tab-pane label="工单列表" name="list">
              <el-empty v-if="!workorderList.length" description="暂无工单" />
              <el-table v-else :data="workorderList" stripe max-height="500">
                <el-table-column prop="order_id" label="工单号" width="140" />
                <el-table-column prop="diagnosis_title" label="标题" min-width="180" show-overflow-tooltip />
                <el-table-column prop="priority" label="优先级" width="80">
                  <template #default="{ row }">
                    <el-tag :type="priorityTagType(row.priority)" size="small" effect="dark">{{ row.priority || 'P2' }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="assignee_name" label="负责人" width="100">
                  <template #default="{ row }">{{ row.assignee_name || '-' }}</template>
                </el-table-column>
                <el-table-column prop="sla_status" label="SLA状态" width="100">
                  <template #default="{ row }">
                    <el-tag :type="row.sla_status === 'overdue' ? 'danger' : row.sla_status === 'soon' ? 'warning' : 'success'" size="small">{{ slaStatusLabel(row.sla_status) }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="status" label="状态" width="100" />
                <el-table-column prop="created_at" label="创建时间" width="160" />
                <el-table-column label="操作" width="120" fixed="right">
                  <template #default="{ row }">
                    <el-button size="small" type="primary" link @click="dispatchOrder(row.order_id)">智能派单</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>
            <el-tab-pane label="备件库存" name="parts">
              <el-empty v-if="!partsList.length" description="暂无备件数据" />
              <el-table v-else :data="partsList" stripe>
                <el-table-column prop="part_id" label="编号" width="100" />
                <el-table-column prop="part_name" label="备件名称" min-width="180" />
                <el-table-column prop="category" label="类别" width="120" />
                <el-table-column prop="stock_qty" label="库存" width="80" align="right" />
                <el-table-column prop="min_stock" label="安全库存" width="100" align="right" />
                <el-table-column label="状态" width="100">
                  <template #default="{ row }">
                    <el-tag :type="row.stock_qty < row.min_stock ? 'danger' : 'success'" size="small">{{ row.stock_qty < row.min_stock ? '需补货' : '正常' }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="location" label="存放位置" width="120" />
              </el-table>
            </el-tab-pane>
          </el-tabs>
        </div>
      </el-tab-pane>

      <!-- ========== 分类3-ESG与投资决策 ========== -->
      <!-- Tab 7: ESG 报告 -->
      <el-tab-pane v-if="category === 'esg'" label="🌍 ESG 报告" name="esg">
        <div v-loading="esgLoading">
          <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <StatCard label="ESG 总分" :value="(esgOverview.total_score || 0) + ' 分'" :color="esgGradeColor" />
            <StatCard label="评级" :value="esgOverview.grade?.name || '-'" :color="esgGradeColor" />
            <StatCard label="E 环境" :value="((esgOverview.dimensions?.E?.score) || 0) + ' 分'" color="emerald" />
            <StatCard label="S 社会 / G 治理" :value="((esgOverview.dimensions?.S?.score) || 0) + ' / ' + ((esgOverview.dimensions?.G?.score) || 0)" color="indigo" />
          </div>

          <div ref="esgRadarRef" class="w-full h-80 bg-white rounded-xl border border-slate-100 p-3 mb-4"></div>
          <div ref="esgTrendRef" class="w-full h-80 bg-white rounded-xl border border-slate-100 p-3 mb-4"></div>

          <!-- ESG 维度详情卡片 -->
          <div v-if="esgReport?.dimensions" class="grid grid-cols-1 lg:grid-cols-3 gap-3 mb-4">
            <div v-for="(dim, key) in esgReport.dimensions" :key="key" class="bg-white rounded-xl border border-slate-100 p-4">
              <div class="flex items-center justify-between mb-2">
                <div class="font-bold text-slate-700">{{ dim.name }}（{{ key }}）</div>
                <el-tag :color="dim.score >= 80 ? '#52c41a' : (dim.score >= 60 ? '#faad14' : '#ff4d4f')" effect="dark" round>
                  {{ dim.score }} 分
                </el-tag>
              </div>
              <div class="text-xs text-slate-400 mb-2">权重 {{ (dim.weight * 100).toFixed(0) }}% ｜ {{ dim.description }}</div>
              <!-- 关键子指标 -->
              <div v-if="dim.metrics" class="space-y-1.5">
                <div v-for="(val, mk) in dimMetricsBrief(dim.metrics, key)" :key="mk" class="flex items-center justify-between text-xs">
                  <span class="text-slate-600">{{ val.label }}</span>
                  <span :class="val.warn ? 'text-rose-500 font-bold' : 'text-slate-700'">{{ val.text }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- G 维度工单完成率详情 -->
          <div v-if="esgWorkorderInfo" class="bg-indigo-50 border border-indigo-200 rounded-xl p-4 mb-4 text-sm text-indigo-800 flex items-center gap-3">
            <el-icon class="text-lg"><CircleCheckFilled /></el-icon>
            <div>
              <div class="font-bold">G 治理 - 工单完成率（真实数据）</div>
              <div class="text-xs mt-1">
                近 {{ esgOverview.period_days || 30 }} 天共 {{ esgWorkorderInfo.total }} 单，
                已完成 {{ esgWorkorderInfo.completed }} 单，
                完成率 <b>{{ (esgWorkorderInfo.completion_rate * 100).toFixed(1) }}%</b>，
                平均处理时长 <b>{{ esgWorkorderInfo.avg_hours }} 小时</b>
                <el-tag v-if="esgWorkorderInfo.source === 'real'" type="success" size="small" class="ml-2">真实数据</el-tag>
                <el-tag v-else type="warning" size="small" class="ml-2">模拟</el-tag>
              </div>
            </div>
          </div>

          <!-- ESG 报告结论 -->
          <div v-if="esgReport?.conclusion" class="bg-emerald-50 border border-emerald-200 rounded-xl p-4 mb-4 text-sm text-emerald-800 flex items-start gap-2">
            <el-icon class="mt-0.5"><MagicStick /></el-icon>
            <div>{{ esgReport.conclusion }}</div>
          </div>

          <div v-if="esgReport?.standards" class="bg-slate-50 rounded-xl p-4 text-xs text-slate-500">
            报告标准：{{ esgReport.standards.join('、') }} ｜ 数据周期：近 {{ esgOverview.period_days || 30 }} 天 ｜ 生成时间：{{ esgReport.generated_at }}
          </div>
        </div>
      </el-tab-pane>

      <!-- Tab 7.5: ESG 碳排放与对标 -->
      <el-tab-pane v-if="category === 'esg'" label="🏭 碳排放与对标" name="esg_carbon">
        <div v-loading="esgCarbonLoading">
          <!-- 建筑碳排放明细 -->
          <div class="font-bold text-slate-700 mb-2 flex items-center gap-2"><el-icon><Histogram /></el-icon> 建筑碳排放明细（帕累托分析）</div>
          <div v-if="esgCarbonData?.total_carbon_kg" class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
            <StatCard label="总碳排放" :value="formatKwh(esgCarbonData.total_carbon_kg, 'kg')" color="rose" />
            <StatCard label="建筑数量" :value="esgCarbonData.total_buildings + ' 栋'" color="indigo" />
            <StatCard label="排放最多的建筑" :value="esgCarbonData.buildings?.[0]?.building_name || '-'" color="amber" />
            <StatCard label="最大占比" :value="(esgCarbonData.buildings?.[0]?.carbon_pct || 0) + '%'" color="rose" />
          </div>

          <div ref="esgCarbonParetoRef" class="w-full h-96 bg-white rounded-xl border border-slate-100 p-3 mb-4"></div>

          <el-empty v-if="!esgCarbonData?.buildings?.length" description="暂无碳排放数据" />
          <el-table v-else :data="esgCarbonData.buildings" stripe max-height="500" size="small">
            <el-table-column prop="rank" label="排名" width="70" align="center">
              <template #default="{ row }">
                <el-tag :type="row.priority === 'high' ? 'danger' : (row.priority === 'medium' ? 'warning' : 'info')" effect="dark" round size="small">{{ row.rank }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="building_name" label="建筑名称" min-width="160" />
            <el-table-column prop="building_type" label="类型" width="100" />
            <el-table-column prop="total_kwh" label="总能耗(kWh)" width="120" align="right" sortable />
            <el-table-column prop="carbon_kg" label="碳排放(kg)" width="120" align="right" sortable />
            <el-table-column prop="carbon_pct" label="占比%" width="90" align="right" sortable>
              <template #default="{ row }">
                <span class="font-bold" :class="row.carbon_pct > 20 ? 'text-rose-500' : ''">{{ row.carbon_pct }}%</span>
              </template>
            </el-table-column>
            <el-table-column prop="cumulative_pct" label="累计%" width="90" align="right" />
            <el-table-column prop="carbon_intensity_kg_per_m2" label="强度(kgCO2/㎡·年)" width="160" align="right" sortable />
            <el-table-column prop="annual_carbon_kg" label="年化排放(kg)" width="130" align="right" sortable />
            <el-table-column label="优先级" width="90">
              <template #default="{ row }">
                <el-tag :type="row.priority === 'high' ? 'danger' : (row.priority === 'medium' ? 'warning' : 'success')" size="small">
                  {{ row.priority === 'high' ? '高' : (row.priority === 'medium' ? '中' : '低') }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>

          <!-- 行业对标 -->
          <div class="mt-6 font-bold text-slate-700 mb-2 flex items-center gap-2"><el-icon><TrendCharts /></el-icon> 行业对标分析</div>
          <div v-if="esgBenchmark?.overall_score" class="grid grid-cols-2 lg:grid-cols-3 gap-3 mb-3">
            <StatCard label="总体对标得分" :value="esgBenchmark.overall_score + ' 分'" :color="esgBenchmark.overall_level === '领先' ? 'emerald' : (esgBenchmark.overall_level === '平均' ? 'amber' : 'rose')" />
            <StatCard label="对标等级" :value="esgBenchmark.overall_level" :color="esgBenchmark.overall_level === '领先' ? 'emerald' : (esgBenchmark.overall_level === '平均' ? 'amber' : 'rose')" />
            <StatCard label="参考标准" :value="esgBenchmark.standards_reference?.includes('GB') ? '国标' : '行业'" color="indigo" />
          </div>

          <div ref="esgBenchmarkRef" class="w-full h-96 bg-white rounded-xl border border-slate-100 p-3 mb-4"></div>

          <el-empty v-if="!esgBenchmark?.benchmarks?.length" description="暂无对标数据" />
          <el-table v-else :data="esgBenchmark.benchmarks" stripe size="small">
            <el-table-column prop="metric_name" label="指标" min-width="140" />
            <el-table-column label="当前值" width="120" align="right">
              <template #default="{ row }">
                <span class="font-bold">{{ row.actual_value }} {{ row.unit }}</span>
              </template>
            </el-table-column>
            <el-table-column label="先进值" width="100" align="right">
              <template #default="{ row }">{{ row.benchmark.advanced }} {{ row.unit }}</template>
            </el-table-column>
            <el-table-column label="平均值" width="100" align="right">
              <template #default="{ row }">{{ row.benchmark.average }} {{ row.unit }}</template>
            </el-table-column>
            <el-table-column label="落后值" width="100" align="right">
              <template #default="{ row }">{{ row.benchmark.laggard }} {{ row.unit }}</template>
            </el-table-column>
            <el-table-column prop="score" label="对标得分" width="100" align="center" sortable>
              <template #default="{ row }">
                <el-progress :percentage="row.score" :color="row.score >= 85 ? '#52c41a' : (row.score >= 55 ? '#faad14' : '#ff4d4f')" :stroke-width="10" :text-inside="true" />
              </template>
            </el-table-column>
            <el-table-column label="等级" width="80">
              <template #default="{ row }">
                <el-tag :type="row.level === '领先' ? 'success' : (row.level === '平均' ? 'warning' : 'danger')" size="small">{{ row.level }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="距先进值差距" width="120" align="right">
              <template #default="{ row }">
                <span :class="row.gap_to_advanced > 0 ? 'text-rose-500' : 'text-emerald-500'">
                  {{ row.gap_to_advanced > 0 ? '+' : '' }}{{ row.gap_to_advanced }} {{ row.unit }}
                </span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- Tab 7.6: ESG 改进建议 -->
      <el-tab-pane v-if="category === 'esg'" label="💡 ESG 改进建议" name="esg_advice">
        <div v-loading="esgAdviceLoading">
          <div v-if="esgAdvice?.potential_total_score" class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <StatCard label="当前 ESG 总分" :value="esgAdvice.current_total_score + ' 分'" color="amber" />
            <StatCard label="潜在最高分" :value="esgAdvice.potential_total_score + ' 分'" color="emerald" />
            <StatCard label="预期提升" :value="'+' + esgAdvice.total_improvement + ' 分'" color="cyan" />
            <StatCard label="改进点数" :value="esgAdvice.recommendations_count + ' 项'" color="indigo" />
          </div>

          <div v-if="esgAdvice?.summary" class="bg-cyan-50 border border-cyan-200 rounded-xl p-4 mb-4 text-sm text-cyan-800 flex items-start gap-2">
            <el-icon class="mt-0.5"><MagicStick /></el-icon>
            <div>{{ esgAdvice.summary }}</div>
          </div>

          <el-empty v-if="!esgAdvice?.recommendations?.length" description="暂无改进建议" />
          <div v-else class="space-y-3">
            <div v-for="(rec, idx) in esgAdvice.recommendations" :key="idx" class="bg-white rounded-xl border border-slate-100 p-4 shadow-sm">
              <div class="flex items-start justify-between mb-2">
                <div class="flex-1">
                  <div class="flex items-center gap-2 mb-1">
                    <el-tag :type="rec.dimension === 'E' ? 'success' : (rec.dimension === 'S' ? 'warning' : 'primary')" effect="dark" size="small">{{ rec.dimension_name }}</el-tag>
                    <span class="font-bold text-slate-700">{{ rec.title }}</span>
                    <el-tag :type="rec.priority === 'high' ? 'danger' : (rec.priority === 'medium' ? 'warning' : 'info')" size="small">{{ rec.priority === 'high' ? '高优先级' : (rec.priority === 'medium' ? '中优先级' : '低优先级') }}</el-tag>
                  </div>
                  <div class="text-xs text-rose-500 mb-2">{{ rec.issue }}</div>
                </div>
                <div class="text-right ml-4">
                  <div class="text-xs text-slate-400">得分提升</div>
                  <div class="text-emerald-600 font-bold text-lg">+{{ rec.expected_improvement }} 分</div>
                  <div class="text-xs text-slate-400 mt-1">{{ rec.current_score }} → {{ rec.target_score }}</div>
                </div>
              </div>
              <div class="text-xs text-slate-600">
                <div class="text-slate-400 mb-1">改进措施（实施难度：{{ rec.difficulty }}）：</div>
                <ul class="list-disc list-inside space-y-0.5">
                  <li v-for="(act, ai) in rec.actions" :key="ai">{{ act }}</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- Tab 8: ROI 测算 -->
      <el-tab-pane v-if="category === 'esg'" label="💰 ROI 测算" name="roi">
        <div v-loading="roiLoading">
          <div class="bg-white rounded-xl border border-slate-100 p-4 mb-4">
            <div class="font-bold text-slate-700 mb-3 flex items-center gap-2"><el-icon><Coin /></el-icon> 节能改造方案测算（增强版：含 IRR / 衰减率 / 运维成本）</div>
            <div class="grid grid-cols-1 md:grid-cols-4 gap-3 mb-3">
              <el-select v-model="roiForm.scenario_id" placeholder="选择改造方案" @change="onScenarioChange">
                <el-option v-for="s in roiScenarios" :key="s.scenario_id" :label="s.scenario_name" :value="s.scenario_id" />
              </el-select>
              <el-select v-model="roiForm.building_id" placeholder="选择建筑">
                <el-option v-for="b in benchmarkBuildings" :key="b.building_id" :label="b.building_name" :value="b.building_id" />
              </el-select>
              <el-button type="primary" @click="calcRoi" :loading="roiCalculating" :disabled="!roiForm.scenario_id || !roiForm.building_id">
                <el-icon class="mr-1"><Histogram /></el-icon> 开始测算
              </el-button>
              <el-button @click="roiCompareVisible = true; roiCompareResult = null">
                <el-icon class="mr-1"><DataAnalysis /></el-icon> 方案对比
              </el-button>
            </div>

            <!-- 操作按钮组：敏感性分析、风险评估、组合优化 -->
            <div v-if="roiResult" class="flex items-center gap-2 flex-wrap mb-3">
              <el-button size="small" type="success" @click="loadSensitivity" :loading="sensitivityLoading">
                <el-icon class="mr-1"><TrendCharts /></el-icon> 敏感性分析
              </el-button>
              <el-button size="small" type="warning" @click="loadRiskAssessment" :loading="riskLoading">
                <el-icon class="mr-1"><Warning /></el-icon> 风险评估
              </el-button>
              <el-button size="small" type="primary" @click="portfolioVisible = true; portfolioResult = null">
                <el-icon class="mr-1"><Coin /></el-icon> 组合优化
              </el-button>
            </div>

            <!-- 方案对比对话框 -->
            <el-dialog v-model="roiCompareVisible" title="节能改造方案对比分析" width="90%" top="5vh">
              <div class="mb-4">
                <div class="flex items-center gap-3 mb-3">
                  <el-select v-model="roiCompareBuilding" placeholder="选择建筑" style="width: 200px">
                    <el-option v-for="b in benchmarkBuildings" :key="b.building_id" :label="b.building_name" :value="b.building_id" />
                  </el-select>
                  <el-button type="primary" @click="runRoiCompare" :loading="roiCompareLoading"
                    :disabled="!roiCompareBuilding || roiCompareSelected.length < 2">
                    开始对比
                  </el-button>
                  <span class="text-xs text-slate-400">已选 {{ roiCompareSelected.length }} 个方案</span>
                </div>
                <el-checkbox-group v-model="roiCompareSelected" class="flex flex-wrap gap-2">
                  <el-checkbox v-for="s in roiScenarios" :key="s.scenario_id" :label="s.scenario_id">
                    {{ s.scenario_name }}
                  </el-checkbox>
                </el-checkbox-group>
              </div>

              <div v-if="roiCompareResult">
                <el-alert v-if="roiCompareResult.best_scenario" type="success" :closable="false" class="mb-4">
                  推荐方案：{{ roiCompareResult.best_scenario.scenario_name }}（ROI {{ roiCompareResult.best_scenario.roi_pct }}%，回收期 {{ roiCompareResult.best_scenario.payback_years }} 年）
                </el-alert>
                <el-table :data="roiCompareResult.comparisons" border stripe size="small">
                  <el-table-column prop="scenario_name" label="方案" min-width="120" />
                  <el-table-column prop="category" label="类型" width="80" />
                  <el-table-column label="投资额" width="100">
                    <template #default="{ row }">{{ formatMoney(row.investment_yuan) }}</template>
                  </el-table-column>
                  <el-table-column label="年节省电费" width="110">
                    <template #default="{ row }">{{ formatMoney(row.annual_saving_cost_yuan) }}</template>
                  </el-table-column>
                  <el-table-column label="回收期(年)" width="100">
                    <template #default="{ row }">{{ row.payback_years != null ? row.payback_years.toFixed(1) : '—' }}</template>
                  </el-table-column>
                  <el-table-column label="ROI%" width="80">
                    <template #default="{ row }">
                      <span :class="row.roi_pct > 0 ? 'text-emerald-600 font-bold' : 'text-rose-600'">{{ row.roi_pct }}%</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="IRR%" width="80">
                    <template #default="{ row }">
                      <span :class="row.irr_pct != null && row.irr_pct > 0 ? 'text-emerald-600' : 'text-rose-600'">{{ row.irr_pct != null ? row.irr_pct + '%' : '—' }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="NPV" width="100">
                    <template #default="{ row }">{{ formatMoney(row.npv_yuan) }}</template>
                  </el-table-column>
                  <el-table-column label="年减排CO₂(kg)" width="120">
                    <template #default="{ row }">{{ row.annual_carbon_reduction_kg?.toFixed(0) || '—' }}</template>
                  </el-table-column>
                  <el-table-column label="总减排CO₂(kg)" width="120">
                    <template #default="{ row }">{{ row.total_carbon_reduction_kg?.toFixed(0) || '—' }}</template>
                  </el-table-column>
                </el-table>
              </div>
              <el-empty v-else description="选择建筑和至少 2 个方案后点击对比" />
            </el-dialog>

            <!-- 敏感性分析对话框 -->
            <el-dialog v-model="sensitivityVisible" title="ROI 敏感性分析（龙卷风图）" width="80%" top="5vh">
              <div v-loading="sensitivityLoading">
                <div v-if="sensitivityResult?.most_sensitive_label" class="mb-3">
                  <el-alert type="info" :closable="false">
                    最敏感变量：<b>{{ sensitivityResult.most_sensitive_label }}</b> ｜ 基准 ROI：<b>{{ sensitivityResult.base_results.roi_pct }}%</b> ｜ 基准 NPV：<b>{{ formatMoney(sensitivityResult.base_results.npv_yuan) }}</b>
                  </el-alert>
                </div>
                <div ref="sensitivityChartRef" class="w-full h-96 bg-slate-50 rounded-xl p-3"></div>
                <div v-if="sensitivityResult?.sensitivity" class="mt-4 space-y-3">
                  <div v-for="(s, key) in sensitivityResult.sensitivity" :key="key" class="bg-white border border-slate-100 rounded-lg p-3">
                    <div class="flex items-center justify-between mb-2">
                      <span class="font-bold text-slate-700">{{ s.label }}</span>
                      <span class="text-xs">敏感度系数：<b :class="Math.abs(s.sensitivity_coef) > 1 ? 'text-rose-500' : 'text-slate-600'">{{ s.sensitivity_coef }}</b></span>
                    </div>
                    <el-table :data="s.points" size="small" stripe>
                      <el-table-column prop="delta_pct" label="变化%" width="80" align="center">
                        <template #default="{ row }">
                          <el-tag :type="row.delta_pct > 0 ? 'success' : (row.delta_pct < 0 ? 'danger' : 'info')" size="small">{{ row.delta_pct > 0 ? '+' : '' }}{{ row.delta_pct }}%</el-tag>
                        </template>
                      </el-table-column>
                      <el-table-column prop="roi_pct" label="ROI%" width="80" align="right" />
                      <el-table-column label="NPV" width="120" align="right">
                        <template #default="{ row }">{{ formatMoney(row.npv_yuan) }}</template>
                      </el-table-column>
                      <el-table-column label="回收期(年)" width="100" align="right">
                        <template #default="{ row }">{{ row.payback_years != null ? row.payback_years.toFixed(1) : '—' }}</template>
                      </el-table-column>
                      <el-table-column label="IRR%" width="80" align="right">
                        <template #default="{ row }">{{ row.irr_pct != null ? row.irr_pct + '%' : '—' }}</template>
                      </el-table-column>
                    </el-table>
                  </div>
                </div>
              </div>
            </el-dialog>

            <!-- 风险评估对话框 -->
            <el-dialog v-model="riskVisible" title="方案风险评估" width="70%" top="8vh">
              <div v-loading="riskLoading">
                <div v-if="riskResult?.risk_level" class="mb-4">
                  <el-alert :type="riskResult.risk_level === '低' || riskResult.risk_level === '中低' ? 'success' : (riskResult.risk_level === '中' ? 'warning' : 'error')" :closable="false">
                    <div class="flex items-center gap-3">
                      <span>方案：<b>{{ riskResult.scenario_name }}</b></span>
                      <span>综合风险分：<b>{{ riskResult.composite_risk }}</b> / 5</span>
                      <el-tag :color="riskResult.risk_color" effect="dark" round>{{ riskResult.risk_level }}</el-tag>
                    </div>
                  </el-alert>
                </div>
                <div v-if="riskResult?.risk_scores" ref="riskRadarRef" class="w-full h-72 bg-slate-50 rounded-xl p-3 mb-4"></div>
                <div v-if="riskResult?.risk_factors" class="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div class="bg-rose-50 border border-rose-200 rounded-xl p-4">
                    <div class="font-bold text-rose-700 mb-2 flex items-center gap-1"><el-icon><Warning /></el-icon> 风险因素</div>
                    <ul class="list-disc list-inside text-sm text-rose-700 space-y-1">
                      <li v-for="(f, i) in riskResult.risk_factors" :key="i">{{ f }}</li>
                    </ul>
                  </div>
                  <div class="bg-emerald-50 border border-emerald-200 rounded-xl p-4">
                    <div class="font-bold text-emerald-700 mb-2 flex items-center gap-1"><el-icon><CircleCheckFilled /></el-icon> 缓解措施</div>
                    <ul class="list-disc list-inside text-sm text-emerald-700 space-y-1">
                      <li v-for="(m, i) in riskResult.mitigation_measures" :key="i">{{ m }}</li>
                    </ul>
                  </div>
                </div>
              </div>
            </el-dialog>

            <!-- 组合优化对话框 -->
            <el-dialog v-model="portfolioVisible" title="预算约束下的组合优化（背包算法）" width="85%" top="5vh">
              <div class="mb-4 flex items-center gap-3 flex-wrap">
                <el-select v-model="portfolioBuilding" placeholder="选择建筑" style="width: 200px">
                  <el-option v-for="b in benchmarkBuildings" :key="b.building_id" :label="b.building_name" :value="b.building_id" />
                </el-select>
                <el-input-number v-model="portfolioBudget" :min="10000" :step="100000" :controls="true" placeholder="预算上限（元）" style="width: 200px" />
                <el-button type="primary" @click="runPortfolio" :loading="portfolioLoading" :disabled="!portfolioBuilding || !portfolioBudget">
                  <el-icon class="mr-1"><Coin /></el-icon> 优化求解
                </el-button>
                <span class="text-xs text-slate-400">在给定预算内，从所有方案中选择 NPV 最大化的方案组合</span>
              </div>
              <div v-loading="portfolioLoading">
                <div v-if="portfolioResult?.summary" class="mb-4">
                  <el-alert type="success" :closable="false" class="mb-3">
                    {{ portfolioResult.recommendation }}
                  </el-alert>
                  <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
                    <StatCard label="总投资" :value="formatMoney(portfolioResult.summary.total_investment_yuan)" color="rose" />
                    <StatCard label="预算利用率" :value="portfolioResult.summary.budget_utilization_pct + '%'" color="cyan" />
                    <StatCard label="总 NPV" :value="formatMoney(portfolioResult.summary.total_npv_yuan)" :color="portfolioResult.summary.total_npv_yuan > 0 ? 'emerald' : 'rose'" />
                    <StatCard label="平均 ROI" :value="portfolioResult.summary.avg_roi_pct + '%'" color="indigo" />
                    <StatCard label="年节省电费" :value="formatMoney(portfolioResult.summary.total_annual_saving_yuan)" color="emerald" />
                    <StatCard label="年减排 CO₂" :value="formatKwh(portfolioResult.summary.total_annual_carbon_kg, 'kg')" color="indigo" />
                    <StatCard label="剩余预算" :value="formatMoney(portfolioResult.summary.remaining_budget_yuan)" color="amber" />
                    <StatCard label="选中方案数" :value="portfolioResult.summary.selected_count + ' 个'" color="indigo" />
                  </div>
                </div>
                <div v-if="portfolioResult?.selected?.length" class="mb-4">
                  <div class="font-bold text-emerald-700 mb-2 flex items-center gap-1"><el-icon><CircleCheckFilled /></el-icon> 推荐方案组合（{{ portfolioResult.selected.length }} 个）</div>
                  <el-table :data="portfolioResult.selected" border stripe size="small">
                    <el-table-column prop="scenario_name" label="方案" min-width="160" />
                    <el-table-column prop="category" label="类型" width="80" />
                    <el-table-column label="投资额" width="110" align="right">
                      <template #default="{ row }">{{ formatMoney(row.investment) }}</template>
                    </el-table-column>
                    <el-table-column label="NPV" width="110" align="right">
                      <template #default="{ row }">{{ formatMoney(row.npv) }}</template>
                    </el-table-column>
                    <el-table-column label="ROI%" width="80" align="right" />
                    <el-table-column label="IRR%" width="80" align="right">
                      <template #default="{ row }">{{ row.irr_pct != null ? row.irr_pct + '%' : '—' }}</template>
                    </el-table-column>
                    <el-table-column label="回收期(年)" width="100" align="right">
                      <template #default="{ row }">{{ row.payback_years != null ? row.payback_years.toFixed(1) : '—' }}</template>
                    </el-table-column>
                  </el-table>
                </div>
                <div v-if="portfolioResult?.not_selected?.length">
                  <div class="font-bold text-slate-500 mb-2 text-sm">未选中的方案（按 NPV 降序，前 5 个）</div>
                  <el-table :data="portfolioResult.not_selected" size="small" stripe>
                    <el-table-column prop="scenario_name" label="方案" min-width="160" />
                    <el-table-column label="投资额" width="110" align="right">
                      <template #default="{ row }">{{ formatMoney(row.investment) }}</template>
                    </el-table-column>
                    <el-table-column label="NPV" width="110" align="right">
                      <template #default="{ row }">{{ formatMoney(row.npv) }}</template>
                    </el-table-column>
                    <el-table-column label="ROI%" width="80" align="right" />
                  </el-table>
                </div>
                <el-empty v-else-if="!portfolioResult" description="选择建筑与预算后点击优化求解" />
              </div>
            </el-dialog>

            <div v-if="roiForm.scenario_id" class="text-xs text-slate-500">
              预期节能率：{{ currentScenario?.saving_rate != null ? (currentScenario.saving_rate * 100) + '%' : '不适用' }} ｜ 使用寿命：{{ currentScenario?.lifetime_years }} 年 ｜ 计价依据：{{ costBasisLabel(currentScenario?.cost_basis) }}
            </div>
          </div>

          <el-empty v-if="!roiResult" description="请选择方案和建筑后点击测算" />
          <template v-else>
            <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
              <StatCard label="投资额" :value="formatMoney(roiResult.results.investment_yuan)" color="rose" />
              <StatCard label="年节省电费" :value="formatMoney(roiResult.results.annual_saving_cost_yuan)" color="emerald" />
              <StatCard label="投资回收期" :value="roiResult.results.payback_years != null ? roiResult.results.payback_years + ' 年' : '无法回收'" color="amber" />
              <StatCard label="ROI" :value="roiResult.results.roi_pct + '%'" :color="roiResult.results.roi_pct > 0 ? 'emerald' : 'rose'" />
            </div>
            <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
              <StatCard label="IRR 内部收益率" :value="roiResult.results.irr_pct != null ? roiResult.results.irr_pct + '%' : '无法求解'" :color="roiResult.results.irr_pct != null && roiResult.results.irr_pct > 0 ? 'emerald' : 'rose'" />
              <StatCard label="NPV 净现值" :value="formatMoney(roiResult.results.npv_yuan)" :color="roiResult.results.npv_yuan > 0 ? 'emerald' : 'rose'" />
              <StatCard label="年运维成本" :value="formatMoney(roiResult.results.annual_om_cost_yuan)" color="slate" />
              <StatCard label="首年净收益" :value="formatMoney(roiResult.results.first_year_net_yuan)" :color="roiResult.results.first_year_net_yuan > 0 ? 'emerald' : 'rose'" />
            </div>
            <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
              <StatCard label="年节能量" :value="formatKwh(roiResult.results.annual_saving_kwh)" color="cyan" />
              <StatCard label="年减排 CO₂" :value="formatKwh(roiResult.results.annual_carbon_reduction_kg, 'kg')" color="indigo" />
              <StatCard label="总减排 CO₂" :value="formatKwh(roiResult.results.total_carbon_reduction_kg, 'kg')" color="indigo" />
              <StatCard label="衰减率/运维率" :value="(roiResult.results.decay_rate * 100) + '% / ' + (roiResult.results.om_rate * 100) + '%'" color="slate" />
            </div>

            <!-- 现金流图表 -->
            <div v-if="roiResult.cash_flows?.length" ref="cashflowChartRef" class="w-full h-80 bg-white rounded-xl border border-slate-100 p-3 mb-4"></div>

            <!-- 现金流明细表 -->
            <details class="bg-slate-50 rounded-xl p-3 mb-4">
              <summary class="cursor-pointer font-bold text-slate-700 mb-2">展开查看全生命周期现金流明细（{{ roiResult.cash_flows?.length || 0 }} 年）</summary>
              <el-table v-if="roiResult.cash_flows?.length" :data="roiResult.cash_flows" size="small" stripe max-height="400">
                <el-table-column prop="year" label="年份" width="70" align="center" />
                <el-table-column label="年毛收益" width="120" align="right">
                  <template #default="{ row }">{{ formatMoney(row.saving_gross) }}</template>
                </el-table-column>
                <el-table-column label="运维成本" width="120" align="right">
                  <template #default="{ row }">-{{ formatMoney(row.om_cost) }}</template>
                </el-table-column>
                <el-table-column label="年净现金流" width="130" align="right">
                  <template #default="{ row }">
                    <span :class="row.net_cash_flow > 0 ? 'text-emerald-600 font-bold' : 'text-rose-500'">{{ formatMoney(row.net_cash_flow) }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="累计现金流" width="140" align="right">
                  <template #default="{ row }">
                    <span :class="row.cumulative > 0 ? 'text-emerald-600' : 'text-rose-500'">{{ formatMoney(row.cumulative) }}</span>
                  </template>
                </el-table-column>
              </el-table>
            </details>

            <div class="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-sm text-emerald-800 flex items-center gap-2">
              <el-icon><CircleCheckFilled /></el-icon>
              {{ roiResult.building.building_name }} 实施 {{ roiResult.scenario.scenario_name }}，预计 {{ roiResult.results.payback_years != null ? roiResult.results.payback_years + ' 年回收投资' : '无法在生命周期内回收' }}，全生命周期 ROI {{ roiResult.results.roi_pct }}%{{ roiResult.results.irr_pct != null ? '，IRR ' + roiResult.results.irr_pct + '%' : '' }}。
            </div>
          </template>
        </div>
      </el-tab-pane>

      <!-- Tab 9: Web Push 推送服务 -->
      <el-tab-pane v-if="category === 'esg'" label="📲 Web Push 推送" name="push">
        <div v-loading="pushLoading">
          <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <StatCard label="订阅设备数" :value="pushSubsCount" color="indigo" />
            <StatCard label="历史推送数" :value="pushNotifications.length" color="cyan" />
            <StatCard label="浏览器支持" :value="pushSupported ? '支持' : '不支持'" :color="pushSupported ? 'emerald' : 'rose'" />
            <StatCard label="当前订阅" :value="pushSubscribed ? '已订阅' : '未订阅'" :color="pushSubscribed ? 'emerald' : 'amber'" />
          </div>

          <div class="bg-white rounded-xl border border-slate-100 p-4 mb-4">
            <div class="font-bold text-slate-700 mb-3 flex items-center gap-2"><el-icon><Promotion /></el-icon> 推送订阅管理</div>
            <div class="flex items-center gap-3 flex-wrap">
              <el-button v-if="!pushSubscribed" type="primary" @click="subscribePush" :disabled="!pushSupported" :loading="pushSubscribing">
                <el-icon class="mr-1"><Bell /></el-icon> 订阅推送通知
              </el-button>
              <el-button v-else type="danger" @click="unsubscribe" :loading="pushSubscribing">
                <el-icon class="mr-1"><CircleClose /></el-icon> 取消订阅
              </el-button>
              <el-button type="success" @click="sendTestPush" :disabled="!pushSubscribed" :loading="pushSending">
                <el-icon class="mr-1"><Position /></el-icon> 发送测试通知
              </el-button>
            </div>
            <div v-if="!pushSupported" class="mt-3 text-xs text-rose-500">
              当前浏览器不支持 Web Push API，请使用 Chrome/Edge 等现代浏览器。
            </div>
          </div>

          <div class="font-bold text-slate-700 mb-2 flex items-center gap-2"><el-icon><Message /></el-icon> 历史推送记录</div>
          <el-empty v-if="!pushNotifications.length" description="暂无推送记录" />
          <el-table v-else :data="pushNotifications" stripe max-height="400">
            <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
            <el-table-column prop="body" label="内容" min-width="240" show-overflow-tooltip />
            <el-table-column prop="created_at" label="推送时间" width="160" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">{{ row.status === 'success' ? '成功' : '失败' }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

    </el-tabs>

    <!-- RUL 设备详情抽屉 -->
    <el-drawer v-model="rulDrawerVisible" size="60%" :title="`设备健康度详情 - ${rulDetail?.device?.device_name || ''}`">
      <template v-if="rulDetail">
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
          <StatCard label="健康度总分" :value="rulDetail.health?.score + ' 分'" :color="healthColor(rulDetail.health?.score)" />
          <StatCard label="分级" :value="rulDetail.health?.grade_name" :color="healthColor(rulDetail.health?.score)" />
          <StatCard label="剩余寿命 RUL" :value="rulDetail.rul?.rul_days != null ? rulDetail.rul.rul_days + ' 天' : '数据不足'" color="amber" />
          <StatCard label="置信度" :value="confidenceLabel(rulDetail.rul?.confidence)" color="indigo" />
        </div>

        <div ref="rulTrendRef" class="w-full h-72 bg-white rounded-xl border border-slate-100 p-3 mb-4"></div>
        <div ref="rulCopTrendRef" class="w-full h-72 bg-white rounded-xl border border-slate-100 p-3 mb-4"></div>

        <!-- 健康度各维度 -->
        <div class="bg-white rounded-xl border border-slate-100 p-4 mb-4">
          <div class="font-bold text-slate-700 mb-3">健康度各维度评分</div>
          <div v-for="(dim, key) in rulDetail.health?.dimensions" :key="key" class="flex items-center gap-3 mb-2">
            <span class="w-28 text-sm text-slate-600">{{ dimensionName(key) }}</span>
            <el-progress :percentage="dim.score" :stroke-width="14" :text-inside="true" :color="healthColor(dim.score)" class="flex-1" />
            <span class="w-20 text-xs text-slate-400 text-right">权重 {{ (dim.weight * 100).toFixed(0) }}%</span>
          </div>
        </div>

        <div class="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800 mb-4">
          <el-icon class="mr-1"><MagicStick /></el-icon>{{ rulDetail.suggestion }}
        </div>

        <div v-if="rulDetail.recent_faults?.length" class="bg-white rounded-xl border border-slate-100 p-4">
          <div class="font-bold text-slate-700 mb-2">最近故障记录</div>
          <el-table :data="rulDetail.recent_faults" size="small">
            <el-table-column prop="time" label="时间" width="180" />
            <el-table-column prop="fault_code" label="故障码" width="120" />
            <el-table-column prop="run_status" label="运行状态" />
          </el-table>
        </div>
      </template>
    </el-drawer>

  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick, onMounted, onBeforeUnmount, defineComponent, h } from 'vue'
import * as echarts from 'echarts'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  fetchRulOverview, fetchRulRanking, fetchRulDeviceDetail,
  fetchBenchmarkOverview,
  fetchMultiEnergyOverview, fetchMultiEnergyOptimize, fetchMultiEnergyComparison,
  fetchAlertsCenter, fetchAlertsStats, acknowledgeAlert, silenceAlert, fetchAlertChannels, updateAlertChannels, testAlertPush,
  fetchAuditBuildings, fetchAuditReport, exportAuditReport,
  fetchWorkOrdersPro, fetchSlaStats, fetchPartsInventory, dispatchWorkOrder,
  fetchEsgOverview, fetchEsgReport, fetchEsgTrend, fetchEsgBuildingCarbon, fetchEsgBenchmark, fetchEsgRecommendations,
  fetchRoiScenarios, calculateRoi, compareRoiScenarios, analyzeRoiSensitivity, fetchRoiRiskAssessment, optimizeRoiPortfolio,
  fetchVapidPublicKey, subscribePush as subscribePushApi, fetchPushSubscriptions, unsubscribePush, sendPushNotification, fetchPushNotifications
} from '../api/index.js'

const props = defineProps({
  category: { type: String, default: 'diagnose' }
})

// ===== 分类配置 =====
const categories = [
  { value: 'diagnose', label: '能源诊断与优化', icon: '⚡' },
  { value: 'ops', label: '运营管理', icon: '🛠️' },
  { value: 'esg', label: 'ESG 与投资决策', icon: '🌍' }
]

const tabMap = {
  diagnose: 'rul',
  ops: 'alert',
  esg: 'esg'
}
const activeTab = ref(tabMap[props.category] || 'rul')
const refreshing = ref(false)

// 监听路由分类变化，重置 activeTab 并刷新数据
watch(() => props.category, (newCat) => {
  activeTab.value = tabMap[newCat] || 'rul'
  refreshAll()
}, { immediate: false })

// 等待容器可见后再渲染 ECharts（解决隐藏 Tab 容器尺寸为 0 导致图表挤压）
const waitForContainerAndRender = (refObj, renderFn, maxAttempts = 15) => {
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

// 监听 Tab 切换，延迟渲染对应图表（解决隐藏 Tab 容器尺寸为 0 的问题）
watch(activeTab, (newTab) => {
  nextTick(() => {
    setTimeout(() => {
      if (newTab === 'benchmark') waitForContainerAndRender(benchmarkChartRef, renderBenchmarkChart)
      else if (newTab === 'multi_energy') renderMultiEnergyCharts()
      else if (newTab === 'audit') renderAuditCharts()
      else if (newTab === 'esg') renderEsgCharts()
      else if (newTab === 'esg_carbon') {
        // 碳排放与对标标签页：等待容器可见后渲染
        waitForContainerAndRender(esgCarbonParetoRef, renderEsgCarbonPareto)
        waitForContainerAndRender(esgBenchmarkRef, renderEsgBenchmark)
      }
      else if (newTab === 'roi') {
        // ROI 测算结果已存在时，渲染现金流图
        if (roiResult.value?.cash_flows?.length) {
          waitForContainerAndRender(cashflowChartRef, renderCashflowChart)
        }
      }
      else if (newTab === 'rul' && rulDetail.value) { renderRulTrend(); renderRulCopTrend() }
    }, 200)
  })
})

// ===== StatCard 组件（内联定义）=====
const StatCard = defineComponent({
  props: {
    label: { type: String, required: true },
    value: { type: [String, Number], default: '-' },
    color: { type: String, default: 'indigo' }
  },
  setup(p) {
    const colorMap = {
      indigo: 'text-indigo-600 bg-indigo-50',
      rose: 'text-rose-600 bg-rose-50',
      amber: 'text-amber-600 bg-amber-50',
      emerald: 'text-emerald-600 bg-emerald-50',
      cyan: 'text-cyan-600 bg-cyan-50',
      slate: 'text-slate-600 bg-slate-50',
      blue: 'text-blue-600 bg-blue-50'
    }
    return () => h('div', { class: 'bg-white rounded-xl p-3 border border-slate-100 shadow-sm' }, [
      h('div', { class: 'text-xs text-slate-400 mb-1' }, p.label),
      h('div', { class: ['text-lg font-bold rounded-lg inline-block px-2 py-0.5', colorMap[p.color] || colorMap.indigo] }, String(p.value))
    ])
  }
})

// ===== 工具函数 =====
const formatKwh = (v, unit = 'kWh') => {
  if (v == null) return '-'
  if (Math.abs(v) >= 10000) return (v / 10000).toFixed(2) + ' 万' + unit
  return v.toLocaleString() + ' ' + unit
}
const formatMoney = (v) => {
  if (v == null) return '-'
  if (Math.abs(v) >= 10000) return '¥' + (v / 10000).toFixed(2) + ' 万'
  return '¥' + v.toLocaleString()
}
const healthColor = (score) => {
  if (score == null) return 'slate'
  if (score >= 80) return 'emerald'
  if (score >= 60) return 'indigo'
  if (score >= 40) return 'amber'
  return 'rose'
}
const dimensionName = (key) => ({
  cop_degradation: 'COP 衰减度', stability: '运行稳定性', loading_rate: '负载率合理性',
  fault_freq: '故障频率', delta_temp: '温差异常度'
})[key] || key
const confidenceLabel = (c) => ({ high: '高', medium: '中', low: '低', insufficient_data: '数据不足', no_degradation: '无衰减', below_threshold: '已超限' })[c] || c || '-'
const levelLabel = (l) => ({ critical: '紧急', important: '重要', normal: '普通' })[l] || l
const sourceLabel = (s) => ({ device_anomaly: '设备异常', energy_overload: '能耗超标', cop_decline: '预测预警' })[s] || s
const statusLabel = (s) => ({ active: '活跃', acknowledged: '已确认', silenced: '已静默', resolved: '已恢复' })[s] || s
const statusTagType = (s) => ({ active: 'danger', acknowledged: 'warning', silenced: 'info', resolved: 'success' })[s] || 'info'
const slaStatusLabel = (s) => ({ on_track: '进行中', soon: '即将超时', overdue: '已超时', completed: '已完成' })[s] || s
const priorityTagType = (p) => ({ P0: 'danger', P1: 'warning', P2: 'primary', P3: 'info' })[p] || 'info'
const costBasisLabel = (c) => ({ power: '按设备功率', area: '按面积', pv: '光伏按装机', storage: '储能按容量' })[c] || c

// ESG 维度子指标简表（从复杂 metrics 对象提取关键指标）
const dimMetricsBrief = (metrics, dimKey) => {
  if (!metrics) return []
  const fmt = (v, unit = '') => (v == null ? '-' : (typeof v === 'number' ? v.toLocaleString() : v) + unit)
  if (dimKey === 'E') {
    return [
      { label: '碳排放总量', text: fmt(metrics.carbon_emission_total_kg, ' kg') },
      { label: '碳排放强度', text: fmt(metrics.carbon_intensity_kg_per_m2, ' kgCO₂/㎡·年') },
      { label: '能耗强度', text: fmt(metrics.energy_intensity_kwh_per_m2, ' kWh/㎡·年') },
      { label: '绿电占比', text: fmt(metrics.green_ratio_pct, '%') },
    ]
  }
  if (dimKey === 'S') {
    const safety = metrics.employee_safety
    return [
      { label: '员工安全', text: fmt(typeof safety === 'object' ? safety.value : safety), warn: typeof safety === 'object' && safety.mock },
      { label: '社区影响', text: fmt(metrics.community_impact_score), warn: false },
      { label: '高影响建筑占比', text: fmt(metrics.community_impact_ratio, '%') },
      { label: '合规性得分', text: fmt(metrics.compliance_score) },
    ]
  }
  if (dimKey === 'G') {
    const audit = metrics.audit_completion_pct
    const auditVal = typeof audit === 'object' ? audit.value : audit
    const auditMock = typeof audit === 'object' ? audit.mock : false
    return [
      { label: '数据治理', text: fmt(metrics.data_governance_score) },
      { label: '数据完整性', text: fmt(metrics.data_completeness_pct, '%') },
      { label: '工单完成率', text: fmt(auditVal, '%'), warn: auditMock },
      { label: '风险管控', text: fmt(metrics.risk_management_score) },
    ]
  }
  return []
}

// ===== 1. RUL 设备健康度 =====
const rulLoading = ref(false)
const rulSummary = ref({})
const rulGrades = ref([])
const rulRanking = ref([])
const rulDrawerVisible = ref(false)
const rulDetail = ref(null)

async function loadRul() {
  rulLoading.value = true
  try {
    const [overviewRes, rankingRes] = await Promise.all([
      fetchRulOverview(), fetchRulRanking(10)
    ])
    if (overviewRes.status === 'success') {
      rulSummary.value = overviewRes.data.summary || {}
      rulGrades.value = overviewRes.data.grades || []
    }
    if (rankingRes.status === 'success') {
      rulRanking.value = rankingRes.data || []
    }
  } catch (e) { console.error('RUL 加载失败', e) }
  rulLoading.value = false
}

async function viewRulDetail(deviceId) {
  rulDrawerVisible.value = true
  rulDetail.value = null
  try {
    const res = await fetchRulDeviceDetail(deviceId)
    if (res.status === 'success') {
      rulDetail.value = res.data
      nextTick(() => {
        renderRulTrend()
        renderRulCopTrend()
      })
    }
  } catch (e) { ElMessage.error('详情加载失败') }
}

let rulTrendChart = null, rulCopTrendChart = null
function renderRulTrend() {
  const dom = document.querySelector('[ref="rulTrendRef"]') || rulTrendRef.value
  if (!dom || !rulDetail.value?.trend?.daily_health?.length) return
  if (rulTrendChart) rulTrendChart.dispose()
  rulTrendChart = echarts.init(dom)
  const data = rulDetail.value.trend.daily_health
  rulTrendChart.setOption({
    title: { text: '健康度日趋势（近 30 天）', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: data.map(d => d.day), axisLabel: { rotate: 45, fontSize: 10 } },
    yAxis: { type: 'value', min: 0, max: 100, name: '健康度' },
    series: [
      { name: '健康度', type: 'line', smooth: true, data: data.map(d => d.health_score), itemStyle: { color: '#10b981' }, areaStyle: { opacity: 0.1 } },
      { name: 'COP', type: 'line', smooth: true, yAxisIndex: 0, data: data.map(d => d.cop), itemStyle: { color: '#6366f1' } }
    ]
  })
}
function renderRulCopTrend() {
  const dom = document.querySelector('[ref="rulCopTrendRef"]') || rulCopTrendRef.value
  if (!dom || !rulDetail.value?.trend?.cop_monthly_trend?.length) return
  if (rulCopTrendChart) rulCopTrendChart.dispose()
  rulCopTrendChart = echarts.init(dom)
  const data = rulDetail.value.trend.cop_monthly_trend
  const nominalCop = rulDetail.value.device?.nominal_cop || 0
  const threshold = nominalCop * 0.6
  rulCopTrendChart.setOption({
    title: { text: 'COP 月度衰减曲线 & RUL 预测', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0 },
    xAxis: { type: 'category', data: data.map(d => d.month) },
    yAxis: { type: 'value', name: 'COP' },
    series: [
      { name: '历史 COP', type: 'line', smooth: true, data: data.map(d => d.cop_avg), itemStyle: { color: '#0ea5e9' } },
      { name: '额定 COP', type: 'line', data: data.map(() => nominalCop), itemStyle: { color: '#94a3b8', type: 'dashed' } },
      { name: '寿命阈值', type: 'line', data: data.map(() => threshold), itemStyle: { color: '#ef4444', type: 'dashed' } }
    ]
  })
}

// ===== 2. 能耗基准对标 =====
const benchmarkLoading = ref(false)
const benchmarkSummary = ref({})
const benchmarkGrades = ref([])
const benchmarkBuildings = ref([])
const benchmarkChartRef = ref(null)
let benchmarkChart = null

async function loadBenchmark() {
  benchmarkLoading.value = true
  try {
    const res = await fetchBenchmarkOverview()
    if (res.status === 'success') {
      benchmarkSummary.value = res.data.summary || {}
      benchmarkGrades.value = res.data.grades || []
      benchmarkBuildings.value = res.data.buildings || []
      nextTick(renderBenchmarkChart)
    }
  } catch (e) { console.error('对标加载失败', e) }
  benchmarkLoading.value = false
}

function renderBenchmarkChart() {
  if (!benchmarkChartRef.value || !benchmarkBuildings.value.length) return
  if (benchmarkChart) benchmarkChart.dispose()
  benchmarkChart = echarts.init(benchmarkChartRef.value)
  const buildings = benchmarkBuildings.value.filter(b => b.has_data).slice(0, 15)
  benchmarkChart.setOption({
    title: { text: '各建筑能耗强度对标（kWh/㎡·年）', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0 },
    grid: { left: 50, right: 30, bottom: 80, top: 50 },
    xAxis: { type: 'category', data: buildings.map(b => b.building_name), axisLabel: { rotate: 30, fontSize: 10 } },
    yAxis: { type: 'value', name: 'kWh/㎡·年' },
    series: [
      { name: '实际强度', type: 'bar', data: buildings.map(b => b.intensity), itemStyle: { color: (p) => buildings[p.dataIndex].color } },
      { name: '先进值', type: 'line', data: buildings.map(b => b.standard.advanced), itemStyle: { color: '#52c41a', type: 'dashed' } },
      { name: '限额值', type: 'line', data: buildings.map(b => b.standard.limit), itemStyle: { color: '#ff4d4f', type: 'dashed' } }
    ]
  })
}

// ===== 3. 多能耦合优化 =====
const multiEnergyLoading = ref(false)
const multiEnergyOverview = ref({})
const multiEnergyComparison = ref({})
const multiEnergyScheduleRef = ref(null)
const multiEnergyComparisonRef = ref(null)
let multiEnergyScheduleChart = null, multiEnergyComparisonChart = null

async function loadMultiEnergy() {
  multiEnergyLoading.value = true
  try {
    const [ovRes, cmpRes] = await Promise.all([fetchMultiEnergyOverview(), fetchMultiEnergyComparison()])
    if (ovRes.status === 'success') multiEnergyOverview.value = ovRes.data || {}
    if (cmpRes.status === 'success') {
      multiEnergyComparison.value = cmpRes.data || {}
      nextTick(renderMultiEnergyCharts)
    }
  } catch (e) { console.error('多能优化加载失败', e) }
  multiEnergyLoading.value = false
}

async function renderMultiEnergyCharts() {
  // 调度图
  const cmp = multiEnergyComparison.value
  const hourly = cmp.hourly_comparison || []
  if (multiEnergyScheduleRef.value && hourly.length) {
    if (multiEnergyScheduleChart) multiEnergyScheduleChart.dispose()
    multiEnergyScheduleChart = echarts.init(multiEnergyScheduleRef.value)
    multiEnergyScheduleChart.setOption({
      title: { text: '24h 调度方案（基线 vs 优化）', left: 'center', textStyle: { fontSize: 14 } },
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0 },
      grid: { left: 50, right: 30, bottom: 60, top: 50 },
      xAxis: { type: 'category', data: hourly.map(h => h.hour + ':00') },
      yAxis: { type: 'value', name: 'kW / 元' },
      series: [
        { name: '电网(基线)', type: 'bar', data: hourly.map(h => h.baseline_grid), itemStyle: { color: '#94a3b8' } },
        { name: '电网(优化)', type: 'bar', data: hourly.map(h => h.optimized_grid), itemStyle: { color: '#10b981' } },
        { name: '储能功率', type: 'line', data: hourly.map(h => h.battery_power), itemStyle: { color: '#f59e0b' } }
      ]
    })
  }
  // 成本对比图
  if (multiEnergyComparisonRef.value && hourly.length) {
    if (multiEnergyComparisonChart) multiEnergyComparisonChart.dispose()
    multiEnergyComparisonChart = echarts.init(multiEnergyComparisonRef.value)
    multiEnergyComparisonChart.setOption({
      title: { text: '逐时段成本对比', left: 'center', textStyle: { fontSize: 14 } },
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0 },
      grid: { left: 50, right: 30, bottom: 60, top: 50 },
      xAxis: { type: 'category', data: hourly.map(h => h.hour + ':00') },
      yAxis: { type: 'value', name: '元' },
      series: [
        { name: '基线成本', type: 'line', smooth: true, data: hourly.map(h => h.baseline_cost), itemStyle: { color: '#ef4444' } },
        { name: '优化成本', type: 'line', smooth: true, data: hourly.map(h => h.optimized_cost), itemStyle: { color: '#10b981' } },
        { name: '节省', type: 'bar', data: hourly.map(h => h.saving), itemStyle: { color: '#6366f1' } }
      ]
    })
  }
}

// ===== 4. 智能告警中心 =====
const alertLoading = ref(false)
const alertStats = ref({})
const alertList = ref([])
const alertTotal = ref(0)
const alertFilter = reactive({ level: '', status: '', page: 1 })
const alertChannels = reactive({ sms_enabled: true, email_enabled: true, inapp_enabled: true })
const pushTesting = ref(false)

async function loadAlerts() {
  alertLoading.value = true
  try {
    const [statsRes, listRes, channelsRes] = await Promise.all([fetchAlertsStats(), fetchAlertsCenter(alertFilter), fetchAlertChannels()])
    if (statsRes.status === 'success') alertStats.value = statsRes.data || {}
    if (listRes.status === 'success') {
      alertList.value = listRes.data?.alerts || []
      alertTotal.value = listRes.data?.pagination?.total || 0
    }
    if (channelsRes.status === 'success') Object.assign(alertChannels, channelsRes.data || {})
  } catch (e) { console.error('告警加载失败', e) }
  alertLoading.value = false
}

async function ackAlert(id) {
  try {
    const res = await acknowledgeAlert(id)
    if (res.status === 'success') { ElMessage.success('告警已确认'); loadAlerts() }
    else ElMessage.error(res.message || '操作失败')
  } catch (e) { ElMessage.error('操作失败') }
}

async function silenceAlertRow(id) {
  try {
    const res = await silenceAlert(id, 60)
    if (res.status === 'success') { ElMessage.success('告警已静默 1 小时'); loadAlerts() }
    else ElMessage.error(res.message || '操作失败')
  } catch (e) { ElMessage.error('操作失败') }
}

async function saveChannels() {
  try {
    const res = await updateAlertChannels({ ...alertChannels })
    if (res.status === 'success') ElMessage.success('渠道配置已更新')
  } catch (e) { ElMessage.error('保存失败') }
}

async function testPush() {
  pushTesting.value = true
  try {
    const res = await testAlertPush({ title: '测试告警', message: '这是一条测试推送消息' })
    if (res.status === 'success') ElMessage.success('测试推送已发送')
    else ElMessage.error(res.message || '推送失败')
  } catch (e) { ElMessage.error('推送失败') }
  pushTesting.value = false
}

// ===== 5. 能源审计报告 =====
const auditLoading = ref(false)
const auditBuildings = ref([])
const auditBuildingId = ref('')
const auditReport = ref(null)
const auditExporting = ref(false)
const auditTrendRef = ref(null)
const auditBreakdownRef = ref(null)
let auditTrendChart = null, auditBreakdownChart = null

async function loadAuditBuildings() {
  try {
    const res = await fetchAuditBuildings()
    if (res.status === 'success') {
      auditBuildings.value = res.data || []
      if (auditBuildings.value.length && !auditBuildingId.value) {
        auditBuildingId.value = auditBuildings.value[0].building_id
        loadAuditReport()
      }
    }
  } catch (e) { console.error('审计建筑列表加载失败', e) }
}

async function loadAuditReport() {
  if (!auditBuildingId.value) return
  auditLoading.value = true
  try {
    const res = await fetchAuditReport(auditBuildingId.value)
    if (res.status === 'success') {
      auditReport.value = res.data || null
      nextTick(renderAuditCharts)
    }
  } catch (e) { console.error('审计报告加载失败', e) }
  auditLoading.value = false
}

function renderAuditCharts() {
  const r = auditReport.value
  if (!r) return
  // 能耗趋势
  if (auditTrendRef.value && r.daily_trend?.length) {
    if (auditTrendChart) auditTrendChart.dispose()
    auditTrendChart = echarts.init(auditTrendRef.value)
    auditTrendChart.setOption({
      title: { text: '近 30 天能耗趋势', left: 'center', textStyle: { fontSize: 14 } },
      tooltip: { trigger: 'axis' },
      grid: { left: 50, right: 30, bottom: 60, top: 50 },
      xAxis: { type: 'category', data: r.daily_trend.map(d => d.day), axisLabel: { rotate: 30, fontSize: 10 } },
      yAxis: { type: 'value', name: 'kWh' },
      series: [{ name: '日能耗', type: 'bar', data: r.daily_trend.map(d => d.kwh), itemStyle: { color: '#6366f1' } }]
    })
  }
  // 分项能耗
  if (auditBreakdownRef.value && r.type_breakdown?.length) {
    if (auditBreakdownChart) auditBreakdownChart.dispose()
    auditBreakdownChart = echarts.init(auditBreakdownRef.value)
    auditBreakdownChart.setOption({
      title: { text: '分项能耗占比', left: 'center', textStyle: { fontSize: 14 } },
      tooltip: { trigger: 'item', formatter: '{b}: {c} kWh ({d}%)' },
      legend: { bottom: 0, type: 'scroll' },
      series: [{
        type: 'pie', radius: ['40%', '70%'],
        data: r.type_breakdown.map(t => ({ name: t.device_type, value: t.kwh }))
      }]
    })
  }
}

async function exportAudit() {
  if (!auditBuildingId.value) return
  auditExporting.value = true
  try {
    const blob = await exportAuditReport(auditBuildingId.value)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `能源审计报告_${auditBuildingId.value}_${Date.now()}.docx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('报告已导出')
  } catch (e) { ElMessage.error(e.message || '导出失败') }
  auditExporting.value = false
}

// ===== 6. 工单全生命周期 =====
const workorderLoading = ref(false)
const slaStats = ref({})
const workorderList = ref([])
const partsList = ref([])
const workorderSubTab = ref('list')

async function loadWorkorders() {
  workorderLoading.value = true
  try {
    const [slaRes, listRes, partsRes] = await Promise.all([fetchSlaStats(), fetchWorkOrdersPro({ page_size: 100, page: 1 }), fetchPartsInventory()])
    if (slaRes.status === 'success') slaStats.value = slaRes.data || {}
    if (listRes.status === 'success') workorderList.value = listRes.data?.orders || listRes.data || []
    if (partsRes.status === 'success') partsList.value = partsRes.data || []
  } catch (e) { console.error('工单加载失败', e) }
  workorderLoading.value = false
}

async function dispatchOrder(orderId) {
  try {
    const res = await dispatchWorkOrder(orderId)
    if (res.status === 'success') {
      ElMessage.success(`已派单给 ${res.data.assigned_to.name}（${res.data.assigned_to.skill}）`)
      loadWorkorders()
    } else ElMessage.error(res.message || '派单失败')
  } catch (e) { ElMessage.error('派单失败') }
}

// ===== 7. ESG 报告 =====
const esgLoading = ref(false)
const esgOverview = ref({})
const esgReport = ref({})
const esgTrendData = ref([])
const esgRadarRef = ref(null)
const esgTrendRef = ref(null)
let esgRadarChart = null, esgTrendChart = null

const esgGradeColor = computed(() => esgOverview.value.grade?.color || 'slate')

async function loadEsg() {
  esgLoading.value = true
  try {
    const [ovRes, reportRes, trendRes] = await Promise.all([fetchEsgOverview(), fetchEsgReport(), fetchEsgTrend()])
    if (ovRes.status === 'success') esgOverview.value = ovRes.data || {}
    if (reportRes.status === 'success') {
      esgReport.value = reportRes.data || {}
      // 提取 G 维度工单完成率（真实数据）
      const wo = reportRes.data?.raw_data?.workorder
      if (wo && wo.total > 0) {
        esgWorkorderInfo.value = { ...wo, source: 'real' }
      } else {
        esgWorkorderInfo.value = { total: 0, completed: 0, completion_rate: 0, avg_hours: 0, source: 'mock' }
      }
    }
    if (trendRes.status === 'success') esgTrendData.value = trendRes.data?.trend || []
    nextTick(renderEsgCharts)
    // 同时加载碳排放与对标（避免阻塞主报告）
    loadEsgCarbon()
    loadEsgAdvice()
  } catch (e) { console.error('ESG 加载失败', e) }
  esgLoading.value = false
}

// ESG 工单完成率信息（G 维度）
const esgWorkorderInfo = ref(null)

// ===== 7.2 ESG 碳排放与对标 =====
const esgCarbonLoading = ref(false)
const esgCarbonData = ref({})
const esgCarbonParetoRef = ref(null)
let esgCarbonParetoChart = null
const esgBenchmark = ref({})
const esgBenchmarkRef = ref(null)
let esgBenchmarkChart = null

async function loadEsgCarbon() {
  esgCarbonLoading.value = true
  try {
    const [carbonRes, benchRes] = await Promise.all([fetchEsgBuildingCarbon(30), fetchEsgBenchmark(30)])
    if (carbonRes.status === 'success') esgCarbonData.value = carbonRes.data || {}
    if (benchRes.status === 'success') esgBenchmark.value = benchRes.data || {}
    nextTick(() => {
      renderEsgCarbonPareto()
      renderEsgBenchmark()
    })
  } catch (e) { console.error('ESG 碳排放/对标加载失败', e) }
  esgCarbonLoading.value = false
}

function renderEsgCarbonPareto() {
  if (!esgCarbonParetoRef.value || !esgCarbonData.value?.buildings?.length) return
  if (esgCarbonParetoChart) esgCarbonParetoChart.dispose()
  esgCarbonParetoChart = echarts.init(esgCarbonParetoRef.value)
  const buildings = esgCarbonData.value.buildings
  esgCarbonParetoChart.setOption({
    title: { text: '建筑碳排放帕累托分析（按排放量降序）', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => {
        const b = buildings[params[0].dataIndex]
        return `${b.building_name}<br/>碳排放: ${b.carbon_kg} kg<br/>占比: ${b.carbon_pct}%<br/>累计: ${b.cumulative_pct}%`
      }
    },
    legend: { bottom: 0, data: ['碳排放(kg)', '累计占比%'] },
    grid: { left: 70, right: 70, bottom: 90, top: 60, containLabel: true },
    xAxis: { type: 'category', data: buildings.map(b => b.building_name), axisLabel: { rotate: 35, interval: 0, fontSize: 11, width: 80, overflow: 'truncate' } },
    yAxis: [
      { type: 'value', name: '碳排放(kg)', position: 'left', axisLabel: { formatter: (v) => v >= 1000 ? (v / 1000).toFixed(0) + 'k' : v } },
      { type: 'value', name: '累计占比%', position: 'right', max: 100, axisLabel: { formatter: '{value}%' } }
    ],
    series: [
      {
        name: '碳排放(kg)', type: 'bar', data: buildings.map(b => b.carbon_kg), barWidth: '50%',
        itemStyle: {
          color: (p) => {
            const b = buildings[p.dataIndex]
            return b.priority === 'high' ? '#ef4444' : (b.priority === 'medium' ? '#faad14' : '#52c41a')
          }
        },
        label: { show: true, position: 'top', formatter: (p) => buildings[p.dataIndex].carbon_pct + '%', fontSize: 10 }
      },
      {
        name: '累计占比%', type: 'line', yAxisIndex: 1, data: buildings.map(b => b.cumulative_pct),
        itemStyle: { color: '#1890ff' }, lineStyle: { width: 2, type: 'dashed' },
        markLine: { silent: true, data: [{ yAxis: 80, name: '80% 帕累托线', lineStyle: { color: '#ff4d4f' } }] }
      }
    ]
  })
  esgCarbonParetoChart.resize()
}

function renderEsgBenchmark() {
  if (!esgBenchmarkRef.value || !esgBenchmark.value?.benchmarks?.length) return
  if (esgBenchmarkChart) esgBenchmarkChart.dispose()
  esgBenchmarkChart = echarts.init(esgBenchmarkRef.value)
  const benchmarks = esgBenchmark.value.benchmarks
  esgBenchmarkChart.setOption({
    title: { text: '行业对标雷达图', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: {},
    legend: { bottom: 0, data: ['当前值', '先进值', '平均值'] },
    radar: {
      center: ['50%', '50%'],
      radius: '65%',
      indicator: benchmarks.map(b => ({ name: b.metric_name, max: Math.max(b.benchmark.advanced, b.actual_value) * 1.2 }))
    },
    series: [{
      type: 'radar',
      data: [
        { value: benchmarks.map(b => b.actual_value), name: '当前值', areaStyle: { opacity: 0.3 }, itemStyle: { color: '#1890ff' } },
        { value: benchmarks.map(b => b.benchmark.advanced), name: '先进值', areaStyle: { opacity: 0.2 }, itemStyle: { color: '#52c41a' } },
        { value: benchmarks.map(b => b.benchmark.average), name: '平均值', areaStyle: { opacity: 0.2 }, itemStyle: { color: '#faad14' } }
      ]
    }]
  })
  esgBenchmarkChart.resize()
}

// ===== 7.3 ESG 改进建议 =====
const esgAdviceLoading = ref(false)
const esgAdvice = ref({})

async function loadEsgAdvice() {
  esgAdviceLoading.value = true
  try {
    const res = await fetchEsgRecommendations(30)
    if (res.status === 'success') esgAdvice.value = res.data || {}
  } catch (e) { console.error('ESG 改进建议加载失败', e) }
  esgAdviceLoading.value = false
}

function renderEsgCharts() {
  // 雷达图
  if (esgRadarRef.value && esgOverview.value.dimensions) {
    if (esgRadarChart) esgRadarChart.dispose()
    esgRadarChart = echarts.init(esgRadarRef.value)
    const dims = esgOverview.value.dimensions
    esgRadarChart.setOption({
      title: { text: 'ESG 三维度得分', left: 'center', textStyle: { fontSize: 14 } },
      tooltip: {},
      radar: {
        indicator: [
          { name: `E 环境\n权重${(dims.E?.weight * 100).toFixed(0)}%`, max: 100 },
          { name: `S 社会\n权重${(dims.S?.weight * 100).toFixed(0)}%`, max: 100 },
          { name: `G 治理\n权重${(dims.G?.weight * 100).toFixed(0)}%`, max: 100 }
        ]
      },
      series: [{
        type: 'radar',
        data: [{ value: [dims.E?.score || 0, dims.S?.score || 0, dims.G?.score || 0], name: '当前得分', areaStyle: { opacity: 0.3 } }],
        itemStyle: { color: '#10b981' }
      }]
    })
  }
  // 趋势图
  if (esgTrendRef.value && esgTrendData.value.length) {
    if (esgTrendChart) esgTrendChart.dispose()
    esgTrendChart = echarts.init(esgTrendRef.value)
    esgTrendChart.setOption({
      title: { text: 'ESG 指标趋势（近 12 个月）', left: 'center', textStyle: { fontSize: 14 } },
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0 },
      grid: { left: 50, right: 30, bottom: 60, top: 50 },
      xAxis: { type: 'category', data: esgTrendData.value.map(t => t.month) },
      yAxis: { type: 'value', name: '分', min: 0, max: 100 },
      series: [
        { name: 'E 环境', type: 'line', smooth: true, data: esgTrendData.value.map(t => t.e_score), itemStyle: { color: '#10b981' } },
        { name: 'S 社会', type: 'line', smooth: true, data: esgTrendData.value.map(t => t.s_score), itemStyle: { color: '#6366f1' } },
        { name: 'G 治理', type: 'line', smooth: true, data: esgTrendData.value.map(t => t.g_score), itemStyle: { color: '#f59e0b' } },
        { name: '总分', type: 'line', smooth: true, data: esgTrendData.value.map(t => t.total_score), itemStyle: { color: '#ef4444', width: 3 } }
      ]
    })
  }
}

// ===== 8. ROI 测算 =====
const roiLoading = ref(false)
const roiScenarios = ref([])
const roiForm = reactive({ scenario_id: '', building_id: '' })
const roiResult = ref(null)
const roiCalculating = ref(false)

const currentScenario = computed(() => roiScenarios.value.find(s => s.scenario_id === roiForm.scenario_id))

async function loadRoiScenarios() {
  roiLoading.value = true
  try {
    const res = await fetchRoiScenarios()
    if (res.status === 'success') roiScenarios.value = res.data?.scenarios || []
  } catch (e) { console.error('ROI 方案加载失败', e) }
  roiLoading.value = false
}

function onScenarioChange() { roiResult.value = null }

async function calcRoi() {
  if (!roiForm.scenario_id || !roiForm.building_id) return
  roiCalculating.value = true
  try {
    const res = await calculateRoi(roiForm)
    if (res.status === 'success') {
      roiResult.value = res.data
      ElMessage.success('测算完成')
      nextTick(renderCashflowChart)
    } else ElMessage.error(res.message || '测算失败')
  } catch (e) { ElMessage.error('测算失败') }
  roiCalculating.value = false
}

// ===== 8.5 ROI 方案对比 =====
const roiCompareVisible = ref(false)
const roiCompareBuilding = ref('')
const roiCompareSelected = ref([])  // 选中的方案 ID 列表
const roiCompareResult = ref(null)
const roiCompareLoading = ref(false)

async function runRoiCompare() {
  if (!roiCompareBuilding.value || roiCompareSelected.value.length < 2) {
    ElMessage.warning('请选择建筑和至少 2 个方案')
    return
  }
  roiCompareLoading.value = true
  try {
    const res = await compareRoiScenarios(roiCompareBuilding.value, roiCompareSelected.value)
    if (res.status === 'success') {
      roiCompareResult.value = res.data
    } else ElMessage.error(res.message || '对比失败')
  } catch (e) { ElMessage.error('对比失败') }
  roiCompareLoading.value = false
}

// ===== 8.6 ROI 现金流图 =====
const cashflowChartRef = ref(null)
let cashflowChart = null

function renderCashflowChart() {
  if (!cashflowChartRef.value || !roiResult.value?.cash_flows?.length) return
  if (cashflowChart) cashflowChart.dispose()
  cashflowChart = echarts.init(cashflowChartRef.value)
  const flows = roiResult.value.cash_flows
  const investment = roiResult.value.results.investment_yuan
  cashflowChart.setOption({
    title: { text: '全生命周期现金流（含衰减与运维成本）', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis', formatter: (p) => p.map(x => `${x.seriesName}: ${formatMoney(x.value)} 元`).join('<br/>') },
    legend: { bottom: 0 },
    grid: { left: 70, right: 40, bottom: 60, top: 50 },
    xAxis: { type: 'category', data: flows.map(f => '第' + f.year + '年'), name: '年份' },
    yAxis: { type: 'value', name: '金额(元)', axisLabel: { formatter: (v) => v / 10000 + '万' } },
    series: [
      { name: '年毛收益', type: 'bar', stack: 'cash', data: flows.map(f => f.saving_gross), itemStyle: { color: '#52c41a' } },
      { name: '运维成本', type: 'bar', stack: 'cash', data: flows.map(f => -f.om_cost), itemStyle: { color: '#faad14' } },
      { name: '年净现金流', type: 'line', data: flows.map(f => f.net_cash_flow), itemStyle: { color: '#1890ff' }, lineStyle: { width: 2 } },
      { name: '累计现金流', type: 'line', smooth: true, data: flows.map(f => f.cumulative), itemStyle: { color: '#722ed1' }, lineStyle: { width: 3 },
        markLine: { silent: true, symbol: 'none', data: [{ yAxis: investment, name: '投资额', lineStyle: { color: '#ff4d4f', type: 'dashed' }, label: { formatter: '投资额 ' + formatMoney(investment) } }] } }
    ]
  })
}

// ===== 8.7 ROI 敏感性分析 =====
const sensitivityVisible = ref(false)
const sensitivityLoading = ref(false)
const sensitivityResult = ref(null)
const sensitivityChartRef = ref(null)
let sensitivityChart = null

async function loadSensitivity() {
  if (!roiForm.scenario_id || !roiForm.building_id) {
    ElMessage.warning('请先完成 ROI 测算')
    return
  }
  sensitivityVisible.value = true
  sensitivityLoading.value = true
  try {
    const res = await analyzeRoiSensitivity(roiForm.scenario_id, roiForm.building_id)
    if (res.status === 'success') {
      sensitivityResult.value = res.data
      nextTick(renderSensitivityChart)
    } else ElMessage.error(res.message || '敏感性分析失败')
  } catch (e) { ElMessage.error('敏感性分析失败') }
  sensitivityLoading.value = false
}

function renderSensitivityChart() {
  if (!sensitivityChartRef.value || !sensitivityResult.value?.sensitivity) return
  if (sensitivityChart) sensitivityChart.dispose()
  sensitivityChart = echarts.init(sensitivityChartRef.value)
  const sens = sensitivityResult.value.sensitivity
  const baseRoi = sensitivityResult.value.base_results.roi_pct
  // 龙卷风图：展示每变量 ±20% 时 ROI 的变化范围
  const vars = Object.keys(sens)
  const categories = []
  const ranges = []
  vars.forEach(key => {
    const points = sens[key].points.filter(p => p.roi_pct != null)
    if (points.length === 0) return
    const min = Math.min(...points.map(p => p.roi_pct))
    const max = Math.max(...points.map(p => p.roi_pct))
    categories.push(sens[key].label)
    ranges.push([min, max])
  })
  sensitivityChart.setOption({
    title: { text: 'ROI 敏感性分析（龙卷风图）', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis', formatter: (p) => `${p[0].name}<br/>ROI 范围: ${p[0].value[0]}% ~ ${p[1]?.value || p[0].value[1]}%<br/>基准 ROI: ${baseRoi}%` },
    grid: { left: 80, right: 40, bottom: 40, top: 50 },
    xAxis: { type: 'value', name: 'ROI%', axisLabel: { formatter: '{value}%' } },
    yAxis: { type: 'category', data: categories },
    series: [
      {
        name: 'ROI 范围', type: 'bar', data: ranges.map(r => r[1] - r[0]),
        itemStyle: { color: '#faad14' },
        label: { show: true, position: 'right', formatter: (p) => `${ranges[p.dataIndex][0]}% ~ ${ranges[p.dataIndex][1]}%` }
      },
      {
        name: '基准 ROI', type: 'scatter', data: categories.map(() => baseRoi),
        symbolSize: 12, itemStyle: { color: '#1890ff' }
      }
    ]
  })
}

// ===== 8.8 ROI 风险评估 =====
const riskVisible = ref(false)
const riskLoading = ref(false)
const riskResult = ref(null)
const riskRadarRef = ref(null)
let riskRadarChart = null

async function loadRiskAssessment() {
  if (!roiForm.scenario_id) {
    ElMessage.warning('请先选择方案')
    return
  }
  riskVisible.value = true
  riskLoading.value = true
  try {
    const res = await fetchRoiRiskAssessment(roiForm.scenario_id)
    if (res.status === 'success') {
      riskResult.value = res.data
      nextTick(renderRiskRadar)
    } else ElMessage.error(res.message || '风险评估失败')
  } catch (e) { ElMessage.error('风险评估失败') }
  riskLoading.value = false
}

function renderRiskRadar() {
  if (!riskRadarRef.value || !riskResult.value?.risk_scores) return
  if (riskRadarChart) riskRadarChart.dispose()
  riskRadarChart = echarts.init(riskRadarRef.value)
  const scores = riskResult.value.risk_scores
  const labels = riskResult.value.risk_labels || {
    tech_risk: '技术风险', market_risk: '市场风险',
    implementation_risk: '实施风险', maintenance_risk: '运维风险'
  }
  riskRadarChart.setOption({
    title: { text: '风险维度雷达图（1=低，5=高）', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: {},
    radar: {
      indicator: Object.keys(scores).map(k => ({ name: labels[k] || k, max: 5, min: 0 }))
    },
    series: [{
      type: 'radar',
      data: [{
        value: Object.keys(scores).map(k => scores[k]),
        name: riskResult.value.scenario_name,
        areaStyle: { opacity: 0.3, color: riskResult.value.risk_color },
        itemStyle: { color: riskResult.value.risk_color }
      }]
    }]
  })
}

// ===== 8.9 ROI 组合优化 =====
const portfolioVisible = ref(false)
const portfolioLoading = ref(false)
const portfolioResult = ref(null)
const portfolioBuilding = ref('')
const portfolioBudget = ref(500000)

async function runPortfolio() {
  if (!portfolioBuilding.value || !portfolioBudget.value) {
    ElMessage.warning('请选择建筑并输入预算')
    return
  }
  portfolioLoading.value = true
  try {
    const res = await optimizeRoiPortfolio(portfolioBuilding.value, portfolioBudget.value, [])
    if (res.status === 'success') {
      portfolioResult.value = res.data
      if (res.data.selected?.length) ElMessage.success(`已推荐 ${res.data.selected.length} 个方案`)
      else ElMessage.warning('当前预算不足以实施任何方案')
    } else ElMessage.error(res.message || '组合优化失败')
  } catch (e) { ElMessage.error('组合优化失败') }
  portfolioLoading.value = false
}

// ===== 9. Web Push 推送 =====
const pushLoading = ref(false)
const pushSubscriptions = ref([])
const pushNotifications = ref([])
const pushSubscribing = ref(false)
const pushSending = ref(false)
let pushSubscriptionObj = null

const pushSupported = computed(() => typeof window !== 'undefined' && 'serviceWorker' in navigator && 'PushManager' in window)
const pushSubscribed = computed(() => !!pushSubscriptionObj)
const pushSubsCount = computed(() => pushSubscriptions.value.length)

async function loadPushData() {
  pushLoading.value = true
  try {
    const [subsRes, notifRes] = await Promise.all([fetchPushSubscriptions(), fetchPushNotifications(20)])
    if (subsRes.status === 'success') pushSubscriptions.value = subsRes.data || []
    if (notifRes.status === 'success') pushNotifications.value = notifRes.data?.notifications || []
  } catch (e) { console.error('推送数据加载失败', e) }
  pushLoading.value = false
}

async function subscribePush() {
  if (!pushSupported.value) return
  pushSubscribing.value = true
  try {
    // 注册 Service Worker
    const reg = await navigator.serviceWorker.register('/sw.js').catch(() => navigator.serviceWorker.ready)
    // 获取 VAPID 公钥
    const vapidRes = await fetchVapidPublicKey()
    if (vapidRes.status !== 'success' || !vapidRes.data?.public_key) {
      ElMessage.warning('服务端未配置 VAPID 密钥，使用本地模拟订阅')
      pushSubscriptionObj = { endpoint: 'mock-endpoint-' + Date.now(), keys: { p256dh: 'mock', auth: 'mock' } }
      pushSubscribing.value = false
      return
    }
    const applicationServerKey = urlBase64ToUint8Array(vapidRes.data.public_key)
    pushSubscriptionObj = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey
    })
    // 上报订阅信息
    const sub = pushSubscriptionObj.toJSON()
    await subscribePushApi({
      endpoint: sub.endpoint,
      keys: sub.keys,
      user_agent: navigator.userAgent
    })
    ElMessage.success('订阅成功，将接收实时告警推送')
    loadPushData()
  } catch (e) {
    console.error('订阅失败', e)
    ElMessage.error('订阅失败：' + (e.message || '权限被拒绝'))
  }
  pushSubscribing.value = false
}

async function unsubscribe() {
  if (!pushSubscriptionObj) return
  pushSubscribing.value = true
  try {
    await pushSubscriptionObj.unsubscribe()
    await unsubscribePush(pushSubscriptionObj.endpoint)
    pushSubscriptionObj = null
    ElMessage.success('已取消订阅')
    loadPushData()
  } catch (e) { ElMessage.error('取消订阅失败') }
  pushSubscribing.value = false
}

async function sendTestPush() {
  pushSending.value = true
  try {
    const res = await sendPushNotification({ title: '测试推送', body: '这是一条来自擎翼数字中枢的测试通知', tag: 'test-' + Date.now() })
    if (res.status === 'success') ElMessage.success('测试通知已发送')
    else ElMessage.error(res.message || '发送失败')
    loadPushData()
  } catch (e) { ElMessage.error('发送失败') }
  pushSending.value = false
}

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const rawData = window.atob(base64)
  const arr = new Uint8Array(rawData.length)
  for (let i = 0; i < rawData.length; i++) arr[i] = rawData.charCodeAt(i)
  return arr
}

// ===== 刷新与生命周期 =====
async function refreshAll() {
  refreshing.value = true
  const cat = props.category
  const tasks = []
  if (cat === 'diagnose') tasks.push(loadRul(), loadBenchmark(), loadMultiEnergy())
  else if (cat === 'ops') tasks.push(loadAlerts(), loadAuditBuildings(), loadWorkorders())
  else if (cat === 'esg') tasks.push(loadEsg(), loadRoiScenarios(), loadPushData(), loadEsgCarbon(), loadEsgAdvice())
  await Promise.allSettled(tasks)
  refreshing.value = false
}

function handleResize() {
  ;[benchmarkChart, multiEnergyScheduleChart, multiEnergyComparisonChart, auditTrendChart, auditBreakdownChart, esgRadarChart, esgTrendChart, rulTrendChart, rulCopTrendChart, esgCarbonParetoChart, esgBenchmarkChart, cashflowChart, sensitivityChart, riskRadarChart]
    .forEach(c => c && c.resize && c.resize())
}

onMounted(() => {
  refreshAll()
  window.addEventListener('resize', handleResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  ;[benchmarkChart, multiEnergyScheduleChart, multiEnergyComparisonChart, auditTrendChart, auditBreakdownChart, esgRadarChart, esgTrendChart, rulTrendChart, rulCopTrendChart, esgCarbonParetoChart, esgBenchmarkChart, cashflowChart, sensitivityChart, riskRadarChart]
    .forEach(c => c && c.dispose && c.dispose())
})
</script>

<style scoped>
.advanced-tabs :deep(.el-tabs__header) {
  background: linear-gradient(90deg, #f0fdfa, #ecfeff);
  border-radius: 1rem 1rem 0 0;
}
.advanced-tabs :deep(.el-tabs__item) {
  height: 44px;
  font-weight: 500;
}
.advanced-tabs :deep(.el-tabs__item:hover) {
  color: #0d9488;
}
</style>
