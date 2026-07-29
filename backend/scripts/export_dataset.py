import os
import sqlite3
import pandas as pd

# 1. 连接你的百万级数据库
conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'enterprise_building_energy.db'))

# 2. 从主表抽取 5000 条代表性数据（包含正常和异常记录）
# 假设你的表名是 fact_energy_records
query = """
    SELECT * FROM fact_energy_records 
    ORDER BY monitor_time DESC 
    LIMIT 100000
"""
df = pd.read_sql_query(query, conn)

# 3. 导出为 CSV（使用 utf-8-sig 防止在 Windows Excel 里打开中文乱码）
df.to_csv('building_energy_dataset_5000.csv', index=False, encoding='utf-8-sig')
conn.close()

print("🎉 提交版 CSV 数据集导出成功！")