# -*- coding: utf-8 -*-
"""
智能告警中心 & 多渠道推送路由
- GET    /api/alerts/center             ：告警中心列表（支持 level/status/source 筛选 + 分页）
- GET    /api/alerts/stats              ：告警统计（按级别、来源、状态分布）
- POST   /api/alerts/{alert_id}/acknowledge ：确认告警
- POST   /api/alerts/{alert_id}/silence     ：静默告警（指定时长，单位分钟）
- GET    /api/alerts/channels            ：推送渠道配置（短信/邮件/站内信状态）
- POST   /api/alerts/test_push           ：测试推送（发送测试告警到各渠道）

设计要点：
1. 告警来源聚合：
   - device_anomaly：从 fact_energy_records 查 run_status != 'NORMAL' 的最新记录
   - energy_overload：COP < 2.0 或 elec_consumption > rated_power * 1.2
   - cop_decline：COP 持续下降趋势（近 24h 均值 < 近 7 天均值的 80%）
2. 告警级别：critical（紧急）/ important（重要）/ normal（普通）
3. 告警状态：active / acknowledged / silenced / resolved
4. 告警合并：同设备 5 分钟内同来源告警合并为一条
5. 推送渠道配置存内存；邮件走 SMTP，短信/电话标注"模拟发送"
6. 使用 get_conn() 创建 sys_alerts 表（CREATE TABLE IF NOT EXISTS）
"""
import math
import smtplib
import logging
import datetime
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.database import get_conn, run_in_thread, DBUnavailableError
from app.core.response_cache import cache_response
from app.core.rate_limit import limiter
from app.core.route_error import handle_route_error
from app.core.config import (
    SMTP_SERVER,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    MANAGER_EMAIL,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ===== 推送渠道配置（内存存储，进程级共享）=====
# 短信 / 邮件 / 站内信 三个渠道的启停状态
_CHANNEL_CONFIG: dict = {
    "sms_enabled": True,
    "email_enabled": True,
    "inapp_enabled": True,
}

# ===== 告警级别与状态枚举 =====
VALID_LEVELS = {"critical", "important", "normal"}
VALID_STATUSES = {"active", "acknowledged", "silenced", "resolved"}
VALID_SOURCES = {"device_anomaly", "energy_overload", "cop_decline"}

# 级别中文标签
LEVEL_LABELS = {
    "critical": "紧急",
    "important": "重要",
    "normal": "普通",
}
STATUS_LABELS = {
    "active": "活跃",
    "acknowledged": "已确认",
    "silenced": "已静默",
    "resolved": "已恢复",
}
SOURCE_LABELS = {
    "device_anomaly": "设备异常",
    "energy_overload": "能耗超标",
    "cop_decline": "预测预警",
}

# 告警合并窗口（分钟）
MERGE_WINDOW_MINUTES = 5

# 表初始化标记（保证建表只执行一次）
_table_initialized = False


def _init_table():
    """惰性创建 sys_alerts 表（仅执行一次）"""
    global _table_initialized
    if _table_initialized:
        return
    try:
        with get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sys_alerts (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    level           VARCHAR(20) NOT NULL,
                    source          VARCHAR(40) NOT NULL,
                    device_id       VARCHAR(50),
                    device_name     VARCHAR(100),
                    building_id     VARCHAR(50),
                    title           VARCHAR(255) NOT NULL,
                    message         TEXT,
                    status          VARCHAR(20) NOT NULL DEFAULT 'active',
                    created_at      DATETIME NOT NULL,
                    acknowledged_at DATETIME,
                    silenced_until  DATETIME
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sys_alerts_status ON sys_alerts(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sys_alerts_device_source ON sys_alerts(device_id, source, created_at)"
            )
            conn.commit()
        _table_initialized = True
        logger.info("sys_alerts 表已就绪")
    except Exception as e:
        logger.exception(f"初始化 sys_alerts 表失败: {e}")


def _safe_float(v, ndigits=2):
    """安全转换为 float，处理 NaN/Infinity/None"""
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


# ===== 告警检测：从 fact_energy_records 实时检测并落库 =====
def _detect_and_persist_alerts():
    """
    扫描近 24 小时运行数据，按设备检测告警，合并去重后写入 sys_alerts。
    同时将已恢复设备的历史 active 告警置为 resolved。
    """
    _init_table()
    now = datetime.datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    try:
        with get_conn() as conn:
            # 1. 拉取每台设备最新一条运行记录（用窗口函数取首行）
            latest_df = pd.read_sql(
                """
                SELECT t.device_id, t.device_name, t.building_id, t.param_type,
                       t.monitor_time, t.elec_consumption, t.cop, t.supply_temp,
                       t.return_temp, t.run_status, t.fault_code, t.loading_rate
                FROM (
                    SELECT device_id, device_name, building_id, param_type,
                           monitor_time, elec_consumption, cop, supply_temp,
                           return_temp, run_status, fault_code, loading_rate,
                           ROW_NUMBER() OVER (PARTITION BY device_id ORDER BY monitor_time DESC) AS rn
                    FROM fact_energy_records
                    WHERE monitor_time >= datetime('now', 'localtime', '-24 hours')
                ) t
                WHERE t.rn = 1
                """,
                conn,
            )

            # 2. 拉取设备额定参数（rated_power / nominal_cop）用于阈值判断
            dev_df = pd.read_sql(
                "SELECT device_id, device_name, device_type, rated_power, nominal_cop FROM dim_devices",
                conn,
            )
            dev_map = {r["device_id"]: r for _, r in dev_df.iterrows()}

            # 3. COP 趋势：近 24h 均值 vs 近 7 天均值
            trend_df = pd.read_sql(
                """
                SELECT device_id,
                       AVG(CASE WHEN monitor_time >= datetime('now', 'localtime', '-24 hours') THEN cop END) AS cop_24h,
                       AVG(CASE WHEN monitor_time >= datetime('now', 'localtime', '-7 days') THEN cop END) AS cop_7d
                FROM fact_energy_records
                WHERE cop IS NOT NULL
                  AND monitor_time >= datetime('now', 'localtime', '-7 days')
                GROUP BY device_id
                """,
                conn,
            )
            trend_map = {r["device_id"]: r for _, r in trend_df.iterrows()}

        if latest_df.empty:
            return

        # 4. 逐设备判定告警
        new_alerts: list[dict] = []
        active_device_ids: set = set()  # 当前存在告警的设备
        for _, row in latest_df.iterrows():
            dev_id = str(row["device_id"])
            run_status = str(row["run_status"] or "")
            cop = _safe_float(row.get("cop"), 3)
            elec = _safe_float(row.get("elec_consumption"), 3)
            dev_meta = dev_map.get(dev_id, {})
            rated_power = _safe_float(dev_meta.get("rated_power"), 3) or 0
            nominal_cop = _safe_float(dev_meta.get("nominal_cop"), 3) or 0
            dev_name = str(row.get("device_name") or dev_meta.get("device_name") or dev_id)
            building_id = str(row.get("building_id") or "")

            # —— 来源1：设备异常（run_status != NORMAL）——
            if run_status and run_status != "NORMAL":
                if run_status == "CRITICAL":
                    level = "critical"
                elif run_status == "ABNORMAL":
                    level = "important"
                else:  # WARNING 等
                    level = "normal"
                new_alerts.append({
                    "level": level,
                    "source": "device_anomaly",
                    "device_id": dev_id,
                    "device_name": dev_name,
                    "building_id": building_id,
                    "title": f"{dev_name} 运行状态异常（{run_status}）",
                    "message": (
                        f"设备 {dev_name}（{dev_id}）当前状态为 {run_status}，"
                        f"故障码：{row.get('fault_code') or '无'}，"
                        f"监测时间：{row.get('monitor_time')}。"
                    ),
                })
                active_device_ids.add(dev_id)

            # —— 来源2：能耗超标（COP < 2.0 或 elec > rated_power * 1.2）——
            overload_msgs = []
            if cop is not None and cop < 2.0:
                overload_msgs.append(f"COP={cop} 低于阈值 2.0")
            if rated_power and rated_power > 0 and elec is not None and elec > rated_power * 1.2:
                overload_msgs.append(f"功耗 {elec}kW 超额定功率 {rated_power}kW 的 120%")
            if overload_msgs:
                # COP 严重偏低视为 important，其余 normal
                level = "important" if (cop is not None and cop < 2.0) else "normal"
                new_alerts.append({
                    "level": level,
                    "source": "energy_overload",
                    "device_id": dev_id,
                    "device_name": dev_name,
                    "building_id": building_id,
                    "title": f"{dev_name} 能耗超标",
                    "message": "；".join(overload_msgs) + f"。监测时间：{row.get('monitor_time')}。",
                })
                active_device_ids.add(dev_id)

            # —— 来源3：COP 持续下降趋势 ——
            trend = trend_map.get(dev_id)
            if trend is not None:
                cop_24h = _safe_float(trend.get("cop_24h"), 3)
                cop_7d = _safe_float(trend.get("cop_7d"), 3)
                if (cop_24h is not None and cop_7d is not None and cop_7d > 0
                        and cop_24h < cop_7d * 0.8):
                    decline_pct = round((1 - cop_24h / cop_7d) * 100, 1)
                    new_alerts.append({
                        "level": "important",
                        "source": "cop_decline",
                        "device_id": dev_id,
                        "device_name": dev_name,
                        "building_id": building_id,
                        "title": f"{dev_name} COP 持续下降",
                        "message": (
                            f"近 24h 平均 COP={cop_24h}，较 7 天均值 {cop_7d} 下降 {decline_pct}%，"
                            f"存在性能衰退风险。"
                        ),
                    })
                    active_device_ids.add(dev_id)

        # 5. 写入 sys_alerts（5 分钟去重：同设备同来源）
        with get_conn() as conn:
            merge_cutoff = (now - datetime.timedelta(minutes=MERGE_WINDOW_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
            inserted = 0
            for a in new_alerts:
                # 查询近 5 分钟内是否已有同设备同来源的告警
                exists = conn.execute(
                    """
                    SELECT id FROM sys_alerts
                    WHERE device_id = ? AND source = ? AND created_at >= ?
                    LIMIT 1
                    """,
                    [a["device_id"], a["source"], merge_cutoff],
                ).fetchone()
                if exists:
                    continue
                conn.execute(
                    """
                    INSERT INTO sys_alerts
                        (level, source, device_id, device_name, building_id,
                         title, message, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?)
                    """,
                    (
                        a["level"], a["source"], a["device_id"], a["device_name"],
                        a["building_id"], a["title"], a["message"], now_str,
                    ),
                )
                inserted += 1

            # 6. 自动恢复：active 告警中，设备最新记录已回归 NORMAL 且无超标 → resolved
            if active_device_ids:
                placeholders = ",".join(["?"] * len(active_device_ids))
                conn.execute(
                    f"""
                    UPDATE sys_alerts
                    SET status = 'resolved'
                    WHERE status = 'active'
                      AND device_id NOT IN ({placeholders})
                    """,
                    list(active_device_ids),
                )
            else:
                # 无任何活跃告警设备，全部 active 转 resolved
                conn.execute(
                    "UPDATE sys_alerts SET status = 'resolved' WHERE status = 'active'"
                )
            conn.commit()

            # 7. 静默告警到期自动转回 active
            conn.execute(
                """
                UPDATE sys_alerts
                SET status = 'active', silenced_until = NULL
                WHERE status = 'silenced'
                  AND silenced_until IS NOT NULL
                  AND silenced_until < ?
                """,
                [now_str],
            )
            conn.commit()

            if inserted:
                logger.info(f"告警检测新增 {inserted} 条告警")
    except DBUnavailableError:
        raise
    except Exception as e:
        logger.exception(f"告警检测失败: {e}")


# ===== 推送实现 =====
def _push_email(title: str, message: str) -> dict:
    """邮件推送（复用现有 SMTP 配置）"""
    if not _CHANNEL_CONFIG["email_enabled"]:
        return {"channel": "email", "ok": False, "reason": "渠道未启用"}
    if not (SMTP_USER and SMTP_PASSWORD and MANAGER_EMAIL):
        return {"channel": "email", "ok": False, "reason": "SMTP 未配置"}
    try:
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart()
        msg["From"] = SMTP_USER
        msg["To"] = MANAGER_EMAIL
        msg["Subject"] = f"【告警】{title}"
        msg.attach(MIMEText(message, "plain", "utf-8"))
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, MANAGER_EMAIL, msg.as_string())
        return {"channel": "email", "ok": True, "to": MANAGER_EMAIL}
    except Exception as e:
        logger.exception(f"邮件告警发送失败: {e}")
        return {"channel": "email", "ok": False, "reason": "邮件发送失败，请稍后重试"}


def _push_sms(message: str) -> dict:
    """短信推送（模拟发送）"""
    if not _CHANNEL_CONFIG["sms_enabled"]:
        return {"channel": "sms", "ok": False, "reason": "渠道未启用"}
    # 模拟发送：实际生产对接阿里云/腾讯云短信服务
    logger.info(f"[模拟短信推送] {message[:80]}")
    return {"channel": "sms", "ok": True, "simulated": True, "reason": "模拟发送成功"}


def _push_inapp(title: str, message: str) -> dict:
    """站内信推送（内存暂存，最近 100 条）"""
    if not _CHANNEL_CONFIG["inapp_enabled"]:
        return {"channel": "inapp", "ok": False, "reason": "渠道未启用"}
    # 内存暂存（轻量实现；生产环境落库）
    _inapp_box = _push_inapp.__dict__.setdefault("_box", [])
    _inapp_box.append({
        "title": title,
        "message": message,
        "sent_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "read": False,
    })
    # 仅保留最近 100 条
    if len(_inapp_box) > 100:
        del _inapp_box[: len(_inapp_box) - 100]
    return {"channel": "inapp", "ok": True, "queued": True}


# ===== 请求模型 =====
class SilenceRequest(BaseModel):
    """静默告警请求"""
    duration_minutes: int = Field(60, ge=1, le=4320, description="静默时长（分钟），最长 72 小时")


class ChannelConfigUpdate(BaseModel):
    """推送渠道配置更新"""
    sms_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    inapp_enabled: Optional[bool] = None


class TestPushRequest(BaseModel):
    """测试推送请求"""
    channels: Optional[list[str]] = Field(None, description="指定渠道列表：sms/email/inapp；为空则全推")
    title: str = Field("测试告警", description="测试告警标题")
    message: str = Field("这是一条来自智能告警中心的测试推送。", description="测试告警内容")


# ===== 路由 =====
@router.get("/api/alerts/center")
@run_in_thread
def list_alerts(
    level: Optional[str] = Query(None, description="按级别过滤：critical/important/normal"),
    status: Optional[str] = Query(None, description="按状态过滤：active/acknowledged/silenced/resolved"),
    source: Optional[str] = Query(None, description="按来源过滤：device_anomaly/energy_overload/cop_decline"),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=200, description="每页条数"),
):
    """告警中心列表（先实时检测再分页返回）"""
    try:
        # 先触发实时检测，落库最新告警
        _detect_and_persist_alerts()

        # 参数校验
        if level and level not in VALID_LEVELS:
            raise HTTPException(status_code=400, detail=f"level 非法，合法值: {sorted(VALID_LEVELS)}")
        if status and status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail=f"status 非法，合法值: {sorted(VALID_STATUSES)}")
        if source and source not in VALID_SOURCES:
            raise HTTPException(status_code=400, detail=f"source 非法，合法值: {sorted(VALID_SOURCES)}")

        offset = (page - 1) * page_size
        where = "WHERE 1=1"
        params: list = []
        if level:
            where += " AND level = ?"
            params.append(level)
        if status:
            where += " AND status = ?"
            params.append(status)
        if source:
            where += " AND source = ?"
            params.append(source)

        with get_conn() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) FROM sys_alerts {where}", params
            ).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM sys_alerts {where} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                params + [page_size, offset],
            ).fetchall()

        items = []
        for r in rows:
            d = _row_to_dict(r)
            d["level_label"] = LEVEL_LABELS.get(d["level"], d["level"])
            d["status_label"] = STATUS_LABELS.get(d["status"], d["status"])
            d["source_label"] = SOURCE_LABELS.get(d["source"], d["source"])
            items.append(d)

        return {
            "status": "success",
            "data": {
                "alerts": items,
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
        return handle_route_error(e, logger, "告警列表查询")


@router.get("/api/alerts/stats")
@cache_response(ttl=15)  # 告警统计，缓存 15 秒
@run_in_thread
def alert_stats():
    """告警统计（按级别、来源、状态分布）"""
    try:
        _detect_and_persist_alerts()
        with get_conn() as conn:
            # 按级别
            level_rows = conn.execute(
                "SELECT level, COUNT(*) AS cnt FROM sys_alerts GROUP BY level"
            ).fetchall()
            # 按来源
            source_rows = conn.execute(
                "SELECT source, COUNT(*) AS cnt FROM sys_alerts GROUP BY source"
            ).fetchall()
            # 按状态
            status_rows = conn.execute(
                "SELECT status, COUNT(*) AS cnt FROM sys_alerts GROUP BY status"
            ).fetchall()
            # 活跃告警数（按级别细分）
            active_by_level = conn.execute(
                "SELECT level, COUNT(*) AS cnt FROM sys_alerts WHERE status = 'active' GROUP BY level"
            ).fetchall()
            total = conn.execute("SELECT COUNT(*) FROM sys_alerts").fetchone()[0]
            # 今日新增告警数
            today_count = conn.execute(
                "SELECT COUNT(*) FROM sys_alerts WHERE DATE(created_at) = DATE('now', 'localtime')"
            ).fetchone()[0]

        by_level = {lv: 0 for lv in VALID_LEVELS}
        for r in level_rows:
            by_level[r["level"]] = int(r["cnt"])
        by_source = {s: 0 for s in VALID_SOURCES}
        for r in source_rows:
            by_source[r["source"]] = int(r["cnt"])
        by_status = {s: 0 for s in VALID_STATUSES}
        for r in status_rows:
            by_status[r["status"]] = int(r["cnt"])
        active_count = sum(int(r["cnt"]) for r in active_by_level)
        active_by_level_dict = {r["level"]: int(r["cnt"]) for r in active_by_level}

        return {
            "status": "success",
            "data": {
                "total": int(total),
                "active_count": active_count,
                # 前端期望的扁平字段
                "critical_count": active_by_level_dict.get("critical", 0),
                "today_count": int(today_count),
                "resolved_count": by_status.get("resolved", 0),
                "by_level": by_level,
                "by_source": by_source,
                "by_status": by_status,
                "active_by_level": active_by_level_dict,
                "labels": {
                    "level": LEVEL_LABELS,
                    "source": SOURCE_LABELS,
                    "status": STATUS_LABELS,
                },
            },
        }
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "告警统计查询")


@router.post("/api/alerts/{alert_id}/acknowledge")
@run_in_thread
def acknowledge_alert(alert_id: int):
    """确认告警（状态 active → acknowledged）"""
    try:
        _init_table()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM sys_alerts WHERE id = ?", [alert_id]
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail=f"告警不存在: {alert_id}")
            conn.execute(
                """
                UPDATE sys_alerts
                SET status = 'acknowledged', acknowledged_at = ?
                WHERE id = ? AND status IN ('active', 'silenced')
                """,
                [now_str, alert_id],
            )
            conn.commit()
            updated = conn.execute(
                "SELECT * FROM sys_alerts WHERE id = ?", [alert_id]
            ).fetchone()
        d = _row_to_dict(updated)
        d["level_label"] = LEVEL_LABELS.get(d["level"], d["level"])
        d["status_label"] = STATUS_LABELS.get(d["status"], d["status"])
        d["source_label"] = SOURCE_LABELS.get(d["source"], d["source"])
        return {
            "status": "success",
            "message": f"告警 {alert_id} 已确认",
            "data": d,
        }
    except HTTPException:
        raise
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "告警确认")


