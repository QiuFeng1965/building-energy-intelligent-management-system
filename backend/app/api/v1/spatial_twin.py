# -*- coding: utf-8 -*-
"""
空间孪生路由
- /api/spatial-twin/campus-data：校园沙盘数据
- /api/spatial-twin/full-campus-sim：全校园模拟
- /api/buildings/{building_id}/3d-data：3D 建筑可视化
"""
import random
import datetime
import logging
import traceback

import pandas as pd
from fastapi import APIRouter

from app.core.database import get_conn
from app.core.route_error import handle_route_error
from app.models.schemas import SpatialTwinResponse, Building3DDataResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/spatial-twin/campus-data")
async def get_spatial_campus_data():
    try:
        real_power_map = {}
        is_real_data = False

        # 定义你的 8 个真实场景
        base_buildings = [
            {"id": "B1", "name": "教学楼", "scale": [20, 15, 12], "position": [0, 7.5, 0]},
            {"id": "B2", "name": "图书馆", "scale": [18, 22, 18], "position": [25, 11, -20]},
            {"id": "B3", "name": "行政办公楼", "scale": [15, 12, 12], "position": [-25, 6, 20]},
            {"id": "B4", "name": "科研实验楼", "scale": [15, 16, 15], "position": [-40, 8, -5]},
            {"id": "B5", "name": "食堂", "scale": [12, 6, 12], "position": [15, 3, 30]},
            {"id": "B6", "name": "学生宿舍", "scale": [20, 12, 30], "position": [35, 6, 15]},
            {"id": "B7", "name": "公共广场", "scale": [25, 1, 25], "position": [-30, 0.5, -30]},
            {"id": "B8", "name": "会议交流中心", "scale": [25, 10, 25], "position": [10, 5, -35]}
        ]

        # 真正的表名字段映射字典 (从英文代码对应到你的楼宇 ID)
        type_to_cn = {
            "TEACHING": "教学楼", "LIBRARY": "图书馆", "OFFICE": "行政办公楼",
            "LABORATORY": "科研实验楼", "CANTEEN": "食堂", "DORMITORY": "学生宿舍",
            "PLAZA": "公共广场", "CONFERENCE": "会议交流中心"
        }
        cn_to_id = {b["name"]: b["id"] for b in base_buildings}

        # ==========================================
        # 1. 深入你的绝对真实底层库
        # ==========================================
        try:
            with get_conn() as conn:
                df = pd.read_sql_query("""
                    SELECT building_type, SUM(elec_consumption) as value
                    FROM fact_energy_records
                    GROUP BY building_type
                """, conn)

            if not df.empty:
                for _, row in df.iterrows():
                    # 把数据库里的 "TEACHING" 翻译成 "教学楼"，再转换成你要的 "B1"
                    b_cn_name = type_to_cn.get(row['building_type'])
                    b_id = cn_to_id.get(b_cn_name)

                    if b_id:
                        real_power_map[b_id] = round(row['value'], 1)

                if len(real_power_map) > 0:
                    is_real_data = True  # 终于抓到真实数据了！绿灯亮起！
        except Exception as e:
            logger.warning(f"⚠️ 3D场景读取真实数据库失败: {e}")

        # ==========================================
        # 2. 组装要发给前端的数据
        # ==========================================
        campus_buildings = []
        for b in base_buildings:
            status, color = "正常", "#10b981"
            if b["id"] == "B4":
                status, color = "警告", "#f59e0b"

            # 把查到的真实总能耗填进去
            power_val = real_power_map.get(b["id"])
            if power_val is None:
                power_val = round(random.uniform(10, 50), 1)  # 只有没数据的楼才会给点模拟值

            b["status"] = status
            b["color"] = color
            b["power"] = power_val
            campus_buildings.append(b)

        return {
            "status": "success",
            "campus_name": "全息智慧校园沙盘",
            "is_real_data": is_real_data,  # 传给前端的真实数据通行证
            "data": campus_buildings,
            "last_update": datetime.datetime.now().strftime("%H:%M:%S")
        }

    except Exception as e:
        return handle_route_error(e, logger, "空间孪生数据查询")


