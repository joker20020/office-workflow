# -*- coding: utf-8 -*-
"""
文本处理节点定义

提供：
- text.clean: 文本清洗（去除不可见字符）
- text.generate_questions: 基于结构化Markdown生成询问型/请求型问题
- text.augment: 文本增强（近义词替换、随机删除、回译、LLM改写）
- text.save_jsonl: 保存数据为JSONL文件
"""

import json
import os
import random
import re
import unicodedata
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
    import asyncio
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
        t.join(timeout=120)
        if result[1]:
            raise result[1]
        return result[0]
    else:
        return asyncio.run(coro)


# =============================================================================
# 1. 文本清洗节点
# =============================================================================

def _execute_text_clean(
    text: str,
    preserve_linebreaks: bool = True,
    normalize_whitespace: bool = True,
) -> Dict[str, Any]:
    """清洗文本，去除不可见字符和控制字符。

    - 去除零宽字符、控制字符（除换行/回车外）
    - 可选保留换行符
    - 规范化连续空白
    """
    if not text:
        return {"cleaned_text": "", "removed_count": 0}

    original_len = len(text)

    # 1. 去除零宽字符
    zero_width_chars = '\u200b\u200c\u200d\ufeff\u2060\u180e'
    for ch in zero_width_chars:
        text = text.replace(ch, '')

    # 2. NFC 规范化
    text = unicodedata.normalize('NFC', text)

    # 3. 去除控制字符，保留换行/回车/制表符
    cleaned = []
    for ch in text:
        cat = unicodedata.category(ch)
        if cat.startswith('C') and ch not in '\n\r\t':
            continue
        cleaned.append(ch)
    text = ''.join(cleaned)

    # 4. 是否保留换行
    if not preserve_linebreaks:
        text = text.replace('\n', ' ').replace('\r', ' ')

    # 5. 规范化连续空白
    if normalize_whitespace:
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n+', '\n', text)
        text = text.strip()

    removed = original_len - len(text)
    _logger.info(f"文本清洗完成，去除 {removed} 个字符")
    return {"cleaned_text": text, "removed_count": removed}


text_clean = NodeDefinition(
    node_type="text.clean",
    display_name="文本清洗",
    description="去除文本中的不可见字符、零宽字符和控制字符，保留有效内容",
    category="text",
    icon="🧹",
    inputs=[
        PortDefinition("text", PortType.STRING, "原始文本", widget_type="text_edit"),
        PortDefinition("preserve_linebreaks", PortType.BOOLEAN, "保留换行符",
                       default=True, required=False, widget_type="checkbox"),
        PortDefinition("normalize_whitespace", PortType.BOOLEAN, "规范化连续空白",
                       default=True, required=False, widget_type="checkbox"),
    ],
    outputs=[
        PortDefinition("cleaned_text", PortType.STRING, "清洗后文本"),
        PortDefinition("removed_count", PortType.INTEGER, "去除字符数"),
    ],
    execute=_execute_text_clean,
)


# =============================================================================
# 2. 问题生成节点
# =============================================================================

# 询问型问题模板（基于装配知识）
_INQUIRY_TEMPLATES = [
    "{entity}的装配要求是什么？",
    "{entity}在工艺文件中如何规定？",
    "请说明{entity}的操作规范。",
    "{entity}的拧紧力矩是多少？",
    "工艺文件中{entity}的符号含义是什么？",
    "{entity}的检验标准有哪些？",
    "如何正确执行{entity}的装配操作？",
    "{entity}需要注意哪些质量隐患？",
    "{entity}的工序顺序是什么？",
    "{entity}和{related}的装配关系如何？",
]

# 请求型问题模板
_REQUEST_TEMPLATES = [
    "请生成{entity}的工序内容。",
    "请给出{entity}的装配操作说明。",
    "请输出{entity}的工艺步骤。",
    "请根据装配要求生成{entity}的清理工序。",
    "请生成{entity}的打印记工序内容，包括产品号、零件号和批次号。",
    "请提供{entity}的拧紧工序说明。",
    "请生成{entity}的检验工序内容。",
    "请根据工艺文件生成{entity}的对称拧紧操作说明。",
]


