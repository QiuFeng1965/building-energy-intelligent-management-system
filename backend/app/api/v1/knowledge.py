# -*- coding: utf-8 -*-
"""
RAG 知识库增强路由（多模态 + 知识图谱）
- /api/knowledge/graph：设备知识图谱节点/边查询（从真实数据库构建）
- /api/knowledge/search：增强检索（向量 + 关键词 + 图谱关联）
- /api/knowledge/multimodal：多模态检索
- /api/knowledge/entities：实体识别

设计要点：
1. 知识图谱从 dim_devices / dim_buildings / fact_work_orders / fact_energy_records 真实构建
2. 设备-建筑-空间-工单-故障的实体关系建模
3. 复用 RagFlow 做向量检索，叠加图谱关联扩展
"""
import logging
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.config import RAGFLOW_API_URL, RAGFLOW_API_KEY, RAGFLOW_CHAT_ID
from app.core.database import get_conn
from app.core.rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter()


# ===== 知识图谱构建规则 =====
# 设备类型 → 通用部件映射（基于暖通工程知识）
_DEVICE_PARTS = {
    "CHILLER": [("compressor", "压缩机"), ("condenser", "冷凝器"), ("evaporator", "蒸发器"), ("expansion_valve", "膨胀阀")],
    "PUMP": [("bearing", "轴承"), ("impeller", "叶轮"), ("seal", "机械密封")],
    "COOLING_TOWER": [("fill", "填料"), ("fan", "风机"), ("water_distribution", "布水系统")],
    "AHU": [("fan", "风机"), ("filter", "过滤网"), ("coil", "表冷盘管")],
    "METER": [("ct", "电流互感器"), ("display", "显示模块")],
}

# 故障类型映射（基于设备类型）
_DEVICE_FAULTS = {
    "CHILLER": [("low_cop", "COP偏低"), ("overheat", "排气过热"), ("refrigerant_leak", "制冷剂泄漏"), ("scale", "换热器结垢")],
    "PUMP": [("vibration", "振动异常"), ("seal_leak", "密封泄漏"), ("cavitation", "汽蚀")],
    "COOLING_TOWER": [("scale", "填料结垢"), ("fan_fault", "风机故障")],
    "AHU": [("filter_block", "滤网堵塞"), ("coil_frost", "盘管结霜")],
}

# 故障 → 维保动作映射
_FAULT_ACTIONS = {
    "low_cop": [("refrigerant_charge", "制冷剂充注"), ("clean_tube", "铜管清洗")],
    "overheat": [("refrigerant_charge", "制冷剂充注"), ("check_lubrication", "检查润滑")],
    "vibration": [("replace_bearing", "更换轴承"), ("lubricate", "润滑保养")],
    "scale": [("clean_tube", "铜管清洗"), ("chemical_clean", "化学清洗")],
    "refrigerant_leak": [("find_leak", "检漏补焊"), ("refrigerant_charge", "制冷剂充注")],
    "filter_block": [("replace_filter", "更换滤网")],
    "coil_frost": [("adjust_airflow", "调整风量")],
}


