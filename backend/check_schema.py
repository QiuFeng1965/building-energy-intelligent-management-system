# -*- coding: utf-8 -*-
"""检查数据库 schema 和空间层级数据"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'enterprise_building_energy.db')
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== 所有 dim_ 表 ===")
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'dim%' ORDER BY name")
for r in cur.fetchall():
    print(r[0])

print("\n=== dim_buildings 结构 ===")
cur.execute("PRAGMA table_info(dim_buildings)")
for r in cur.fetchall():
    print(dict(r))

print("\n=== dim_buildings 数据 ===")
cur.execute("SELECT * FROM dim_buildings")
for r in cur.fetchall():
    print(dict(r))

print("\n=== space_id 分布 ===")
cur.execute("SELECT space_id, COUNT(*) as cnt FROM dim_devices GROUP BY space_id ORDER BY space_id")
for r in cur.fetchall():
    print(dict(r))

print("\n=== 检查是否有 dim_spaces 表 ===")
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dim_spaces'")
result = cur.fetchone()
print("dim_spaces exists:", result is not None)

conn.close()
