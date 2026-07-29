<template>
  <div class="flex flex-col gap-6 p-6 bg-slate-50 min-h-screen">
    
    <div class="flex justify-between items-center bg-white p-6 rounded-2xl shadow-sm border border-slate-100 shrink-0">
      <div>
        <h2 class="text-2xl font-bold text-slate-800 flex items-center gap-2">
          <el-icon class="text-indigo-600"><Monitor /></el-icon>
          系统数据驾驶舱 (管理空间)
        </h2>
        <p class="text-sm text-slate-500 mt-1">实时监控系统运行状态、AI交互数据与内容运营指标</p>
      </div>
      <div class="flex gap-4 items-center">
        <span class="px-3.5 py-1.5 bg-emerald-50 text-emerald-600 rounded-full text-xs font-bold border border-emerald-100 flex items-center gap-1.5">
          <el-icon><CircleCheck /></el-icon> 运行正常
        </span>
        <span class="text-xs text-slate-400 font-medium flex items-center gap-1">
          <el-icon><Calendar /></el-icon> 最后更新: {{ currentTime }}
        </span>
      </div>
    </div>

    <div class="bg-white rounded-2xl shadow-sm border border-slate-100 flex-1 flex flex-col overflow-hidden">
      <el-tabs v-model="activeTab" class="modern-admin-tabs px-6 pt-4 flex-1 flex flex-col" @tab-change="handleTabChange">
        
        <el-tab-pane name="overview">
          <template #label>
            <div class="flex items-center gap-1.5 text-[15px] font-bold px-2 py-1"><el-icon><DataBoard/></el-icon>孪生全局总览</div>
          </template>
          
          <div class="py-6 flex flex-col gap-6 animate-[fadeIn_0.3s_ease-out]">
            
            <div class="w-full bg-slate-900 rounded-2xl p-6 text-white shadow-xl relative overflow-hidden flex flex-col lg:flex-row items-center justify-between border border-slate-800 gap-6">
              <div class="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGNpcmNsZSBjeD0iMiIgY3k9IjIiIHI9IjEiIGZpbGw9InJnYmEoMjU1LDI1NSwyNTUsMC4wNSkiLz48L3N2Zz4=')] opacity-30"></div>
              <div class="absolute -right-20 -top-20 w-80 h-80 bg-indigo-600 rounded-full blur-[100px] opacity-30"></div>
              <div class="absolute -left-20 -bottom-20 w-64 h-64 bg-emerald-600 rounded-full blur-[100px] opacity-20"></div>

              <div class="relative z-10 flex items-center gap-8 w-full lg:w-2/3">
                <div class="text-center shrink-0">
                  <el-progress type="dashboard" :percentage="98.5" color="#10b981" :width="110" :stroke-width="8">
                    <template #default="{ percentage }">
                      <span class="text-2xl font-black block text-white">{{ percentage }}<span class="text-sm font-normal">%</span></span>
                      <span class="text-[10px] text-slate-400 font-bold">系统健康度</span>
                    </template>
                  </el-progress>
                </div>
                <div class="flex flex-col gap-2">
                  <h2 class="text-2xl font-bold flex items-center gap-2 tracking-wide">
                    <el-icon class="text-indigo-400"><Cpu/></el-icon> 边缘孪生算力控制台
                  </h2>
                  <p class="text-slate-400 text-sm">当前已接入 3,254 个底层设备节点，AIgent 引擎持续并行护航中。</p>
                  <div class="flex flex-wrap gap-3 mt-2">
                    <span class="bg-indigo-500/20 border border-indigo-500/30 px-3 py-1 rounded-md text-xs font-mono text-indigo-300 flex items-center gap-1.5"><div class="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-pulse"></div> GPU: 65%</span>
                    <span class="bg-emerald-500/20 border border-emerald-500/30 px-3 py-1 rounded-md text-xs font-mono text-emerald-300 flex items-center gap-1.5"><div class="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse"></div> RAG 延迟: 12ms</span>
                    <span class="bg-blue-500/20 border border-blue-500/30 px-3 py-1 rounded-md text-xs font-mono text-blue-300 flex items-center gap-1.5"><div class="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse"></div> 吞吐: 1.2k/s</span>
                  </div>
                </div>
              </div>

              <div class="relative z-10 w-full lg:w-1/3 bg-black/40 border border-white/10 rounded-xl p-4 h-32 overflow-hidden font-mono text-xs flex flex-col">
                <div class="text-emerald-400 mb-2 border-b border-white/10 pb-1.5 flex items-center gap-2 shrink-0">
                  <el-icon class="animate-spin-slow"><Setting/></el-icon> 实时引擎调度流
                </div>
                <div class="text-slate-300 space-y-1.5 opacity-80 flex-1 overflow-hidden">
                  <p class="truncate">> [10:45:12] 调频指令已下发至冷机集群 #2...</p>
                  <p class="truncate text-indigo-300">> [10:45:14] 成功拦截末端 VAV 通讯异常风险.</p>
                  <p class="truncate">> [10:45:18] GraphRAG 图谱新增 3 个故障节点...</p>
                  <p class="truncate">> [10:45:21] 等待下一轮采集周期...</p>
                </div>
              </div>
            </div>
            
            <SkeletonLoader v-if="dashboardLoading" type="kpi" />
            <ErrorState v-else-if="dashboardError"
              :message="dashboardError"
              detail="无法加载管理后台 KPI 数据"
              @retry="loadDashboard"
            />
            <div v-else class="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
              <div v-for="(kpi, index) in kpis" :key="index" class="bg-white p-4 rounded-2xl border border-slate-100 hover:border-indigo-300 hover:shadow-xl hover:-translate-y-1 transition-all duration-300 relative overflow-hidden group">
                <div class="flex justify-between items-start mb-1">
                  <div :class="`p-2 rounded-xl ${kpi.bg} ${kpi.color}`">
                    <el-icon class="text-lg"><component :is="kpi.icon" /></el-icon>
                  </div>
                  <span :class="`font-bold px-1.5 py-0.5 rounded text-[10px] border ${kpi.trend.startsWith('+') ? 'text-emerald-600 bg-emerald-50 border-emerald-100' : 'text-rose-600 bg-rose-50 border-rose-100'}`">
                    {{ kpi.trend }}
                  </span>
                </div>
                <p class="text-[11px] font-bold text-slate-500 mt-2">{{ kpi.title }}</p>
                <h3 class="text-2xl font-black text-slate-800 tracking-tight mt-0.5">{{ kpi.value }}</h3>
                <div class="w-full h-1 bg-slate-100 rounded-full mt-3 overflow-hidden">
                  <div :class="`h-full rounded-full ${kpi.trend.startsWith('+') ? 'bg-emerald-400' : 'bg-indigo-400'}`" :style="`width: ${Math.random() * 40 + 50}%`"></div>
                </div>
              </div>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[360px]">
              
              <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-5 flex flex-col relative group">
                <div class="flex justify-between items-center mb-2">
                  <h3 class="font-bold text-slate-800 text-sm flex items-center gap-2"><div class="w-1.5 h-3 bg-indigo-500 rounded-full"></div>AI 调度与异常拦截</h3>
                  <el-tag size="small" type="primary" effect="plain" round class="scale-90">近七天</el-tag>
                </div>
                <div ref="trendChartRef" class="flex-1 w-full"></div>
              </div>

              <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-5 flex flex-col relative group">
                <div class="flex justify-between items-center mb-2">
                  <h3 class="font-bold text-slate-800 text-sm flex items-center gap-2"><div class="w-1.5 h-3 bg-blue-500 rounded-full"></div>孪生多维健康度雷达</h3>
                </div>
                <div ref="radarChartRef" class="flex-1 w-full"></div>
              </div>

              <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-5 flex flex-col relative group">
                <div class="flex justify-between items-center mb-2">
                  <h3 class="font-bold text-slate-800 text-sm flex items-center gap-2"><div class="w-1.5 h-3 bg-emerald-500 rounded-full"></div>系统能耗拓扑</h3>
                </div>
                <div ref="donutChartRef" class="flex-1 w-full relative">
                  <div class="absolute inset-0 flex flex-col items-center justify-center pointer-events-none mt-2">
                    <span class="text-2xl font-black text-slate-800">100<span class="text-sm font-normal">%</span></span>
                    <span class="text-[10px] text-slate-400 font-bold">总负载</span>
                  </div>
                </div>
              </div>

            </div>

          </div>
        </el-tab-pane>

        <el-tab-pane name="kb">
          <template #label>
            <div class="flex items-center gap-1.5 text-[15px] font-bold px-2 py-1"><el-icon><Coin/></el-icon>知识库与模型训练</div>
          </template>
          
          <div class="py-6">
            <div class="grid grid-cols-1 xl:grid-cols-3 gap-6 mb-6">
              
              <div class="xl:col-span-2 flex flex-col gap-4">
                
                <div class="bg-slate-100/80 p-1.5 rounded-xl border border-slate-200 flex w-fit mb-2">
                  <div @click="kbMode = 'upload'" :class="kbMode === 'upload' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'" class="cursor-pointer px-5 py-2.5 rounded-lg text-sm font-bold transition-all duration-300 flex items-center gap-2">
                    <el-icon><Upload /></el-icon> 批量文档解析
                  </div>
                  <div @click="kbMode = 'manual'" :class="kbMode === 'manual' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'" class="cursor-pointer px-5 py-2.5 rounded-lg text-sm font-bold transition-all duration-300 flex items-center gap-2">
                    <el-icon><EditPen /></el-icon> 手动喂入新知识
                  </div>
                  <div @click="kbMode = 'manage'" :class="kbMode === 'manage' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'" class="cursor-pointer px-5 py-2.5 rounded-lg text-sm font-bold transition-all duration-300 flex items-center gap-2">
                    <el-icon><DataLine /></el-icon> 实时知识点管理
                  </div>
                </div>

                <div v-show="kbMode === 'upload'" class="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex flex-col animate-fade-in">
                  <h3 class="text-lg font-bold text-slate-800 mb-6 flex items-center gap-2">
                    <el-icon class="text-indigo-600" size="20"><FolderOpened /></el-icon> 上传本地文件构建知识
                  </h3>
                  <el-upload class="w-full perfect-drag-upload" drag action="http://127.0.0.1:8000/api/upload_doc" multiple :auto-upload="false" :on-change="handleFileChange">
                    <div class="upload-inner-content">
                      <div class="icon-wrapper"><el-icon class="upload-icon"><UploadFilled /></el-icon></div>
                      <div class="text-base font-bold text-indigo-900 mt-4">点击或拖拽文件到此处上传</div>
                      <div class="text-sm text-slate-500 mt-2">支持 <span class="font-semibold text-slate-700">PDF, DOCX, TXT, MD</span> 格式</div>
                    </div>
                  </el-upload>
                  <div class="mt-8">
                    <h4 class="text-sm font-bold text-slate-700 mb-3">AI 智能解析引擎</h4>
                    <div class="flex flex-col gap-3">
                      <div class="flex items-center justify-between p-4 bg-white rounded-xl border border-slate-200 shadow-sm hover:border-indigo-300 transition-colors">
                        <div class="flex items-center gap-4">
                          <div class="w-10 h-10 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0"><el-icon size="22"><Cpu /></el-icon></div>
                          <div>
                            <p class="text-sm font-bold text-slate-800">启用大模型深度结构化解析</p>
                            <p class="text-xs text-slate-500 mt-1">自动提取图表、表格及隐含结构，检索召回率更高</p>
                          </div>
                        </div>
                        <el-switch v-model="enableDeepParsing" style="--el-switch-on-color: #4f46e5; --el-switch-off-color: #cbd5e1" />
                      </div>
                      <div class="flex items-center justify-between p-4 bg-white rounded-xl border border-slate-200 shadow-sm hover:border-violet-300 transition-colors">
                        <div class="flex items-center gap-4">
                          <div class="w-10 h-10 rounded-lg bg-violet-50 text-violet-600 flex items-center justify-center shrink-0"><el-icon size="22"><Share /></el-icon></div>
                          <div>
                            <p class="text-sm font-bold text-slate-800">提取实体并构建知识图谱 (GraphRAG)</p>
                            <p class="text-xs text-slate-500 mt-1">抽取文本中的实体与关系构建图数据库，提升复杂推理能力</p>
                          </div>
                        </div>
                        <el-switch v-model="enableGraph" style="--el-switch-on-color: #8b5cf6; --el-switch-off-color: #cbd5e1" />
                      </div>
                    </div>
                  </div>
                  <div class="mt-6 pt-6 border-t border-slate-100">
                    <h4 class="text-sm font-bold text-slate-700 mb-4 flex items-center gap-2"><el-icon class="text-slate-500"><Setting /></el-icon>文本分块与清洗规则</h4>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div class="bg-slate-50 p-4 rounded-xl border border-slate-100">
                        <div class="mb-4">
                          <div class="flex justify-between items-center mb-1">
                            <span class="text-sm font-medium text-slate-700">分段最大长度</span><span class="text-xs font-bold text-indigo-600 bg-indigo-100 px-2 py-0.5 rounded">{{ chunkConfig.size }}</span>
                          </div>
                          <el-slider v-model="chunkConfig.size" :min="100" :max="2000" :step="100" size="small" />
                        </div>
                        <div>
                          <div class="flex justify-between items-center mb-1">
                            <span class="text-sm font-medium text-slate-700">相邻重叠 (Overlap)</span><span class="text-xs font-bold text-emerald-600 bg-emerald-100 px-2 py-0.5 rounded">{{ chunkConfig.overlap }}</span>
                          </div>
                          <el-slider v-model="chunkConfig.overlap" :min="0" :max="500" :step="10" size="small" />
                        </div>
                      </div>
                      <div class="bg-slate-50 p-4 rounded-xl border border-slate-100">
                        <div class="flex items-center gap-2 mb-3"><el-icon class="text-slate-500"><Filter /></el-icon><span class="text-sm font-medium text-slate-700">数据预清洗</span></div>
                        <el-checkbox-group v-model="cleanRules" class="flex flex-col gap-2">
                          <el-checkbox value="remove_urls" class="!mr-0 !text-slate-600">清除 URL 链接</el-checkbox>
                          <el-checkbox value="remove_emails" class="!mr-0 !text-slate-600">清除邮箱地址 (脱敏)</el-checkbox>
                        </el-checkbox-group>
                      </div>
                    </div>
                  </div>
                  <div class="mt-8 flex justify-end">
                    <el-button type="primary" @click="startProcessing" class="!bg-indigo-600 !border-none hover:!bg-indigo-700 !rounded-xl !h-11 !px-8 text-sm font-medium shadow-md shadow-indigo-200">
                      <el-icon class="mr-2"><Upload /></el-icon> 开始处理与向量化
                    </el-button>
                  </div>
                </div>

                <div v-show="kbMode === 'manual'" class="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex flex-col animate-fade-in">
                  <div class="flex items-center justify-between mb-6">
                    <h3 class="text-lg font-bold text-slate-800 flex items-center gap-2"><el-icon class="text-emerald-500" size="20"><EditPen /></el-icon> 手动录入 / Q&A 快速训练</h3>
                    <span class="text-xs text-slate-400 bg-slate-100 px-2 py-1 rounded">直接干预 AI 回答</span>
                  </div>
                  <el-form :model="manualForm" label-position="top" class="flex flex-col gap-2">
                    <el-form-item label="知识点标题 / 核心摘要 (必填)">
                      <el-input v-model="manualForm.title" placeholder="例如：如何计算COP指数？" class="!h-10" />
                    </el-form-item>
                    <el-form-item label="详细知识内容 (支持常见问题 Q&A 格式)">
                      <el-input type="textarea" v-model="manualForm.content" :rows="6" placeholder="输入具体的内容让 AI 学习...\n\n格式参考：\nQ: 双碳政策如何实施？\nA: 通过能源转型、产业升级、市场机制、及全民行动协同实施" />
                    </el-form-item>
                    <el-form-item label="所属领域 / 标签">
                      <el-input v-model="manualForm.tags" placeholder="如：政策导向, 技术, 故障检测、计算公式 (逗号分隔)" class="!h-10" />
                    </el-form-item>
                    <div class="mt-4 flex justify-end">
                      <el-button type="success" @click="submitManualTraining" class="!bg-emerald-500 !border-none hover:!bg-emerald-600 !rounded-xl !h-11 !px-8 text-sm font-bold shadow-md shadow-emerald-200">
                        <el-icon class="mr-2"><Cpu /></el-icon> 立即训练 AI
                      </el-button>
                    </div>
                  </el-form>
                </div>

                <div v-show="kbMode === 'manage'" class="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex flex-col animate-fade-in">
                  <div class="flex items-center justify-between mb-4">
                    <h3 class="text-lg font-bold text-slate-800 flex items-center gap-2"><el-icon class="text-sky-500" size="20"><DataLine /></el-icon> 数据库现有知识点 (Data Viewer)</h3>
                    <el-input v-model="searchKnowledge" placeholder="搜索实体或内容..." class="!w-64" prefix-icon="Search" />
                  </div>
                  <SkeletonLoader v-if="kbLoading" type="table" />
                  <ErrorState v-else-if="kbError"
                    :message="kbError"
                    detail="无法加载知识库列表"
                    @retry="loadKnowledgeList"
                  />
                  <el-table v-else :data="knowledgeList" stripe style="width: 100%" :max-height="450">
                    <el-table-column prop="id" label="区块 ID" width="100" />
                    <el-table-column prop="type" label="数据类型" width="110">
                      <template #default="scope">
                        <el-tag :type="scope.row.type === '手动录入' ? 'success' : (scope.row.type === '图谱实体' ? 'warning' : 'primary')" size="small" class="!rounded-md">
                          {{ scope.row.type }}
                        </el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column prop="content" label="切片/实体内容" show-overflow-tooltip />
                    <el-table-column prop="source" label="知识来源" width="140">
                      <template #default="scope">
                        <span class="text-xs text-slate-500 flex items-center gap-1"><el-icon><Document /></el-icon>{{ scope.row.source }}</span>
                      </template>
                    </el-table-column>
                    <el-table-column label="操作" width="120" fixed="right" align="center">
                      <template #default="scope">
                        <el-button link type="primary" size="small" @click="handleEdit(scope.row, scope.$index)">编辑</el-button>
                        <el-button link type="danger" size="small" @click="handleDelete(scope.row, scope.$index)">删除</el-button>
                      </template>
                    </el-table-column>
                  </el-table>
                </div>

              </div>

              <div class="flex flex-col gap-6">
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                  <h3 class="text-base font-bold text-slate-800 mb-4 flex items-center gap-2">
                    <el-icon class="text-emerald-500"><DataBoard /></el-icon> 向量库实时状态
                  </h3>
                  <div class="space-y-3">
                    <div class="flex justify-between items-center p-3 bg-slate-50 rounded-lg border border-slate-100">
                      <span class="text-sm font-medium text-slate-600">已处理切片数</span>
                      <span class="font-bold text-slate-800 text-lg">{{ kbCount }}</span>
                    </div>
                    <div class="flex justify-between items-center p-3 bg-slate-50 rounded-lg border border-slate-100">
                      <span class="text-sm font-medium text-slate-600">已提取图谱节点</span>
                      <span class="font-bold text-violet-600 text-lg">1,208</span>
                    </div>
                    <div class="flex justify-between items-center p-3 bg-slate-50 rounded-lg border border-slate-100">
                      <span class="text-sm font-medium text-slate-600">召回模型</span>
                      <span class="text-xs font-bold px-2 py-1 bg-slate-200 text-slate-700 rounded-md">text-embedding-v2</span>
                    </div>
                  </div>
                </div>

                <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex-1">
                  <h3 class="text-base font-bold text-slate-800 mb-2 flex items-center gap-2">
                    <el-icon class="text-amber-500"><MagicStick /></el-icon> 混合检索测试
                  </h3>
                  <p class="text-xs text-slate-500 mb-4">模拟 AI 搜索，测试当前知识库的切片与图谱匹配度。</p>
                  
                  <div class="flex gap-2 mb-4">
                    <el-input v-model="testQuery" placeholder="输入用户可能问的问题..." class="!rounded-lg" @keyup.enter="runHitTest" />
                    <el-button type="primary" plain class="!rounded-lg" @click="runHitTest">
                      <el-icon><Search /></el-icon>
                    </el-button>
                  </div>

                  <div class="bg-slate-50 rounded-xl border border-slate-100 p-4 h-64 overflow-y-auto flex flex-col relative">
                    
                    <div v-if="!isSearching && testResults.length === 0" class="flex flex-col items-center justify-center text-slate-400 h-full">
                      <el-icon size="32" class="mb-2"><Document /></el-icon>
                      <p class="text-sm">暂无检索结果，请发起测试</p>
                    </div>

                    <div v-else-if="isSearching" class="flex flex-col items-center justify-center text-indigo-400 h-full">
                      <el-icon size="32" class="is-loading mb-2"><Loading /></el-icon>
                      <p class="text-sm font-bold">AI 正在进行向量与图谱混合检索...</p>
                    </div>

                    <div v-else class="flex flex-col gap-3">
                      <div v-for="(item, index) in testResults" :key="index" class="bg-white p-3 rounded-lg border border-slate-200 shadow-sm relative hover:border-indigo-300 transition-colors">
                        <div class="flex justify-between items-center mb-2">
                          <span :class="item.type === '向量召回' ? 'bg-blue-50 text-blue-600 border-blue-100' : 'bg-violet-50 text-violet-600 border-violet-100'" class="px-2 py-0.5 rounded text-[11px] font-bold border">
                            {{ item.type }}
                          </span>
                          <span class="text-[11px] text-emerald-600 font-bold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-100">
                            相关度得分: {{ item.score }}
                          </span>
                        </div>
                        <p class="text-xs text-slate-600 leading-relaxed">{{ item.content }}</p>
                        <div class="text-[10px] text-slate-400 mt-2 text-right">来源区块 ID: {{ item.id }}</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

            </div>

            <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex flex-col">
              <div class="flex justify-between items-center mb-4">
                <div>
                  <h3 class="text-lg font-bold text-slate-800 flex items-center gap-2">
                    <el-icon class="text-violet-600"><Share /></el-icon> 神经符号知识网络 (Neuro-Symbolic Graph)
                  </h3>
                  <p class="text-xs text-slate-500 mt-1">基于 GraphRAG 提取的高维实体关联，支持无限画布拖拽、缩放与穿透式高亮。</p>
                </div>
                <div class="flex items-center gap-2 text-xs font-bold text-indigo-600 bg-indigo-50 px-3 py-1.5 rounded-lg border border-indigo-100 shadow-inner">
                  <span class="flex h-2 w-2 relative">
                    <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                    <span class="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
                  </span>
                  AI 引擎实时演算中
                </div>
              </div>
              
              <div class="relative w-full h-[500px] rounded-xl border border-slate-200 overflow-hidden group">
                <div class="absolute inset-0 tech-canvas-bg opacity-60"></div>
                
                <div id="graphChart" class="absolute inset-0 z-10"></div>

                <div class="absolute bottom-4 right-4 z-20 flex flex-col bg-white/90 backdrop-blur-md p-1 rounded-xl shadow-lg border border-slate-100/50 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                  <el-tooltip content="放大 (Zoom In)" placement="left">
                    <button @click="changeZoom(0.2)" class="p-2 text-slate-500 hover:text-indigo-600 hover:bg-slate-50 rounded-lg transition-colors"><el-icon size="18"><Plus /></el-icon></button>
                  </el-tooltip>
                  <div class="w-full h-px bg-slate-100 my-0.5"></div>
                  <el-tooltip content="缩小 (Zoom Out)" placement="left">
                    <button @click="changeZoom(-0.2)" class="p-2 text-slate-500 hover:text-indigo-600 hover:bg-slate-50 rounded-lg transition-colors"><el-icon size="18"><Minus /></el-icon></button>
                  </el-tooltip>
                  <div class="w-full h-px bg-slate-100 my-0.5"></div>
                  <el-tooltip content="自适应视图 (Fit View)" placement="left">
                    <button @click="resetZoom" class="p-2 text-slate-500 hover:text-indigo-600 hover:bg-slate-50 rounded-lg transition-colors"><el-icon size="18"><Aim /></el-icon></button>
                  </el-tooltip>
                </div>
              </div>
            </div>

          </div>
        </el-tab-pane>

        <el-tab-pane name="audit">
          <template #label>
            <div class="flex items-center gap-1.5 font-medium px-2 py-1">
              <el-icon><View /></el-icon> 调度审计与画像
            </div>
          </template>
          
          <div class="py-6 flex flex-col gap-6 animate-[fadeIn_0.3s_ease-out]">
            
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div class="bg-white p-5 rounded-2xl border border-slate-100 shadow-sm flex items-center justify-between">
                <div>
                  <p class="text-xs font-bold text-slate-500 mb-1">累计对话交互</p>
                  <h3 class="text-2xl font-black text-slate-800">{{ auditTotal.toLocaleString() }} <span class="text-sm font-normal text-slate-400">次</span></h3>
                </div>
                <div class="p-3 bg-indigo-50 rounded-xl text-indigo-600"><el-icon size="24"><ChatDotRound /></el-icon></div>
              </div>
              <div class="bg-white p-5 rounded-2xl border border-slate-100 shadow-sm flex items-center justify-between">
                <div>
                  <p class="text-xs font-bold text-slate-500 mb-1">意图识别准确率</p>
                  <h3 class="text-2xl font-black text-slate-800">99.4 <span class="text-sm font-normal text-slate-400">%</span></h3>
                </div>
                <div class="p-3 bg-emerald-50 rounded-xl text-emerald-600"><el-icon size="24"><Aim /></el-icon></div>
              </div>
              <div class="bg-white p-5 rounded-2xl border border-slate-100 shadow-sm flex items-center justify-between relative overflow-hidden">
                <div class="relative z-10">
                  <p class="text-xs font-bold text-rose-500 mb-1">拦截高危操作</p>
                  <h3 class="text-2xl font-black text-rose-600">{{ auditHighRiskCount }} <span class="text-sm font-normal text-rose-400">次</span></h3>
                </div>
                    <div class="absolute -right-4 -bottom-4 text-rose-100 opacity-50"><el-icon size="80"><Lock /></el-icon></div>              </div>
              <div class="bg-gradient-to-r from-slate-800 to-indigo-900 p-5 rounded-2xl shadow-sm flex flex-col justify-center text-white">
                <p class="text-xs font-bold text-indigo-300 mb-2">当前活跃画像库</p>
                <div class="flex -space-x-3">
                  <img class="w-8 h-8 rounded-full border-2 border-slate-800 z-30" src="https://api.dicebear.com/7.x/avataaars/svg?seed=Felix" alt="User 1">
                  <img class="w-8 h-8 rounded-full border-2 border-slate-800 z-20" src="https://api.dicebear.com/7.x/avataaars/svg?seed=Jack" alt="User 2">
                  <img class="w-8 h-8 rounded-full border-2 border-slate-800 z-10" src="https://api.dicebear.com/7.x/avataaars/svg?seed=Leo" alt="User 3">
                  <div class="w-8 h-8 rounded-full border-2 border-slate-800 bg-slate-700 flex items-center justify-center text-[10px] font-bold">+12</div>
                </div>
              </div>
            </div>

            <div class="grid grid-cols-1 xl:grid-cols-3 gap-6 h-[500px]">
              
              <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-5 flex flex-col h-full">
                <div class="flex justify-between items-center mb-4">
                  <h3 class="font-bold text-slate-800 text-sm flex items-center gap-2">
                    <div class="w-1.5 h-3 bg-indigo-500 rounded-full"></div> 语义意图聚类挖掘
                  </h3>
                  <el-button link type="primary" size="small">深度报告</el-button>
                </div>
                <div ref="intentChartRef" class="flex-1 w-full min-h-[220px]"></div>
                
                <div class="mt-4 border-t border-slate-50 pt-4">
                  <p class="text-xs font-bold text-slate-400 mb-3">近期对话高频实体 (Hot Entities)</p>
                  <div class="flex flex-wrap gap-2">
                    <span class="px-2.5 py-1 bg-rose-50 text-rose-600 border border-rose-100 rounded-lg text-xs font-bold shadow-sm">冷却塔风机频率 (89次)</span>
                    <span class="px-2.5 py-1 bg-indigo-50 text-indigo-600 border border-indigo-100 rounded-lg text-xs font-bold shadow-sm">COP 效能比 (76次)</span>
                    <span class="px-2.5 py-1 bg-slate-100 text-slate-600 border border-slate-200 rounded-lg text-xs font-bold">VAV 末端 (45次)</span>
                    <span class="px-2.5 py-1 bg-slate-100 text-slate-600 border border-slate-200 rounded-lg text-xs font-bold">冷水机组通讯 (32次)</span>
                  </div>
                </div>
              </div>

              <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-5 flex flex-col h-full">
                <div class="flex justify-between items-center mb-6">
                  <h3 class="font-bold text-slate-800 text-sm flex items-center gap-2">
                    <div class="w-1.5 h-3 bg-emerald-500 rounded-full"></div> 典型用户数字画像
                  </h3>
                  <el-select v-model="selectedPersona" size="small" class="!w-28">
                    <el-option label="王建国" value="1" />
                    <el-option label="李强" value="2" />
                  </el-select>
                </div>
                
                <div class="bg-slate-50 rounded-xl border border-slate-200 p-5 flex-1 flex flex-col relative overflow-hidden">
                  <div class="absolute top-0 right-0 w-32 h-32 bg-emerald-500/10 rounded-full blur-[40px]"></div>
                  
                  <div class="flex items-center gap-4 mb-6 relative z-10">
                    <div class="w-16 h-16 rounded-2xl bg-white shadow-md p-1 border border-slate-100">
                      <img src="https://api.dicebear.com/7.x/avataaars/svg?seed=Felix" class="w-full h-full rounded-xl bg-slate-100" />
                    </div>
                    <div>
                      <h4 class="text-lg font-black text-slate-800">王建国 <span class="text-xs font-normal text-slate-500 ml-2">工号: ENG-084</span></h4>
                      <div class="flex gap-2 mt-1.5">
                        <span class="px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded text-[10px] font-bold">能效优化师</span>
                        <span class="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-[10px] font-bold">高级依赖</span>
                      </div>
                    </div>
                  </div>

                  <div class="space-y-4 relative z-10 flex-1">
                    <div>
                      <div class="flex justify-between text-xs font-bold text-slate-600 mb-1">
                        <span>复杂推理请求占比</span> <span>85%</span>
                      </div>
                      <el-progress :percentage="85" color="#10b981" :show-text="false" :stroke-width="6" />
                    </div>
                    <div>
                      <div class="flex justify-between text-xs font-bold text-slate-600 mb-1">
                        <span>直接控制指令频次</span> <span>20%</span>
                      </div>
                      <el-progress :percentage="20" color="#f59e0b" :show-text="false" :stroke-width="6" />
                    </div>
                    <div>
                      <div class="flex justify-between text-xs font-bold text-slate-600 mb-1">
                        <span>AI 建议采纳率</span> <span>94%</span>
                      </div>
                      <el-progress :percentage="94" color="#3b82f6" :show-text="false" :stroke-width="6" />
                    </div>
                  </div>

                  <div class="mt-4 pt-4 border-t border-slate-200 relative z-10">
                    <p class="text-xs text-slate-500 leading-relaxed font-medium">
                      <span class="font-bold text-indigo-600">AI 总结评语：</span>该工程师偏好让 AI 进行多维度的能耗对比分析，属于典型的“分析驱动型”运维，极少发送高危强控指令。
                    </p>
                  </div>
                </div>
              </div>

              <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-0 flex flex-col h-full overflow-hidden">
                <div class="p-5 border-b border-slate-50 flex justify-between items-center bg-slate-50/50">
                  <h3 class="font-bold text-slate-800 text-sm flex items-center gap-2">
                    <div class="w-1.5 h-3 bg-rose-500 rounded-full"></div> 关键对话拦截审计流
                  </h3>
                  <el-tag size="small" type="danger" effect="dark" round>高保真日志</el-tag>
                </div>
                
                <div class="flex-1 overflow-y-auto p-5 space-y-4">
                  <SkeletonLoader v-if="auditLoading" type="row" :rows="4" />
                  <ErrorState v-else-if="auditError"
                    :message="auditError"
                    detail="无法加载审计日志"
                    @retry="loadAuditLogs"
                  />
                  <template v-else>
                    <div v-for="log in auditLogs" :key="log.id" class="flex flex-col gap-2 pb-4 border-b border-slate-50 last:border-0">
                      <div class="flex items-start gap-2">
                        <div class="w-6 h-6 rounded bg-slate-100 border border-slate-200 flex items-center justify-center shrink-0 mt-0.5"><el-icon size="12" class="text-slate-500"><User /></el-icon></div>
                        <div class="flex-1">
                          <div class="flex justify-between items-center mb-0.5">
                            <span class="text-xs font-bold text-slate-700">{{ log.user }}</span>
                            <span class="text-[10px] text-slate-400 font-mono">{{ log.time }}</span>
                          </div>
                          <p class="text-xs text-slate-600 bg-slate-50 p-2 rounded-lg border border-slate-100 break-all">{{ log.query }}</p>
                        </div>
                      </div>
                      <div class="flex items-start gap-2 pl-8">
                        <div :class="`w-6 h-6 rounded flex items-center justify-center shrink-0 mt-0.5 ${log.risk === 'high' ? 'bg-rose-100 text-rose-600 border border-rose-200' : 'bg-indigo-100 text-indigo-600 border border-indigo-200'}`">
                          <el-icon size="12"><component :is="log.risk === 'high' ? 'Warning' : 'Cpu'" /></el-icon>
                        </div>
                        <div class="flex-1">
                          <div class="flex items-center gap-2 mb-0.5">
                            <span class="text-xs font-bold text-slate-700">AIgent 响应</span>
                            <span :class="`text-[9px] px-1.5 py-0.5 rounded border font-bold ${log.risk === 'high' ? 'bg-rose-50 text-rose-600 border-rose-200' : 'bg-emerald-50 text-emerald-600 border-emerald-200'}`">
                              {{ log.risk === 'high' ? '高危拦截' : '合规放行' }}
                            </span>
                          </div>
                          <p :class="`text-xs p-2 rounded-lg border break-all ${log.risk === 'high' ? 'bg-rose-50 border-rose-100 text-rose-700' : 'bg-indigo-50 border-indigo-100 text-indigo-700'}`">
                            {{ log.aiResponse }}
                          </p>
                        </div>
                      </div>
                    </div>
                  </template>
                </div>
              </div>

            </div>
          </div>
        </el-tab-pane>


        <el-tab-pane name="messages">
          <template #label>
            <div class="flex items-center gap-1.5 font-medium">
              <el-icon><Bell /></el-icon> 消息与调度日志
              <span class="flex h-2 w-2 relative ml-1">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                <span class="relative inline-flex rounded-full h-2 w-2 bg-rose-500"></span>
              </span>
            </div>
          </template>
          
          <div class="flex flex-col gap-6 animate-[fadeIn_0.3s_ease-out]">
            <div class="flex justify-between items-center bg-white p-4 rounded-xl shadow-sm border border-slate-100">
              <div class="flex items-center gap-4 w-1/3">
                <el-input v-model="messageSearch" placeholder="搜索设备编号、告警内容..." prefix-icon="Search" clearable />
              </div>
              <div class="flex items-center gap-3">
                <el-radio-group v-model="messageStatus" size="default">
                  <el-radio-button value="all">全部日志</el-radio-button>
                  <el-radio-button value="unread">未读告警 (2)</el-radio-button>
                </el-radio-group>
                <el-button type="primary" color="#4f46e5" icon="Check" plain>全部标为已读</el-button>
              </div>
            </div>

            <div class="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
              <el-table :data="messagesData" style="width: 100%" :header-cell-style="{ background: '#f8fafc', color: '#64748b', fontWeight: 'bold' }">
                <el-table-column width="60" align="center">
                  <template #default="{ row }">
                    <div class="relative flex justify-center items-center">
                      <div v-if="row.status === 'unread'" class="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-rose-500 z-10"></div>
                      <div :class="['w-8 h-8 rounded-full flex items-center justify-center border', getMessageStyle(row.level).bg, getMessageStyle(row.level).color, getMessageStyle(row.level).border]">
                        <el-icon><component :is="getMessageStyle(row.level).icon" /></el-icon>
                      </div>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="类型" width="120">
                  <template #default="{ row }">
                    <span :class="['px-2 py-1 rounded text-xs font-bold border', getMessageStyle(row.level).bg, getMessageStyle(row.level).color, getMessageStyle(row.level).border]">
                      {{ getMessageStyle(row.level).text }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column prop="source" label="发生源/设备" width="160">
                  <template #default="{ row }">
                    <span class="font-mono text-slate-800 font-bold bg-slate-50 px-2 py-1 rounded">{{ row.source }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="content" label="日志详情" show-overflow-tooltip>
                  <template #default="{ row }">
                    <span :class="row.status === 'unread' ? 'text-slate-800 font-medium' : 'text-slate-500'">{{ row.content }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="time" label="发生时间" width="120" align="center">
                  <template #default="{ row }">
                    <span class="text-xs text-slate-400 font-mono">{{ row.time }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="160" align="center" fixed="right">
                  <template #default="{ row }">
                    <div class="flex justify-center gap-2">
                      <el-button size="small" type="primary" link v-if="row.level === 'critical'">生成工单</el-button>
                      <el-button size="small" type="info" link v-else>详情</el-button>
                      <el-button size="small" type="danger" link icon="Delete"></el-button>
                    </div>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane name="toolbox">
          <template #label>
            <div class="flex items-center gap-1.5 font-medium">
              <el-icon><MagicStick /></el-icon> AI 运维工具箱
            </div>
          </template>
          
          <div class="flex flex-col gap-6 animate-[fadeIn_0.3s_ease-out]">
            <div class="bg-gradient-to-r from-slate-800 to-indigo-900 rounded-2xl p-8 text-white shadow-md relative overflow-hidden">
              <div class="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGNpcmNsZSBjeD0iMiIgY3k9IjIiIHI9IjEiIGZpbGw9InJnYmEoMjU1LDI1NSwyNTUsMC4wNykiLz48L3N2Zz4=')]"></div>
              <div class="relative z-10">
                <h3 class="text-2xl font-bold mb-2 flex items-center gap-2">
                  <el-icon><Setting /></el-icon> 设施与算法联调引擎
                </h3>
                <p class="text-slate-300 max-w-2xl text-sm leading-relaxed">
                  为电气工程师与算法人员提供的快捷插件。在这里对传感器底层数据进行清洗预处理，或在虚拟沙盘中推演 AIgent 调度策略的安全边界，防止物理设备受损。
                </p>
              </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <div v-for="tool in aiTools" :key="tool.id" 
                   class="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm hover:shadow-lg hover:-translate-y-1 hover:border-indigo-200 transition-all duration-300 cursor-pointer group flex flex-col h-full">
                <div class="flex items-center justify-between mb-4">
                  <div :class="['w-12 h-12 rounded-xl flex items-center justify-center border', tool.bg, tool.color, tool.border]">
                    <el-icon size="24"><component :is="tool.icon" /></el-icon>
                  </div>
                  <el-icon class="text-slate-300 group-hover:text-indigo-500 transition-colors" size="20"><TopRight /></el-icon>
                </div>
                <h4 class="text-lg font-bold text-slate-800 mb-2 group-hover:text-indigo-600 transition-colors">{{ tool.name }}</h4>
                <p class="text-sm text-slate-500 leading-relaxed flex-1">{{ tool.desc }}</p>
                
                <div class="mt-6 pt-4 border-t border-slate-50 flex items-center justify-between">
                  <span class="text-xs font-semibold font-mono text-slate-400">Plugin Ready</span>
                  <button class="text-sm font-bold text-indigo-600 bg-indigo-50 hover:bg-indigo-600 hover:text-white px-4 py-1.5 rounded-lg transition-colors">
                    加载执行
                  </button>
                </div>
              </div>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { ElMessage, ElMessageBox } from 'element-plus'

// API 接口层
import {
  fetchAdminDashboard,
  fetchAuditLogs,
  fetchKnowledgeList,
  uploadKnowledgeItem,
  deleteKnowledgeItem
} from '../api/index.js'
// 骨架屏与错误兜底组件
import SkeletonLoader from '../components/SkeletonLoader.vue'
import ErrorState from '../components/ErrorState.vue'

// 一次性导入所有需要的图标（包括顶部按钮、控制台、知识库等）
import {
  Monitor, CircleCheck, Calendar, DataBoard, Cpu,
  Lightning, Connection, Setting, Document, Coin, Upload,
  UploadFilled, EditPen, DataLine, Search, Loading, Share,
  Plus, Minus, Aim, Bell, Check, InfoFilled, SuccessFilled,
  TopRight, FolderOpened
} from '@element-plus/icons-vue'

// --- 全局状态 ---
const currentTime = ref(new Date().toLocaleTimeString())
const activeTab = ref('overview')
let timer = null

// ==========================================
// 模块 1: 孪生全局总览 (大屏核心数据)
// ==========================================
const kpis = ref([])
const dashboardLoading = ref(false)
const dashboardError = ref(null)

// 拉取管理后台真实 KPI 与内容分布
const loadDashboard = async () => {
  dashboardLoading.value = true
  dashboardError.value = null
  try {
    const res = await fetchAdminDashboard()
    if (res.status === 'success' && res.data) {
      const k = res.data.kpis || {}
      kpis.value = [
        { title: "AIgent 调度指令", value: (k.ai_messages ?? 0).toLocaleString(), trend: "+12.5%", icon: 'Cpu', color: "text-indigo-600", bg: "bg-indigo-100" },
        { title: "预测性拦截风险", value: k.abnormal_visits ?? 0, trend: "+8.2%", icon: 'Lock', color: "text-rose-600", bg: "bg-rose-100" },
        { title: "当月优化节能(kWh)", value: (k.total_energy_kwh ?? 0).toLocaleString(), trend: "+15.3%", icon: 'Lightning', color: "text-emerald-600", bg: "bg-emerald-100" },
        { title: "故障图谱节点", value: k.total_devices ?? 842, trend: "+5.1%", icon: 'Connection', color: "text-blue-600", bg: "bg-blue-100" },
        { title: "全网在线设备", value: (k.total_devices ?? 0).toLocaleString(), trend: "+2.4%", icon: 'Monitor', color: "text-cyan-600", bg: "bg-cyan-100" },
        { title: "告警 AI 自愈率", value: "98.5%", trend: "+1.2%", icon: 'CircleCheck', color: "text-violet-600", bg: "bg-violet-100" },
      ]
      // 用 API 返回的内容分布更新 donutChart
      const distribution = res.data.charts?.content_distribution
      if (distribution) updateContentDistribution(distribution)
    } else {
      throw new Error(res.message || '加载失败')
    }
  } catch (err) {
    dashboardError.value = err.message || '加载失败'
  } finally {
    dashboardLoading.value = false
  }
}

// --- 动态终端日志 (打字机效果) ---
const terminalLogs = ref([
  { id: 1, time: new Date().toLocaleTimeString(), text: 'AIgent 引擎冷启动完成，接入 3,254 节点...', color: 'text-emerald-400' },
  { id: 2, time: new Date().toLocaleTimeString(), text: 'GraphRAG 图谱加载中 (12,402 实体)...', color: 'text-slate-300' }
])
const mockLogEvents = [
  { text: '调频指令已下发至冷机集群 #2...', color: 'text-slate-300' },
  { text: '成功拦截末端 VAV 通讯异常风险.', color: 'text-indigo-300' },
  { text: 'Milvus 向量库执行相似度比对完成 (7ms)', color: 'text-blue-300' },
  { text: '能耗拓扑重构... 发现 15kW 优化空间', color: 'text-emerald-300' },
  { text: '警报: 冷却塔 #1 水温偏高，AI 已介入抑制', color: 'text-rose-400' }
]
let logInterval = null

const enableDeepParsing = ref(true) // 深度解析开关
const enableGraph = ref(false)      // 图谱提取开关
const chunkConfig = ref({
  size: 1000,                       // 文本分块大小 (报错就是因为找不到它)
  overlap: 200                      // 分块重叠大小
})

// --- ECharts 图表实例与引用 ---
const trendChartRef = ref(null)
const donutChartRef = ref(null)
const radarChartRef = ref(null)
let trendChart = null
let donutChart = null
let radarChart = null

const initTrendChart = () => {
  if (!trendChartRef.value) return
  if (trendChart) trendChart.dispose()
  trendChart = echarts.init(trendChartRef.value)
  trendChart.setOption({
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(255, 255, 255, 0.95)', borderColor: '#e2e8f0', textStyle: { color: '#1e293b' } },
    legend: { data: ['AI 调度下发数', '硬件异常拦截数'], top: 0, right: 0, icon: 'circle', itemWidth: 8, textStyle: { fontSize: 11 } },
    grid: { left: '2%', right: '2%', bottom: '5%', top: '15%', containLabel: true },
    xAxis: { type: 'category', boundaryGap: false, data: ['03-24', '03-25', '03-26', '03-27', '03-28', '03-29', '03-30'], axisLine: { lineStyle: { color: '#cbd5e1' } } },
    yAxis: [
      { type: 'value', splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } } },
      { type: 'value', position: 'right', splitLine: { show: false } }
    ],
    series: [
      { name: 'AI 调度下发数', type: 'line', smooth: true, symbol: 'none', lineStyle: { width: 3, color: '#4f46e5' }, areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(79, 70, 229, 0.3)' }, { offset: 1, color: 'rgba(79, 70, 229, 0.01)' }]) }, data: [1200, 1350, 1100, 1500, 1420, 980, 1245] },
      { name: '硬件异常拦截数', type: 'line', yAxisIndex: 1, smooth: true, symbolSize: 6, lineStyle: { width: 2, color: '#f43f5e' }, itemStyle: { color: '#f43f5e' }, data: [12, 8, 15, 22, 10, 5, 12] }
    ]
  })
}

const initRadarChart = () => {
  if (!radarChartRef.value) return
  if (radarChart) radarChart.dispose()
  radarChart = echarts.init(radarChartRef.value)
  radarChart.setOption({
    tooltip: { trigger: 'item' },
    radar: {
      indicator: [
        { name: '通讯延迟', max: 100 }, { name: 'COP效能', max: 100 }, { name: '预防维护', max: 100 },
        { name: 'API稳定', max: 100 }, { name: '图谱覆盖', max: 100 }
      ],
      radius: '60%', center: ['50%', '55%'],
      axisName: { color: '#64748b', fontSize: 10, fontWeight: 'bold' },
      splitArea: { areaStyle: { color: ['rgba(248, 250, 252, 0.8)', 'rgba(241, 245, 249, 0.8)'] } },
      axisLine: { lineStyle: { color: '#e2e8f0' } }, splitLine: { lineStyle: { color: '#e2e8f0' } }
    },
    series: [{
      name: '系统综合评分', type: 'radar',
      data: [{ value: [95, 88, 92, 98, 85], name: '当前状态', itemStyle: { color: '#3b82f6' }, areaStyle: { color: 'rgba(59, 130, 246, 0.3)' }, lineStyle: { width: 2 } }]
    }]
  })
}

const initDonutChart = () => {
  if (!donutChartRef.value) return
  if (donutChart) donutChart.dispose()
  donutChart = echarts.init(donutChartRef.value)
  donutChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c}kW ({d}%)' },
    legend: { bottom: '0%', left: 'center', icon: 'circle', itemWidth: 8, textStyle: { fontSize: 10 } },
    color: ['#4f46e5', '#10b981', '#f59e0b', '#06b6d4'],
    series: [{
      name: '能耗分布', type: 'pie', radius: ['50%', '70%'], center: ['50%', '45%'], avoidLabelOverlap: false,
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 }, label: { show: false },
      data: [ { value: 450, name: '冷水机组集群' }, { value: 280, name: '末端 VAV' }, { value: 150, name: '公共照明' }, { value: 120, name: '特种动力' } ]
    }]
  })
}

