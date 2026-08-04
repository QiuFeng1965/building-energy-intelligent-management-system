# 擎翼数字中枢 · Qingyi Digital Hub

> **工业级全域数智底座** —— 面向建筑能源智能管理的数字孪生平台
>
> 融合 **3D 实时孪生 · AI 自主决策 · 时序预测 · ESG 碳追踪** 的一体化解决方案

---

## 项目亮点

- **3D 高保真孪生**：基于 Three.js + TresJS 构建建筑级 3D 实时镜像，支持 InstancedMesh 海量设备渲染、材质动态过渡、时间引擎回溯推演
- **AI 自主决策流**：大模型 Function Calling 驱动的 Agent 系统，支持设备功率调节、工单自动派发，内置安全拦截层与幂等性校验
- **工业级高可用**：断路器模式、缓存雪崩防护（singleflight + TTL 抖动）、连接池优化、异步 I/O 下沉，可应对千万级高并发请求
- **全链路可观测**：结构化 JSON 日志、trace_id 全链路追踪、X-API-Version 版本治理、健康检查探针
- **安全零信任**：JWT 鉴权、WebSocket Token 校验、CSP 策略、参数化 SQL、异常信息脱敏、弱口令强制拦截
- **9 大业务模块**：3D 孪生、能源总览、能效诊断、设备监测、AI 寻优、数据驾驶舱、前沿能力、进阶能力、管理后台

---

## 演示动图

> 以下为 9 大核心页面的实际运行录屏（GIF 动图）

### 1. 登录页 — 安全入口，JWT 身份认证

![登录页](demos/gifs/01_login.gif)

### 2. 全息建筑孪生 — 3D 实时数字孪生，鼠标拖拽旋转

![全息建筑孪生](demos/gifs/02_spatial_twin.gif)

### 3. 能源态势总览 — 全楼能耗全景，ECharts 数据可视化

![能源态势总览](demos/gifs/03_dashboard.gif)

### 4. 能效诊断分析 — 能耗趋势，时间范围切换，图表交互

![能效诊断分析](demos/gifs/04_energy_analysis.gif)

### 5. 能耗设备监测 — 设备级实时监控，分类切换

![能耗设备监测](demos/gifs/05_devices.gif)

### 6. AI 策略寻优 — 大模型流式对话，实时分析能耗

![AI 策略寻优](demos/gifs/06_ai_agent.gif)

### 7. 全局数据驾驶舱 — 管理视角数据聚合，多维交叉分析

![全局数据驾驶舱](demos/gifs/07_admin_dashboard.gif)

### 8. 前沿能力中心 — 高级能力展示，卡片悬停交互

![前沿能力中心](demos/gifs/08_frontier_hub.gif)

### 9. 进阶能力中心 — ESG 碳追踪与投资决策闭环

![进阶能力中心](demos/gifs/09_advanced_hub.gif)

---

## 核心能力矩阵

| 模块 | 能力描述 | 关键技术 |
|------|---------|---------|
| **全息建筑孪生** | 建筑级 3D 实时镜像，设备状态可视化，时间引擎回溯历史故障/推演未来能耗热力图 | Three.js · InstancedMesh · 时间轴 lerp 插值 · WebGL 显存管理 |
| **能源态势总览** | 全楼能耗全景，实时功率曲线，异常告警，COP 效率看板 | ECharts · WebSocket 实时推送 · 缓存优化 |
| **能效诊断分析** | Prophet 时序预测未来 7 天能耗，RUL 剩余寿命预测，异常根因分析 | Prophet · RandomForest · 异步训练 · 缓存 TTL |
| **能耗设备监测** | 设备级实时监控，运行状态流转，阈值告警，工单全生命周期管理 | WebSocket · 参数化查询 · 工单状态机 |
| **AI 策略寻优** | 大模型流式对话，Function Calling 调用业务工具，RAGFlow 知识库检索 | OpenAI 兼容 API · SSE 流式 · MCP 工具协议 · RAGFlow |
| **AI Agent 决策流** | 自动化决策：RUL 告警→LLM 生成 Action→安全校验→执行→幂等防重放 | Function Calling · 安全拦截层 · X-Idempotency-Key · CAS 乐观锁 |
| **全局数据驾驶舱** | 管理视角数据聚合，多维度交叉分析，报表导出 | 数据聚合 · Word/PDF 报表生成 |
| **ESG 与投资决策** | 碳排放追踪，ESG 报告，ROI 投资回报测算，改造方案对比 | 碳核算模型 · DCF 测算 · 敏感性分析 |
| **管理后台** | 用户管理，权限治理，系统配置，API 版本管控 | RBAC · JWT · 版本治理 |

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     前端 (Vue3 + Three.js)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ 3D 孪生   │ │ 能源看板  │ │ AI 对话   │ │ 时间引擎      │   │
│  │ Canvas   │ │ ECharts  │ │ SSE 流式  │ │ TimeEngine   │   │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘   │
│       └─────────────┴────────────┴──────────────┘            │
│                    authFetch + JWT 路由守卫                    │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTPS / WebSocket
┌─────────────────────────┴───────────────────────────────────┐
│                  后端 (FastAPI + 异步架构)                     │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  AuthMiddleware · CORS · CSP · X-API-Version · Trace │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐   │
│  │ REST API  │ │ WebSocket │ │ SSE 流式   │ │ MCP 工具   │   │
│  │ 33 路由   │ │ 实时推送   │ │ AI 对话    │ │ 服务器     │   │
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘   │
│  ┌─────┴─────────────┴─────────────┴─────────────┴─────┐   │
│  │  断路器 · 幂等性 · 缓存(singleflight+TTL抖动) · 限流  │   │
│  └─────────────────────────┬───────────────────────────┘   │
│  ┌─────────────────────────┴───────────────────────────┐   │
│  │  DDD 领域层 · Prophet 预测 · RandomForest RUL · Agent │   │
│  └─────────────────────────┬───────────────────────────┘   │
└─────────────────────────────┬─────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │     SQLite (WAL) + Alembic     │
              │     8760 小时仿真数据 · 索引优化 │
              └───────────────────────────────┘
