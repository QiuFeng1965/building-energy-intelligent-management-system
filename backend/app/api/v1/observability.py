# -*- coding: utf-8 -*-
"""
可观测性指标路由（OpenTelemetry 风格）
- /api/observability/metrics：系统指标（请求量、延迟、错误率、DB 连接）
- /api/observability/traces：最近请求链路追踪
- /api/observability/health：组件级健康检查
- /api/observability/dashboard：Grafana 风格概览数据

设计要点：
1. 在内存中维护滑动窗口的指标统计
2. trace_id 关联整条请求链
3. 不依赖外部 Prometheus/Grafana，开箱即用
"""
import time
import logging
import threading
from collections import defaultdict, deque

from fastapi import APIRouter, Request

from app.core.database import get_conn, DBUnavailableError
from app.core.config import DB_PATH

logger = logging.getLogger(__name__)
router = APIRouter()


# ===== 指标存储（滑动窗口 5 分钟）=====
_metrics_lock = threading.Lock()
_request_metrics: deque = deque(maxlen=5000)  # 每条：{path, method, status, duration_ms, ts}
_db_metrics: deque = deque(maxlen=1000)       # 每条：{query, duration_ms, ts}
_error_events: deque = deque(maxlen=200)      # 错误事件
_trace_spans: deque = deque(maxlen=500)       # trace spans


def record_request(path: str, method: str, status: int, duration_ms: float, trace_id: str = ""):
    """记录 HTTP 请求指标（由中间件调用）"""
    with _metrics_lock:
        _request_metrics.append({
            "path": path, "method": method, "status": status,
            "duration_ms": round(duration_ms, 2), "ts": time.time(),
            "trace_id": trace_id,
        })


def record_db_query(query: str, duration_ms: float, trace_id: str = ""):
    """记录 DB 查询指标"""
    with _metrics_lock:
        _db_metrics.append({
            "query": query[:200], "duration_ms": round(duration_ms, 2),
            "ts": time.time(), "trace_id": trace_id,
        })


def record_error(path: str, error: str, trace_id: str = ""):
    """记录错误事件"""
    with _metrics_lock:
        _error_events.append({
            "path": path, "error": error[:500], "trace_id": trace_id,
            "ts": time.time(),
        })


def record_span(trace_id: str, span_id: str, operation: str, duration_ms: float, parent_id: str = ""):
    """记录 trace span"""
    with _metrics_lock:
        _trace_spans.append({
            "trace_id": trace_id, "span_id": span_id, "parent_id": parent_id,
            "operation": operation, "duration_ms": round(duration_ms, 2),
            "ts": time.time(),
        })


@router.get("/api/observability/metrics")
def get_metrics(window_seconds: int = 300):
    """系统指标（默认 5 分钟滑动窗口）"""
    now = time.time()
    cutoff = now - window_seconds

    with _metrics_lock:
        recent = [m for m in _request_metrics if m["ts"] >= cutoff]
        recent_db = [m for m in _db_metrics if m["ts"] >= cutoff]
        recent_errors = [e for e in _error_events if e["ts"] >= cutoff]

    # 聚合统计
    total_requests = len(recent)
    status_counts = defaultdict(int)
    path_latency = defaultdict(list)
    for m in recent:
        status_counts[m["status"]] += 1
        path_latency[m["path"]].append(m["duration_ms"])

    error_count = sum(c for s, c in status_counts.items() if s >= 400)
    error_rate = error_count / total_requests * 100 if total_requests > 0 else 0

    # P50 / P95 / P99
    all_latencies = sorted([m["duration_ms"] for m in recent])
    def percentile(data, p):
        if not data:
            return 0
        idx = min(int(len(data) * p / 100), len(data) - 1)
        return data[idx]

    # Top 5 慢接口
    path_stats = []
    for path, lats in path_latency.items():
        path_stats.append({
            "path": path,
            "count": len(lats),
            "avg_ms": round(sum(lats) / len(lats), 2),
            "max_ms": round(max(lats), 2),
            "min_ms": round(min(lats), 2),
        })
    path_stats.sort(key=lambda x: x["avg_ms"], reverse=True)

    # DB 查询统计
    db_total = len(recent_db)
    db_avg = sum(d["duration_ms"] for d in recent_db) / db_total if db_total > 0 else 0
    db_slow = [d for d in recent_db if d["duration_ms"] > 100]

    return {
        "status": "success",
        "data": {
            "window_seconds": window_seconds,
            "http": {
                "total_requests": total_requests,
                "rps": round(total_requests / window_seconds, 2),
                "status_counts": dict(status_counts),
                "error_count": error_count,
                "error_rate_pct": round(error_rate, 2),
                "latency": {
                    "p50_ms": percentile(all_latencies, 50),
                    "p95_ms": percentile(all_latencies, 95),
                    "p99_ms": percentile(all_latencies, 99),
                    "avg_ms": round(sum(all_latencies) / len(all_latencies), 2) if all_latencies else 0,
                },
                "slowest_endpoints": path_stats[:5],
            },
            "database": {
                "total_queries": db_total,
                "avg_duration_ms": round(db_avg, 2),
                "slow_query_count": len(db_slow),
                "slow_queries": db_slow[:10],
            },
            "errors": {
                "total": len(recent_errors),
                "recent": recent_errors[-20:][::-1],
            },
        },
    }