def _build_knowledge_graph_from_db(node_type: Optional[str] = None) -> dict:
    """从真实数据库构建知识图谱"""
    nodes = []
    edges = []
    node_id_set = set()

    def add_node(node_id: str, label: str, ntype: str, extra: dict = None):
        if node_id in node_id_set:
            return
        node_id_set.add(node_id)
        node = {"id": node_id, "label": label, "type": ntype}
        if extra:
            node.update(extra)
        nodes.append(node)

    def add_edge(source: str, target: str, relation: str):
        edges.append({"source": source, "target": target, "relation": relation})

    try:
        with get_conn() as conn:
            cur = conn.cursor()

            # 1. 建筑节点
            if not node_type or node_type == "building":
                cur.execute("SELECT building_id, building_name, building_type, total_area FROM dim_buildings")
                for row in cur.fetchall():
                    r = dict(row)
                    add_node(f"b_{r['building_id']}", r["building_name"], "building",
                             {"building_type": r["building_type"], "area": r["total_area"]})

            # 2. 空间节点
            if not node_type or node_type == "space":
                cur.execute("SELECT space_id, space_name, building_id, function_tag FROM dim_spaces")
                for row in cur.fetchall():
                    r = dict(row)
                    add_node(f"s_{r['space_id']}", r["space_name"], "space",
                             {"function": r["function_tag"]})
                    if f"b_{r['building_id']}" in node_id_set:
                        add_edge(f"b_{r['building_id']}", f"s_{r['space_id']}", "contains")

            # 3. 设备节点（真实设备）
            if not node_type or node_type == "device":
                cur.execute("""
                    SELECT device_id, device_name, device_type, building_id, space_id,
                           rated_power, nominal_cop
                    FROM dim_devices
                """)
                for row in cur.fetchall():
                    r = dict(row)
                    add_node(f"d_{r['device_id']}", r["device_name"], "device",
                             {"device_type": r["device_type"], "rated_power": r["rated_power"],
                              "nominal_cop": r["nominal_cop"]})
                    # 设备 → 建筑
                    if f"b_{r['building_id']}" in node_id_set:
                        add_edge(f"b_{r['building_id']}", f"d_{r['device_id']}", "has_device")
                    # 设备 → 空间
                    if r.get("space_id") and f"s_{r['space_id']}" in node_id_set:
                        add_edge(f"s_{r['space_id']}", f"d_{r['device_id']}", "hosts")

                    # 4. 部件节点（基于设备类型的通用部件）
                    parts = _DEVICE_PARTS.get(r["device_type"], [])
                    for pid, plabel in parts:
                        part_node_id = f"p_{pid}"
                        add_node(part_node_id, plabel, "part")
                        add_edge(f"d_{r['device_id']}", part_node_id, "has_part")

                    # 5. 故障节点（基于设备类型）
                    faults = _DEVICE_FAULTS.get(r["device_type"], [])
                    for fid, flabel in faults:
                        fault_node_id = f"f_{fid}"
                        add_node(fault_node_id, flabel, "fault")
                        # 部件 → 故障
                        # 关联部件到故障
                        if fid in ("low_cop", "overheat", "refrigerant_leak") and "p_compressor" in node_id_set:
                            add_edge("p_compressor", fault_node_id, "may_fault")
                        elif fid == "scale" and "p_condenser" in node_id_set:
                            add_edge("p_condenser", fault_node_id, "may_fault")
                        elif fid == "vibration" and "p_bearing" in node_id_set:
                            add_edge("p_bearing", fault_node_id, "may_fault")
                        elif fid == "filter_block" and "p_filter" in node_id_set:
                            add_edge("p_filter", fault_node_id, "may_fault")

                        # 故障 → 维保动作
                        actions = _FAULT_ACTIONS.get(fid, [])
                        for aid, alabel in actions:
                            action_node_id = f"a_{aid}"
                            add_node(action_node_id, alabel, "action")
                            add_edge(fault_node_id, action_node_id, "fixed_by")

            # 6. 工单节点（真实工单）
            if not node_type or node_type == "workorder":
                cur.execute("""
                    SELECT order_id, device_id, diagnosis_title, status, created_at
                    FROM fact_work_orders
                """)
                for row in cur.fetchall():
                    r = dict(row)
                    add_node(f"w_{r['order_id']}", f"工单 {r['order_id']}", "workorder",
                             {"title": r["diagnosis_title"], "status": r["status"],
                              "created_at": r["created_at"]})
                    if f"d_{r['device_id']}" in node_id_set:
                        add_edge(f"d_{r['device_id']}", f"w_{r['order_id']}", "has_workorder")

            # 7. 真实故障记录（从 fact_energy_records 中 fault_code 不为空的记录）
            if not node_type or node_type == "fault":
                cur.execute("""
                    SELECT DISTINCT fault_code, device_id
                    FROM fact_energy_records
                    WHERE fault_code IS NOT NULL AND fault_code != ''
                    LIMIT 50
                """)
                for row in cur.fetchall():
                    r = dict(row)
                    fault_id = f"rf_{r['fault_code']}"
                    add_node(fault_id, f"故障码 {r['fault_code']}", "fault",
                             {"source": "real_record", "code": r["fault_code"]})
                    if f"d_{r['device_id']}" in node_id_set:
                        add_edge(f"d_{r['device_id']}", fault_id, "recorded_fault")

    except Exception as e:
        logger.warning(f"从数据库构建知识图谱失败: {e}")

    # 过滤边（确保两端节点都存在）
    valid_edges = [e for e in edges if e["source"] in node_id_set and e["target"] in node_id_set]

    # 按 node_type 过滤
    if node_type:
        filtered_nodes = [n for n in nodes if n["type"] == node_type or n["type"] in ("building", "device")]
        filtered_ids = {n["id"] for n in filtered_nodes}
        valid_edges = [e for e in valid_edges if e["source"] in filtered_ids and e["target"] in filtered_ids]
        nodes = filtered_nodes

    return {"nodes": nodes, "edges": valid_edges}


