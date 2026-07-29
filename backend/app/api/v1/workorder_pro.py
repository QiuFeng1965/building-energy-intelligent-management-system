# -*- coding: utf-8 -*-
"""
工单全生命周期管理增强路由
- GET  /api/workorders/pro/list        ：增强工单列表（含 SLA 状态、优先级、负责人）
- GET  /api/workorders/pro/{order_id}  ：工单详情（含处理时间线、备件清单）
- POST /api/workorders/pro/dispatch    ：智能派单（根据设备类型、位置、技能匹配推荐人员）
- GET  /api/workorders/pro/sla_stats   ：SLA 统计（按时完成率、超时率、平均处理时长）
- GET  /api/workorders/pro/parts       ：备件库存查询

增强表（CREATE TABLE IF NOT EXISTS）：
- sys_workorder_ext: order_id, priority(P0-P3), assignee, assignee_skill,
                     sla_due_at, sla_status, created_by, created_at, updated_at
- sys_parts_inventory: part_id, part_name, category, stock_qty, unit_price,
                       min_stock, location

SLA 规则：
- P0（紧急）：4 小时内响应，8 小时内完成
- P1（高）：  8 小时响应，  24 小时完成
- P2（中）：  24 小时响应， 72 小时完成
- P3（低）：  48 小时响应，  7 天完成

智能派单：基于设备类型匹配技能，优先分配负载最低的工程师
- CHILLER / PRECISION_AC / REFRIGERATION / WATER_HEATER → 制冷工程师
- PUMP → 机械工程师
- HVAC / AHU / VENTILATION → 暖通工程师
- LIGHTING / SOCKET / EV_CHARGER / METER → 电气工程师
"""
import math
import logging
import datetime
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.database import get_conn, run_in_thread, DBUnavailableError
from app.core.route_error import handle_route_error

logger = logging.getLogger(__name__)
router = APIRouter()

# ===== SLA 规则（响应时长 / 完成时长，单位小时）=====
SLA_RULES: dict = {
    "P0": {"name": "紧急", "response_hours": 4,  "completion_hours": 8},
    "P1": {"name": "高",   "response_hours": 8,  "completion_hours": 24},
    "P2": {"name": "中",   "response_hours": 24, "completion_hours": 72},
    "P3": {"name": "低",   "response_hours": 48, "completion_hours": 168},  # 7 天
}
VALID_PRIORITIES = set(SLA_RULES.keys())
DEFAULT_PRIORITY = "P2"

# ===== 设备类型 → 所需技能映射 =====
# 兼容任务约定的 CHILLER/AHU/METER 与数据库实际的 HVAC/PUMP/LIGHTING 等
DEVICE_TYPE_SKILL: dict = {
    # 制冷类
    "CHILLER": "制冷工程师",
    "PRECISION_AC": "制冷工程师",
    "REFRIGERATION": "制冷工程师",
    "WATER_HEATER": "制冷工程师",
    # 机械类
    "PUMP": "机械工程师",
    # 暖通类
    "HVAC": "暖通工程师",
    "AHU": "暖通工程师",
    "VENTILATION": "暖通工程师",
    # 电气类
    "LIGHTING": "电气工程师",
    "SOCKET": "电气工程师",
    "EV_CHARGER": "电气工程师",
    "METER": "电气工程师",
}

# ===== 工程师花名册（内存存储，含技能与当前活跃工单数）=====
# 每位工程师可掌握多技能；active_orders 用于派单时挑选负载最低者
_ENGINEERS: list = [
    {"id": "E001", "name": "张工", "skills": ["暖通工程师", "制冷工程师"], "active_orders": 0},
    {"id": "E002", "name": "李工", "skills": ["机械工程师", "暖通工程师"], "active_orders": 0},
    {"id": "E003", "name": "王工", "skills": ["电气工程师"], "active_orders": 0},
    {"id": "E004", "name": "赵工", "skills": ["制冷工程师", "暖通工程师"], "active_orders": 0},
    {"id": "E005", "name": "钱工", "skills": ["机械工程师"], "active_orders": 0},
    {"id": "E006", "name": "孙工", "skills": ["电气工程师", "暖通工程师"], "active_orders": 0},
]

# 优先级中文标签
PRIORITY_LABELS = {p: cfg["name"] for p, cfg in SLA_RULES.items()}

# SLA 状态标签
SLA_STATUS_LABELS = {
    "on_track": "进行中/未超时",
    "met": "按时完成",
    "breached": "超时",
    "n/a": "不适用",
}

# 表初始化标记
_table_initialized = False


