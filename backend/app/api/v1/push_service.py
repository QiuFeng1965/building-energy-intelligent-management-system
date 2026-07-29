# -*- coding: utf-8 -*-
"""
告警推送后端服务路由（为移动端 PWA 提供 Web Push 订阅与通知）
- POST /api/push/subscribe         ：订阅推送（存储订阅信息）
- GET  /api/push/subscriptions     ：查询当前订阅列表
- POST /api/push/unsubscribe       ：取消订阅
- POST /api/push/send              ：发送推送通知（Web Push 协议模拟）
- GET  /api/push/notifications     ：查询历史通知记录（支持分页）
- GET  /api/push/vapid_public_key  ：获取 VAPID 公钥（用于前端订阅）

表结构：
- sys_push_subscriptions(id, endpoint, keys_p256dh, keys_auth, user_agent, created_at, is_active)
- sys_push_notifications(id, subscription_id, title, body, data, sent_at, status)

说明：
- VAPID 密钥对：使用固定演示值（生产环境应从环境变量加载）
- 发送推送：模拟 Web Push 协议（实际不发送，但记录状态为 sent）
- 订阅信息与通知记录均从数据库读取（真实数据）
"""
import math
import json
import logging
import datetime
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.database import get_conn, run_in_thread, DBUnavailableError
from app.core.route_error import handle_route_error

logger = logging.getLogger(__name__)
router = APIRouter()

# ===== VAPID 密钥对（固定演示值，生产环境应从环境变量加载）=====
# 这是一个有效的 base64url 编码的 P-256 公钥示例（演示用）
VAPID_PUBLIC_KEY = "BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U"
VAPID_SUBJECT = "mailto:admin@building-energy.com"

# 表初始化标记
_table_initialized = False


# ===== 请求模型 =====
class PushSubscribeRequest(BaseModel):
    """订阅推送请求（对齐 Web Push API 的 PushSubscription 结构）"""
    endpoint: str = Field(..., description="推送服务端点 URL")
    keys: dict = Field(..., description="加密密钥，含 p256dh 与 auth")
    user_agent: Optional[str] = Field(None, description="客户端 User-Agent")


class PushUnsubscribeRequest(BaseModel):
    """取消订阅请求"""
    endpoint: Optional[str] = Field(None, description="按端点 URL 取消")
    subscription_id: Optional[int] = Field(None, description="按订阅 ID 取消")


class PushSendRequest(BaseModel):
    """发送推送通知请求"""
    title: str = Field(..., description="通知标题")
    body: str = Field(..., description="通知正文")
    data: Optional[dict] = Field(None, description="附加数据（JSON 对象）")
    subscription_id: Optional[int] = Field(
        None, description="指定订阅 ID 发送；为空则向所有活跃订阅群发"
    )