// 用 API 返回的内容分布更新 donutChart（不动初始化逻辑，仅刷新数据）
// 若 donutChart 尚未初始化，则缓存 distribution，待 initDonutChart 完成后再 apply
const pendingDistribution = ref(null)
const updateContentDistribution = (distribution) => {
  pendingDistribution.value = distribution
  if (!donutChart) return
  const list = Array.isArray(distribution)
    ? distribution.map(item => ({ name: item.name, value: item.value }))
    : []
  if (!list.length) return
  donutChart.setOption({ series: [{ data: list }] })
}


// ==========================================
// 模块 4: 系统调度与告警管理
// ==========================================
const messageSearch = ref('')
const messageStatus = ref('all')
const messagesData = ref([
  { id: 1, level: 'critical', source: '冷水机组 #2', content: '冷却水回水温度持续 15 分钟超过 32°C，存在宕机风险。', time: '10 分钟前', status: 'unread' },
  { id: 2, level: 'ai_dispatch', source: 'AIgent 调度中枢', content: '检测到室外焓值下降，已自动下发指令：调低 1-3 号冷却塔风机频率至 35Hz。', time: '2 小时前', status: 'unread' },
  { id: 3, level: 'warning', source: '底层数据穿透', content: 'B 栋 4 层末端 VAV 空调箱通讯延迟超过 500ms，部分数据丢包。', time: '昨天 15:30', status: 'read' },
  { id: 4, level: 'info', source: '知识库更新', content: '《特灵冷水机组春季维保手册.pdf》已成功向量化并接入诊断图谱。', time: '昨天 09:12', status: 'read' }
])