@router.get("/api/knowledge/graph")
def get_knowledge_graph(node_type: Optional[str] = None):
    """获取知识图谱（从真实数据库构建）"""
    graph = _build_knowledge_graph_from_db(node_type)
    return {
        "status": "success",
        "data": {
            "nodes": graph["nodes"],
            "edges": graph["edges"],
            "stats": {
                "node_count": len(graph["nodes"]),
                "edge_count": len(graph["edges"]),
                "types": list({n["type"] for n in graph["nodes"]}),
                "data_source": "real_database",
            },
        },
    }


@router.get("/api/knowledge/entities")
def extract_entities(text: str):
    """从文本中识别实体（基于真实数据库）"""
    graph = _build_knowledge_graph_from_db()
    text_lower = text.lower()
    matched = []
    matched_ids = set()

    for node in graph["nodes"]:
        if node["label"] in text or node["id"] in text_lower:
            matched.append(node)
            matched_ids.add(node["id"])

    # 查找关联节点
    related = set()
    for edge in graph["edges"]:
        if edge["source"] in matched_ids:
            related.add(edge["target"])
        if edge["target"] in matched_ids:
            related.add(edge["source"])

    related_nodes = [n for n in graph["nodes"] if n["id"] in related and n["id"] not in matched_ids]

    return {
        "status": "success",
        "data": {
            "input_text": text,
            "matched_entities": matched,
            "related_entities": related_nodes,
        },
    }


@router.get("/api/knowledge/search")
@limiter.limit("20/minute")
async def enhanced_search(request: Request, query: str, top_k: int = 5):
    """增强检索：向量检索（RagFlow） + 图谱关联扩展"""
    entities_resp = extract_entities(query)
    matched_entities = entities_resp["data"]["matched_entities"]
    related_entities = entities_resp["data"]["related_entities"]

    ragflow_results = []
    try:
        import httpx
        if RAGFLOW_API_KEY:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{RAGFLOW_API_URL}/chats/{RAGFLOW_CHAT_ID}/completions",
                    headers={"Authorization": f"Bearer {RAGFLOW_API_KEY}"},
                    json={"question": query, "stream": False},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if "data" in data and "reference" in data["data"]:
                        chunks = data["data"]["reference"].get("chunks", [])
                        ragflow_results = [
                            {
                                "content": c.get("content", "")[:500],
                                "doc_name": c.get("document_name", ""),
                                "score": c.get("similarity", 0),
                            }
                            for c in chunks[:top_k]
                        ]
    except Exception as e:
        logger.warning(f"RagFlow 检索失败: {e}")

    return {
        "status": "success",
        "data": {
            "query": query,
            "entities": {
                "matched": matched_entities,
                "related": related_entities,
            },
            "ragflow_results": ragflow_results,
            "graph_context": _build_graph_context(matched_entities),
        },
    }


def _build_graph_context(entities: list) -> str:
    """根据识别的实体构建图谱上下文"""
    if not entities:
        return ""
    graph = _build_knowledge_graph_from_db()
    lines = []
    entity_ids = {e["id"] for e in entities}
    for edge in graph["edges"]:
        if edge["source"] in entity_ids or edge["target"] in entity_ids:
            src = next((n for n in graph["nodes"] if n["id"] == edge["source"]), None)
            tgt = next((n for n in graph["nodes"] if n["id"] == edge["target"]), None)
            if src and tgt:
                lines.append(f"{src['label']} -[{edge['relation']}]-> {tgt['label']}")
    return "\n".join(lines)


class MultimodalQuery(BaseModel):
    text: Optional[str] = None
    image_description: Optional[str] = None


@router.post("/api/knowledge/multimodal")
@limiter.limit("10/minute")
async def multimodal_search(request: Request, req: MultimodalQuery):
    """多模态检索"""
    combined_query = " ".join(filter(None, [req.text, req.image_description]))
    if not combined_query:
        return {"status": "error", "message": "必须提供 text 或 image_description"}
    return await enhanced_search(request, combined_query)