```

---

## 技术栈

### 前端
| 技术 | 用途 |
|------|------|
| Vue 3 + Composition API | 响应式框架，路由懒加载，代码分割 |
| Three.js + TresJS | 3D 数字孪生渲染，InstancedMesh 性能优化 |
| ECharts | 数据可视化，图表内存泄漏防护 |
| TailwindCSS + Element Plus | 深色模式 UI，CSS 变量主题 |
| Vite | 构建工具，HMR 热更新 |
| WebSocket | 实时数据推送，指数退避重连，心跳检测 |

### 后端
| 技术 | 用途 |
|------|------|
| FastAPI | 异步 Web 框架，OpenAPI 文档自动生成 |
| SQLite (WAL 模式) | 嵌入式数据库，8760 小时仿真数据 |
| Alembic | 数据库迁移版本控制，支持回滚 |
| OpenAI 兼容 API | LLM 流式对话，Function Calling |
| Prophet + scikit-learn | 时序预测 + RUL 剩余寿命模型 |
| Pydantic | 数据校验与序列化 |
| python-jose + passlib | JWT 认证与密码哈希 |

### 工程化与运维
| 技术 | 用途 |
|------|------|
| Docker + docker-compose | 容器化部署，健康检查，服务依赖 |
| 结构化 JSON 日志 | trace_id 全链路追踪 |
| GitHub Actions Ready | CI/CD 就绪 |

---

## 工业级架构设计

本项目以「应对千万级高并发请求与工业级高可用交付」为标准，内置以下架构能力：

### 1. 熔断与级联故障隔离
- **断路器模式**（CLOSED → OPEN → HALF_OPEN）：LLM/外部 API 故障时自动降级，防止级联雪崩
- **缓存雪崩防护**：TTL ±20% 抖动 + singleflight 防击穿，容量 4096 槽位

### 2. 接口幂等性
- **X-Idempotency-Key**：POST/PUT/DELETE 防重放防并发
- **CAS 乐观锁**：设备状态更新防止并发覆盖

### 3. 异步 I/O 优化
- **asyncio.to_thread**：Prophet 训练、大模型调用下沉到线程池，不阻塞事件循环
- **连接池复用**：SQLite 线程级复用，PostgreSQL 健康检查

### 4. 安全零信任
- JWT 鉴权 + WebSocket Token 校验
- 参数化 SQL（禁止 f-string 拼接）
- CSP 环境感知策略
- 异常信息脱敏（生产环境不返回 `str(e)`）
- 弱口令强制拦截（生产环境无默认密码兜底）
- CORS 启动校验（生产环境禁止通配符 origin）

### 5. AI Agent 安全拦截层
- **极端参数拦截**：功率 <10 或 >90 强制人工二次确认
- **单次调节幅度限制**：防止大模型幻觉下发极端指令
- **执行前二次校验**：防止 decision 阶段后参数被篡改
- **reason 量化校验**：必须包含 RUL/COP 等量化依据

---

## 快速启动

### 方式一：Docker Compose（推荐）

```bash
# 配置环境变量
cp backend/.env.example backend/.env
# 编辑 .env 填入 AI_API_KEY、JWT_SECRET 等

# 一键启动
docker-compose up -d

# 查看健康状态
docker-compose ps
```

### 方式二：本地开发

#### 后端

```bash
cd backend

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入：
#   JWT_SECRET=你的密钥
#   AI_API_KEY=你的大模型密钥
#   AI_BASE_URL=https://opencode.ai/zen/v1
#   MODEL_TEXT=deepseek-v4-flash-free