# ===== 表初始化 =====
def _init_tables():
    """惰性创建 sys_workorder_ext / sys_parts_inventory 表并预置备件（仅执行一次）"""
    global _table_initialized
    if _table_initialized:
        return
    try:
        with get_conn() as conn:
            # 工单扩展表
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sys_workorder_ext (
                    order_id        VARCHAR(50) PRIMARY KEY,
                    priority        VARCHAR(5) NOT NULL DEFAULT 'P2',
                    assignee        VARCHAR(50),
                    assignee_skill  VARCHAR(50),
                    sla_due_at      DATETIME,
                    sla_status      VARCHAR(20) DEFAULT 'on_track',
                    created_by      VARCHAR(50),
                    created_at      DATETIME,
                    updated_at      DATETIME
                )
                """
            )
            # 备件库存表
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sys_parts_inventory (
                    part_id     VARCHAR(50) PRIMARY KEY,
                    part_name   VARCHAR(100) NOT NULL,
                    category    VARCHAR(50),
                    stock_qty   INTEGER NOT NULL DEFAULT 0,
                    unit_price  REAL NOT NULL DEFAULT 0,
                    min_stock   INTEGER NOT NULL DEFAULT 0,
                    location    VARCHAR(100)
                )
                """
            )
            conn.commit()

            # 预置 15 种常见备件（仅在表为空时插入）
            cnt = conn.execute("SELECT COUNT(*) FROM sys_parts_inventory").fetchone()[0]
            if cnt == 0:
                _seed_parts(conn)
                conn.commit()

        _table_initialized = True
        logger.info("sys_workorder_ext / sys_parts_inventory 表已就绪")
    except Exception as e:
        logger.exception(f"初始化工单增强表失败: {e}")


# 15 种常见备件预置数据
_PARTS_SEED: list = [
    ("P-001", "螺杆式压缩机", "压缩机", 2, 38000, 1, "A区备件库-货架3"),
    ("P-002", "离心式压缩机", "压缩机", 1, 52000, 1, "A区备件库-货架3"),
    ("P-003", "深沟球轴承 6206", "轴承", 20, 80, 10, "B区备件库-货架1"),
    ("P-004", "机械密封件 DN50", "密封件", 8, 350, 5, "B区备件库-货架2"),
    ("P-005", "温度传感器 PT1000", "传感器", 15, 120, 8, "C区电子件库-货架1"),
    ("P-006", "压力传感器 0-1.6MPa", "传感器", 10, 180, 5, "C区电子件库-货架1"),
    ("P-007", "电动二通阀 DN65", "阀门", 6, 1200, 3, "B区备件库-货架4"),
    ("P-008", "V型三角带 B-71", "传动件", 12, 45, 6, "B区备件库-货架1"),
    ("P-009", "初效滤芯 595x595x46", "滤芯", 30, 60, 15, "D区耗材库-货架2"),
    ("P-010", "中效滤芯 F8", "滤芯", 20, 130, 10, "D区耗材库-货架2"),
    ("P-011", "交流接触器 LC1D40", "电气件", 8, 280, 4, "C区电子件库-货架3"),
    ("P-012", "运行电容 30μF/450V", "电气件", 25, 35, 12, "C区电子件库-货架3"),
    ("P-013", "离心风机叶轮 Φ400", "叶轮", 3, 1800, 2, "A区备件库-货架5"),
    ("P-014", "PLC 控制板", "控制件", 2, 6500, 1, "C区电子件库-货架4"),
    ("P-015", "R410a 制冷剂 10kg", "制冷剂", 5, 850, 3, "E区危化库-冷柜1"),
]


