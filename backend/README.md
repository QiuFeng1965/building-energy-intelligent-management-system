# 后端模块说明

## 架构概览

采用分层架构，代码组织在 `app/` 包下，按职责分离：

```
backend/
├── app/                        # 应用主包
│   ├── main.py                 # FastAPI 入口（创建 app、CORS、异常处理、路由挂载、定时任务）
│   ├── core/                   # 核心配置层
│   │   ├── config.py           # 统一配置中心（路径、密钥、常量，全部从 .env 加载）
│   │   ├── database.py         # 数据库连接管理（WAL + 重试 + 线程池）
│   │   └── security.py         # JWT + bcrypt 鉴权体系
│   ├── models/                 # 数据模型层
│   │   └── schemas.py          # Pydantic 模型（ChatRequest、SpatialTwinResponse 等）
│   ├── services/               # 业务逻辑层
│   │   ├── ai_service.py       # LLM 客户端 + 6 个 AI 工具函数
│   │   ├── sql_service.py      # SQL 方言转换 + SELECT 白名单校验（sqlglot）
│   │   ├── ragflow_service.py  # RagFlow 知识库检索
│   │   └── email_service.py    # 定时邮件日报（APScheduler + SMTP）
│   ├── api/v1/                 # API 路由层（9 个路由模块）
│   │   ├── login.py            # POST /api/login
│   │   ├── dashboard.py        # GET /api/dashboard, /api/cop_trend, /api/energy_distribution
│   │   ├── devices.py          # GET /api/devices, /api/equipment/predictive_maintenance
│   │   ├── spatial_twin.py     # GET /api/spatial-twin/*, /api/buildings/{id}/3d-data
│   │   ├── chat.py             # POST /api/chat/stream, /api/upload_doc
│   │   ├── energy.py           # GET /api/energy/forecast（Prophet 预测）
│   │   ├── report.py           # GET /api/report/weekly_ai（Word 报表）
│   │   ├── admin.py            # GET /api/admin/dashboard
│   │   └── websocket.py        # WS /ws/realtime_energy
│   └── utils/
│       └── name_maps.py        # 设备名称中英文映射字典
├── scripts/                    # 独立脚本（非运行时依赖）
│   ├── energy_digital_twin_engine.py   # 数据库初始化 + 8760 小时仿真数据
│   ├── train_rul_model.py              # 训练 RandomForest RUL 预测模型
│   ├── generate_report_charts.py       # 生成报告图表
│   ├── generate_thesis_charts.py       # 生成论文图表
│   ├── export_dataset.py               # 导出数据集为 CSV
│   └── test_api.py                     # RagFlow API 探测脚本
├── mcp/                        # MCP 服务器
│   └── mcp_server.py           # 向 LLM 暴露 3 个工具（能耗查询/异常设备/RUL 预测）
├── data/                       # 数据文件
│   ├── enterprise_building_energy.db   # 主数据库（SQLite）
│   ├── building_energy.db             # 旧数据库
│   └── rul_prediction_model.pkl       # 训练好的 RUL 预测模型
├── assets/                     # 论文/报告图表 PNG
├── logs/                       # uvicorn 运行日志
├── temp/                       # 临时文件
├── .env                        # 环境变量（密钥、SMTP、RagFlow）
├── .env.example                # 环境变量模板
├── main.py                     # [已弃用] 旧版单文件入口，保留作备份，勿使用
├── db.py                       # [已弃用] 旧版数据库模块，已迁移到 app/core/database.py
└── auth.py                     # [已弃用] 旧版鉴权模块，已迁移到 app/core/security.py
```

## 启动命令

```bash
# 启动后端（使用新分层架构）
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 旧版启动方式（已弃用）
# uvicorn main:app --port 8000
```

## 分层职责

| 层级 | 目录 | 职责 |
|------|------|------|
| 入口 | `app/main.py` | 创建 FastAPI、CORS、异常处理器、路由挂载、定时任务调度 |
| 核心 | `app/core/` | 配置中心、数据库连接、JWT 鉴权 |
| 模型 | `app/models/` | Pydantic 请求/响应模型 |
| 服务 | `app/services/` | 业务逻辑（AI、SQL、知识库、邮件） |
| 路由 | `app/api/v1/` | HTTP 路由定义，按业务域拆分 |
| 工具 | `app/utils/` | 通用工具函数和常量字典 |
| 脚本 | `scripts/` | 一次性/独立运行的脚本 |
| 数据 | `data/` | 数据库和模型文件 |