# 安装依赖（建议使用虚拟环境）
pip install -r requirements.txt

# 数据库迁移
alembic upgrade head

# 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 前端

```bash
cd frontend
npm install
npm run dev
```

### 访问

- **前端**：http://localhost:5173
- **后端 API 文档**：http://localhost:8000/docs
- **健康检查**：http://localhost:8000/health

### 默认账户

| 用户名 | 密码 | 角色 |
|--------|------|------|
| `admin` | `admin123` | 管理员 |

> ⚠️ 生产环境请通过 `ADMIN_PASSWORD_HASH` 环境变量配置强密码

---

## 目录结构

```
Building Energy Intelligent Management System2/
├── backend/                          # 后端服务
│   ├── app/
│   │   ├── main.py                   # FastAPI 应用入口
│   │   ├── core/                     # 核心基础设施
│   │   │   ├── config.py             # 配置中心（API版本、DB、LLM、CORS）
│   │   │   ├── database.py           # 统一 get_conn() 上下文管理器
│   │   │   ├── middleware.py         # AuthMiddleware + X-API-Version
│   │   │   ├── circuit_breaker.py    # 断路器模式
│   │   │   ├── idempotency.py        # 幂等性装饰器
│   │   │   ├── response_cache.py     # 缓存（singleflight + TTL 抖动）
│   │   │   ├── rate_limit.py         # 限流
│   │   │   └── security.py           # JWT + 密码哈希
│   │   ├── api/v1/                   # 业务路由（33 个端点）
│   │   │   ├── login.py              # 认证
│   │   │   ├── dashboard.py          # 能源总览
│   │   │   ├── devices.py            # 设备监测
│   │   │   ├── chat.py               # AI 流式对话
│   │   │   ├── agent_service.py      # AI Agent 决策流
│   │   │   ├── rul.py                # RUL 剩余寿命预测
│   │   │   ├── esg_report.py         # ESG 报告
│   │   │   ├── roi_calculator.py     # ROI 投资测算
│   │   │   └── ...
│   │   ├── services/                 # 领域服务
│   │   │   ├── agent_tools.py        # Function Calling 工具定义 + 安全拦截
│   │   │   ├── ragflow_service.py    # RAGFlow 知识库
│   │   │   ├── email_service.py      # 定时邮件
│   │   │   └── report_service.py     # Word 报表生成
│   │   └── migrations/               # Alembic 数据库迁移
│   ├── data/                         # SQLite 数据库（不入库）
│   ├── .env.example                  # 环境变量示例
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                         # 前端应用
│   ├── src/
│   │   ├── views/                    # 页面视图（9 大模块）
│   │   │   ├── Login.vue
│   │   │   ├── Dashboard.vue         # 能源态势总览
│   │   │   ├── SpatialTwin.vue       # 3D 全息孪生
│   │   │   ├── EnergyAnalysis.vue    # 能效诊断
│   │   │   ├── DeviceMonitor.vue     # 设备监测
│   │   │   ├── AiAgent.vue           # AI 策略寻优
│   │   │   ├── AdminDashboard.vue    # 数据驾驶舱
│   │   │   ├── FrontierHub.vue       # 前沿能力中心
│   │   │   └── AdvancedHub.vue       # 进阶能力中心
│   │   ├── components/               # 组件
│   │   │   ├── TimeEngine.vue        # 3D 孪生时间引擎面板
│   │   │   ├── Campus3DCanvas.vue    # 3D 场景画布
│   │   │   ├── CommandPalette.vue    # 命令面板
│   │   │   └── ...
│   │   ├── utils/
│   │   │   ├── TwinRenderer.js       # 3D 渲染器（材质 lerp + 显存释放）
│   │   │   ├── request.js            # authFetch（401 自动跳登录）
│   │   │   └── websocket.js          # WebSocket（指数退避重连）
│   │   ├── router/                   # 路由（懒加载 + JWT 守卫）
│   │   └── main.js
│   ├── Dockerfile
│   ├── nginx.conf
│   └── package.json
├── docker-compose.yml                # 容器编排（含健康检查）
├── .env.example
└── README.md
```

---

## API 概览

### 核心端点