def _seed_parts(conn):
    """预置 15 种备件库存"""
    for p in _PARTS_SEED:
        conn.execute(
            """
            INSERT INTO sys_parts_inventory
                (part_id, part_name, category, stock_qty, unit_price, min_stock, location)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            p,
        )


# ===== 工具函数 =====
def _safe_float(v, ndigits=2):
    """安全转换为 float"""
    try:
        if v is None:
            return None
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, ndigits)
    except (TypeError, ValueError):
        return None


def _row_to_dict(row) -> Optional[dict]:
    """sqlite3.Row → dict"""
    return {k: row[k] for k in row.keys()} if row is not None else None


def _parse_dt(dt_str) -> Optional[datetime.datetime]:
    """解析 'YYYY-MM-DD HH:MM:SS' 字符串为 datetime"""
    if not dt_str:
        return None
    try:
        return datetime.datetime.strptime(str(dt_str), "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        try:
            return datetime.datetime.fromisoformat(str(dt_str))
        except (ValueError, TypeError):
            return None


def _calc_sla_due_at(created_at_str: str, priority: str) -> Optional[str]:
    """根据工单创建时间与优先级计算 SLA 完成截止时间"""
    cfg = SLA_RULES.get(priority)
    if not cfg:
        return None
    created = _parse_dt(created_at_str)
    if created is None:
        return None
    due = created + datetime.timedelta(hours=cfg["completion_hours"])
    return due.strftime("%Y-%m-%d %H:%M:%S")


def _compute_sla_status(order_status: str, created_at_str: str,
                        completed_at_str: Optional[str],
                        sla_due_at_str: Optional[str]) -> str:
    """计算 SLA 状态：on_track / met / breached / n/a"""
    if order_status == "REJECTED":
        return "n/a"
    due = _parse_dt(sla_due_at_str)
    if due is None:
        return "n/a"
    now = datetime.datetime.now()

    if order_status in ("COMPLETED", "VERIFIED"):
        completed = _parse_dt(completed_at_str) or now
        return "met" if completed <= due else "breached"

    # 仍处于 PENDING / IN_PROGRESS
    return "on_track" if now <= due else "breached"


def _ensure_ext_record(conn, order_id: str, created_at_str: str,
                       priority: str = DEFAULT_PRIORITY,
                       created_by: str = "system"):
    """确保工单存在 ext 扩展记录，不存在则按默认优先级创建"""
    row = conn.execute(
        "SELECT order_id FROM sys_workorder_ext WHERE order_id = ?",
        [order_id],
    ).fetchone()
    if row:
        return
    sla_due = _calc_sla_due_at(created_at_str, priority)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """
        INSERT INTO sys_workorder_ext
            (order_id, priority, assignee, assignee_skill, sla_due_at,
             sla_status, created_by, created_at, updated_at)
        VALUES (?, ?, NULL, NULL, ?, 'on_track', ?, ?, ?)
        """,
        [order_id, priority, sla_due, created_by, created_at_str, now_str],
    )


def _refresh_sla_status_for_orders(conn, order_ids: list):
    """批量刷新工单 SLA 状态（基于 fact_work_orders 实际状态）"""
    if not order_ids:
        return
    placeholders = ",".join(["?"] * len(order_ids))
    rows = conn.execute(
        f"""
        SELECT w.order_id, w.status, w.created_at, w.completed_at, e.sla_due_at, e.priority
        FROM fact_work_orders w
        JOIN sys_workorder_ext e ON e.order_id = w.order_id
        WHERE w.order_id IN ({placeholders})
        """,
        order_ids,
    ).fetchall()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for r in rows:
        sla_status = _compute_sla_status(
            r["status"], r["created_at"], r["completed_at"], r["sla_due_at"]
        )
        conn.execute(
            "UPDATE sys_workorder_ext SET sla_status = ?, updated_at = ? WHERE order_id = ?",
            [sla_status, now_str, r["order_id"]],
        )


# ===== 请求模型 =====
class DispatchRequest(BaseModel):
    """智能派单请求"""
    order_id: str = Field(..., description="工单号")
    priority: Optional[str] = Field(None, description="优先级 P0/P1/P2/P3，为空则保持不变")
    assignee: Optional[str] = Field(None, description="指定负责人（为空则自动推荐）")
    created_by: str = Field("system", description="派单人")


class PartsQueryRequest(BaseModel):
    """备件查询请求（可选）"""
    category: Optional[str] = None
    keyword: Optional[str] = None


# ===== 路由 =====
@router.get("/api/workorders/pro/list")
@run_in_thread
def list_workorders_pro(
    status: Optional[str] = Query(None, description="按工单状态过滤：PENDING/IN_PROGRESS/COMPLETED/VERIFIED/REJECTED"),
    priority: Optional[str] = Query(None, description="按优先级过滤：P0/P1/P2/P3"),
    assignee: Optional[str] = Query(None, description="按负责人过滤"),
    sla_status: Optional[str] = Query(None, description="按 SLA 状态过滤：on_track/met/breached/n/a"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页条数"),
):
    """增强工单列表（含 SLA 状态、优先级、负责人）"""
    try:
        _init_tables()
        if priority and priority not in VALID_PRIORITIES:
            raise HTTPException(status_code=400, detail=f"priority 非法，合法值: {sorted(VALID_PRIORITIES)}")

        offset = (page - 1) * page_size
        # 先确保所有工单都有 ext 记录（批量 INSERT OR IGNORE 替代 N+1）
        with get_conn() as conn:
            # 一条 SQL 批量补充缺失的 ext 记录，避免 N+1 查询
            conn.execute(
                """
                INSERT OR IGNORE INTO sys_workorder_ext (order_id, priority, assignee, assignee_skill,
                    sla_due_at, sla_status, created_by, created_at)
                SELECT w.order_id, 'P2', NULL, NULL,
                    datetime(w.created_at, '+' || (
                        SELECT completion_hours FROM (
                            SELECT 'P0' AS p, 4 AS completion_hours
                            UNION ALL SELECT 'P1', 8
                            UNION ALL SELECT 'P2', 24
                            UNION ALL SELECT 'P3', 72
                        ) WHERE p = 'P2'
                    ) || ' hours'),
                    'on_track', 'system', w.created_at
                FROM fact_work_orders w
                WHERE w.order_id NOT IN (SELECT order_id FROM sys_workorder_ext)
                """
            )
            conn.commit()
            # 仅刷新当前页工单的 SLA 状态（而非全量）
            page_order_ids = [
                r["order_id"] for r in conn.execute(
                    "SELECT order_id FROM fact_work_orders ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    [page_size, offset],
                ).fetchall()
            ]
            if page_order_ids:
                _refresh_sla_status_for_orders(conn, page_order_ids)
                conn.commit()

            # 构造查询
            where = "WHERE 1=1"
            params: list = []
            if status:
                where += " AND w.status = ?"
                params.append(status)
            if priority:
                where += " AND e.priority = ?"
                params.append(priority)
            if assignee:
                where += " AND e.assignee = ?"
                params.append(assignee)
            if sla_status:
                where += " AND e.sla_status = ?"
                params.append(sla_status)

            total = conn.execute(
                f"""
                SELECT COUNT(*) FROM fact_work_orders w
                JOIN sys_workorder_ext e ON e.order_id = w.order_id
                {where}
                """,
                params,
            ).fetchone()[0]

            rows = conn.execute(
                f"""
                SELECT w.order_id, w.device_id, w.diagnosis_title, w.status,
                       w.created_at, w.completed_at, w.repair_cost,
                       w.maintenance_action, w.user_feedback,
                       d.device_name, d.device_type, d.building_id,
                       b.building_name,
                       e.priority, e.assignee, e.assignee_skill,
                       e.sla_due_at, e.sla_status, e.created_by
                FROM fact_work_orders w
                LEFT JOIN dim_devices d ON d.device_id = w.device_id
                LEFT JOIN dim_buildings b ON b.building_id = d.building_id
                JOIN sys_workorder_ext e ON e.order_id = w.order_id
                {where}
                ORDER BY
                    CASE e.priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1
                                    WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END,
                    w.created_at DESC
                LIMIT ? OFFSET ?
                """,
                params + [page_size, offset],
            ).fetchall()

        items = []
        for r in rows:
            d = _row_to_dict(r)
            d["priority_label"] = PRIORITY_LABELS.get(d.get("priority"), d.get("priority") or "")
            d["sla_status_label"] = SLA_STATUS_LABELS.get(d.get("sla_status"), d.get("sla_status") or "")
            # 计算 SLA 剩余时长
            if d.get("sla_due_at") and d.get("status") not in ("COMPLETED", "VERIFIED", "REJECTED"):
                due = _parse_dt(d["sla_due_at"])
                if due:
                    delta = due - datetime.datetime.now()
                    d["sla_remaining_hours"] = round(delta.total_seconds() / 3600, 1)
                else:
                    d["sla_remaining_hours"] = None
            else:
                d["sla_remaining_hours"] = None
            items.append(d)

        return {
            "status": "success",
            "data": {
                "orders": items,
                "pagination": {
                    "total": int(total),
                    "page": page,
                    "page_size": page_size,
                },
            },
        }
    except HTTPException:
        raise
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "工单列表查询")


@router.get("/api/workorders/pro/sla_stats")
@run_in_thread
def sla_stats():
    """SLA 统计（按时完成率、超时率、平均处理时长）"""
    try:
        _init_tables()
        with get_conn() as conn:
            # 批量补充缺失的 ext 记录（一条 SQL，避免 N+1）
            conn.execute(
                """
                INSERT OR IGNORE INTO sys_workorder_ext (order_id, priority, assignee, assignee_skill,
                    sla_due_at, sla_status, created_by, created_at)
                SELECT w.order_id, 'P2', NULL, NULL,
                    datetime(w.created_at, '+24 hours'),
                    'on_track', 'system', w.created_at
                FROM fact_work_orders w
                WHERE w.order_id NOT IN (SELECT order_id FROM sys_workorder_ext)
                """
            )
            conn.commit()
            # 仅刷新未完成工单的 SLA 状态
            active_ids = [
                r["order_id"] for r in conn.execute(
                    "SELECT order_id FROM fact_work_orders WHERE status NOT IN ('COMPLETED', 'VERIFIED', 'REJECTED')"
                ).fetchall()
            ]
            if active_ids:
                _refresh_sla_status_for_orders(conn, active_ids)
                conn.commit()

            # SLA 状态分布
            sla_rows = conn.execute(
                """
                SELECT e.sla_status, COUNT(*) AS cnt
                FROM sys_workorder_ext e
                JOIN fact_work_orders w ON w.order_id = e.order_id
                GROUP BY e.sla_status
                """
            ).fetchall()

            # 已完成工单的处理时长统计
            duration_row = conn.execute(
                """
                SELECT
                    AVG(CASE WHEN w.completed_at IS NOT NULL AND w.created_at IS NOT NULL
                        THEN (julianday(w.completed_at) - julianday(w.created_at)) * 24 END) AS avg_hours,
                    MAX(CASE WHEN w.completed_at IS NOT NULL AND w.created_at IS NOT NULL
                        THEN (julianday(w.completed_at) - julianday(w.created_at)) * 24 END) AS max_hours,
                    MIN(CASE WHEN w.completed_at IS NOT NULL AND w.created_at IS NOT NULL
                        THEN (julianday(w.completed_at) - julianday(w.created_at)) * 24 END) AS min_hours,
                    COUNT(CASE WHEN w.completed_at IS NOT NULL THEN 1 END) AS completed_cnt
                FROM fact_work_orders w
                """
            ).fetchone()

            # 按优先级统计
            priority_rows = conn.execute(
                """
                SELECT e.priority,
                       COUNT(*) AS total,
                       SUM(CASE WHEN e.sla_status = 'met' THEN 1 ELSE 0 END) AS met_cnt,
                       SUM(CASE WHEN e.sla_status = 'breached' THEN 1 ELSE 0 END) AS breached_cnt,
                       SUM(CASE WHEN e.sla_status = 'on_track' THEN 1 ELSE 0 END) AS on_track_cnt
                FROM sys_workorder_ext e
                JOIN fact_work_orders w ON w.order_id = e.order_id
                GROUP BY e.priority
                """
            ).fetchall()

        sla_dist = {s: 0 for s in SLA_STATUS_LABELS}
        for r in sla_rows:
            sla_dist[r["sla_status"]] = int(r["cnt"])
        total_orders = sum(sla_dist.values())
        completed_cnt = int(duration_row["completed_cnt"] or 0)
        avg_hours = _safe_float(duration_row["avg_hours"], 2)
        # 按时完成率 = met / (met + breached)
        met_breached = sla_dist.get("met", 0) + sla_dist.get("breached", 0)
        on_time_rate = round(sla_dist.get("met", 0) / met_breached * 100, 2) if met_breached > 0 else 0
        breach_rate = round(sla_dist.get("breached", 0) / max(1, total_orders) * 100, 2)

        by_priority = []
        for r in priority_rows:
            p_total = int(r["total"])
            p_met = int(r["met_cnt"])
            p_breached = int(r["breached_cnt"])
            by_priority.append({
                "priority": r["priority"],
                "priority_label": PRIORITY_LABELS.get(r["priority"], r["priority"]),
                "total": p_total,
                "met": p_met,
                "breached": p_breached,
                "on_track": int(r["on_track_cnt"]),
                "on_time_rate": round(p_met / max(1, p_met + p_breached) * 100, 2),
            })

        return {
            "status": "success",
            "data": {
                "total_orders": total_orders,
                "completed_count": completed_cnt,
                "sla_distribution": sla_dist,
                "sla_labels": SLA_STATUS_LABELS,
                "on_time_rate": on_time_rate,
                "breach_rate": breach_rate,
                "avg_processing_hours": avg_hours,
                "max_processing_hours": _safe_float(duration_row["max_hours"], 2),
                "min_processing_hours": _safe_float(duration_row["min_hours"], 2),
                "by_priority": by_priority,
                # 前端期望的扁平字段
                "active_count": sla_dist.get("on_track", 0) + sla_dist.get("soon", 0),
                "overdue_count": sla_dist.get("breached", 0),
                "avg_handle_hours": avg_hours,
                "sla_rules": {
                    p: {"name": cfg["name"],
                        "response_hours": cfg["response_hours"],
                        "completion_hours": cfg["completion_hours"]}
                    for p, cfg in SLA_RULES.items()
                },
            },
        }
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "SLA统计查询")


@router.get("/api/workorders/pro/parts")
@run_in_thread
def list_parts(
    category: Optional[str] = Query(None, description="按备件分类过滤"),
    keyword: Optional[str] = Query(None, description="按备件名称/编号模糊查询"),
    low_stock_only: bool = Query(False, description="仅返回库存低于安全阈值的备件"),
):
    """备件库存查询"""
    try:
        _init_tables()
        where = "WHERE 1=1"
        params: list = []
        if category:
            where += " AND category = ?"
            params.append(category)
        if keyword:
            where += " AND (part_name LIKE ? OR part_id LIKE ?)"
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        if low_stock_only:
            where += " AND stock_qty <= min_stock"

        with get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM sys_parts_inventory {where}
                ORDER BY category, part_name
                """,
                params,
            ).fetchall()
            total_value_row = conn.execute(
                f"SELECT SUM(stock_qty * unit_price) AS total_value FROM sys_parts_inventory {where}",
                params,
            ).fetchone()

        items = []
        for r in rows:
            d = _row_to_dict(r)
            d["total_value"] = round((d["stock_qty"] or 0) * (d["unit_price"] or 0), 2)
            d["is_low_stock"] = (d["stock_qty"] or 0) <= (d["min_stock"] or 0)
            items.append(d)

        # 分类汇总
        cat_summary: dict = {}
        for it in items:
            cat = it["category"]
            if cat not in cat_summary:
                cat_summary[cat] = {"category": cat, "count": 0, "stock_qty": 0, "total_value": 0.0}
            cat_summary[cat]["count"] += 1
            cat_summary[cat]["stock_qty"] += it["stock_qty"]
            cat_summary[cat]["total_value"] += it["total_value"]

        return {
            "status": "success",
            "data": items,
            "total": len(items),
            "low_stock_count": sum(1 for it in items if it["is_low_stock"]),
            "total_inventory_value": round(_safe_float(total_value_row["total_value"], 2) or 0, 2),
            "category_summary": [
                {**v, "total_value": round(v["total_value"], 2)}
                for v in cat_summary.values()
            ],
        }
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "备件库存查询")