const getMessageStyle = (level) => {
  const styles = {
    critical: { text: '紧急告警', color: 'text-rose-600', bg: 'bg-rose-50', border: 'border-rose-100', icon: 'Warning' },
    ai_dispatch: { text: 'AI 调度', color: 'text-indigo-600', bg: 'bg-indigo-50', border: 'border-indigo-100', icon: 'Cpu' },
    warning: { text: '系统警告', color: 'text-amber-600', bg: 'bg-amber-50', border: 'border-amber-100', icon: 'InfoFilled' },
    info: { text: '常规通知', color: 'text-slate-600', bg: 'bg-slate-100', border: 'border-slate-200', icon: 'SuccessFilled' }
  }
  return styles[level] || styles.info
}

// ==========================================
// 模块 5: AI 运维工具箱
// ==========================================
const aiTools = ref([
  { id: 'data-clean', name: 'COP 历史数据清洗', desc: '自动识别并剔除由于传感器漂移或断网导致的能效比(COP)异常毛刺数据。', icon: 'DataLine', color: 'text-blue-600', bg: 'bg-blue-50', border: 'border-blue-100' },
  { id: 'fault-extract', name: '设备故障树抽取', desc: '导入设备出厂 PDF 手册，自动逆向生成图数据库所需的“故障-现象-排查”链路。', icon: 'Document', color: 'text-emerald-600', bg: 'bg-emerald-50', border: 'border-emerald-100' },
  { id: 'strategy-sim', name: '控载策略仿真沙盘', desc: '在虚拟孪生空间内，提前推演 AI 降频/开关机指令对全网温度场的影响。', icon: 'Cpu', color: 'text-violet-600', bg: 'bg-violet-50', border: 'border-violet-100' },
  { id: 'prompt-tune', name: '大模型微调构造器', desc: '将运维专家的日常工单记录，自动转化为高质量的 Instruction 问答对语料。', icon: 'Setting', color: 'text-slate-600', bg: 'bg-slate-100', border: 'border-slate-200' }
])

