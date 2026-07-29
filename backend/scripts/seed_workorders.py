# -*- coding: utf-8 -*-
"""
工单种子数据生成器
基于 fact_energy_records 中的异常记录自动生成工单，实现"异常检测 → 工单生成"数据共通

数据来源：
- fact_energy_records 中 run_status != 'NORMAL' 或 fault_code 非空且 != 'NONE' 的记录
- dim_devices 设备元信息
- dim_buildings 建筑元信息

生成规则：
- 每条异常记录生成一个工单
- 故障码映射优先级：ERR_* → P0/P1，WARN_* → P2/P3
- 工单状态分布：PENDING(20%) / IN_PROGRESS(15%) / COMPLETED(50%) / VERIFIED(15%)
- 已完成工单设置 completed_at 和 repair_cost
- 生成 diagnosis_title / maintenance_action / user_feedback
"""
import sqlite3
import random
import datetime
import hashlib

random.seed(42)  # 可复现

DB_PATH = 'backend/data/enterprise_building_energy.db'

# 故障码 → 诊断/维护建议/优先级映射
FAULT_CODE_MAP = {
    'WARN_LOW_COP': {
        'priority': 'P2',
        'title': 'COP 低于预警阈值，制冷效率下降',
        'action': '检查冷凝器/蒸发器结垢情况，清洗换热器；检查制冷剂充注量；校准膨胀阀',
        'cost_range': (500, 2000),
    },
    'WARN_LOW_ILLUMINANCE': {
        'priority': 'P3',
        'title': '照度低于设计标准，影响视觉舒适度',
        'action': '清洁灯具表面；检查驱动电源输出；评估是否需要更换光衰严重的 LED 模组',
        'cost_range': (100, 800),
    },
    'ERR_LOW_DELTA_T': {
        'priority': 'P1',
        'title': '供回水温差异常偏小，换热效率严重下降',
        'action': '检查阀门开度；排查旁通阀是否窜水；清洗过滤器；检查水泵流量',
        'cost_range': (800, 3500),
    },
    'WARN_HIGH_CONSUMPTION': {
        'priority': 'P2',
        'title': '能耗较同类设备偏高，存在节能空间',
        'action': '分析运行时段负载率；检查启停策略；评估变频改造可行性；校核计量仪表',
        'cost_range': (300, 1500),
    },
    'ERR_VENTILATION_FAULT': {
        'priority': 'P1',
        'title': '通风系统故障，新风量不足',
        'action': '检查风机运行状态；排查风阀执行器；清洁过滤网；检查皮带松紧度',
        'cost_range': (600, 2800),
    },
    'ERR_SOCKET_OVERLOAD': {
        'priority': 'P0',
        'title': '插座回路过载告警，存在电气安全隐患',
        'action': '立即排查负载接入情况；检查断路器整定值；测量回路电流；必要时增设回路',
        'cost_range': (200, 1200),
    },
    'ERR_LIGHT_FLICKER': {
        'priority': 'P1',
        'title': '灯具频闪异常，驱动电源可能故障',
        'action': '更换 LED 驱动电源；检查接线端子是否松动；测量供电电压稳定性',
        'cost_range': (150, 900),
    },
    'ERR_DOOR_OPEN': {
        'priority': 'P2',
        'title': '门禁异常长时间开启，冷量流失',
        'action': '检查门磁开关；校准闭门器；检查门禁控制器联动逻辑；设置告警延时',
        'cost_range': (100, 600),
    },
    'WARN_LOW_AIRFLOW': {
        'priority': 'P3',
        'title': '风量低于设计值，空调效果偏差',
        'action': '检查送风口调节阀；清洁过滤网；检查风管是否漏风；校核风机转速',
        'cost_range': (200, 1000),
    },
}

# 工单状态分布（权重）
STATUS_DIST = [
    ('PENDING', 0.20),
    ('IN_PROGRESS', 0.15),
    ('COMPLETED', 0.50),
    ('VERIFIED', 0.15),
]

# 负责人池
ASSIGNEES = ['张工', '李工', '王工', '赵工', '陈工', '刘工', '周工', '吴工']
ASSIGNEE_SKILLS = {
    '张工': '暖通',
    '李工': '电气',
    '王工': '弱电',
    '赵工': '暖通',
    '陈工': '综合',
    '刘工': '电气',
    '周工': '暖通',
    '吴工': '弱电',
}

