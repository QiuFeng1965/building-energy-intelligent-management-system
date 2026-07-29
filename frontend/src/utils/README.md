# 工具函数目录

本目录存放前端通用工具函数，为各业务模块提供统一的底层能力支持。

## 工具清单

- **request.js**
  前端统一请求工具，核心能力包括：
  - `safeFetch()`：具备超时控制与 `AbortController` 取消能力的请求封装；
  - `getAuthHeaders()`：自动注入 JWT 鉴权头的请求头生成函数；
  - `createAbortableFetch()`：创建可取消请求工厂，便于业务侧管理请求生命周期。
