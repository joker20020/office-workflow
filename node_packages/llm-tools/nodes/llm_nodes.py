# -*- coding: utf-8 -*-
"""
大语言模型节点定义

提供：
- llm.chat: 通用LLM对话节点（OpenAI兼容格式）
- llm.markdown_structure: CAPP工艺卡片→结构化Markdown专用节点
"""

import asyncio
import json
import os
from typing import Any, Dict, List

import aiohttp

from src.engine.definitions import NodeDefinition, PortDefinition, PortType
from src.utils.logger import get_logger

_logger = get_logger(__name__)


# =============================================================================
# 工具函数
# =============================================================================

def _run_async(coro):
    """在同步环境中运行异步协程"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import threading
        result = [None, None]
        def _target():
            try:
                result[0] = asyncio.run(coro)
            except Exception as e:
                result[1] = e
        t = threading.Thread(target=_target)
        t.start()
        t.join(timeout=300)
        if result[1]:
            raise result[1]
        return result[0]
    else:
        return asyncio.run(coro)


# =============================================================================
# 1. 通用LLM对话节点
# =============================================================================

async def _chat_completion_async(
    api_key: str,
    base_url: str,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> Dict[str, Any]:
    """调用OpenAI兼容格式的Chat Completion API。"""
    if not api_key:
        return {"success": False, "error": "API密钥未配置", "response": ""}

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            text = await resp.text()
            if resp.status == 200:
                data = json.loads(text)
                choice = data.get("choices", [{}])[0]
                msg = choice.get("message", {})
                content = msg.get("content", "")
                usage = data.get("usage", {})
                return {
                    "success": True,
                    "response": content,
                    "usage": json.dumps(usage, ensure_ascii=False),
                    "finish_reason": choice.get("finish_reason", ""),
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {resp.status}: {text[:500]}",
                    "response": "",
                }


def _execute_llm_chat(
    prompt: str,
    system_prompt: str = "你是一个有用的助手。",
    api_key: str = "",
    base_url: str = "https://api.openai.com/v1",
    model: str = "gpt-4",
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> Dict[str, Any]:
    """执行LLM对话调用。"""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    result = _run_async(_chat_completion_async(
        api_key=api_key,
        base_url=base_url,
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    ))

    _logger.info(f"LLM调用完成: model={model}, success={result.get('success')}")
    return result


llm_chat = NodeDefinition(
    node_type="llm.chat",
    display_name="LLM对话",
    description="调用大语言模型进行对话，支持OpenAI兼容格式API。用于通用文本生成、推理、改写等任务。",
    category="llm",
    icon="🤖",
    inputs=[
        PortDefinition("prompt", PortType.STRING, "用户提示词", widget_type="text_edit"),
        PortDefinition("system_prompt", PortType.STRING, "系统提示词",
                       default="你是一个有用的助手。", required=False, widget_type="text_edit"),
        PortDefinition("api_key", PortType.STRING, "API密钥",
                       default="", required=False),
        PortDefinition("base_url", PortType.STRING, "API地址",
                       default="https://api.openai.com/v1", required=False),
        PortDefinition("model", PortType.STRING, "模型名称",
                       default="gpt-4", required=False, widget_type="text_edit"),
        PortDefinition("temperature", PortType.FLOAT, "温度(0-2)",
                       default=0.7, required=False, widget_type="number"),
        PortDefinition("max_tokens", PortType.INTEGER, "最大Token数",
                       default=4096, required=False, widget_type="number"),
    ],
    outputs=[
        PortDefinition("response", PortType.STRING, "模型回复"),
        PortDefinition("success", PortType.BOOLEAN, "是否成功"),
        PortDefinition("usage", PortType.STRING, "用量信息(JSON)"),
        PortDefinition("error", PortType.STRING, "错误信息"),
    ],
    execute=_execute_llm_chat,
)


# =============================================================================
# 2. CAPP→结构化Markdown专用节点
# =============================================================================

_CAPP_STRUCTURE_SYSTEM_PROMPT = """你是一名航空装配工艺专家。你的任务是将输入的CAPP工艺卡片纯文本整理为结构化的Markdown文档。

整理要求：
1. 保留所有工艺信息，不得遗漏任何工序、参数或注意事项。
2. 使用清晰的Markdown标题层级（# ## ###）组织内容。
3. 将工序步骤编号，每个步骤包含：工序名称、操作内容、工艺参数、质量要求、注意事项。
4. 提取工艺符号（如●、★、▲等）并解释其含义。
5. 对关键数据（力矩值、尺寸、材料牌号等）使用加粗标记。
6. 输出必须是合法的Markdown格式，不要添加任何解释性文字。

输出格式示例：
# 工艺卡片标题

## 基本信息
- **产品型号**: xxx
- **零件名称**: xxx

## 工序列表

### 工序1: xxx
- **操作内容**: xxx
- **工艺参数**: xxx
- **质量要求**: xxx
- **注意事项**: ●表示操作注意点；★表示质量隐患点
"""


def _execute_markdown_structure(
    raw_text: str,
    api_key: str = "",
    base_url: str = "https://api.openai.com/v1",
    model: str = "gpt-4",
    temperature: float = 0.3,
) -> Dict[str, Any]:
    """调用LLM将CAPP原始文本整理为结构化Markdown。"""
    if not raw_text:
        return {"markdown": "", "success": False, "error": "输入文本为空"}

    result = _execute_llm_chat(
        prompt=raw_text,
        system_prompt=_CAPP_STRUCTURE_SYSTEM_PROMPT,
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=temperature,
        max_tokens=8192,
    )

    return {
        "markdown": result.get("response", ""),
        "success": result.get("success", False),
        "usage": result.get("usage", ""),
        "error": result.get("error", ""),
    }


llm_markdown_structure = NodeDefinition(
    node_type="llm.markdown_structure",
    display_name="CAPP结构化Markdown",
    description="调用大语言模型将CAPP工艺卡片原始文本整理为结构化的Markdown文档。专为航空装配工艺设计。",
    category="llm",
    icon="📋",
    inputs=[
        PortDefinition("raw_text", PortType.STRING, "CAPP原始文本", widget_type="text_edit"),
        PortDefinition("api_key", PortType.STRING, "API密钥",
                       default="", required=False),
        PortDefinition("base_url", PortType.STRING, "API地址",
                       default="https://api.openai.com/v1", required=False),
        PortDefinition("model", PortType.STRING, "模型名称",
                       default="gpt-4", required=False, widget_type="text_edit"),
        PortDefinition("temperature", PortType.FLOAT, "温度",
                       default=0.3, required=False, widget_type="number"),
    ],
    outputs=[
        PortDefinition("markdown", PortType.STRING, "结构化Markdown"),
        PortDefinition("success", PortType.BOOLEAN, "是否成功"),
        PortDefinition("usage", PortType.STRING, "用量信息(JSON)"),
        PortDefinition("error", PortType.STRING, "错误信息"),
    ],
    execute=_execute_markdown_structure,
)
