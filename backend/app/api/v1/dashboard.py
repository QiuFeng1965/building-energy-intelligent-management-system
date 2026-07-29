# -*- coding: utf-8 -*-
"""
仪表盘路由
- /api/dashboard：数字孪生大屏 KPI/折线/饼图/柱图
- /api/cop_trend：COP 趋势
- /api/energy_distribution：能耗分布
"""
import datetime
import logging

import pandas as pd
from fastapi import APIRouter

from app.core.database import get_conn, DBUnavailableError
from app.utils.name_maps import NAME_MAP
from app.core.route_error import handle_route_error

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/dashboard")
async def get_dashboard_data():
    """
    数字孪生大屏：KPI / 折线 / 饼图 / 柱图
    数据来源：backend/data/enterprise_building_energy.db（统一通过 get_conn 取连接）
    “业务今天”取数据库里最新的一天，避免当前系统日期与数据日期错位时返回空。
    """
    try:
        with get_conn() as conn:
            # 业务今天 = 数据库里最新的一天（避免系统时间与数据日期错位）
            max_date_row = pd.read_sql(
                "SELECT MAX(DATE(monitor_time)) as max_date FROM fact_energy_records",
                conn
            )
            max_date = max_date_row['max_date'].iloc[0]
            if not max_date:
                # 表为空，直接走兜底
                raise RuntimeError("fact_energy_records 表为空")

            kpi_df = pd.read_sql(
                "SELECT SUM(elec_consumption) as total_elec, "
                "SUM(CASE WHEN run_status != 'NORMAL' THEN 1 ELSE 0 END) as alarms "
                "FROM fact_energy_records WHERE DATE(monitor_time) = ?",
                conn, params=[max_date]
            )
            total_elec = int(kpi_df['total_elec'].iloc[0] or 0)
            alarms = int(kpi_df['alarms'].iloc[0] or 0)

            cop_df = pd.read_sql(
                "SELECT AVG(cop) as cop FROM fact_energy_records "
                "WHERE DATE(monitor_time) = ? AND param_type = 'HVAC'",
                conn, params=[max_date]
            )
            cop_value = round(cop_df['cop'].iloc[0] or 4.5, 1)

            kpi = {
                "total_elec": f"{total_elec:,}",
                "carbon": f"{int(total_elec * 0.785):,}",
                "cop": str(cop_value),
                "alarms": str(alarms)
            }

            line_df = pd.read_sql(
                "SELECT strftime('%H:00', monitor_time) as hour, SUM(elec_consumption) as load "
                "FROM fact_energy_records WHERE DATE(monitor_time) = ? "
                "GROUP BY hour ORDER BY hour",
                conn, params=[max_date]
            )
            line = {
                "x": line_df['hour'].tolist(),
                "y": [round(val, 1) for val in line_df['load'].tolist()]
            }

            pie_df = pd.read_sql(
                "SELECT param_type, SUM(elec_consumption) as value "
                "FROM fact_energy_records WHERE DATE(monitor_time) = ? "
                "GROUP BY param_type",
                conn, params=[max_date]
            )

            pie = [{"name": NAME_MAP.get(row['param_type'], row['param_type']), "value": int(row['value'])}
                   for _, row in pie_df.iterrows()]

            bar_df = pd.read_sql(
                "SELECT DATE(monitor_time) as date, SUM(elec_consumption) as total_load "
                "FROM fact_energy_records "
                "WHERE DATE(monitor_time) < ? AND DATE(monitor_time) >= date(?, '-7 days') "
                "GROUP BY date ORDER BY date",
                conn, params=[max_date, max_date]
            )
            bar = {
                "x": [d[5:] for d in bar_df['date'].tolist()],
                "y": [int(val) for val in bar_df['total_load'].tolist()]
            }

        return {
            "kpi": kpi,
            "line": line,
            "pie": pie,
            "bar": bar
        }

    except Exception as e:
        logger.exception(f"Dashboard 数据库读取失败: {e}")
        raise DBUnavailableError(f"Dashboard 数据读取失败: {e}")


@router.get("/api/cop_trend")
async def get_cop_trend():
    """
    COP 趋势：取数据库最新一天的 COP 按小时聚合
    数据来源：fact_energy_records
    异常时返回空数组，绝不返回假数据。
    """
    try:
        with get_conn() as conn:
            df = pd.read_sql(
                """
                SELECT
                    strftime('%H:00', monitor_time) as hour,
                    AVG(cop) as avg_cop
                FROM fact_energy_records
                WHERE DATE(monitor_time) = (SELECT MAX(DATE(monitor_time)) FROM fact_energy_records)
                  AND cop IS NOT NULL
                GROUP BY hour
                ORDER BY hour
                """,
                conn
            )

        if df.empty:
            logger.warning("COP 趋势查询结果为空，返回空数组")
            return {"status": "success", "times": [], "values": []}

        times = df['hour'].tolist()
        values = [round(float(v), 2) for v in df['avg_cop'].tolist()]

        return {
            "status": "success",
            "times": times,
            "values": values
        }
    except Exception as e:
        logger.exception(f"获取 COP 趋势失败: {e}")
        return {"status": "success", "times": [], "values": []}


@router.get("/api/energy_distribution")
async def get_energy_distribution():
    try:
        with get_conn() as conn:
            query = """
                SELECT param_type, SUM(elec_consumption) as total_energy
                FROM fact_energy_records
                GROUP BY param_type
                ORDER BY total_energy DESC
            """
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()

        chart_data = []
        colors = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#14b8a6']

        if rows:
            for i, row in enumerate(rows):
                db_param_name = row[0]
                total_value = row[1]
                display_name = NAME_MAP.get(db_param_name, db_param_name)

                chart_data.append({
                    "value": round(total_value, 2),
                    "name": display_name,
                    "itemStyle": {"color": colors[i % len(colors)]}
                })
        else:
            chart_data = [
                {"value": 4500, "name": "IT设备 (真实数据未就绪)", "itemStyle": {"color": "#3b82f6"}},
                {"value": 2800, "name": "精密空调 (真实数据未就绪)", "itemStyle": {"color": "#10b981"}},
                {"value": 850, "name": "UPS (真实数据未就绪)", "itemStyle": {"color": "#f59e0b"}}
            ]

        return {"status": "success", "data": chart_data}

    except Exception as e:
        return handle_route_error(e, logger, "能耗分布查询")
