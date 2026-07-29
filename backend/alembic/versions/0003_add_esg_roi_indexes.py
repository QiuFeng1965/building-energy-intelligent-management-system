"""新增 ESG/ROI 模块性能索引

Revision ID: 0003_add_esg_roi_indexes
Revises: 0002_add_indexes
Create Date: 2026-07-28

优化目标：
1. fact_new_energy.timestamp：ESG 绿电查询按时间范围扫描（之前全表扫描）
2. dim_devices.building_id：ROI 测算按建筑汇总设备功率（之前全表扫描）
3. fact_energy_records(monitor_time)：ESG/审计报告按时间范围查询可走索引
全部使用 IF NOT EXISTS，确保可重复执行。
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_add_esg_roi_indexes"
down_revision: Union[str, Sequence[str], None] = "0002_add_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """添加 ESG/ROI 模块性能索引"""
    # ===== fact_new_energy：新能源表（光伏/储能）=====
    # ESG 绿电查询：WHERE timestamp >= datetime('now', 'localtime', '-30 days')
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_new_energy_time ON fact_new_energy (timestamp)"
    )

    # ===== dim_devices：设备维度表 =====
    # ROI 测算：SELECT SUM(rated_power) FROM dim_devices WHERE building_id = ?
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_dim_devices_building ON dim_devices (building_id)"
    )

    # ===== fact_energy_records：补建 monitor_time 原始值索引 =====
    # ESG/审计：WHERE monitor_time >= datetime(...)，MAX(monitor_time) 可走索引
    # 注：已有 idx_energy_date(DATE(monitor_time)) 函数索引，但原始值索引更高效
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_energy_monitor_time ON fact_energy_records (monitor_time)"
    )


def downgrade() -> None:
    """回滚索引"""
    op.execute("DROP INDEX IF EXISTS idx_new_energy_time")
    op.execute("DROP INDEX IF EXISTS idx_dim_devices_building")
    op.execute("DROP INDEX IF EXISTS idx_energy_monitor_time")