def _extract_entities_from_markdown(md: str) -> List[str]:
    """从Markdown中提取实体（标题、关键词）。"""
    entities = []
    # 提取标题
    for line in md.split('\n'):
        line = line.strip()
        if line.startswith('#'):
            title = line.lstrip('#').strip()
            if title and len(title) < 50:
                entities.append(title)
        # 提取加粗关键词
        for match in re.finditer(r'\*\*(.+?)\*\*', line):
            word = match.group(1).strip()
            if 2 < len(word) < 30:
                entities.append(word)
    # 去重并保持顺序
    seen = set()
    unique = []
    for e in entities:
        if e not in seen:
            seen.add(e)
            unique.append(e)
    return unique[:20]  # 最多20个实体


def _execute_generate_questions(
    markdown_text: str,
    question_type: str = "全部",
    count_per_type: int = 5,
) -> Dict[str, Any]:
    """基于Markdown内容生成询问型和请求型问题。"""
    if not markdown_text:
        return {"questions": [], "question_json": "[]"}

    entities = _extract_entities_from_markdown(markdown_text)
    if not entities:
        entities = ["该工序"]

    questions = []
    rng = random.Random(42)  # 固定种子保证可复现

    def _pick(templates, label, limit):
        count = 0
        for i, entity in enumerate(entities):
            if count >= limit:
                break
            related = entities[(i + 1) % len(entities)] if len(entities) > 1 else "相关工序"
            tpl = rng.choice(templates)
            q = tpl.format(entity=entity, related=related)
            questions.append({
                "question": q,
                "type": label,
                "source_entity": entity,
                "answer": "",  # 正样本答案在后续由LLM或人工填充
            })
            count += 1

    if question_type in ("全部", "询问型"):
        _pick(_INQUIRY_TEMPLATES, "询问型", count_per_type)

    if question_type in ("全部", "请求型"):
        _pick(_REQUEST_TEMPLATES, "请求型", count_per_type)

    _logger.info(f"生成 {len(questions)} 个问题")
    return {
        "questions": questions,
        "question_json": json.dumps(questions, ensure_ascii=False, indent=2),
    }


text_generate_questions = NodeDefinition(
    node_type="text.generate_questions",
    display_name="问题生成",
    description="基于结构化Markdown内容生成询问型（知识查询）和请求型（生成需求）问题",
    category="text",
    icon="❓",
    inputs=[
        PortDefinition("markdown_text", PortType.STRING, "结构化Markdown文本", widget_type="text_edit"),
        PortDefinition("question_type", PortType.STRING, "问题类型",
                       default="全部", required=False, widget_type="dropdown"),
        PortDefinition("count_per_type", PortType.INTEGER, "每种类型生成数量",
                       default=5, required=False, widget_type="number"),
    ],
    outputs=[
        PortDefinition("questions", PortType.LIST, "问题列表（字典）"),
        PortDefinition("question_json", PortType.STRING, "问题JSON文本"),
    ],
    execute=_execute_generate_questions,
)


# =============================================================================
# 3. 文本增强节点
# =============================================================================

# 简单近义词映射（装配领域常用词）
_SYNONYMS = {
    "应当": ["应该", "应", "须"],
    "如何": ["怎么", "怎样", "用什么方式"],
    "拧紧": ["旋紧", "紧固", "锁紧"],
    "装配": ["组装","安装"],
    "清理": ["清除", "清洁", "去除"],
    "生成": ["给出", "输出", "提供"],
    "表示": ["代表", "意味着", "指"],
    "规范": ["规定", "标准", "要求"],
    "工序": ["步骤", "流程", "工艺步骤"],
    "注意": ["留意", "关注", "重视"],
    "所有": ["全部", "各个", "一切"],
    "内部": ["内侧", "里面"],
    "多余物": ["杂物", "残留物", "异物"],
}


