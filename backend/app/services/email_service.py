# -*- coding: utf-8 -*-
"""
邮件与定时任务服务
- 后台任务：收集当日数据并发送邮件日报
"""
import smtplib
import datetime
import logging

import pandas as pd
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import (
    SMTP_SERVER,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    MANAGER_EMAIL,
)
from app.core.database import get_conn
from app.utils.name_maps import NAME_MAP

logger = logging.getLogger(__name__)


def generate_and_send_daily_report():
    """后台任务：收集当日数据并发送邮件"""
    logger.info("⏰ [定时任务] 开始生成并发送今日能源与设备日报...")

    try:
        # 1. 抓取今日数据 (只取需要的列，加 LIMIT 兜底防 OOM)
        today = datetime.datetime.now().strftime('%Y-%m-%d')

        query = """
            SELECT monitor_time, building_type, param_type, run_status, elec_consumption
            FROM fact_energy_records
            WHERE monitor_time >= ? AND monitor_time <= ?
            ORDER BY monitor_time DESC
            LIMIT 10000
        """
        params = [f"{today} 00:00:00", f"{today} 23:59:59"]
        with get_conn() as conn:
            df = pd.read_sql(query, conn, params=params)

        # 2. 数据分析与汇总
        total_records = len(df)
        if total_records == 0:
            logger.warning("[定时任务] 今日无数据记录，取消发送。")
            return

        total_energy = round(df['elec_consumption'].sum(), 2)

        # 筛选出异常设备 (运行状态不是 NORMAL 的)
        abnormal_df = df[df['run_status'] != 'NORMAL']
        abnormal_count = len(abnormal_df)

        # 3. 构建精美的 HTML 邮件内容
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; color: #333; }}
                h2 {{ color: #2563eb; }}
                .summary {{ background-color: #f3f4f6; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
                .highlight {{ color: #e11d48; font-weight: bold; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f8fafc; color: #333; }}
            </style>
        </head>
        <body>
            <h2>📊 智慧校园数字孪生 - 每日运行报告</h2>
            <div class="summary">
                <p><strong>🗓️ 日期：</strong>{today}</p>
                <p><strong>⚡ 今日总耗电量：</strong>{total_energy} kWh</p>
                <p><strong>📡 采集数据总条数：</strong>{total_records} 条</p>
                <p><strong>🚨 今日发现异常设备数：</strong><span class="highlight">{abnormal_count} 次</span></p>
            </div>
        """

        # 如果有异常，把异常设备清单列成表格附在邮件里
        if abnormal_count > 0:
            html_content += "<h3>⚠️ 今日设备异常记录</h3><table><tr><th>时间</th><th>建筑</th><th>设备类型</th><th>状态</th></tr>"
            # 取前 50 条异常展示，防止邮件过长
            for _, row in abnormal_df.head(50).iterrows():
                b_name = NAME_MAP.get(row['building_type'], row['building_type'])
                t_name = NAME_MAP.get(row['param_type'], row['param_type'])
                s_name = NAME_MAP.get(row['run_status'], row['run_status'])
                html_content += f"<tr><td>{row['monitor_time']}</td><td>{b_name}</td><td>{t_name}</td><td style='color:red;'>{s_name}</td></tr>"
            html_content += "</table>"
        else:
            html_content += "<h3>✅ 今日设备全部运行正常，无异常告警。</h3>"

        html_content += "<br><p style='font-size: 12px; color: #888;'>此邮件由数字孪生底层引擎自动发送，请勿直接回复。</p></body></html>"

        # 4. 发送邮件逻辑（用 with 上下文管理器，异常时自动关闭连接）
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = MANAGER_EMAIL
        msg['Subject'] = f"【系统日报】智慧校园能耗与设备运行报告 ({today})"
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))

        # 使用 SSL 发送邮件 (大部分邮箱如 QQ, 163 强制要求 SSL)
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, MANAGER_EMAIL, msg.as_string())

        logger.info("✅ [定时任务] 今日邮件日报发送成功！")

    except Exception as e:
        logger.exception(f"🔥 [定时任务报错] 邮件发送失败: {e}")
