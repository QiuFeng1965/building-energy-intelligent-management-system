# 擎翼数字中枢（Qingyi Digital Hub）

> 工业级全域数智底座，面向建筑能源智能管理的数字孪生平台。

## 技术栈

- **前端**：Vue3 + Three.js + TresJS + ECharts + TailwindCSS
- **后端**：FastAPI + SQLite + Pandas + OpenAI 兼容 API（OpenCode Zen）
- **AI**：流式对话、Prophet 时序预测、RandomForest RUL 模型、MCP 工具协议
- **数据**：SQLite（WAL 模式），8760 小时仿真数据

## 目录结构

| 一级目录 / 文件 | 职责 |
| --- | --- |
| `backend/` | FastAPI 后端服务，承载 REST API、WebSocket、AI 流式对话、定时邮件、Prophet 预测、Word 报表、MCP 工具服务器 |
| `frontend/` | Vue3 前端应用，含 3D 数字孪生可视化、能源分析、设备监控、AI Agent、管理后台 |
| `temp/` | 根目录临时文件存放区，存放 Word 临时锁文件（`~$*.docx`）等开发临时产物 |
| `.idea/` | JetBrains IDE 工程配置 |
| `__pycache__/` | Python 字节码缓存 |
| `全域基础设施运行安全与维保标准化大纲（Outline of Standardization of Global Infrastructure Operation Safety and Maintenance）/` | 各类建筑设备（暖通、空调、水泵、照明、充电桩等）维护保养手册 |
| `全域资产运行态势自动化复盘与决策沙盘 (Global Asset Operation Stance Automated Retrospective Sandbox)/` | AI 能效诊断周报与样板图 |
| `全息物理孪生高保真遥测数据湖 (Holographic Physical Twin High-Fidelity Telemetry Data Lake)/` | 仿真数据集 CSV 与数据库 dump |
| `全链路 API 自动化校验与零信任熔断战报（Full-link API automated verification and zero-trust circuit breaker battle report）/` | API 自动化校验战报 |
| `多模态视觉诊断凭证 (Multi-modal Visual Diagnostic Evidence)/` | 多模态诊断图例 |
| `大模型红队对抗演练与指令"越狱"防御体系 (LLM Red Teaming & Jailbreak Defense System)/` | LLM 红队对抗、提示注入、权限劫持等安全测试用例 |
| `擎翼数字中枢：工业级全域数智底座核心资产包（Qingyi Digital Hub Core Asset Package of Industrial-Grade Full-Domain Digital Intelligence Foundation）/` | 项目全套白皮书与文档（架构、部署、API 审计、ROI、数据字典、算法评估等） |
| `擎翼数字中枢_全量优化报告.md` | 项目全量优化报告 |

## 快速启动

### 1. 后端

```bash
cd backend
# 配置环境变量（首次需复制示例）
cp .env.example .env
# 安装依赖（建议使用虚拟环境）
pip install -r requirements.txt
# 启动服务
uvicorn main:app --port 8000
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

## 登录信息

- 用户名：`admin`
- 密码：`admin123`

## 环境变量

后端需在 `backend/.env` 中配置环境变量，可参考 `backend/.env.example`。常用配置项包含：

- 数据库路径
- OpenAI 兼容 API 端点与密钥（OpenCode Zen）
- SMTP 邮件服务配置（定时邮件）
- JWT 密钥与过期时间