# 用户反馈池（已完成工单）
USER_FEEDBACKS = [
    '维修及时，问题已解决',
    '响应迅速，服务满意',
    '处理专业，设备恢复正常',
    '维修质量良好',
    '问题彻底解决，无复发',
    '沟通顺畅，处理高效',
    '技术水平高，建议采纳',
    '',  # 部分无反馈
    '',
    '维修时间略长，但结果满意',
]


def _gen_order_id(idx: int) -> str:
    """生成工单 ID：WO + 日期 + 序号"""
    return f'WO-20260728-{idx:04d}'


def _gen_sla_due(created_at: str, priority: str) -> str:
    """根据优先级生成 SLA 到期时间"""
    ct = datetime.datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
    hours_map = {'P0': 2, 'P1': 8, 'P2': 24, 'P3': 72}
    delta = datetime.timedelta(hours=hours_map.get(priority, 48))
    return (ct + delta).strftime('%Y-%m-%d %H:%M:%S')


def _calc_sla_status(status: str, created_at: str, completed_at: str, sla_due: str) -> str:
    """计算 SLA 状态"""
    if status in ('COMPLETED', 'VERIFIED'):
        if not completed_at:
            return 'NORMAL'
        comp = datetime.datetime.strptime(completed_at, '%Y-%m-%d %H:%M:%S')
        due = datetime.datetime.strptime(sla_due, '%Y-%m-%d %H:%M:%S')
        return 'BREACH' if comp > due else 'NORMAL'
    # 未完成：与当前时间比较
    now = datetime.datetime.now()
    due = datetime.datetime.strptime(sla_due, '%Y-%m-%d %H:%M:%S')
    if now > due:
        return 'BREACH'
    return 'AT_RISK' if (due - now).total_seconds() < 4 * 3600 else 'NORMAL'