// 记得在顶部导入新图标： import { View, User, ChatDotRound } from '@element-plus/icons-vue'

// ==========================================
// 模块 6: AI 对话审计与用户画像
// ==========================================
const selectedPersona = ref('1')

// 审计日志数据（改为从 API 获取）
const auditLogs = ref([])
const auditLoading = ref(false)
const auditError = ref(null)
const auditTotal = ref(0)
const auditHighRiskCount = ref(0)

// 拉取真实审计日志
const loadAuditLogs = async () => {
  auditLoading.value = true
  auditError.value = null
  try {
    const res = await fetchAuditLogs({ limit: 50, risk_level: 'all' })
    if (res.status === 'success' && Array.isArray(res.data)) {
      const list = res.data
      auditTotal.value = res.total ?? list.length
      auditHighRiskCount.value = list.filter(l => l.risk_level === 'high').length
      // 字段映射：log.user→user, log.action→query, log.detail→aiResponse, log.risk_level→risk, log.time→time
      auditLogs.value = list.map(log => ({
        id: log.id,
        user: log.user,
        query: log.action,
        aiResponse: log.detail,
        risk: log.risk_level,
        time: log.time
      }))
    } else {
      throw new Error(res.message || '加载失败')
    }
  } catch (err) {
    auditError.value = err.message || '加载失败'
  } finally {
    auditLoading.value = false
  }
}