@router.get("/api/workorders/pro/{order_id}")
@run_in_thread
def get_workorder_detail(order_id: str):
    """工单详情（含处理时间线、备件清单）"""
    try:
        _init_tables()
        with get_conn() as conn:
            # 工单基本信息 + 扩展信息
            row = conn.execute(
                """
                SELECT w.*, d.device_name, d.device_type, d.building_id, d.rated_power,
                       b.building_name,
                       e.priority, e.assignee, e.assignee_skill, e.sla_due_at,
                       e.sla_status, e.created_by, e.created_at AS ext_created_at,
                       e.updated_at AS ext_updated_at
                FROM fact_work_orders w
                LEFT JOIN dim_devices d ON d.device_id = w.device_id
                LEFT JOIN dim_buildings b ON b.building_id = d.building_id
                LEFT JOIN sys_workorder_ext e ON e.order_id = w.order_id
                WHERE w.order_id = ?
                """,
                [order_id],
            ).fetchone()

            if row is None:
                raise HTTPException(status_code=404, detail=f"工单不存在: {order_id}")

            # 确保 ext 记录存在
            if row["priority"] is None:
                _ensure_ext_record(conn, order_id, row["created_at"])
                conn.commit()
                _refresh_sla_status_for_orders(conn, [order_id])
                conn.commit()
                row = conn.execute(
                    """
                    SELECT w.*, d.device_name, d.device_type, d.building_id, d.rated_power,
                           b.building_name,
                           e.priority, e.assignee, e.assignee_skill, e.sla_due_at,
                           e.sla_status, e.created_by, e.created_at AS ext_created_at,
                           e.updated_at AS ext_updated_at
                    FROM fact_work_orders w
                    LEFT JOIN dim_devices d ON d.device_id = w.device_id
                    LEFT JOIN dim_buildings b ON b.building_id = d.building_id
                    LEFT JOIN sys_workorder_ext e ON e.order_id = w.order_id
                    WHERE w.order_id = ?
                    """,
                    [order_id],
                ).fetchone()

        d = _row_to_dict(row)
        d["priority_label"] = PRIORITY_LABELS.get(d.get("priority"), d.get("priority") or "")
        d["sla_status_label"] = SLA_STATUS_LABELS.get(d.get("sla_status"), d.get("sla_status") or "")

        # 构造处理时间线
        timeline = _build_timeline(d)

        # 计算处理时长
        processing_hours = None
        if d.get("completed_at") and d.get("created_at"):
            created = _parse_dt(d["created_at"])
            completed = _parse_dt(d["completed_at"])
            if created and completed:
                processing_hours = round((completed - created).total_seconds() / 3600, 2)
        d["processing_hours"] = processing_hours

        # SLA 剩余时长
        if d.get("sla_due_at") and d.get("status") not in ("COMPLETED", "VERIFIED", "REJECTED"):
            due = _parse_dt(d["sla_due_at"])
            if due:
                delta = due - datetime.datetime.now()
                d["sla_remaining_hours"] = round(delta.total_seconds() / 3600, 1)
            else:
                d["sla_remaining_hours"] = None
        else:
            d["sla_remaining_hours"] = None

        # 推荐备件清单（基于设备类型）
        recommended_parts = _recommend_parts(d.get("device_type"))

        return {
            "status": "success",
            "data": {
                "workorder": d,
                "timeline": timeline,
                "recommended_parts": recommended_parts,
                "sla_rules": {
                    p: {"name": cfg["name"],
                        "response_hours": cfg["response_hours"],
                        "completion_hours": cfg["completion_hours"]}
                    for p, cfg in SLA_RULES.items()
                },
            },
        }
    except HTTPException:
        raise
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "工单详情查询")


