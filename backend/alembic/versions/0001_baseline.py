"""基线迁移：标记当前数据库 schema 为已初始化状态

Revision ID: 0001_baseline
Revises:
Create Date: 2026-07-28

说明：
- 当前项目的 schema 由 backend/data/database_dump.sql 初始化，
  已包含全部业务表（fact_energy_records / dim_devices / fact_work_orders 等）。
- 本基线迁移为空操作，仅用于在 Alembic 版本表中建立起点。
- 后续新增表/字段/索引均以本基线为基准增量迁移。
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """基线空操作：现有 schema 由 database_dump.sql 初始化，无需重建。"""
    pass


def downgrade() -> None:
    """基线不可回滚（回滚会丢失业务数据）。"""
    pass