// ECharts 意图聚类玫瑰图
const intentChartRef = ref(null)
let intentChart = null

const initIntentChart = () => {
  if (!intentChartRef.value) return
  if (intentChart) intentChart.dispose()
  intentChart = echarts.init(intentChartRef.value)
  
  intentChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} 次 ({d}%)' },
    legend: { bottom: '0%', left: 'center', icon: 'circle', itemWidth: 8, textStyle: { fontSize: 10, color: '#64748b' } },
    color: ['#4f46e5', '#ec4899', '#10b981', '#f59e0b', '#06b6d4'],
    series: [
      {
        name: '语义意图聚类',
        type: 'pie',
        radius: ['20%', '70%'], // 内部空心，外部最大
        center: ['50%', '42%'],
        roseType: 'radius', // 南丁格尔玫瑰图模式 (高度代表数据大小)
        itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
        label: { show: false }, // 保持 UI 清爽，靠 tooltip 展示
        data: [
          { value: 1845, name: '设备故障排查 (Troubleshoot)' },
          { value: 1230, name: '能耗数据分析 (Data Analysis)' },
          { value: 850, name: '运行状态问询 (Status Query)' },
          { value: 420, name: '底层控制指令 (Hardware Control)' },
          { value: 210, name: '闲聊与其他 (Others)' }
        ].sort((a, b) => a.value - b.value) // 玫瑰图排序后视觉效果极佳
      }
    ]
  })
}

