# -*- coding: utf-8 -*-
"""
设备工单路由
- GET    /api/workorders              ：查询工单列表（支持 status/device_id 分页查询）
- GET    /api/workorders/{order_id}   ：查询单个工单详情
- PUT    /api/workorders/{order_id}/status：更新工单状态（状态流转）
- POST   /api/workorders              ：创建新工单（手动报修）

工单状态机：
    PENDING → IN_PROGRESS → COMPLETED → VERIFIED
    PENDING → REJECTED（可拒绝）
    IN_PROGRESS → PENDING（可退回）
    不允许跳跃流转（如 PENDING 直接到 COMPLETED）

每次状态流转调用 write_audit_log 记录审计日志。
所有接口需管理员权限（require_admin）+ 限流 30/minute。
"""
import logging
import datetime
import uuid
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.database import get_conn, DBUnavailableError
from app.core.rate_limit import limiter
from app.core.route_error import handle_route_error
from app.core.security import require_admin
from app.core.idempotency import idempotent
from app.api.v1.admin import write_audit_log

logger = logging.getLogger(__name__)
router = APIRouter()

# ===== 状态机定义 =====
# 允许的状态集合 + 合法流转
VALID_STATUSES = {"PENDING", "IN_PROGRESS", "COMPLETED", "VERIFIED", "REJECTED"}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "PENDING": {"IN_PROGRESS", "REJECTED"},
    "IN_PROGRESS": {"COMPLETED", "PENDING"},  # 可流转到已完成，也可退回到待处理
    "COMPLETED": {"VERIFIED"},
    "VERIFIED": set(),   # 终态
    "REJECTED": set(),   # 终态
}

# 状态中文标签（用于审计日志可读性）
STATUS_LABELS = {
    "PENDING": "待处理",
    "IN_PROGRESS": "处理中",
    "COMPLETED": "已完成",
    "VERIFIED": "已验证",
    "REJECTED": "已拒绝",
}


# ===== 请求模型 =====
class WorkOrderCreate(BaseModel):
    """手动报修创建工单"""
    device_id: str = Field(..., description="设备ID")
    diagnosis_title: str = Field(..., description="故障/诊断标题")
    rag_advice: str = Field("", description="RAG 建议（可选）")
    maintenance_action: str = Field("", description="维护动作（可选）")
    repair_cost: float = Field(0.0, ge=0, description="维修成本（可选）")
    user_feedback: str = Field("", description="用户备注（可选）")


class WorkOrderStatusUpdate(BaseModel):
    """工单状态流转"""
    new_status: str = Field(..., description="目标状态：PENDING/IN_PROGRESS/COMPLETED/VERIFIED/REJECTED")
    maintenance_action: str = Field("", description="维护动作记录（可选，流转时补充）")
    user_feedback: str = Field("", description="用户反馈/备注（可选）")
    repair_cost: float | None = Field(None, ge=0, description="维修成本（可选，流转时更新）")


# ===== 工具函数 =====
def _row_to_dict(row) -> dict:
    """sqlite3.Row → dict"""
    return {k: row[k] for k in row.keys()} if row is not None else None


def _gen_order_id() -> str:
    """生成工单号：WO-YYYYMMDDHHMMSS-8位短UUID，全局唯一"""
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    short_uuid = uuid.uuid4().hex[:8]
    return f"WO-{ts}-{short_uuid}"


def _validate_transition(current: str, target: str) -> None:
    """校验状态流转是否合法，非法则抛 400"""
    if current not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"工单当前状态非法: {current}",
        )
    if target not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"目标状态非法: {target}，合法值: {sorted(VALID_STATUSES)}",
        )
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(
            status_code=400,
            detail=(
                f"不允许的状态流转: {current} → {target}。"
                f"当前状态 {current} 仅可流转到 {sorted(allowed) or ['（终态，不可流转）']}"
            ),
        )


# ===== 路由 =====
@router.get("/api/workorders")
@limiter.limit("30/minute")
async def list_workorders(
    request: Request,
    user: str = Depends(require_admin),
    status: str | None = Query(None, description="按状态过滤：PENDING/IN_PROGRESS/COMPLETED/VERIFIED/REJECTED"),
    device_id: str | None = Query(None, description="按设备ID过滤"),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=200, description="每页条数，最大 200"),
):
    """查询工单列表（支持 status/device_id 分页查询）"""
    try:
        # 计算分页偏移
        offset = (page - 1) * page_size

        with get_conn() as conn:
            # 构造 WHERE
            where = "WHERE 1=1"
            params: list = []
            if status:
                where += " AND status = ?"
                params.append(status)
            if device_id:
                where += " AND device_id = ?"
                params.append(device_id)

            # 总数
            total = conn.execute(
                f"SELECT COUNT(*) FROM fact_work_orders {where}", params
            ).fetchone()[0]

            # 分页查询（按创建时间倒序）
            rows = conn.execute(
                f"SELECT * FROM fact_work_orders {where} "
                f"ORDER BY created_at DESC, order_id DESC LIMIT ? OFFSET ?",
                params + [page_size, offset],
            ).fetchall()

        items = [_row_to_dict(r) for r in rows]
        return {
            "status": "success",
            "data": items,
            "total": int(total),
            "page": page,
            "page_size": page_size,
        }
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "查询工单列表")