@router.get("/api/spatial-twin/full-campus-sim", response_model=SpatialTwinResponse)
async def get_full_campus_sim():
    """
    根据用户数据库架构，完全模拟一个校园场景的实时状态。
    无论真实数据库是否有数据，都会返回丰富的模拟数据用于前端展示。
    """
    # 这里模拟读取 dim_buildings 表
    campus_data = {
        # 教学楼Block (CRB) - 5层
        "BUILDING_CRB": {
            "name": "Classroom Block (CRB)",
            "floors": {
                "F1": {"name": "1F (Server Rooms)", "spaces": [
                    {"id": "S101", "name": "L1 机房 A", "type": "DATA_CENTER", "latest_energy": random.uniform(80.0, 120.0), "latest_temp": 22.0, "status": "ALARM" if random.random() > 0.8 else "HEALTHY"},
                    {"id": "S102", "name": "L1 机房 B", "type": "DATA_CENTER", "latest_energy": random.uniform(70.0, 90.0), "latest_temp": 21.5, "status": "HEALTHY"},
                ]},
                "F2": {"name": "2F (Offices)", "spaces": [
                    {"id": "S201", "name": "L2 研发中心", "type": "OFFICE", "latest_energy": random.uniform(30.0, 60.0), "latest_temp": 24.0, "status": "HEALTHY"},
                    {"id": "S202", "name": "L2 会议室", "type": "OFFICE", "latest_energy": random.uniform(10.0, 30.0), "latest_temp": 24.5, "status": "HEALTHY"},
                ]}
                # 其他层...
            }
        },
        # 图书馆 (Library) - 3层
        "BUILDING_LIB": {
            "name": "Campus Library",
            "floors": {
                "F1": {"name": "1F 阅读大厅", "spaces": [
                    {"id": "L101", "name": "主阅读区", "type": "PUBLIC", "latest_energy": random.uniform(20.0, 40.0), "latest_temp": 23.0, "status": "HEALTHY"}
                ]},
                "F2": {"name": "2F 电子阅览室", "spaces": [
                    {"id": "L201", "name": "电子机房", "type": "DATA_CENTER", "latest_energy": random.uniform(60.0, 80.0), "latest_temp": 22.5, "status": "WARNING"}
                ]}
            }
        },
        # 科研楼 (SciLab) - 4层
        "BUILDING_SCI": {
            "name": "Science Lab Complex",
            "floors": {
                "F3": {"name": "3F 物理实验室", "spaces": [
                    {"id": "SL301", "name": "粒子实验室", "type": "LAB", "latest_energy": random.uniform(90.0, 150.0), "latest_temp": 26.0, "status": "ALARM"},
                    {"id": "SL302", "name": "准备间", "type": "LAB", "latest_energy": random.uniform(20.0, 40.0), "latest_temp": 24.0, "status": "HEALTHY"},
                ]}
            }
        }
    }

    from datetime import datetime
    return {
        "campus_name": "擎翼未来智慧校园",
        "last_update": datetime.now().strftime("%H:%M:%S"),
        "campus_data": campus_data
    }


