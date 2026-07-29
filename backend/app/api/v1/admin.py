# -*- coding: utf-8 -*-
"""
管理后台路由
- /api/admin/dashboard：数据驾驶舱（真实 KPI，从数据库聚合）
- /api/admin/audit_logs：审计日志查询（高危操作拦截记录）
- /api/admin/kb/list：知识库文档列表
- /api/admin/kb/upload：知识库文档上传（手动喂入）
- /api/admin/kb/{doc_id}：知识库文档删除
所有接口均需管理员权限（JWT + require_admin）。
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.security import require_admin
from app.core.database import get_conn
from app.core.route_error import handle_route_error

logger = logging.getLogger(__name__)
router = APIRouter()


# ===== 请求/响应模型 =====
class KnowledgeItem(BaseModel):
    """手动录入知识条目"""
    title: str
    content: str
    tags: str = ""


class AuditLogCreate(BaseModel):
    """审计日志写入模型（供其他模块调用）"""
    user: str
    action: str
    detail: str = ""
    risk_level: str = "low"  # low | high


# ===== 初始化审计日志表（幂等） =====
def _ensure_audit_table():
    """确保 sys_audit_logs 表存在（首次调用时自动建表）"""
    try:
        with get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sys_audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user TEXT NOT NULL,
                    action TEXT NOT NULL,
                    detail TEXT DEFAULT '',
                    risk_level TEXT DEFAULT 'low',
                    trace_id TEXT DEFAULT '',
                    created_time TEXT NOT NULL
                )
                """
            )
            conn.commit()
    except Exception as e:
        logger.exception(f"初始化审计日志表失败: {e}")


def write_audit_log(user: str, action: str, detail: str = "", risk_level: str = "low"):
    """
    写入审计日志（供其他模块调用，如 AI 拦截高危操作时）。
    trace_id 从 ContextVar 自动获取（如果链路追踪中间件已设置）。
    """
    import datetime
    try:
        from app.core.logging_config import trace_id_var
        trace_id = trace_id_var.get("")
    except Exception:
        trace_id = ""

    try:
        _ensure_audit_table()
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO sys_audit_logs (user, action, detail, risk_level, trace_id, created_time) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    user,
                    action,
                    detail,
                    risk_level,
                    trace_id,
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            conn.commit()
        logger.info(f"审计日志已记录: user={user}, action={action}, risk={risk_level}")
    except Exception as e:
        logger.exception(f"写入审计日志失败: {e}")


# ===== 真实 KPI 聚合 =====
def _fetch_real_kpis() -> dict:
    """从数据库聚合真实 KPI 数据"""
    kpis = {
        "total_consultations": 0,
        "ai_messages": 0,
        "abnormal_visits": 0,
        "published_articles": 0,
        "kb_trained": 0,
        "audit_intercepts": 0,
        "total_devices": 0,
        "total_energy_kwh": 0.0,
        "today_alarms": 0,
    }
    try:
        with get_conn() as conn:
            # 今日业务日期（取数据库最大日期，而非系统时间）
            row = conn.execute(
                "SELECT MAX(DATE(monitor_time)) as biz_date FROM fact_energy_records"
            ).fetchone()
            biz_date = row[0] if row and row[0] else None

            if biz_date:
                # 今日异常告警数
                today_alarms = conn.execute(
                    "SELECT COUNT(*) FROM fact_energy_records "
                    "WHERE DATE(monitor_time) = ? AND run_status != 'NORMAL'",
                    [biz_date],
                ).fetchone()[0]
                kpis["today_alarms"] = int(today_alarms)

                # 今日总能耗
                today_energy = conn.execute(
                    "SELECT COALESCE(SUM(elec_consumption), 0) FROM fact_energy_records "
                    "WHERE DATE(monitor_time) = ?",
                    [biz_date],
                ).fetchone()[0]
                kpis["total_energy_kwh"] = round(float(today_energy), 2)

            # 累计异常记录数（abnormal_visits）
            abnormal = conn.execute(
                "SELECT COUNT(*) FROM fact_energy_records WHERE run_status != 'NORMAL'"
            ).fetchone()[0]
            kpis["abnormal_visits"] = int(abnormal)

            # 设备总数
            devices = conn.execute("SELECT COUNT(*) FROM dim_devices").fetchone()[0]
            kpis["total_devices"] = int(devices)

            # 累计能耗记录数（ai_messages 代理指标：数据采集量）
            records = conn.execute("SELECT COUNT(*) FROM fact_energy_records").fetchone()[0]
            kpis["ai_messages"] = int(records)

    except Exception as e:
        logger.exception(f"聚合 KPI 失败: {e}")

    return kpis


def _fetch_recent_audit_logs(limit: int = 50) -> list:
    """查询最近的审计日志"""
    _ensure_audit_table()
    try:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT id, user, action, detail, risk_level, trace_id, created_time "
                "FROM sys_audit_logs ORDER BY id DESC LIMIT ?",
                [limit],
            ).fetchall()
            return [
                {
                    "id": r[0],
                    "user": r[1],
                    "action": r[2],
                    "detail": r[3],
                    "risk_level": r[4],
                    "trace_id": r[5],
                    "time": r[6],
                }
                for r in rows
            ]
    except Exception as e:
        logger.exception(f"查询审计日志失败: {e}")
        return []


