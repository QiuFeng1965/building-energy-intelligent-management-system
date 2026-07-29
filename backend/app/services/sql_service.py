# -*- coding: utf-8 -*-
"""
SQL 生成与安全校验服务
1. 清洗大模型输出的 SQL（去除 markdown 代码块）
2. 使用 sqlglot 转成标准 SQLite 方言
3. 安全校验：只允许 SELECT 语句
"""
import logging

import sqlglot
from sqlglot import exp
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def transform_and_validate_sql(raw_sql: str) -> str:
    """
    1. 清洗大模型输出的 SQL（去除 markdown 代码块）
    2. 使用 sqlglot 转成标准 SQLite 方言
    3. 安全校验：只允许 SELECT 语句
    """
    try:
        # 清洗 ```sql ... ``` 包裹的内容
        if "```sql" in raw_sql:
            clean_sql = raw_sql.split("```sql")[-1].split("```")[0].strip()
        elif "```" in raw_sql:
            clean_sql = raw_sql.split("```")[-2].strip() if len(raw_sql.split("```")) > 2 else raw_sql.strip()
        else:
            clean_sql = raw_sql.strip()

        # sqlglot 方言转换（自动处理日期函数、EXTRACT 等差异）
        transpiled_sql = sqlglot.transpile(clean_sql, read=None, write="sqlite")[0]

        # AST 解析校验：必须是 SELECT
        parsed = sqlglot.parse_one(transpiled_sql, read="sqlite")
        if not isinstance(parsed, exp.Select):
            raise ValueError("仅允许执行 SELECT 查询语句，禁止任何修改操作")

        return transpiled_sql
    except Exception as e:
        logger.exception(f"SQL 服务异常: {e}")
        raise HTTPException(status_code=400, detail="SQL 转换或校验失败，请检查输入")
