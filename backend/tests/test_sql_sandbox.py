# -*- coding: utf-8 -*-
"""
SQL 沙箱安全测试
验证 execute_sql_query 是否能正确拦截各类注入/越权/破坏性语句。
这是防 SQL 注入的核心防线，必须有测试覆盖。
"""
import sys
import os

# 把 backend 目录加入 sys.path，让测试能直接 import app.*
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ai_service import execute_sql_query


def _assert_blocked(result: str, *, keyword: str = "拒绝"):
    """断言被沙箱拦截"""
    assert keyword in result, f"期望被拦截（含'{keyword}'），实际返回: {result}"


def test_select_normal_query_returns_data():
    """正常 SELECT 应通过校验并返回数据或空提示"""
    result = execute_sql_query(
        "SELECT COUNT(*) AS cnt FROM fact_energy_records WHERE DATE(monitor_time) = DATE('now', 'localtime')"
    )
    # 不论有没数据，都不应出现 "拒绝"
    assert "拒绝" not in result, f"正常查询被误拦截: {result}"


def test_drop_table_blocked():
    """DROP TABLE 必须被拦截"""
    result = execute_sql_query("DROP TABLE fact_energy_records")
    _assert_blocked(result)


def test_insert_blocked():
    """INSERT 必须被拦截"""
    result = execute_sql_query(
        "INSERT INTO fact_energy_records (device_id) VALUES ('HACKED')"
    )
    _assert_blocked(result)


def test_update_blocked():
    """UPDATE 必须被拦截"""
    result = execute_sql_query(
        "UPDATE fact_energy_records SET elec_consumption = 0 WHERE device_id = 'X'"
    )
    _assert_blocked(result)


def test_delete_blocked():
    """DELETE 必须被拦截"""
    result = execute_sql_query("DELETE FROM fact_energy_records")
    _assert_blocked(result)


def test_create_table_blocked():
    """CREATE TABLE 必须被拦截"""
    result = execute_sql_query(
        "CREATE TABLE hack_table (id INTEGER, payload TEXT)"
    )
    _assert_blocked(result)


def test_sqlite_master_blocked():
    """访问 sqlite_master 系统表必须被拦截（越权）"""
    result = execute_sql_query(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    _assert_blocked(result, keyword="越权")


def test_disallowed_table_blocked():
    """访问白名单外的表必须被拦截"""
    result = execute_sql_query("SELECT * FROM sys_users")
    _assert_blocked(result, keyword="越权")


def test_sql_with_markdown_codeblock_stripped():
    """带 ```sql 代码块标记的 SQL 应被正确清洗后执行"""
    result = execute_sql_query(
        "```sql\nSELECT COUNT(*) AS c FROM dim_buildings\n```"
    )
    assert "拒绝" not in result, f"代码块清洗失败导致误拦截: {result}"


def test_sql_injection_comment_ignored():
    """带注释的注入尝试应被 sqlglot 解析为合法 SELECT（仍受白名单约束）"""
    # SELECT 1; DROP TABLE x 会被 sqlglot 解析为一条 SELECT，DROP 不会被执行
    result = execute_sql_query(
        "SELECT 1 FROM fact_energy_records; -- DROP TABLE fact_energy_records"
    )
    assert "拒绝" not in result, f"注释型注入被误判: {result}"


def test_empty_query_handled_gracefully():
    """空查询应被优雅处理（不抛异常）"""
    result = execute_sql_query("")
    # 应该返回某种错误提示，而不是抛未捕获异常
    assert isinstance(result, str)