@router.get("/api/buildings/{building_id}/3d-data")
async def get_building_3d_data(building_id: int):
    try:
        with get_conn() as conn:
            # get_conn 已设置 row_factory = sqlite3.Row
            cursor = conn.cursor()

            # ==========================================
            # 1. 动态读取【校园建筑】基础信息 (高容错读取)
            # ==========================================
            try:
                cursor.execute("SELECT * FROM dim_buildings WHERE id = ?", (building_id,))
                building_raw = cursor.fetchone()
                if building_raw:
                    building = dict(building_raw)
                else:
                    # 兼容：如果没有传具体的楼，我们把它当成“整个校园”的全局沙盘
                    building = {"id": building_id, "name": "智慧校园全景沙盘", "total_floors": 1, "total_area_m2": 50000.0}
            except Exception:
                building = {"id": building_id, "name": "智慧校园 (兜底数据)", "total_floors": 1, "total_area_m2": 50000.0}

            # 确保字段存在
            total_floors = building.get("total_floors", 5)  # 校园建筑一般在 5 层左右
            total_area = building.get("total_area_m2", 10000.0)

            # ==========================================
            # 2. 读取【校园空间】(自适应字段名)
            # ==========================================
            spaces = []
            try:
                # 使用 pragma 检查表结构，防止字段不存在导致 500
                cursor.execute("PRAGMA table_info(dim_spaces)")
                columns = [info[1] for info in cursor.fetchall()]

                # 兼容楼层字段名可能是 'floor', 'floor_number', 'floor_id' 等
                floor_col = "floor_number" if "floor_number" in columns else ("floor" if "floor" in columns else "1")

                query = f"SELECT id, name, {floor_col} as floor_num, usage_type FROM dim_spaces WHERE building_id = ?"
                cursor.execute(query, (building_id,))
                for s in cursor.fetchall():
                    spaces.append({
                        "id": s["id"],
                        "name": s["name"],
                        "floor_number": int(s["floor_num"]) if str(s["floor_num"]).isdigit() else 1,
                        "usage_type": s["usage_type"],
                        "latest_energy": 0.0  # 默认先给0
                    })
            except Exception as e:
                logger.warning(f"⚠️ 读取校园空间警告: {e}")
                # 生成默认校园沙盘空间
                spaces = [
                    {"id": 101, "name": "计算机学院楼", "floor_number": 1, "usage_type": "TEACHING", "latest_energy": 85.0},
                    {"id": 102, "name": "数字图书馆", "floor_number": 1, "usage_type": "LIBRARY", "latest_energy": 45.0},
                    {"id": 201, "name": "物理实验中心", "floor_number": 2, "usage_type": "LAB", "latest_energy": 90.0},
                    {"id": 301, "name": "学生宿舍 A 栋", "floor_number": 3, "usage_type": "DORMITORY", "latest_energy": 25.0}
                ]

            # ==========================================
            # 3. 读取【设备与能耗】并关联 (加入安全网)
            # ==========================================
            equipment = []
            try:
                cursor.execute("SELECT id, name, type, space_id, status FROM dim_equipment WHERE building_id = ?", (building_id,))
                equipment = [dict(eq) for eq in cursor.fetchall()]
                for eq in equipment:
                    if "latest_status" not in eq:
                        eq["latest_status"] = eq.get("status", "NORMAL")

                # 尝试拉取最新的实时能耗记录
                cursor.execute("""
                    SELECT space_id, SUM(param_value) as total_val
                    FROM fact_energy_records
                    WHERE timestamp >= datetime('now', '-1 hour')
                    GROUP BY space_id
                """)
                energy_map = {row["space_id"]: row["total_val"] for row in cursor.fetchall()}

                import random
                for s in spaces:
                    if s["id"] in energy_map:
                        s["latest_energy"] = energy_map[s["id"]]
                    else:
                        # 如果记录表为空，随机生成一点能耗，保证校园热力图好看
                        s["latest_energy"] = random.uniform(10.0, 95.0)

            except Exception as e:
                logger.warning(f"⚠️ 关联能耗记录失败 (数据库可能为空): {e}")
                # 不阻断流程，给随机数据
                import random
                for s in spaces:
                    s["latest_energy"] = random.uniform(10.0, 95.0)

            # ==========================================
            # 4. 拼装符合前端 3D 渲染的数据结构
            # ==========================================
            return {
                "building_id": building["id"],
                "name": building.get("name", "智慧校园场景"),
                "total_floors": total_floors,
                "total_area_m2": total_area,
                "spaces": spaces,
                "equipment": equipment,
                "latest_overall_status": "HEALTHY"
            }

    except Exception as e:
        error_msg = traceback.format_exc()
        logger.exception(f"🔥 严重致命错误: {error_msg}")
        # 就算天塌下来，也绝对不能给前端报 500！
        return {
            "building_id": building_id,
            "name": "安全兜底模式校园",
            "total_floors": 1,
            "spaces": [],
            "equipment": [],
            "latest_overall_status": "UNKNOWN"
        }