@router.get("/api/workorders/{order_id}")
@limiter.limit("30/minute")
async def get_workorder(
    request: Request,
    order_id: str,
    user: str = Depends(require_admin),
):
    """查询单个工单详情"""
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM fact_work_orders WHERE order_id = ?",
                [order_id],
            ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail=f"工单不存在: {order_id}")

        return {"status": "success", "data": _row_to_dict(row)}
    except HTTPException:
        raise
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "查询工单详情")


@router.post("/api/workorders")
@limiter.limit("30/minute")
@idempotent(key_header="X-Idempotency-Key", ttl=300)
async def create_workorder(
    request: Request,
    payload: WorkOrderCreate,
    user: str = Depends(require_admin),
):
    """创建新工单（手动报修），初始状态为 PENDING"""
    try:
        order_id = _gen_order_id()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        def _do_create(payload, order_id, now):
            """同步 DB 操作：插入工单并回读（在线程池中执行避免阻塞事件循环）"""
            with get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO fact_work_orders
                        (order_id, device_id, anomaly_time, diagnosis_title, rag_advice,
                         maintenance_action, repair_cost, status, created_at, completed_at,
                         user_feedback)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
                    """,
                    (
                        order_id,
                        payload.device_id,
                        now,  # anomaly_time 取当前时间
                        payload.diagnosis_title,
                        payload.rag_advice,
                        payload.maintenance_action,
                        payload.repair_cost,
                        "PENDING",  # 初始状态
                        now,  # created_at
                        payload.user_feedback,
                    ),
                )
                conn.commit()

                # 回读新工单
                row = conn.execute(
                    "SELECT * FROM fact_work_orders WHERE order_id = ?",
                    [order_id],
                ).fetchone()
            return row

        # DB 操作下沉到线程池
        row = await asyncio.to_thread(_do_create, payload, order_id, now)

        # 审计日志
        write_audit_log(
            user=user,
            action="工单创建",
            detail=f"工单号: {order_id}, 设备: {payload.device_id}, 标题: {payload.diagnosis_title}",
            risk_level="low",
        )

        return {
            "status": "success",
            "message": "工单创建成功",
            "data": _row_to_dict(row),
        }
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "创建工单")


@router.put("/api/workorders/{order_id}/status")
@limiter.limit("30/minute")
async def update_workorder_status(
    request: Request,
    order_id: str,
    payload: WorkOrderStatusUpdate,
    user: str = Depends(require_admin),
):
    """更新工单状态（状态流转，校验合法性 + CAS 乐观锁 + 审计日志）"""
    try:
        new_status = payload.new_status.strip().upper()

        def _do_update(order_id, new_status, payload):
            """同步 DB 操作：CAS 乐观锁更新工单状态（在线程池中执行避免阻塞事件循环）"""
            with get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM fact_work_orders WHERE order_id = ?",
                    [order_id],
                ).fetchone()

                if row is None:
                    raise HTTPException(status_code=404, detail=f"工单不存在: {order_id}")

                current_status = row["status"]
                # 校验流转合法性（非法抛 400）
                _validate_transition(current_status, new_status)

                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # 动态构造 UPDATE：状态必更新；其他字段仅在传入非空时更新
                updates = ["status = ?"]
                params: list = [new_status]

                if payload.maintenance_action:
                    updates.append("maintenance_action = ?")
                    params.append(payload.maintenance_action)
                if payload.user_feedback:
                    updates.append("user_feedback = ?")
                    params.append(payload.user_feedback)
                if payload.repair_cost is not None:
                    updates.append("repair_cost = ?")
                    params.append(payload.repair_cost)

                # 流转到 COMPLETED 时回填 completed_at（若尚未设置）
                if new_status == "COMPLETED" and not row["completed_at"]:
                    updates.append("completed_at = ?")
                    params.append(now)

                # 退回 PENDING 时清空 completed_at（恢复待处理）
                if new_status == "PENDING" and row["completed_at"]:
                    updates.append("completed_at = NULL")

                # CAS 乐观锁：WHERE 携带原状态，防止并发覆盖
                params.append(order_id)
                params.append(current_status)
                sql = (
                    f"UPDATE fact_work_orders SET {', '.join(updates)} "
                    f"WHERE order_id = ? AND status = ?"
                )
                cursor = conn.execute(sql, params)

                if cursor.rowcount == 0:
                    raise HTTPException(
                        status_code=409,
                        detail="工单状态已被并发修改，请刷新后重试",
                    )
                conn.commit()

                # 回读更新后的工单
                updated = conn.execute(
                    "SELECT * FROM fact_work_orders WHERE order_id = ?",
                    [order_id],
                ).fetchone()
            return updated, current_status

        # DB 操作下沉到线程池
        updated, current_status = await asyncio.to_thread(
            _do_update, order_id, new_status, payload
        )

        # 审计日志（状态流转属于关键操作，标记 risk_level=low；终态 VERIFIED/REJECTED 标 high）
        risk_level = "high" if new_status in ("VERIFIED", "REJECTED") else "low"
        write_audit_log(
            user=user,
            action="工单状态流转",
            detail=(
                f"工单号: {order_id}, "
                f"流转: {current_status}({STATUS_LABELS.get(current_status, current_status)}) "
                f"→ {new_status}({STATUS_LABELS.get(new_status, new_status)})"
            ),
            risk_level=risk_level,
        )

        return {
            "status": "success",
            "message": f"工单状态已从 {current_status} 流转到 {new_status}",
            "data": _row_to_dict(updated),
        }
    except HTTPException:
        raise
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "更新工单状态")