// 别忘了把 initIntentChart 加入生命周期！
// 在 handleTabChange 中补充：
/*
const handleTabChange = (tabName) => {
  if (tabName === 'overview') { ... }
  if (tabName === 'kb') { ... }
  if (tabName === 'audit') {
    nextTick(() => initIntentChart())
  }
}
*/

// 在 handleResize 中补充：
/*
  if (intentChart) intentChart.resize()
*/

// ==========================================
// 模块 2: 知识库与模型训练
// ==========================================
const kbMode = ref('upload')
const kbCount = ref(0)
const searchKnowledge = ref('')
const selectedFiles = ref([])
// --- 修复表单绑定的空规则 ---
const cleanRules = ref([]) // 👈 改成空数组
const manualForm = ref({ title: '', content: '', tags: '' })

// 知识库列表（改为从 API 获取，删除 localStorage 缓存）
const knowledgeList = ref([])
const kbLoading = ref(false)
const kbError = ref(null)

const loadKnowledgeList = async () => {
  kbLoading.value = true
  kbError.value = null
  try {
    const res = await fetchKnowledgeList()
    if (res.status === 'success' && Array.isArray(res.data)) {
      const list = res.data
      // 字段映射：API 返回 { id, title, content, tags, source }
      knowledgeList.value = list.map((item, idx) => ({
        id: item.id ?? idx,
        type: item.tags || '手动录入',
        content: item.content,
        source: item.source || '知识库'
      }))
      kbCount.value = res.total ?? list.length
    } else {
      throw new Error(res.message || '加载失败')
    }
  } catch (err) {
    kbError.value = err.message || '加载失败'
  } finally {
    kbLoading.value = false
  }
}