def _synonym_replace(text: str, replace_ratio: float = 0.3) -> str:
    """随机近义词替换。"""
    rng = random.Random()
    for word, synonyms in _SYNONYMS.items():
        if word in text and rng.random() < replace_ratio:
            text = text.replace(word, rng.choice(synonyms), 1)
    return text


def _random_delete(text: str, delete_ratio: float = 0.05) -> str:
    """随机字删除（不影响核心语义的虚词/重复词）。"""
    chars = list(text)
    rng = random.Random()
    # 优先删除的字符：的、了、请、等虚词
    optional_chars = set("的了请呢吗吧")
    to_delete = []
    for i, ch in enumerate(chars):
        if ch in optional_chars and rng.random() < delete_ratio * 3:
            to_delete.append(i)
        elif rng.random() < delete_ratio:
            to_delete.append(i)
    result = [ch for i, ch in enumerate(chars) if i not in to_delete]
    return ''.join(result)


def _back_translate(text: str, api_key: str = "", base_url: str = "") -> str:
    """回译：中→英→中。若未配置API则返回简单句式改写。"""
    if not api_key or not base_url:
        # 无API时做简单句式改写
        replacements = [
            ("应该如何", "应当怎么"),
            ("请生成", "生成"),
            ("请给出", "给出"),
            ("是什么", "的含义是什么"),
            ("如何规定", "的规定是什么"),
        ]
        for old, new in replacements:
            if old in text:
                return text.replace(old, new, 1)
        return text

    async def _translate(source: str, target: str, q: str) -> str:
        # 使用通用翻译API或LLM进行翻译
        # 这里使用简化的LLM调用方式
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": f"You are a translator. Translate the following text to {target}. Output only the translation, no explanations."},
                {"role": "user", "content": q},
            ],
            "temperature": 0.3,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{base_url}/chat/completions", headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()
                return q

    try:
        en = _run_async(_translate("zh", "en", text))
        zh = _run_async(_translate("en", "zh", en))
        return zh
    except Exception as e:
        _logger.warning(f"回译失败: {e}")
        return text


def _llm_rephrase(text: str, api_key: str = "", base_url: str = "") -> str:
    """使用LLM对查询进行改写，保持语义不变。"""
    if not api_key or not base_url:
        return text

    async def _call() -> str:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": "你是一个文本改写助手。请对用户的查询进行改写，保持原意不变但改变表达方式。只输出改写后的文本，不要解释。"},
                {"role": "user", "content": f"改写以下查询：{text}"},
            ],
            "temperature": 0.7,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{base_url}/chat/completions", headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()
                return text

    try:
        return _run_async(_call())
    except Exception as e:
        _logger.warning(f"LLM改写失败: {e}")
        return text


def _execute_text_augment(
    text: Any,
    methods: str = "全部",
    augment_count: int = 3,
    api_key: str = "",
    base_url: str = "",
) -> Dict[str, Any]:
    """对文本进行增强，生成语义等价的变体。

    支持两种输入：
    - str: 单条文本
    - list[dict]: 问题列表（对每个元素的'question'字段进行增强）
    """
    if not text:
        return {"augmented_texts": [], "augmented_json": "[]"}

    # 统一为列表处理
    if isinstance(text, list):
        items = text
        is_batch = True
    elif isinstance(text, str):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                items = parsed
                is_batch = True
            else:
                items = [{"question": text}]
                is_batch = False
        except json.JSONDecodeError:
            items = [{"question": text}]
            is_batch = False
    else:
        items = [{"question": str(text)}]
        is_batch = False

    all_results = []

    for item in items:
        if isinstance(item, dict):
            raw = item.get("question", "")
            meta = {k: v for k, v in item.items() if k != "question"}
        else:
            raw = str(item)
            meta = {}

        if not raw:
            continue

        results = []
        used = {raw}

        def _add(t: str, method: str):
            if t and t not in used:
                used.add(t)
                entry = {"text": t, "method": method, "original": raw}
                entry.update(meta)
                results.append(entry)

        if methods in ("全部", "近义词替换"):
            t = _synonym_replace(raw)
            _add(t, "近义词替换")

        if methods in ("全部", "随机删除"):
            for _ in range(min(augment_count, 3)):
                t = _random_delete(raw)
                _add(t, "随机删除")

        if methods in ("全部", "回译"):
            t = _back_translate(raw, api_key, base_url)
            _add(t, "回译")

        if methods in ("全部", "LLM改写") and api_key:
            for _ in range(min(augment_count, 2)):
                t = _llm_rephrase(raw, api_key, base_url)
                _add(t, "LLM改写")

        all_results.extend(results)

    _logger.info(f"文本增强完成，共处理 {len(items)} 条，生成 {len(all_results)} 条变体")
    return {
        "augmented_texts": all_results,
        "augmented_json": json.dumps(all_results, ensure_ascii=False, indent=2),
    }


