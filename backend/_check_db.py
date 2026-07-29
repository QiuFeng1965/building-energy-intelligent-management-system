# -*- coding: utf-8 -*-
"""临时脚本：查看数据库表结构"""
from app.core.database import get_conn

with get_conn() as conn:
    cur = conn.cursor()
    # 列出所有表
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    print(f"数据库共 {len(tables)} 张表：")
    for t in tables:
        print(f"\n=== {t} ===")
        cur.execute(f"PRAGMA table_info({t})")
        cols = [(r[1], r[2]) for r in cur.fetchall()]
        for col_name, col_type in cols:
            print(f"  {col_name:30s} {col_type}")
        # 统计行数
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        count = cur.fetchone()[0]
        print(f"  >>> 行数: {count}")