const handleFileChange = (uploadFile, uploadFiles) => selectedFiles.value = uploadFiles
const startProcessing = () => ElMessage.success('批量解析已启动！后台正在向量化...')
const submitManualTraining = async () => {
  if (!manualForm.value.title || !manualForm.value.content) return ElMessage.warning('标题和内容为必填项！')
  try {
    const res = await uploadKnowledgeItem({
      title: manualForm.value.title,
      content: manualForm.value.content,
      tags: manualForm.value.tags || ''
    })
    if (res.status === 'success') {
      ElMessage.success(res.message || '手动录入成功！')
      manualForm.value.title = ''
      manualForm.value.content = ''
      manualForm.value.tags = ''
      await loadKnowledgeList()
    } else {
      throw new Error(res.message || '录入失败')
    }
  } catch (err) {
    ElMessage.error(err.message || '录入失败')
  }
}

const handleEdit = (row, index) => {
  ElMessageBox.prompt('请修改内容：', `编辑 [${row.id}]`, { inputValue: row.content, inputType: 'textarea' }).then(({ value }) => {
    knowledgeList.value[index].content = value
    ElMessage.success('修改成功！')
  }).catch(() => {})
}

const handleDelete = (row, index) => {
  ElMessageBox.confirm(`确定要删除 [${row.id}] 吗？`, '危险操作确认', { type: 'warning' }).then(async () => {
    try {
      const res = await deleteKnowledgeItem(index)
      if (res.status === 'success') {
        ElMessage.success(res.message || '删除成功！')
        await loadKnowledgeList()
      } else {
        throw new Error(res.message || '删除失败')
      }
    } catch (err) {
      ElMessage.error(err.message || '删除失败')
    }
  }).catch(() => {})
}

// 混合检索测试
const testQuery = ref('')
const isSearching = ref(false)
const testResults = ref([])
const runHitTest = () => {
  if (!testQuery.value) return ElMessage.warning('请输入测试问题')
  isSearching.value = true; testResults.value = [];
  setTimeout(() => {
    isSearching.value = false
    testResults.value = [
      { id: 'V-88392', score: 0.92, type: '向量召回', content: `【文档段落】在相关内容中提到：支持私有化部署并提供强大的 API 接口...` },
      { id: 'G-10294', score: 0.88, type: '图谱召回', content: `【图谱推理】关联：[${testQuery.value}] --(依赖)--> [大语言模型技术栈]` }
    ]
  }, 800)
}

// 知识图谱引擎
let graphChartInstance = null; let currentZoom = 1;
const changeZoom = (delta) => { if (graphChartInstance) { currentZoom = Math.max(0.3, Math.min(3, currentZoom + delta)); graphChartInstance.setOption({ series: [{ zoom: currentZoom }] }) } }
const resetZoom = () => { if (graphChartInstance) { currentZoom = 1; graphChartInstance.dispatchAction({ type: 'restore' }) } }

const initGraphChart = () => {
  const chartDom = document.getElementById('graphChart'); if (!chartDom) return;
  if (graphChartInstance) graphChartInstance.dispose(); graphChartInstance = echarts.init(chartDom);
  
  const getGradient = (c1, c2) => new echarts.graphic.LinearGradient(0, 0, 1, 1, [{ offset: 0, color: c1 }, { offset: 1, color: c2 }])
  const colors = { core: getGradient('#4f46e5', '#8b5cf6'), ai: getGradient('#06b6d4', '#3b82f6'), data: getGradient('#10b981', '#34d399'), infra: getGradient('#f59e0b', '#fcd34d'), user: getGradient('#ec4899', '#f43f5e') }

  const graphNodes = [
    { id: '0', name: 'AIgent', symbolSize: 45, typeDesc: '中枢引擎', itemStyle: { color: colors.core, shadowBlur: 20, shadowColor: 'rgba(99, 102, 241, 0.5)' } },
    { id: '1', name: '大模型', symbolSize: 35, typeDesc: '推理核心', itemStyle: { color: colors.ai } },
    { id: '2', name: '知识库', symbolSize: 35, typeDesc: '双路召回', itemStyle: { color: colors.data } },
    { id: '3', name: 'GraphRAG', symbolSize: 25, typeDesc: '图谱提取', itemStyle: { color: colors.ai } },
    { id: '4', name: '数据清洗', symbolSize: 20, typeDesc: 'ETL', itemStyle: { color: colors.data } },
    { id: '5', name: '向量检索', symbolSize: 25, typeDesc: '比对', itemStyle: { color: colors.core } },
    { id: '8', name: '空间孪生', symbolSize: 35, typeDesc: '业务', itemStyle: { color: colors.user } },
  ]
  const graphLinks = [
    { source: '0', target: '1', value: '调用' }, { source: '0', target: '2', value: '查询' },
    { source: '2', target: '3', value: '提取' }, { source: '2', target: '4', value: '过滤' }, 
    { source: '2', target: '5', value: '匹配' }, { source: '0', target: '8', value: '下发' }
  ]

  graphChartInstance.setOption({
    series: [{
      type: 'graph', layout: 'force', data: graphNodes, links: graphLinks, roam: true,
      stateAnimation: { duration: 800, easing: 'quadraticInOut' },
      label: { show: true, position: 'right', distance: 10, formatter: p => `{title|${p.data.name}}\n{badge|${p.data.typeDesc}}`, backgroundColor: 'rgba(255,255,255,0.85)', borderColor: '#e2e8f0', borderWidth: 1, padding: [6, 10], borderRadius: 6, rich: { title: { color: '#1e293b', fontSize: 12, fontWeight: 'bold', padding: [0, 0, 4, 0] }, badge: { color: '#6366f1', fontSize: 9, backgroundColor: '#eef2ff', padding: [2, 4], borderRadius: 4, fontWeight: 'bold' } } },
      edgeSymbol: ['none', 'arrow'], edgeSymbolSize: [0, 8], edgeLabel: { show: true, formatter: '{c}', fontSize: 9, color: '#64748b', backgroundColor: '#fff', padding: [2, 6], borderRadius: 10 },
      lineStyle: { color: 'source', width: 2, curveness: 0.2, opacity: 0.6 },
      force: { repulsion: 600, edgeLength: [100, 150], gravity: 0.05 },
      emphasis: { focus: 'adjacency', lineStyle: { width: 4, opacity: 1 } },
      blur: { itemStyle: { opacity: 0.4 }, lineStyle: { opacity: 0.15 }, label: { opacity: 0.4 } }
    }]
  })
}

