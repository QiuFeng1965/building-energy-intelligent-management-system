# -*- coding: utf-8 -*-
"""检查 dim_spaces 表"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'enterprise_building_energy.db')
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== dim_spaces 结构 ===")
cur.execute("PRAGMA table_info(dim_spaces)")
for r in cur.fetchall():
    print(dict(r))

print("\n=== dim_spaces 数据（前 15 条）===")
cur.execute("SELECT * FROM dim_spaces LIMIT 15")
for r in cur.fetchall():
    print(dict(r))

print("\n=== dim_spaces 总数 ===")
cur.execute("SELECT COUNT(*) FROM dim_spaces")
print("total:", cur.fetchone()[0])

print("\n=== 建筑+空间+设备联合查询示例 ===")
cur.execute("""
    SELECT b.building_name, s.space_name, s.function_type, d.device_name, d.device_type
    FROM dim_devices d
    JOIN dim_buildings b ON b.building_id = d.building_id
    JOIN dim_spaces s ON s.space_id = d.space_id
    ORDER BY b.building_id, s.space_id
    LIMIT 20
""")
for r in cur.fetchall():
    print(dict(r))

conn.close()