@router.get("/api/observability/traces")
def get_traces(limit: int = 50):
    """获取最近的 trace spans"""
    with _metrics_lock:
        spans = list(_trace_spans)[-limit:][::-1]

    # 按 trace_id 分组
    traces = defaultdict(list)
    for span in spans:
        traces[span["trace_id"]].append(span)

    return {
        "status": "success",
        "data": {
            "total_spans": len(spans),
            "total_traces": len(traces),
            "recent_traces": [
                {
                    "trace_id": tid,
                    "span_count": len(sps),
                    "total_duration_ms": round(sum(s["duration_ms"] for s in sps), 2),
                    "spans": sorted(sps, key=lambda x: x["ts"]),
                }
                for tid, sps in list(traces.items())[:20]
            ],
        },
    }


@router.get("/api/observability/health")
def component_health():
    """组件级健康检查"""
    components = []

    # 数据库
    try:
        with get_conn() as conn:
            conn.execute("SELECT 1").fetchone()
            components.append({"name": "database", "status": "healthy", "latency_ms": 0})
    except DBUnavailableError:
        components.append({"name": "database", "status": "unhealthy", "error": "DB 不可达"})
    except Exception as e:
        logger.exception(f"数据库健康检查失败: {e}")
        components.append({"name": "database", "status": "unhealthy", "error": "数据库连接异常"})

    # LLM API（轻量探测，不实际调用）
    components.append({"name": "llm_api", "status": "unknown", "note": "需实际调用时检测"})

    # 系统指标
    import os
    try:
        import psutil
        cpu_pct = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        # psutil 在 Windows 上需要目录路径而非文件路径
        disk_path = os.path.dirname(DB_PATH) if os.path.isfile(DB_PATH) else DB_PATH
        disk = psutil.disk_usage(disk_path)
        components.append({
            "name": "system",
            "status": "healthy" if cpu_pct < 90 and mem.percent < 90 else "warning",
            "cpu_pct": cpu_pct,
            "memory_pct": mem.percent,
            "disk_pct": disk.percent,
        })
    except ImportError:
        components.append({"name": "system", "status": "unknown", "note": "psutil 未安装"})

    all_healthy = all(c["status"] == "healthy" for c in components)
    return {
        "status": "success",
        "data": {
            "overall": "healthy" if all_healthy else "degraded",
            "components": components,
            "timestamp": time.time(),
        },
    }