def _build_timeline(d: dict) -> list:
    """构造工单处理时间线"""
    timeline = []
    if d.get("created_at"):
        timeline.append({
            "time": d["created_at"],
            "event": "工单创建",
            "detail": d.get("diagnosis_title") or "",
            "status": "PENDING",
        })
    if d.get("ext_created_at") and d.get("created_by"):
        timeline.append({
            "time": d["ext_created_at"],
            "event": "纳入增强管理",
            "detail": f"优先级 {d.get('priority_label') or d.get('priority')}，派单人 {d.get('created_by')}",
            "status": "PENDING",
        })
    if d.get("assignee"):
        timeline.append({
            "time": d.get("ext_updated_at") or d.get("created_at"),
            "event": "派单分配",
            "detail": f"负责人 {d.get('assignee')}（{d.get('assignee_skill') or '—'}）",
            "status": "IN_PROGRESS",
        })
    if d.get("maintenance_action"):
        timeline.append({
            "time": d.get("completed_at") or d.get("ext_updated_at") or d.get("created_at"),
            "event": "维护处置",
            "detail": d.get("maintenance_action"),
            "status": "IN_PROGRESS",
        })
    if d.get("completed_at"):
        timeline.append({
            "time": d["completed_at"],
            "event": "工单完成",
            "detail": f"维修成本 {d.get('repair_cost') or 0} 元",
            "status": "COMPLETED",
        })
    if d.get("user_feedback"):
        timeline.append({
            "time": d.get("completed_at") or d.get("ext_updated_at") or "",
            "event": "用户反馈",
            "detail": d.get("user_feedback"),
            "status": "VERIFIED",
        })
    return timeline