# ===== 表初始化 =====
def _init_table():
    """惰性创建 sys_push_subscriptions / sys_push_notifications 表（仅执行一次）"""
    global _table_initialized
    if _table_initialized:
        return
    try:
        with get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sys_push_subscriptions (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    endpoint        TEXT NOT NULL,
                    keys_p256dh     TEXT,
                    keys_auth       TEXT,
                    user_agent      TEXT,
                    created_at      DATETIME NOT NULL,
                    is_active       INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sys_push_notifications (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    subscription_id INTEGER,
                    title           VARCHAR(255) NOT NULL,
                    body            TEXT,
                    data            TEXT,
                    sent_at         DATETIME NOT NULL,
                    status          VARCHAR(20) NOT NULL DEFAULT 'sent',
                    FOREIGN KEY (subscription_id) REFERENCES sys_push_subscriptions(id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_push_subs_active ON sys_push_subscriptions(is_active)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_push_subs_endpoint ON sys_push_subscriptions(endpoint)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_push_notif_sent ON sys_push_notifications(sent_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_push_notif_sub ON sys_push_notifications(subscription_id)"
            )
            conn.commit()
        _table_initialized = True
        logger.info("sys_push_subscriptions / sys_push_notifications 表已就绪")
    except Exception as e:
        logger.exception(f"初始化推送表失败: {e}")


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


def _sub_row_to_dict(row) -> dict:
    """订阅行转 dict（is_active 转 bool）"""
    d = _row_to_dict(row)
    if d is not None:
        d["is_active"] = bool(d.get("is_active"))
    return d


def _notif_row_to_dict(row) -> dict:
    """通知行转 dict（data JSON 反序列化）"""
    d = _row_to_dict(row)
    if d is not None:
        try:
            d["data"] = json.loads(d["data"]) if d.get("data") else None
        except (json.JSONDecodeError, TypeError):
            pass
    return d


def _simulate_web_push(endpoint: str, keys_p256dh: str, keys_auth: str,
                       title: str, body: str, data: Optional[dict]) -> dict:
    """
    模拟 Web Push 协议发送
    - 实际生产需使用 pywebpush 库，对 payload 用 AES128GCM 加密后 POST 到 endpoint
    - 此处仅模拟发送，返回成功状态
    """
    # 模拟：生产环境应调用 pywebpush.webpush(...)
    payload_size = len(body.encode("utf-8")) if body else 0
    logger.info(
        f"[模拟 Web Push] endpoint={endpoint[:60]}... title={title} payload_size={payload_size}"
    )
    return {
        "ok": True,
        "simulated": True,
        "endpoint": endpoint,
        "payload_bytes": payload_size,
        "message": "模拟发送成功（生产环境将调用 Web Push API）",
    }


# ===== 路由 =====
@router.get("/api/push/vapid_public_key")
@run_in_thread
def vapid_public_key():
    """获取 VAPID 公钥（前端订阅时需用此公钥）"""
    try:
        return {
            "status": "success",
            "data": {
                "public_key": VAPID_PUBLIC_KEY,
                "subject": VAPID_SUBJECT,
                "note": "前端使用此公钥调用 pushManager.subscribe 订阅推送",
            },
        }
    except Exception as e:
        return handle_route_error(e, logger, "VAPID公钥查询")


@router.post("/api/push/subscribe")
@run_in_thread
def push_subscribe(payload: PushSubscribeRequest):
    """订阅推送（存储订阅信息）"""
    try:
        _init_table()
        # 解析 keys
        keys = payload.keys or {}
        keys_p256dh = keys.get("p256dh") or keys.get("keys_p256dh")
        keys_auth = keys.get("auth") or keys.get("keys_auth")
        if not keys_p256dh or not keys_auth:
            raise HTTPException(status_code=400, detail="keys 中必须包含 p256dh 与 auth")

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with get_conn() as conn:
            # 同一 endpoint 已存在则重新激活（避免重复）
            existing = conn.execute(
                "SELECT id FROM sys_push_subscriptions WHERE endpoint = ?",
                [payload.endpoint],
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE sys_push_subscriptions
                    SET keys_p256dh = ?, keys_auth = ?, user_agent = ?, is_active = 1
                    WHERE id = ?
                    """,
                    [keys_p256dh, keys_auth, payload.user_agent, existing["id"]],
                )
                conn.commit()
                sub_id = int(existing["id"])
                row = conn.execute(
                    "SELECT * FROM sys_push_subscriptions WHERE id = ?", [sub_id]
                ).fetchone()
            else:
                cur = conn.execute(
                    """
                    INSERT INTO sys_push_subscriptions
                        (endpoint, keys_p256dh, keys_auth, user_agent, created_at, is_active)
                    VALUES (?, ?, ?, ?, ?, 1)
                    """,
                    [payload.endpoint, keys_p256dh, keys_auth, payload.user_agent, now_str],
                )
                conn.commit()
                sub_id = int(cur.lastrowid)
                row = conn.execute(
                    "SELECT * FROM sys_push_subscriptions WHERE id = ?", [sub_id]
                ).fetchone()

        return {
            "status": "success",
            "message": "订阅成功",
            "data": _sub_row_to_dict(row),
        }
    except HTTPException:
        raise
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "推送订阅创建")


@router.get("/api/push/subscriptions")
@run_in_thread
def push_subscriptions(
    active_only: bool = Query(True, description="仅返回活跃订阅"),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=200, description="每页条数"),
):
    """查询当前订阅列表"""
    try:
        _init_table()
        where = "WHERE 1=1"
        params: list = []
        if active_only:
            where += " AND is_active = 1"

        offset = (page - 1) * page_size
        with get_conn() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) FROM sys_push_subscriptions {where}", params
            ).fetchone()[0]
            rows = conn.execute(
                f"""
                SELECT * FROM sys_push_subscriptions
                {where}
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                params + [page_size, offset],
            ).fetchall()

        items = [_sub_row_to_dict(r) for r in rows]
        active_count = sum(1 for it in items if it.get("is_active"))

        return {
            "status": "success",
            "data": items,
            "total": int(total),
            "active_count": active_count,
            "page": page,
            "page_size": page_size,
        }
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "推送订阅列表查询")


@router.post("/api/push/unsubscribe")
@run_in_thread
def push_unsubscribe(payload: PushUnsubscribeRequest):
    """取消订阅（按 endpoint 或 subscription_id）"""
    try:
        _init_table()
        if payload.subscription_id is None and not payload.endpoint:
            raise HTTPException(status_code=400, detail="需提供 endpoint 或 subscription_id")

        with get_conn() as conn:
            if payload.subscription_id is not None:
                row = conn.execute(
                    "SELECT * FROM sys_push_subscriptions WHERE id = ?",
                    [payload.subscription_id],
                ).fetchone()
                if row is None:
                    raise HTTPException(status_code=404, detail=f"订阅不存在: id={payload.subscription_id}")
                conn.execute(
                    "UPDATE sys_push_subscriptions SET is_active = 0 WHERE id = ?",
                    [payload.subscription_id],
                )
                affected_id = int(row["id"])
            else:
                row = conn.execute(
                    "SELECT * FROM sys_push_subscriptions WHERE endpoint = ?",
                    [payload.endpoint],
                ).fetchone()
                if row is None:
                    raise HTTPException(status_code=404, detail=f"订阅不存在: endpoint={payload.endpoint}")
                conn.execute(
                    "UPDATE sys_push_subscriptions SET is_active = 0 WHERE endpoint = ?",
                    [payload.endpoint],
                )
                affected_id = int(row["id"])
            conn.commit()
            updated = conn.execute(
                "SELECT * FROM sys_push_subscriptions WHERE id = ?", [affected_id]
            ).fetchone()

        return {
            "status": "success",
            "message": "已取消订阅",
            "data": _sub_row_to_dict(updated),
        }
    except HTTPException:
        raise
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "推送订阅取消")


@router.post("/api/push/send")
@run_in_thread
def push_send(payload: PushSendRequest):
    """发送推送通知（Web Push 协议模拟）"""
    try:
        _init_table()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data_json = json.dumps(payload.data, ensure_ascii=False) if payload.data is not None else None

        with get_conn() as conn:
            # 取目标订阅
            if payload.subscription_id is not None:
                subs = conn.execute(
                    "SELECT * FROM sys_push_subscriptions WHERE id = ? AND is_active = 1",
                    [payload.subscription_id],
                ).fetchall()
                if not subs:
                    raise HTTPException(
                        status_code=404,
                        detail=f"未找到活跃订阅: id={payload.subscription_id}"
                    )
            else:
                subs = conn.execute(
                    "SELECT * FROM sys_push_subscriptions WHERE is_active = 1"
                ).fetchall()
                if not subs:
                    raise HTTPException(status_code=404, detail="当前无活跃订阅，无法发送")

            # 逐条模拟发送并落库通知记录
            sent_count = 0
            fail_count = 0
            notif_ids: list = []
            for sub in subs:
                result = _simulate_web_push(
                    endpoint=sub["endpoint"],
                    keys_p256dh=sub["keys_p256dh"] or "",
                    keys_auth=sub["keys_auth"] or "",
                    title=payload.title,
                    body=payload.body,
                    data=payload.data,
                )
                status = "sent" if result.get("ok") else "failed"
                cur = conn.execute(
                    """
                    INSERT INTO sys_push_notifications
                        (subscription_id, title, body, data, sent_at, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [sub["id"], payload.title, payload.body, data_json, now_str, status],
                )
                notif_ids.append(int(cur.lastrowid))
                if result.get("ok"):
                    sent_count += 1
                else:
                    fail_count += 1
            conn.commit()

        return {
            "status": "success",
            "message": f"推送完成：成功 {sent_count} 条，失败 {fail_count} 条",
            "data": {
                "title": payload.title,
                "body": payload.body,
                "data": payload.data,
                "sent_at": now_str,
                "target_count": len(subs),
                "sent_count": sent_count,
                "fail_count": fail_count,
                "notification_ids": notif_ids,
                "simulated": True,
            },
        }
    except HTTPException:
        raise
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "推送任务发送")


@router.get("/api/push/notifications")
@run_in_thread
def push_notifications(
    subscription_id: Optional[int] = Query(None, description="按订阅 ID 过滤"),
    status: Optional[str] = Query(None, description="按状态过滤：sent/failed"),
    limit: int = Query(50, ge=1, le=500, description="每页条数（分页大小）"),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
):
    """查询历史通知记录（支持分页）"""
    try:
        _init_table()
        where = "WHERE 1=1"
        params: list = []
        if subscription_id is not None:
            where += " AND subscription_id = ?"
            params.append(subscription_id)
        if status:
            where += " AND status = ?"
            params.append(status)

        offset = (page - 1) * limit
        with get_conn() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) FROM sys_push_notifications {where}", params
            ).fetchone()[0]
            rows = conn.execute(
                f"""
                SELECT n.*, s.endpoint AS subscription_endpoint
                FROM sys_push_notifications n
                LEFT JOIN sys_push_subscriptions s ON s.id = n.subscription_id
                {where}
                ORDER BY n.sent_at DESC, n.id DESC
                LIMIT ? OFFSET ?
                """,
                params + [limit, offset],
            ).fetchall()

        items = []
        for r in rows:
            d = _notif_row_to_dict(r)
            d["subscription_endpoint"] = r["subscription_endpoint"]
            items.append(d)

        return {
            "status": "success",
            "data": items,
            "total": int(total),
            "limit": limit,
            "page": page,
        }
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "推送记录查询")