def _weighted_choice(dist):
    r = random.random()
    cum = 0.0
    for val, w in dist:
        cum += w
        if r <= cum:
            return val
    return dist[-1][0]


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 查询异常记录（去重，每设备每故障码只取最近一条）
    print('查询异常记录...')
    rows = cur.execute("""
        SELECT device_id, fault_code, monitor_time, run_status
        FROM fact_energy_records
        WHERE fault_code IS NOT NULL AND fault_code != '' AND fault_code != 'NONE'
        ORDER BY monitor_time DESC
    """).fetchall()
    print(f'异常记录总数: {len(rows)}')

    # 按设备+故障码去重，保留最近一条
    seen = set()
    unique_anomalies = []
    for r in rows:
        key = (r[0], r[1])
        if key not in seen:
            seen.add(key)
            unique_anomalies.append(r)
    print(f'去重后异常: {len(unique_anomalies)}')

    # 查询设备元信息
    dev_map = {}
    for d in cur.execute("SELECT device_id, device_name, device_type, building_id FROM dim_devices").fetchall():
        dev_map[d[0]] = {'name': d[1], 'type': d[2], 'building_id': d[3]}

    # 查询建筑元信息
    bld_map = {}
    for b in cur.execute("SELECT building_id, building_name FROM dim_buildings").fetchall():
        bld_map[b[0]] = b[1]

    # 清空旧工单（保留结构）
    cur.execute("DELETE FROM fact_work_orders")
    try:
        cur.execute("DELETE FROM sys_workorder_ext")
    except Exception:
        pass
    conn.commit()
    print('已清空旧工单数据')

    # 生成工单
    wo_records = []
    ext_records = []
    idx = 0
    for device_id, fault_code, monitor_time, run_status in unique_anomalies:
        idx += 1
        if fault_code not in FAULT_CODE_MAP:
            continue

        cfg = FAULT_CODE_MAP[fault_code]
        order_id = _gen_order_id(idx)
        dev = dev_map.get(device_id, {'name': device_id, 'type': '未知', 'building_id': ''})
        bld_name = bld_map.get(dev['building_id'], '未知建筑')

        # 工单创建时间：基于异常发生时间 + 随机延迟（1~6小时）
        try:
            anomaly_t = datetime.datetime.strptime(monitor_time, '%Y-%m-%d %H:%M:%S')
        except Exception:
            anomaly_t = datetime.datetime.now() - datetime.timedelta(days=random.randint(1, 30))
        delay_hours = random.uniform(1, 6)
        created_at = (anomaly_t + datetime.timedelta(hours=delay_hours)).strftime('%Y-%m-%d %H:%M:%S')

        # 工单状态
        status = _weighted_choice(STATUS_DIST)

        # 完成时间（仅 COMPLETED/VERIFIED）
        completed_at = None
        if status in ('COMPLETED', 'VERIFIED'):
            handle_hours = random.uniform(2, 72)
            completed_at = (datetime.datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S') + datetime.timedelta(hours=handle_hours)).strftime('%Y-%m-%d %H:%M:%S')

        # 维修成本
        cost_min, cost_max = cfg['cost_range']
        repair_cost = round(random.uniform(cost_min, cost_max), 2) if status in ('COMPLETED', 'VERIFIED') else None

        # 诊断标题
        diagnosis_title = f'[{bld_name}] {dev["name"]} - {cfg["title"]}'

        # 维护建议
        maintenance_action = cfg['action'] if status in ('COMPLETED', 'VERIFIED', 'IN_PROGRESS') else None

        # 用户反馈
        user_feedback = random.choice(USER_FEEDBACKS) if status == 'VERIFIED' else None

        wo_records.append((
            order_id, device_id, monitor_time, diagnosis_title,
            '请参考设备手册及故障码处置流程', maintenance_action, repair_cost,
            status, created_at, completed_at, user_feedback
        ))

        # 扩展信息
        priority = cfg['priority']
        assignee = random.choice(ASSIGNEES)
        assignee_skill = ASSIGNEE_SKILLS.get(assignee, '综合')
        sla_due = _gen_sla_due(created_at, priority)
        sla_status = _calc_sla_status(status, created_at, completed_at, sla_due)
        created_by = 'system_auto'

        ext_records.append((
            order_id, priority, assignee, assignee_skill,
            sla_due, sla_status, created_by
        ))

    # 批量插入
    cur.executemany("""
        INSERT INTO fact_work_orders
        (order_id, device_id, anomaly_time, diagnosis_title, rag_advice,
         maintenance_action, repair_cost, status, created_at, completed_at, user_feedback)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, wo_records)

    # 插入扩展表
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sys_workorder_ext (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id VARCHAR(50) UNIQUE,
                priority VARCHAR(10),
                assignee VARCHAR(50),
                assignee_skill VARCHAR(50),
                sla_due_at DATETIME,
                sla_status VARCHAR(20),
                created_by VARCHAR(50),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.executemany("""
            INSERT OR REPLACE INTO sys_workorder_ext
            (order_id, priority, assignee, assignee_skill, sla_due_at, sla_status, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ext_records)
    except Exception as e:
        print(f'扩展表写入警告: {e}')

    conn.commit()

    # 统计
    total = cur.execute('SELECT COUNT(*) FROM fact_work_orders').fetchone()[0]
    status_dist = cur.execute('SELECT status, COUNT(*) FROM fact_work_orders GROUP BY status').fetchall()
    priority_dist = cur.execute('SELECT priority, COUNT(*) FROM sys_workorder_ext GROUP BY priority').fetchall()
    sla_dist = cur.execute('SELECT sla_status, COUNT(*) FROM sys_workorder_ext GROUP BY sla_status').fetchall()
    time_span = cur.execute('SELECT MIN(created_at), MAX(created_at) FROM fact_work_orders').fetchone()
    completed_cnt = cur.execute("SELECT COUNT(*) FROM fact_work_orders WHERE completed_at IS NOT NULL").fetchone()[0]
    total_cost = cur.execute("SELECT SUM(repair_cost) FROM fact_work_orders WHERE repair_cost IS NOT NULL").fetchone()[0]

    print(f'\n===== 工单种子数据生成完成 =====')
    print(f'总工单数: {total}')
    print(f'状态分布: {dict(status_dist)}')
    print(f'优先级分布: {dict(priority_dist)}')
    print(f'SLA分布: {dict(sla_dist)}')
    print(f'时间跨度: {time_span[0]} ~ {time_span[1]}')
    print(f'已完工数: {completed_cnt}')
    print(f'累计维修成本: {total_cost:.2f} 元')

    conn.close()


if __name__ == '__main__':
    main()
