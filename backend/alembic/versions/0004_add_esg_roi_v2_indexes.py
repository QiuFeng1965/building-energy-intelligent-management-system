"""新增 ESG/ROI v2 优化索引

Revision ID: 0004_add_esg_roi_v2_indexes
Revises: 0003_add_esg_roi_indexes
Create Date: 2026-07-28

优化目标：
1. fact_work_orders.created_at：ESG G 维度工单完成率查询按时间范围扫描
2. fact_work_orders.status：按状态过滤（COMPLETED/VERIFIED）
3. fact_work_orders.completed_at：完成时间统计
4. fact_new_energy(timestamp, pv_generation_kw)：覆盖索引加速光伏聚合
5. fact_energy_records(building_id, monitor_time)：ESG 建筑碳排放明细 LEFT JOIN 优化
全部使用 IF NOT EXISTS，确保可重复执行。
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_add_esg_roi_v2_indexes"
down_revision: Union[str, Sequence[str], None] = "0003_add_esg_roi_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """添加 ESG/ROI v2 模块性能索引"""
    # ===== fact_work_orders：工单表 =====
    # ESG G 维度：WHERE created_at >= datetime(...)，按时间范围扫描
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_workorders_created ON fact_work_orders (created_at)"
    )
    # 按状态过滤：WHERE status IN ('COMPLETED','VERIFIED')
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_workorders_status ON fact_work_orders (status)"
    )
    # 完成时间统计：AVG(julianday(completed_at) - julianday(created_at))
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_workorders_completed ON fact_work_orders (completed_at)"
    )

    # ===== fact_new_energy：覆盖索引（时间 + 光伏字段）=====
    # SELECT SUM(pv_generation_kw) WHERE timestamp >= ...
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_new_energy_cover_pv ON fact_new_energy (timestamp, pv_generation_kw)"
    )

    # ===== fact_energy_records：建筑+时间复合索引 =====
    # ESG 建筑碳排放明细：LEFT JOIN ON building_id = ? AND monitor_time >= ...
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_energy_building_time ON fact_energy_records (building_id, monitor_time)"
    )


def downgrade() -> None:
    """回滚索引"""
    op.execute("DROP INDEX IF EXISTS idx_workorders_created")
    op.execute("DROP INDEX IF EXISTS idx_workorders_status")
    op.execute("DROP INDEX IF EXISTS idx_workorders_completed")
    op.execute("DROP INDEX IF EXISTS idx_new_energy_cover_pv")
    op.execute("DROP INDEX IF EXISTS idx_energy_building_time")
