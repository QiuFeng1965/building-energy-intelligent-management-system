# -*- coding: utf-8 -*-
"""
RagFlow 知识库服务
封装企业私有知识库的检索调用，处理 RAGFlow 的会话建联与底层原文兜底扒取。
"""
import os
import json
import logging
import httpx

from app.core.config import RAGFLOW_API_URL, RAGFLOW_API_KEY, RAGFLOW_CHAT_ID
from app.core.circuit_breaker import ragflow_breaker, CircuitOpenError
from app.services.demo_mode import try_demo_ragflow

logger = logging.getLogger(__name__)

# 简易 prompt injection 关键词检测（命中即记录告警，原文仍照常传递给 LLM 处理）
_INJECTION_KEYWORDS = ("ignore previous", "ignore above", "system:", "忽略上述", "忽略上面", "系统指令")


def _detect_prompt_injection(text: str) -> None:
    """扫描知识库原文是否包含典型 prompt injection 关键词，命中则告警。"""
    if not text:
        return
    lowered = text.lower()
    for keyword in _INJECTION_KEYWORDS:
        if keyword.lower() in lowered:
            logger.warning("检测到疑似 prompt injection 关键词: %r", keyword)
            return


async def ask_ragflow_knowledge(query: str) -> str:
    # ================= 演示模式：仅 DEMO_MODE=1 时启用硬编码拦截 =================
    demo_answer = try_demo_ragflow(query)
    if demo_answer is not None:
        return demo_answer
    # ================= 演示拦截结束 =================
    API_KEY = RAGFLOW_API_KEY
    CHAT_ID = RAGFLOW_CHAT_ID
    url = f"{RAGFLOW_API_URL}/chats/{CHAT_ID}/completions"

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    # 第一次请求：坚决不带 session_id，让 RAGFlow 自动建联
    payload = {
        "question": query,
        "stream": False
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # ================= 第一击：试探与建联 =================
            response = await ragflow_breaker.call(client.post, url, headers=headers, json=payload)
            if response.status_code == 200:
                result = response.json()
                logger.info("[一击透视]: %s", json.dumps(result, ensure_ascii=False))

                answer = result.get("data", {}).get("answer", "")

                # 包含中文和英文的开场白关键词
                greeting_words = ["助理", "你好", "Hi!", "What can I do"]

                # 核心拦截：如果 RAGFlow 在打招呼，说明它只是建了个新会话，没去查知识库！
                if any(word in answer for word in greeting_words):
                    valid_session_id = result.get("data", {}).get("session_id")
                    logger.warning("触发开场白！已获取合法 session_id: %s，准备发起第二击...", valid_session_id)

                    # ================= 第二击：携带合法 ID 真实追问 =================
                    if valid_session_id:
                        payload["session_id"] = valid_session_id
                        # 发起第二次真实的查询请求
                        response2 = await ragflow_breaker.call(client.post, url, headers=headers, json=payload)
                        result = response2.json()  # 用第二击的结果覆盖之前的 result
                        logger.info("[二击透视]: %s", json.dumps(result, ensure_ascii=False))
                        answer = result.get("data", {}).get("answer", "")

                # ================= 兜底扒皮机制 (无论一击还是二击，只要没实质内容就扒底层) =================
                if not answer or answer.strip() == "" or any(word in answer for word in greeting_words):
                    logger.warning("[深层拦截] RAGFlow 仍未总结出有效答案！正在下潜直接提取向量库底层原文块...")
                    reference_chunks = []
                    data_obj = result.get("data", {})

                    # 贪婪模式：兼容不同版本的 RAGFlow 返回结构
                    if "reference" in data_obj and "chunks" in data_obj["reference"]:
                        reference_chunks = data_obj["reference"]["chunks"]
                    elif "chunks" in data_obj:
                        reference_chunks = data_obj["chunks"]
                    elif "docs" in data_obj:
                        reference_chunks = data_obj["docs"]

                    if reference_chunks:
                        # 提取所有底层检索到的片段并拼装
                        extracted_texts = [chunk.get("content", "") for chunk in reference_chunks if chunk.get("content")]
                        answer = "\n---\n".join(extracted_texts)
                        logger.info("[底层扒皮成功] 已强行抓取到 %d 个原文片段！", len(extracted_texts))
                    else:
                        answer = "无法检索到相关内容，请检查该文档是否已被 RAGFlow 后台成功解析。"
                        logger.warning("[彻底失败] RAGFlow 的向量库里完全没搜到相关特征！")

                # 只记录前 200 字防刷屏
                logger.info("【最终送给主大模型的数据】: %s...", answer[:200])

                # 扫描知识库原文是否存在典型 prompt injection 关键词
                _detect_prompt_injection(answer)

                # ================= 结果包装（中性描述，不再挟持模型） =================
                # 旧版用“系统最高优先级指令、一字不改输出”包裹原文，构成 prompt injection 攻击向量，
                # 现改为中性描述，让主大模型基于检索结果正常综合回答。
                magic_wrapper = f"""
以下是知识库检索结果，请综合参考：

-------------------------知识库原文开始-------------------------
{answer}
-------------------------知识库原文结束-------------------------
"""
                return magic_wrapper

            return f"❌ 接口报错: {response.status_code}"
    except CircuitOpenError:
        return "知识库服务暂时不可用，请稍后重试"
    except Exception as e:
        logger.exception("RagFlow 调用异常: %s", e)
        return "❌ 服务异常，请稍后重试"
