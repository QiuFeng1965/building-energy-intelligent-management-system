# -*- coding: utf-8 -*-
"""
报表路由
- /api/report/weekly_ai：生成企业级 Word 周报（含 AI 诊断）
核心逻辑抽到 app/services/report_service.py，本文件仅负责 HTTP 层。
"""
import datetime

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services.report_service import generate_weekly_report_docx

router = APIRouter()


@router.get("/api/report/weekly_ai")
async def generate_weekly_ai_report():
    """生成并下载 Word 周报"""
    try:
        file_stream = await generate_weekly_report_docx()
        return StreamingResponse(
            file_stream,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename=AI_Energy_Report_{datetime.datetime.now().strftime('%Y%m%d')}.docx"}
        )
    except Exception as fatal_err:
        return {"status": "error", "message": str(fatal_err)}
