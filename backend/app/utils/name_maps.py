# -*- coding: utf-8 -*-
"""
名称映射字典
统一管理设备类型、建筑类型、运行状态等中英文对照，供仪表盘、邮件、设备等模块复用。
"""

# 终极全量中英文翻译字典 (严格对齐物理引擎)
NAME_MAP = {
    # --- 设备类型 (param_type) ---
    "HVAC": "暖通空调系统",
    "PRECISION_AC": "精密空调",
    "LIGHTING": "智能照明系统",
    "SOCKET": "插座与办公用电",
    "EV_CHARGER": "新能源充电桩",
    "WATER_HEATER": "热泵热水系统",
    "PUMP": "动力水泵",
    "VENTILATION": "通风排风系统",
    "REFRIGERATION": "冷冻冷藏系统",

    # --- 建筑类型 (building_type) ---
    "TEACHING": "教学楼",
    "LIBRARY": "图书馆",
    "OFFICE": "行政办公楼",
    "LABORATORY": "科研实验楼",
    "CANTEEN": "食堂",
    "DORMITORY": "学生宿舍",
    "PLAZA": "公共广场",
    "CONFERENCE": "会议交流中心",

    # --- 运行状态 (run_status) ---
    "NORMAL": "运行正常",
    "ABNORMAL": "设备异常",
    "WARNING": "警告提示",
    "CRITICAL": "严重告警"
}
