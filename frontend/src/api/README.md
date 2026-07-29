# API 调用层

本目录是项目的统一 API 调用层，集中管理所有后端接口请求。

## 设计原则

- 所有后端接口调用统一通过 `src/api/index.js` 导出的函数完成，避免在 .vue 业务组件中散落 `fetch` / `axios` 调用。
- 默认基于 `src/utils/request.js` 的 `safeFetch`（含超时控制 + JWT 鉴权 + 错误兜底）。
- 例外：返回二进制流的接口（如 `fetchWeeklyAiReport`）与 FormData 文件上传接口（如 `uploadDoc`）单独使用 `fetch` 处理，原因详见各函数注释。
- 业务层只需关心请求参数与响应数据，无需关注鉴权头、超时、错误兜底等底层细节。

## 导出函数清单

| 函数名 | 方法 | 接口路径 | 说明 |
| --- | --- | --- | --- |
| `fetchDashboard()` | GET | `/api/dashboard` | 首页能效全景监控仪表盘数据 |
| `fetchDevices(params)` | GET | `/api/devices` | 按条件查询设备监测数据 |
| `fetchCopTrend()` | GET | `/api/cop_trend` | 全天候系统能效比 (COP) 趋势 |
| `fetchEnergyDistribution()` | GET | `/api/energy_distribution` | 能耗分布数据（饼图等） |
| `fetchSpatialCampusData()` | GET | `/api/spatial-twin/campus-data` | 空间孪生校园级数据 |
| `fetchFullCampusSim()` | GET | `/api/spatial-twin/full-campus-sim` | 全校园仿真数据 |
| `fetchBuilding3DData(id)` | GET | `/api/buildings/{id}/3d-data` | 指定建筑的 3D 详细数据 |
| `fetchEnergyForecast(hours)` | GET | `/api/energy/forecast` | 未来能耗 AI 预测 |
| `fetchPredictiveMaintenance()` | GET | `/api/equipment/predictive_maintenance` | AI 预测性维护 (RUL) |
| `fetchWeeklyAiReport()` | GET | `/api/report/weekly_ai` | AI 能效诊断周报（Word 二进制流） |
| `fetchAdminDashboard()` | GET | `/api/admin/dashboard` | 管理后台仪表盘数据 |
| `uploadDoc(file, user)` | POST | `/api/upload_doc` | 上传文档至知识库 |

## 使用示例

```js
import { fetchDashboard, fetchDevices, uploadDoc } from '@/api'

// 获取仪表盘数据
const data = await fetchDashboard()

// 按条件查询设备
const result = await fetchDevices({ building: 'TEACHING', status: 'NORMAL', size: 500 })

// 上传文档（FormData 文件上传）
const file = fileInput.files[0]
const res = await uploadDoc(file, 'admin')
```
