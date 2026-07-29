# -*- coding: utf-8 -*-
"""
Pydantic 数据模型层
集中定义所有请求/响应结构，供 API 路由与服务层复用。
"""
from typing import List, Optional
from pydantic import BaseModel


class ChatRequest(BaseModel):
    """AI 对话请求体"""
    prompt: str
    currentPage: str
    image_base64: Optional[str] = None

    # 接收前端传来的历史记录
    history: Optional[List[dict]] = []

    # 接收前端传来的模型模式
    agent_mode: Optional[str] = None


class SpatialEntityData(BaseModel):
    """空间孪生实体数据"""
    id: str
    name: str
    type: str  # BUILDING, FLOOR, SPACE
    floor_number: int
    latest_energy: float
    latest_temp: float
    status: str  # HEALTHY, WARNING, ALARM


class SpatialTwinResponse(BaseModel):
    """空间孪生响应体"""
    campus_name: str
    last_update: str
    campus_data: dict


class Building3DDataResponse(BaseModel):
    """3D 建筑可视化响应体"""
    building_id: int
    name: str
    total_floors: int
    total_area_m2: float
    spaces: List[dict]  # [id, name, floor_number, area, usage_type, current_energy]
    equipment: List[dict]  # [id, name, type, space_id, current_status]
    latest_overall_status: str  # HEALTHY, WARNING, CRITICAL