@router.post("/api/alerts/{alert_id}/silence")
@run_in_thread
def silence_alert(alert_id: int, payload: SilenceRequest):
    """静默告警（指定时长，状态 → silenced）"""
    try:
        _init_table()
        now = datetime.datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        silenced_until = (now + datetime.timedelta(minutes=payload.duration_minutes)).strftime("%Y-%m-%d %H:%M:%S")
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM sys_alerts WHERE id = ?", [alert_id]
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail=f"告警不存在: {alert_id}")
            conn.execute(
                """
                UPDATE sys_alerts
                SET status = 'silenced', silenced_until = ?
                WHERE id = ? AND status IN ('active', 'acknowledged')
                """,
                [silenced_until, alert_id],
            )
            conn.commit()
            updated = conn.execute(
                "SELECT * FROM sys_alerts WHERE id = ?", [alert_id]
            ).fetchone()
        d = _row_to_dict(updated)
        d["level_label"] = LEVEL_LABELS.get(d["level"], d["level"])
        d["status_label"] = STATUS_LABELS.get(d["status"], d["status"])
        d["source_label"] = SOURCE_LABELS.get(d["source"], d["source"])
        return {
            "status": "success",
            "message": f"告警 {alert_id} 已静默至 {silenced_until}",
            "data": d,
        }
    except HTTPException:
        raise
    except DBUnavailableError:
        raise
    except Exception as e:
        return handle_route_error(e, logger, "告警静默")