def _recommend_parts(device_type: Optional[str]) -> list:
    """基于设备类型推荐备件"""
    if not device_type:
        return []
    # 设备类型 → 推荐备件分类
    type_to_category = {
        "HVAC": ["压缩机", "滤芯", "传感器", "阀门", "制冷剂"],
        "PRECISION_AC": ["压缩机", "滤芯", "电气件", "制冷剂"],
        "REFRIGERATION": ["压缩机", "制冷剂", "密封件", "电气件"],
        "WATER_HEATER": ["压缩机", "密封件", "电气件"],
        "PUMP": ["轴承", "密封件", "叶轮", "电气件"],
        "LIGHTING": ["电气件"],
        "SOCKET": ["电气件"],
        "VENTILATION": ["传动件", "轴承", "叶轮"],
        "EV_CHARGER": ["电气件", "控制件"],
    }
    categories = type_to_category.get(device_type, [])
    if not categories:
        return []
    try:
        with get_conn() as conn:
            placeholders = ",".join(["?"] * len(categories))
            rows = conn.execute(
                f"""
                SELECT part_id, part_name, category, stock_qty, unit_price, min_stock, location
                FROM sys_parts_inventory
                WHERE category IN ({placeholders})
                ORDER BY category, part_name
                """,
                categories,
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    except Exception:
        return []


@router.post("/api/workorders/pro/dispatch")
@run_in_thread
def smart_dispatch(payload: DispatchRequest):
    """智能派单（根据设备类型、技能匹配推荐人员）"""
    try:
        _init_tables()
        if payload.priority and payload.priority not in VALID_PRIORITIES:
            raise HTTPException(status_code=400, detail=f"priority 非法，合法值: {sorted(VALID_PRIORITIES)}")

        with get_conn() as conn:
            # 1. 查工单
            wo = conn.execute(
                "SELECT * FROM fact_work_orders WHERE order_id = ?",
                [payload.order_id],
            ).fetchone()
            if wo is None:
                raise HTTPException(status_code=404, detail=f"工单不存在: {payload.order_id}")

            # 2. 查设备信息
            device = conn.execute(
                "SELECT device_id, device_name, device_type, building_id FROM dim_devices WHERE device_id = ?",
                [wo["device_id"]],
            ).fetchone()

            # 3. 确保 ext 记录
            _ensure_ext_record(conn, payload.order_id, wo["created_at"], DEFAULT_PRIORITY, payload.created_by)
            conn.commit()

            # 4. 确定优先级（payload > 现有 > 默认）
            ext_row = conn.execute(
                "SELECT * FROM sys_workorder_ext WHERE order_id = ?",
                [payload.order_id],
            ).fetchone()
            current_priority = ext_row["priority"]
            new_priority = payload.priority or current_priority or DEFAULT_PRIORITY

            # 5. 重新计算 SLA 截止时间
            sla_due = _calc_sla_due_at(wo["created_at"], new_priority)

            # 6. 确定负责人
            device_type = device["device_type"] if device else None
            required_skill = DEVICE_TYPE_SKILL.get(device_type or "", "暖通工程师")

            candidates = []
            chosen_engineer = None
            if payload.assignee:
                # 指定负责人
                for eng in _ENGINEERS:
                    if eng["name"] == payload.assignee or eng["id"] == payload.assignee:
                        chosen_engineer = eng
                        break
                if chosen_engineer is None:
                    chosen_engineer = {
                        "id": payload.assignee,
                        "name": payload.assignee,
                        "skills": [required_skill],
                        "active_orders": 0,
                    }
            else:
                # 自动推荐：技能匹配 + 负载最低
                candidates = [eng for eng in _ENGINEERS if required_skill in eng["skills"]]
                if not candidates:
                    # 无匹配技能者，退化为全部工程师
                    candidates = list(_ENGINEERS)
                candidates.sort(key=lambda x: (x["active_orders"], x["id"]))
                chosen_engineer = candidates[0]

            # 7. 更新 ext 记录
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                """
                UPDATE sys_workorder_ext
                SET priority = ?, assignee = ?, assignee_skill = ?,
                    sla_due_at = ?, created_by = ?, updated_at = ?
                WHERE order_id = ?
                """,
                [
                    new_priority,
                    chosen_engineer["name"],
                    required_skill,
                    sla_due,
                    payload.created_by,
                    now_str,
                    payload.order_id,
                ],
            )
            conn.commit()

            # 8. 刷新 SLA 状态
            _refresh_sla_status_for_orders(conn, [payload.order_id])
            conn.commit()

            # 9. 更新工程师负载计数（内存）
            # 先减去原负责人计数
            old_assignee = ext_row["assignee"]
            if old_assignee:
                for eng in _ENGINEERS:
                    if eng["name"] == old_assignee and eng["active_orders"] > 0:
                        eng["active_orders"] -= 1
                        break
            # 新负责人计数 +1（仅当工单未完成）
            if wo["status"] not in ("COMPLETED", "VERIFIED", "REJECTED"):
                for eng in _ENGINEERS:
                    if eng["name"] == chosen_engineer["name"]:
                        eng["active_orders"] += 1
                        chosen_engineer = eng  # 用真实引用
                        break

            # 10. 回读
            updated = conn.execute(
                """
                SELECT w.order_id, w.device_id, w.diagnosis_title, w.status,
                       w.created_at, w.completed_at,
                       d.device_name, d.device_type, b.building_name,
                       e.priority, e.assignee, e.assignee_skill, e.sla_due_at,
                       e.sla_status, e.created_by
                FROM fact_work_orders w
                LEFT JOIN dim_devices d ON d.device_id = w.device_id
                LEFT JOIN dim_buildings b ON b.building_id = d.building_id
                JOIN sys_workorder_ext e ON e.order_id = w.order_id
                WHERE w.order_id = ?
                """,
                [payload.order_id],
            ).fetchone()

        d = _row_to_dict(updated)
        d["priority_label"] = PRIORITY_LABELS.get(d.get("priority"), "")
        d["sla_status_label"] = SLA_STATUS_LABELS.get(d.get("sla_status"), "")

        return {
            "status": "success",
            "message": (
                f"工单 {payload.order_id} 已派单给 {chosen_engineer['name']}"
                f"（{required_skill}），优先级 {new_priority}"
            ),
            "data": {
                "workorder": d,
                "dispatch": {
                    "device_type": device_type,
                    "required_skill": required_skill,
                    "chosen_engineer": {
                        "id": chosen_engineer.get("id"),
                        "name": chosen_engineer["name"],
                        "active_orders": chosen_engineer.get("active_orders", 0),
                    },
                    "candidate_count": len(candidates) if candidates else 1,
                    "sla_due_at": sla_due,
                    "priority": new_priority,
                },
            },
        }
    except HTTPException:
        raise
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "智能派单")