| 模块 | 端点 | 方法 | 说明 |
|------|------|------|------|
| 认证 | `/api/login` | POST | 登录获取 JWT |
| 健康检查 | `/health` | GET | 存活探针 |
| 健康检查 | `/readiness` | GET | 就绪探针（DB 连通性） |
| 版本 | `/api/version` | GET | API 版本元数据 |
| 能源总览 | `/api/dashboard/overview` | GET | 全楼能耗概览 |
| 能效诊断 | `/api/energy/trend` | GET | 能耗趋势（带缓存） |
| RUL 预测 | `/api/rul/overview` | GET | 剩余寿命预测 |
| 设备监测 | `/api/devices/list` | GET | 设备列表 |
| 工单管理 | `/api/workorders` | GET/POST | 工单 CRUD |
| AI 对话 | `/api/chat/stream` | POST | SSE 流式对话 |
| **Agent 决策** | `/api/agent/decision` | POST | LLM 生成可执行 Action |
| **Agent 执行** | `/api/agent/execute` | POST | 执行 Action（幂等） |
| Agent 历史 | `/api/agent/actions` | GET | Action 历史记录 |
| ESG 报告 | `/api/esg/trend` | GET | ESG 趋势（带缓存） |
| ROI 测算 | `/api/roi/calculate` | POST | 投资回报测算 |
| 实时推送 | `/ws/realtime` | WS | WebSocket 实时数据 |

> 完整 API 文档请访问 `http://localhost:8000/docs`（Swagger UI）

---

## 环境变量

后端配置位于 `backend/.env`，参考 `backend/.env.example`：

| 变量 | 说明 | 示例 |
|------|------|------|
| `JWT_SECRET` | JWT 签名密钥（必填，缺失则终止启动） | `your-secret-key` |
| `AI_API_KEY` | 大模型 API 密钥 | `sk-xxxx` |
| `AI_BASE_URL` | OpenAI 兼容 API 端点 | `https://opencode.ai/zen/v1` |
| `MODEL_TEXT` | 文本模型 | `deepseek-v4-flash-free` |
| `MODEL_VISION` | 视觉模型 | `deepseek-v4-flash-free` |
| `DB_PATH` | SQLite 数据库路径 | `backend/data/enterprise_building_energy.db` |
| `API_VERSION` | API 版本号 | `v2.0.0` |
| `CORS_ORIGINS` | CORS 允许源（生产禁用 *） | `http://localhost:5173` |
| `RAGFLOW_URL` | RagFlow 服务地址 | `http://ragflow:9380` |
| `RAGFLOW_CHAT_ID` | RagFlow 对话 ID | `xxx` |
| `DEMO_MODE` | 演示模式开关 | `0` |

---

## 项目特色

### 3D 孪生时间引擎
- **时间轴回溯**：拖拽时间轴重演历史故障，设备材质随温度平滑过渡到发光红色
- **未来推演**：基于 Prophet 预测推演未来能耗热力图
- **帧率无关插值**：`THREE.MathUtils.lerp` + 指数衰减，快速拖拽不掉帧
- **显存零泄漏**：geometry/material/texture 统一 dispose，WebGL 上下文强制释放

### AI Agent 自动化决策流
```
设备 RUL 告警
    ↓
LLM 分析（Function Calling）
    ↓
生成 Action（adjust_device_power / dispatch_workorder）
    ↓
安全拦截层校验（极端参数拦截 + 幅度限制 + reason 量化）
    ↓
标记 need_human_confirm（高危操作）
    ↓
/api/agent/execute 执行（X-Idempotency-Key 防重放 + CAS 乐观锁）
    ↓
执行前二次校验（防篡改）
    ↓
落地执行 + 结果回传
```

### 工业级缓存策略
- **singleflight**：并发请求合并，防缓存击穿
- **TTL ±20% 抖动**：防缓存雪崩
- **容量 4096 槽位**：LRU 淘汰策略
- **慢接口强制缓存**：`/api/esg/trend`、`/api/twin/realtime`、`/api/rul/overview`

---

## 数据库设计

- **SQLite WAL 模式**：支持并发读写
- **Alembic 迁移**：版本化 schema 管理，支持回滚
- **性能索引**：
  - 函数索引 `DATE(monitor_time)`
  - 复合索引 `(building_id, DATE(monitor_time))`
  - 工单表、Agent 记忆表专用索引
- **8760 小时仿真数据**：全年逐小时能耗数据

---

## 部署

### Docker 部署

```bash
# 构建并启动
docker-compose up -d --build

# 查看日志
docker-compose logs -f backend
docker-compose logs -f frontend

# 健康检查
curl http://localhost:8000/health
curl http://localhost:8000/readiness
```

`docker-compose.yml` 包含：
- 后端服务（含 healthcheck）
- 前端服务（condition: service_healthy 依赖后端）
- Nginx 反向代理
- 数据卷持久化

---

## 贡献

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/AmazingFeature`
3. 提交更改：`git commit -m 'Add some AmazingFeature'`
4. 推送分支：`git push origin feature/AmazingFeature`
5. 提交 Pull Request

---

## License

本项目为私有项目（闭源），未授权不得使用、复制或分发。

---

## 致谢

本项目融合了建筑能源管理、数字孪生、人工智能等多个领域的技术实践，感谢所有开源社区的贡献。
