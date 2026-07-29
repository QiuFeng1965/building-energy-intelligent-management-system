"""新增性能索引：DATE 函数索引 + 工单/记忆表索引

Revision ID: 0002_add_indexes
Revises: 0001_baseline
Create Date: 2026-07-28

优化目标：
1. fact_energy_records：按日期范围查询（dashboard/spatial_twin/report 都用 DATE(monitor_time)）
2. fact_work_orders：按状态/创建时间查询工单
3. sys_agent_memory：按会话/时间查询记忆
全部使用 IF NOT EXISTS，确保可重复执行。
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_add_indexes"
down_revision: Union[str, Sequence[str], None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """添加性能关键索引"""
    # ===== fact_energy_records：核心能耗表（110 万行）=====
    # 按日期范围查询（dashboard 今日数据、报表周报）
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_energy_date ON fact_energy_records (DATE(monitor_time))"
    )
    # 按设备+时间查询（设备监控、AI 工具函数）
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_energy_device_time ON fact_energy_records (device_id, monitor_time)"
    )
    # 按建筑+时间查询（空间孪生、报表分建筑统计）
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_energy_building_time ON fact_energy_records (building_id, monitor_time)"
    )
    # 按运行状态查询（异常告警筛选）
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_energy_status ON fact_energy_records (run_status, DATE(monitor_time))"
    )

    # ===== fact_work_orders：工单表（列名 created_at） =====
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_workorders_status ON fact_work_orders (status, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_workorders_device ON fact_work_orders (device_id, created_at)"
    )

    # ===== sys_agent_memory：智能体记忆表（列名 incident_id + created_at） =====
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_memory_incident ON sys_agent_memory (incident_id, created_at)"
    )


def downgrade() -> None:
    """回滚索引"""
    op.execute("DROP INDEX IF EXISTS idx_energy_date")
    op.execute("DROP INDEX IF EXISTS idx_energy_device_time")
    op.execute("DROP INDEX IF EXISTS idx_energy_building_time")
    op.execute("DROP INDEX IF EXISTS idx_energy_status")
    op.execute("DROP INDEX IF EXISTS idx_workorders_status")
    op.execute("DROP INDEX IF EXISTS idx_workorders_device")
    op.execute("DROP INDEX IF EXISTS idx_agent_memory_incident")