text_augment = NodeDefinition(
    node_type="text.augment",
    display_name="文本增强",
    description="对查询文本进行增强：近义词替换、随机字删除、回译、LLM改写，保持语义不变",
    category="text",
    icon="✨",
    inputs=[
        PortDefinition("text", PortType.STRING, "原始查询文本", widget_type="text_edit"),
        PortDefinition("methods", PortType.STRING, "增强方法",
                       default="全部", required=False, widget_type="dropdown"),
        PortDefinition("augment_count", PortType.INTEGER, "每种方法生成数量",
                       default=3, required=False, widget_type="number"),
        PortDefinition("api_key", PortType.STRING, "API密钥(回译/LLM改写可选)",
                       default="", required=False),
        PortDefinition("base_url", PortType.STRING, "API地址(可选)",
                       default="", required=False),
    ],
    outputs=[
        PortDefinition("augmented_texts", PortType.LIST, "增强文本列表"),
        PortDefinition("augmented_json", PortType.STRING, "增强结果JSON"),
    ],
    execute=_execute_text_augment,
)


# =============================================================================
# 4. 保存JSONL节点
# =============================================================================

def _execute_save_jsonl(
    data: Any,
    file_path: str,
    append: bool = False,
) -> Dict[str, Any]:
    """将数据保存为JSONL格式文件。"""
    if not file_path:
        return {"success": False, "saved_path": "", "error": "文件路径为空"}

    try:
        # 确保目录存在
        dir_path = os.path.dirname(file_path) or "."
        os.makedirs(dir_path, exist_ok=True)

        mode = "a" if append else "w"
        encoding = "utf-8"

        # 统一处理为列表
        if isinstance(data, str):
            try:
                items = json.loads(data)
                if not isinstance(items, list):
                    items = [items]
            except json.JSONDecodeError:
                items = [{"text": data}]
        elif isinstance(data, list):
            items = data
        else:
            items = [data]

        written = 0
        with open(file_path, mode, encoding=encoding) as f:
            for item in items:
                line = json.dumps(item, ensure_ascii=False)
                f.write(line + "\n")
                written += 1

        _logger.info(f"JSONL保存成功: {file_path} ({written} 条)")
        return {"success": True, "saved_path": file_path, "count": written}
    except Exception as e:
        _logger.error(f"JSONL保存失败: {e}")
        return {"success": False, "saved_path": "", "error": str(e)}


text_save_jsonl = NodeDefinition(
    node_type="text.save_jsonl",
    display_name="保存JSONL",
    description="将列表或字典数据保存为JSONL格式文件，支持追加模式",
    category="text",
    icon="💾",
    inputs=[
        PortDefinition("data", PortType.ANY, "数据（列表/字典/JSON字符串）"),
        PortDefinition("file_path", PortType.STRING, "文件路径", widget_type="file_picker"),
        PortDefinition("append", PortType.BOOLEAN, "追加模式",
                       default=False, required=False, widget_type="checkbox"),
    ],
    outputs=[
        PortDefinition("success", PortType.BOOLEAN, "是否成功"),
        PortDefinition("saved_path", PortType.STRING, "保存路径"),
        PortDefinition("count", PortType.INTEGER, "写入条数"),
    ],
    execute=_execute_save_jsonl,
)