@router.get("/api/observability/dashboard")
def dashboard_data():
    """Grafana 风格概览数据（前端可视化用）"""
    now = time.time()
    # 取近 1 小时数据，按分钟聚合
    with _metrics_lock:
        recent = [m for m in _request_metrics if m["ts"] >= now - 3600]
        recent_db = [m for m in _db_metrics if m["ts"] >= now - 3600]

    # 按分钟聚合
    timeline = defaultdict(lambda: {"requests": 0, "errors": 0, "total_latency": 0, "db_queries": 0})
    for m in recent:
        minute = int((m["ts"] // 60) * 60)
        timeline[minute]["requests"] += 1
        if m["status"] >= 400:
            timeline[minute]["errors"] += 1
        timeline[minute]["total_latency"] += m["duration_ms"]

    for m in recent_db:
        minute = int((m["ts"] // 60) * 60)
        timeline[minute]["db_queries"] += 1

    timeline_data = [
        {
            "timestamp": ts,
            "time": time.strftime("%H:%M", time.localtime(ts)),
            "requests": v["requests"],
            "errors": v["errors"],
            "avg_latency_ms": round(v["total_latency"] / v["requests"], 2) if v["requests"] > 0 else 0,
            "db_queries": v["db_queries"],
        }
        for ts, v in sorted(timeline.items())
    ]

    return {
        "status": "success",
        "data": {
            "timeline": timeline_data,
            "summary": {
                "total_requests_1h": len(recent),
                "total_db_queries_1h": len(recent_db),
                "avg_rps": round(len(recent) / 3600, 2),
            },
        },
    }


# ===== 前端 Web Vitals 与错误上报 =====
_web_vitals_store: deque = deque(maxlen=500)   # 存储 Web Vitals 指标
_frontend_errors: deque = deque(maxlen=200)     # 存储前端错误
_telemetry_lock = threading.Lock()


@router.post("/api/observability/web-vitals")
async def receive_web_vitals(request: Request):
    """接收前端上报的 Web Vitals 指标（LCP/CLS/INP/TTFB）"""
    try:
        body = await request.json()
    except Exception:
        return {"status": "ignored", "reason": "invalid_body"}

    with _telemetry_lock:
        _web_vitals_store.append({
            "name": body.get("name"),
            "value": round(float(body.get("value", 0)), 2),
            "rating": body.get("rating", "unknown"),
            "url": body.get("url", ""),
            "ts": body.get("ts", time.time() * 1000),
        })
    return {"status": "ok"}


@router.post("/api/observability/frontend-error")
async def receive_frontend_error(request: Request):
    """接收前端上报的 JS 渲染错误"""
    try:
        body = await request.json()
    except Exception:
        return {"status": "ignored", "reason": "invalid_body"}

    with _telemetry_lock:
        _frontend_errors.append({
            "message": str(body.get("message", ""))[:500],
            "stack": str(body.get("stack", ""))[:2000],
            "url": body.get("url", ""),
            "ts": body.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%S")),
        })
    logger.warning(
        "前端渲染错误",
        extra={
            "error_msg": body.get("message", ""),
            "url": body.get("url", ""),
        },
    )
    return {"status": "ok"}


@router.get("/api/observability/frontend-stats")
def frontend_stats():
    """前端性能与错误统计（供管理后台展示）"""
    with _telemetry_lock:
        vitals = list(_web_vitals_store)
        errors = list(_frontend_errors)

    # 按指标名聚合
    vital_summary = defaultdict(list)
    for v in vitals:
        vital_summary[v["name"]].append(v["value"])

    return {
        "status": "success",
        "data": {
            "web_vitals": {
                "total": len(vitals),
                "summary": {
                    name: {
                        "count": len(vals),
                        "avg": round(sum(vals) / len(vals), 2),
                        "max": round(max(vals), 2),
                        "min": round(min(vals), 2),
                    }
                    for name, vals in vital_summary.items()
                },
                "recent": vitals[-20:][::-1],
            },
            "frontend_errors": {
                "total": len(errors),
                "recent": errors[-20:][::-1],
            },
        },
    }


@router.get("/api/observability/cache-stats")
def cache_stats():
    """API 响应缓存统计（response_cache 模块）"""
    from app.core.response_cache import get_cache_stats
    return {"status": "success", "data": get_cache_stats()}