# ===== 路由 =====
@router.get("/api/admin/dashboard")
async def get_admin_dashboard(user: str = Depends(require_admin)):
    """数据驾驶舱：真实 KPI + 知识库状态 + 图表数据"""
    try:
        from app.main import get_all_knowledge_base

        kb_count = len(get_all_knowledge_base())
        kpis = _fetch_real_kpis()
        kpis["kb_trained"] = kb_count

        # 内容分布图表数据
        content_distribution = [
            {"name": "AI 调度指令", "value": kpis["ai_messages"]},
            {"name": "异常拦截", "value": kpis["abnormal_visits"]},
            {"name": "知识库投喂", "value": kb_count},
            {"name": "今日告警", "value": kpis["today_alarms"]},
        ]

        return {
            "status": "success",
            "data": {
                "kpis": kpis,
                "charts": {
                    "content_distribution": content_distribution,
                },
            },
        }
    except Exception as e:
        return handle_route_error(e, logger, "获取管理大屏数据")


@router.get("/api/admin/audit_logs")
async def get_audit_logs(
    user: str = Depends(require_admin),
    limit: int = Query(50, ge=1, le=500, description="返回条数"),
    risk_level: str = Query("all", description="风险等级过滤：all|low|high"),
):
    """查询审计日志（支持按风险等级过滤）"""
    logs = _fetch_recent_audit_logs(limit=limit)
    if risk_level != "all":
        logs = [log for log in logs if log["risk_level"] == risk_level]

    return {
        "status": "success",
        "data": logs,
        "total": len(logs),
    }


@router.post("/api/admin/audit_logs")
async def create_audit_log(
    log_data: AuditLogCreate,
    user: str = Depends(require_admin),
):
    """手动写入审计日志（也可供其他模块内部调用）"""
    write_audit_log(
        user=user,
        action=log_data.action,
        detail=log_data.detail,
        risk_level=log_data.risk_level,
    )
    return {"status": "success", "message": "审计日志已记录"}


@router.get("/api/admin/kb/list")
async def list_knowledge_base(user: str = Depends(require_admin)):
    """查询知识库文档列表（内存队列中的临时知识 + 元数据）"""
    try:
        from app.main import get_all_knowledge_base

        all_kb = get_all_knowledge_base()
        items = []
        for i, doc in enumerate(all_kb):
            if isinstance(doc, dict):
                items.append({
                    "id": f"KB-{i+1}",
                    "title": doc.get("title", f"文档 {i+1}"),
                    "content": doc.get("content", "")[:200],
                    "tags": doc.get("tags", ""),
                    "source": doc.get("source", "管理员录入"),
                })
            else:
                items.append({
                    "id": f"KB-{i+1}",
                    "title": str(doc)[:100],
                    "content": str(doc)[:200],
                    "tags": "",
                    "source": "未知",
                })

        return {
            "status": "success",
            "data": items,
            "total": len(items),
        }
    except Exception as e:
        return handle_route_error(e, logger, "知识库列表查询")


@router.post("/api/admin/kb/upload")
async def upload_knowledge_item(
    item: KnowledgeItem,
    user: str = Depends(require_admin),
):
    """手动录入知识条目到知识库（有界队列，自动淘汰旧数据）"""
    try:
        from app.main import get_user_knowledge_base

        doc = {
            "title": item.title,
            "content": item.content,
            "tags": item.tags,
            "source": f"管理员 {user} 录入",
        }
        user_kb = get_user_knowledge_base(user)
        user_kb.append(doc)

        # 记录审计日志
        write_audit_log(
            user=user,
            action="知识库录入",
            detail=f"标题: {item.title}",
            risk_level="low",
        )

        return {
            "status": "success",
            "message": "知识条目已添加",
            "data": {"id": f"KB-{len(user_kb)}", "total": len(user_kb)},
        }
    except Exception as e:
        return handle_route_error(e, logger, "知识库录入")


@router.delete("/api/admin/kb/{doc_index}")
async def delete_knowledge_item(
    doc_index: int,
    user: str = Depends(require_admin),
):
    """删除知识库中的指定条目（按索引，原子操作）"""
    try:
        from app.main import delete_knowledge_item_by_index, get_all_knowledge_base

        # 先获取快照用于边界检查和审计日志标题提取
        all_kb = get_all_knowledge_base()
        if doc_index < 0 or doc_index >= len(all_kb):
            raise HTTPException(status_code=404, detail="知识条目不存在")

        deleted_doc = all_kb[doc_index]
        deleted_title = deleted_doc.get("title", "") if isinstance(deleted_doc, dict) else str(deleted_doc)[:50]

        # 原子删除（_kb_lock 保护，避免 clear+extend 竞态）
        if not delete_knowledge_item_by_index(doc_index):
            raise HTTPException(status_code=404, detail="知识条目不存在（可能已被并发操作删除）")

        # 记录审计日志
        write_audit_log(
            user=user,
            action="知识库删除",
            detail=f"删除条目: {deleted_title}",
            risk_level="low",
        )

        return {
            "status": "success",
            "message": "知识条目已删除",
            "data": {"remaining": len(get_all_knowledge_base())},
        }
    except HTTPException:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "知识库删除")