@router.get("/api/alerts/channels")
@run_in_thread
def get_channels():
    """推送渠道配置（短信/邮件/站内信状态）"""
    try:
        return {
            "status": "success",
            "data": {
                "channels": [
                    {"key": "sms", "name": "短信", "enabled": _CHANNEL_CONFIG["sms_enabled"], "simulated": True},
                    {"key": "email", "name": "邮件", "enabled": _CHANNEL_CONFIG["email_enabled"], "configured": bool(SMTP_USER and MANAGER_EMAIL)},
                    {"key": "inapp", "name": "站内信", "enabled": _CHANNEL_CONFIG["inapp_enabled"]},
                ],
                "email_recipient": MANAGER_EMAIL or "",
            },
        }
    except Exception as e:
        return handle_route_error(e, logger, "推送渠道配置查询")


@router.post("/api/alerts/channels")
@run_in_thread
def update_channels(payload: ChannelConfigUpdate):
    """更新推送渠道配置"""
    try:
        if payload.sms_enabled is not None:
            _CHANNEL_CONFIG["sms_enabled"] = payload.sms_enabled
        if payload.email_enabled is not None:
            _CHANNEL_CONFIG["email_enabled"] = payload.email_enabled
        if payload.inapp_enabled is not None:
            _CHANNEL_CONFIG["inapp_enabled"] = payload.inapp_enabled
        return {
            "status": "success",
            "message": "渠道配置已更新",
            "data": _CHANNEL_CONFIG,
        }
    except Exception as e:
        return handle_route_error(e, logger, "推送渠道配置更新")


@router.post("/api/alerts/test_push")
@run_in_thread
def test_push(payload: TestPushRequest):
    """测试推送（发送测试告警到各渠道）"""
    try:
        target_channels = payload.channels or ["sms", "email", "inapp"]
        results = []
        for ch in target_channels:
            if ch == "sms":
                results.append(_push_sms(payload.message))
            elif ch == "email":
                results.append(_push_email(payload.title, payload.message))
            elif ch == "inapp":
                results.append(_push_inapp(payload.title, payload.message))
            else:
                results.append({"channel": ch, "ok": False, "reason": "未知渠道"})

        success_cnt = sum(1 for r in results if r.get("ok"))
        return {
            "status": "success",
            "message": f"测试推送完成，成功 {success_cnt}/{len(results)} 个渠道",
            "data": {
                "title": payload.title,
                "message": payload.message,
                "results": results,
                "sent_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
        }
    except Exception as e:
        return handle_route_error(e, logger, "测试推送")