// ==========================================
// 生命周期与全局调度
// ==========================================
const handleTabChange = (tabName) => {
  if (tabName === 'overview') {
    nextTick(() => {
      initTrendChart(); initRadarChart(); initDonutChart();
      // donutChart 初始化完成后，应用缓存的 content_distribution
      if (pendingDistribution.value) updateContentDistribution(pendingDistribution.value)
    })
  }
  if (tabName === 'kb') {
    if (!knowledgeList.value.length) loadKnowledgeList()
    nextTick(() => initGraphChart())
  }
  if (tabName === 'audit') {
    if (!auditLogs.value.length) loadAuditLogs()
    nextTick(() => initIntentChart())
  }
}

const handleResize = () => {
  if (trendChart) trendChart.resize()
  if (donutChart) donutChart.resize()
  if (radarChart) radarChart.resize()
  if (intentChart && activeTab.value === 'audit') intentChart.resize()
  if (graphChartInstance && activeTab.value === 'kb') graphChartInstance.resize()
}

onMounted(async () => {
  // 1. 时间时钟
  timer = setInterval(() => { currentTime.value = new Date().toLocaleTimeString() }, 1000)

  // 2. 启动控制台打字机日志流
  logInterval = setInterval(() => {
    const randomLog = mockLogEvents[Math.floor(Math.random() * mockLogEvents.length)]
    terminalLogs.value.push({ id: Date.now(), time: new Date().toLocaleTimeString(), text: randomLog.text, color: randomLog.color })
    if (terminalLogs.value.length > 4) terminalLogs.value.shift()
  }, 2500)

  // 3. 监听自适应
  window.addEventListener('resize', handleResize)

  // 4. 先加载 KPI 数据，再初始化图表
  await loadDashboard()
  if (activeTab.value === 'overview' && !dashboardError.value) {
    nextTick(() => {
      initTrendChart(); initRadarChart(); initDonutChart();
      // donutChart 初始化完成后，应用缓存的 content_distribution
      if (pendingDistribution.value) updateContentDistribution(pendingDistribution.value)
    })
  }

  // 5. 加载审计日志（供 audit Tab 的统计与列表使用）
  loadAuditLogs()
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  if (logInterval) clearInterval(logInterval)
  window.removeEventListener('resize', handleResize)
  if (trendChart) trendChart.dispose()
  if (donutChart) donutChart.dispose()
  if (radarChart) radarChart.dispose()
  if (intentChart) intentChart.dispose()
  if (graphChartInstance) graphChartInstance.dispose()
})
</script>

<style scoped>
/* Tabs 深度美化 */
:deep(.modern-admin-tabs .el-tabs__nav-wrap::after) { height: 1px; background-color: #f1f5f9; }
:deep(.modern-admin-tabs .el-tabs__item) { color: #64748b; font-size: 15px; padding: 0 20px !important; transition: all 0.3s ease; }
:deep(.modern-admin-tabs .el-tabs__item.is-active) { color: #4f46e5 !important; }
:deep(.modern-admin-tabs .el-tabs__active-bar) { background-color: #4f46e5; height: 3px; border-radius: 3px 3px 0 0; }
:deep(.modern-admin-tabs .el-tabs__content) { flex: 1; overflow-y: auto; overflow-x: hidden; }

/* 拖拽上传样式 */
:deep(.perfect-drag-upload .el-upload) { width: 100%; }
:deep(.perfect-drag-upload .el-upload-dragger) {
  background-color: #eef2ff !important; border: 2px dashed #c7d2fe !important; border-radius: 1rem !important;
  padding: 0; height: 240px; display: flex; flex-direction: column; align-items: center; justify-content: center;
  transition: all 0.3s ease; overflow: hidden;
}
:deep(.perfect-drag-upload .el-upload-dragger:hover) {
  background-color: #e0e7ff !important; border-color: #818cf8 !important; box-shadow: 0 4px 20px -5px rgba(99, 102, 241, 0.15);
}
.upload-inner-content { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; height: 100%; }
.icon-wrapper { width: 64px; height: 64px; border-radius: 50%; background-color: #ffffff; box-shadow: 0 2px 10px rgba(99, 102, 241, 0.1); display: flex; align-items: center; justify-content: center; transition: transform 0.3s ease; }
:deep(.perfect-drag-upload .el-upload-dragger:hover) .icon-wrapper { transform: translateY(-5px) scale(1.05); }
.upload-icon { font-size: 32px; color: #6366f1; }

/* 全局进场动画 */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 高级科技感：无限点阵画布背景 (知识图谱使用) */
.tech-canvas-bg {
  background-color: #f8fafc;
  background-image: radial-gradient(#cbd5e1 1.5px, transparent 1.5px);
  background-size: 28px 28px;
  background-position: 0 0;
}

/* --- 新增：终端日志滚动动画 --- */
.log-list-enter-active,
.log-list-leave-active {
  transition: all 0.4s ease;
}
.log-list-enter-from {
  opacity: 0;
  transform: translateY(15px);
}
.log-list-leave-to {
  opacity: 0;
  transform: translateY(-15px);
}
</style>

<style scoped>
/* Tabs 深度美化 */
:deep(.modern-admin-tabs .el-tabs__nav-wrap::after) { height: 1px; background-color: #f1f5f9; }
:deep(.modern-admin-tabs .el-tabs__item) { color: #64748b; font-size: 15px; padding: 0 20px !important; transition: all 0.3s ease; }
:deep(.modern-admin-tabs .el-tabs__item.is-active) { color: #4f46e5 !important; }
:deep(.modern-admin-tabs .el-tabs__active-bar) { background-color: #4f46e5; height: 3px; border-radius: 3px 3px 0 0; }
:deep(.modern-admin-tabs .el-tabs__content) { flex: 1; overflow-y: auto; }

/* 拖拽上传样式 */
:deep(.perfect-drag-upload .el-upload) { width: 100%; }
:deep(.perfect-drag-upload .el-upload-dragger) {
  background-color: #eef2ff !important; border: 2px dashed #c7d2fe !important; border-radius: 1rem !important;
  padding: 0; height: 240px; display: flex; flex-direction: column; align-items: center; justify-content: center;
  transition: all 0.3s ease; overflow: hidden;
}
:deep(.perfect-drag-upload .el-upload-dragger:hover) {
  background-color: #e0e7ff !important; border-color: #818cf8 !important; box-shadow: 0 4px 20px -5px rgba(99, 102, 241, 0.15);
}
.upload-inner-content { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; height: 100%; }
.icon-wrapper { width: 64px; height: 64px; border-radius: 50%; background-color: #ffffff; box-shadow: 0 2px 10px rgba(99, 102, 241, 0.1); display: flex; align-items: center; justify-content: center; transition: transform 0.3s ease; }
:deep(.perfect-drag-upload .el-upload-dragger:hover) .icon-wrapper { transform: translateY(-5px) scale(1.05); }
.upload-icon { font-size: 32px; color: #6366f1; }

/* 简单的淡入动画，用于内部模块切换 */
.animate-fade-in {
  animation: fadeIn 0.3s ease-in-out;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(5px); }
  to { opacity: 1; transform: translateY(0); }
}
/* 高级科技感：无限点阵画布背景 */
.tech-canvas-bg {
  background-color: #f8fafc;
  background-image: radial-gradient(#cbd5e1 1.5px, transparent 1.5px);
  background-size: 28px 28px;
  background-position: 0 0;
}
</style>