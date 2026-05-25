# -*- coding: utf-8 -*-
"""
智能体扩展插件

严格按照 main.py 中的实现方式，为AI助手提供以下多智能体扩展能力：
- process_agent_tool: 工艺规划 — 查询RAG知识库 → 重排序 → 构建完整prompt → ReActAgent+PlanNotebook生成工序工步文件
- unity_agent_tool: Unity AR — 通过MCP连接Unity编辑器，自动创建AR辅助装配程序
- blender_agent_tool: Blender建模 — 通过MCP连接Blender，完成三维建模任务
- comfyui_agent_tool: 图像生成 — ReActAgent细化提示词后调用ComfyUI生成图像
"""

import asyncio
import base64
import json
import os
from typing import Any, Dict, List

from src.core.permission_manager import Permission, PermissionSet
from src.core.plugin_base import PluginBase
from src.utils.logger import get_logger

try:
    from agentscope.agent import ReActAgent
    from agentscope.model import OpenAIChatModel
    from agentscope.tool import Toolkit, ToolResponse
    from agentscope.mcp import HttpStatefulClient, StdIOStatefulClient
    from agentscope.formatter import OpenAIMultiAgentFormatter, DeepSeekChatFormatter
    from agentscope.message import Msg, TextBlock, ImageBlock, Base64Source
    from agentscope.memory import InMemoryMemory
    from agentscope.plan import PlanNotebook
    from agentscope.tool import write_text_file, view_text_file

    AGENTSCOPE_AVAILABLE = True
except ImportError:
    AGENTSCOPE_AVAILABLE = False

try:
    from pydantic.networks import AnyUrl
except ImportError:
    AnyUrl = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_logger = get_logger(__name__)

TOOL_GROUP_NAME = "agent_extensions"


def _make_response(content: str, success: bool = True) -> Any:
    if content is None:
        content = "(无返回结果)"
    if AGENTSCOPE_AVAILABLE and ToolResponse is not None:
        return ToolResponse(content=[{"type": "text", "text": str(content)}])
    return str(content)


def _run_async(coro):
    """在同步环境中运行异步协程（供tool函数使用）"""
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
        t.join(timeout=310)
        if result[1]:
            raise result[1]
        if result[0] is None:
            return "(执行超时或无返回结果)"
        return result[0]
    else:
        return asyncio.run(coro)


class _APIRequester:
    """与 requester.py 中 APIRequester 完全一致的 HTTP 客户端"""

    def __init__(self, base_url="http://localhost:8000/api/v1",
                 data_dir="./data/",
                 workflow_path="./data/workflow/Flux-Dev-ComfyUI-Workflow.json"):
        self.base_url = base_url
        self.data_dir = data_dir
        import aiohttp

        if workflow_path and os.path.exists(workflow_path):
            with open(workflow_path, encoding="utf-8") as f:
                self.workflow = json.load(f)
        else:
            self.workflow = None

    async def query_embedding(self, text, embed_image_path=None):
        import aiohttp
        url = f"{self.base_url}/embed"
        if embed_image_path:
            with open(embed_image_path, "rb") as f:
                image = f.read()
        data = aiohttp.FormData()
        data.add_field("text", text or "")
        if embed_image_path:
            ext = embed_image_path.split(".")[-1]
            data.add_field("image", image, filename="embed_image.png",
                           content_type="image/png" if ext == "png" else "image/jpeg")
        else:
            data.add_field("image", b"", filename="embed_image.png", content_type="image/png")
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise RuntimeError(f"嵌入请求失败: {response.status}")

    async def query_rerank(self, query_type, query_text, query_image_path,
                           doc_type, doc_text, doc_image_path):
        import aiohttp
        url = f"{self.base_url}/rerank"
        if query_image_path:
            with open(query_image_path, "rb") as f:
                query_image = f.read()
        if doc_image_path:
            with open(doc_image_path, "rb") as f:
                doc_image = f.read()
        data = aiohttp.FormData()
        data.add_field("query_type", query_type)
        if query_type == 'text':
            data.add_field("query_text", query_text if query_text else "")
        else:
            if query_image_path:
                ext = query_image_path.split(".")[-1]
                data.add_field("query_image", query_image, filename="query_image.png",
                               content_type="image/png" if ext == "png" else "image/jpeg")
        data.add_field("document_type", doc_type)
        if doc_type == 'text':
            data.add_field("document_text", doc_text if doc_text else "")
        else:
            if doc_image_path:
                ext = doc_image_path.split(".")[-1]
                data.add_field("document_image", doc_image, filename="doc_image.png",
                               content_type="image/png" if ext == "png" else "image/jpeg")
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise RuntimeError(f"重排序请求失败: {response.status}")

    async def get_image(self, filename):
        import aiohttp
        url = f"{self.base_url}/images/{filename}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    img_dir = os.path.join(self.data_dir, "img")
                    os.makedirs(img_dir, exist_ok=True)
                    with open(os.path.join(img_dir, filename), "wb") as f:
                        f.write(image_data)
                    return image_data
                else:
                    raise RuntimeError(f"获取图片失败: {response.status}")

    async def text_to_image(self, prompt, output_name, negative_prompt="",
                            width=1024, height=1024, steps=20, seed=None,
                            cfg_scale=3.5, sampler_name="dpmpp_2m",
                            scheduler="simple",
                            checkpoint="flux1-dev.safetensors", loras=None):
        import aiohttp
        name_split = output_name.split(".")
        if name_split[-1] not in ["png", "jpg", "jpeg"]:
            name_split.append(".png")
            output_name = "".join(name_split)
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "steps": steps,
            "cfg_scale": cfg_scale,
            "sampler_name": sampler_name,
            "scheduler": scheduler,
            "checkpoint": checkpoint,
        }
        if self.workflow:
            payload["workflow"] = self.workflow
        if seed is not None:
            payload["seed"] = seed
        if loras:
            payload["loras"] = loras
        async with aiohttp.ClientSession() as session:
            async with session.post(
                    f"{self.base_url}/text-to-image",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=300),
            ) as response:
                if response.status == 200:
                    image_data = await response.read()
                    img_dir = os.path.join(self.data_dir, "img")
                    os.makedirs(img_dir, exist_ok=True)
                    with open(os.path.join(img_dir, output_name), "wb") as f:
                        f.write(image_data)
                    return True
                else:
                    error = await response.text()
                    _logger.error(f"文生图失败: {response.status} - {error}")
                    return False


class _MoyuClient:
    """与 database.py 中 MoyuClient 功能一致：Milvus 向量数据库 + APIRequester"""

    def __init__(self, requester: _APIRequester, uri="http://localhost:19530"):
        from pymilvus import MilvusClient
        self._client = MilvusClient(uri=uri)
        self.requester = requester

    def search(self, data, collection_name="rag_embeddings", limit=10,
               output_fields=None, **kwargs):
        return self._client.search(
            collection_name=collection_name,
            data=data,
            limit=limit,
            output_fields=output_fields,
            **kwargs,
        )

    async def get_fused_embeddings(self, text, image_path=None):
        return (await self.requester.query_embedding(text, image_path))['vector']


# ============================================================
#  工具集
# ============================================================

class AgentExtensionTools:
    """智能体扩展工具集 — 严格对应 main.py 中的四个 agent_tool 函数"""

    def __init__(self):
        self._requester: _APIRequester = None
        self._llm_name = os.environ.get("LLM_MODEL_NAME", "deepseek-reasoner")
        self._vlm_name = os.environ.get("VLM_MODEL_NAME", "qwen3-vl-plus")

    def _get_requester(self) -> _APIRequester:
        if self._requester is None:
            self._requester = _APIRequester(
                base_url=os.environ.get("RAG_BASE_URL", "http://localhost:8000/api/v1"),
                data_dir="./data/",
                workflow_path="./data/workflow/Flux-Dev-ComfyUI-Workflow.json",
            )
        return self._requester

    def get_all_tools(self) -> list:
        return [
            self.tool_unity_ar,
            self.tool_blender_model,
            self.tool_generate_process,
            self.tool_generate_image,
            self.tool_extract_json,
            self.tool_query_knowledge_base,
        ]

    # ==================== 1. Unity AR ====================

    def tool_unity_ar(self, task: str, info: str = "{}") -> Any:
        """根据提供的工序和工步信息生成Unity AR辅助装配程序。
        会自动完成：连接Unity MCP、获取实例、添加XR Rig、XR Simulator、主界面、工序组等。

        Args:
            task: 对Unity程序的需求，需要提供包含工序工步的详细描述
            info: 工序工步信息JSON字符串，格式为 {"工序名": ["工步1", "工步2"]}，默认为空

        Returns:
            Unity操作的执行结果
        """
        try:
            result = _run_async(self._unity_ar_async(task, info))
            return _make_response(result)
        except Exception as e:
            return _make_response(f"Unity操作失败: {e}", success=False)

    async def _unity_ar_async(self, task: str, info: str) -> str:
        if not AGENTSCOPE_AVAILABLE:
            return "AgentScope 未安装，无法使用 Unity MCP 功能"

        # 严格对应 main.py unity_agent_tool
        toolkit = Toolkit()
        unity_mcp = HttpStatefulClient(
            name="unity_mcp",
            transport="streamable_http",
            url="http://localhost:8080/mcp",
        )

        try:
            await unity_mcp.connect()
        except Exception as e:
            return f"无法连接 Unity MCP 服务(请确保 Unity 编辑器已启动且 MCP 服务运行中): {e}"

        # 激活当前 unity editor instance
        instances_response = await unity_mcp.session.read_resource(AnyUrl("mcpforunity://instances"))
        instances = json.loads(instances_response.contents[0].text)["instances"]
        if not instances:
            await unity_mcp.close()
            return "未找到运行中的 Unity 编辑器实例"
        instance_hash = instances[0]["hash"]
        _logger.info(f"Unity instance hash: {instance_hash}")
        await unity_mcp.session.call_tool("set_active_instance", {"instance": instance_hash})

        custom_tools_response = await unity_mcp.session.read_resource(AnyUrl("mcpforunity://custom-tools"))
        custom_tools = json.loads(custom_tools_response.contents[0].text)["data"]["tools"]

        useful_tools = ["addXRRig", "addXRSimulator", "addMainCanvas", "addProcess"]
        custom_tools = [tool for tool in custom_tools if tool["name"] in useful_tools]
        _logger.info(f"Unity custom tools: {custom_tools}")

        await toolkit.register_mcp_client(unity_mcp)

        info_dict = json.loads(info) if isinstance(info, str) else info

        unity_agent = ReActAgent(
            name="unity_agent",
            sys_prompt=f"""
        你是顶尖的一个Unity AR程序开发助手,你的任务是使用工具直接帮助用户完成AR程序的开发，你可以使用的custom tools 包括{custom_tools},
        当你使用custom tools中的工具时，不要直接使用，必须通过调用execute_custom_tool工具来使用，execute_custom_tool工具的使用格式如下：
        {{
            "type": "tool_use",
            "name": "execute_custom_tool",
            "input": {{
                "tool_name": "自定义工具名",
                "parameters": {{ 自定义工具参数字典，注意需要传入字典，而不是字符串 }}
            }}
        }}
        一个常用的AR应用初始化流程如下，请直接使用工具一步一步执行并检查每一步的执行结果：
        1.检查场景中是否有XR Rig对象，若不存在则使用自定义工具向场景中添加一个XR Rig对象
        2.检查场景中是否有XR Simulator对象，若不存在则添加一个XR Simulator对象使用户可以在编辑器中模拟XR操作
        3.检查场景中是否有MainCanvas，若不存在则添加一个主界面
        4.根据工序工步信息向主界面中添加工序组
        5.在unity中运行AR程序
        """,
            model=OpenAIChatModel(
                model_name=self._llm_name,
                api_key=os.environ["LLM_API_KEY"],
                stream=True,
                enable_thinking=False,
                client_kwargs={"base_url": os.environ["LLM_BASE_URL"]},
                generate_kwargs={"max_tokens": 10240, "max_completion_tokens": 10240},
            ),
            formatter=DeepSeekChatFormatter(),
            toolkit=toolkit,
            memory=InMemoryMemory(),
            max_iters=60
        )

        msg = Msg(
            name="user",
            content=f"请完成以下任务：{task}，可用的工艺信息为：{info_dict}",
            role="user",
        )

        msg_res = await unity_agent(msg)
        await unity_mcp.close()

        if msg_res is None:
            return "Unity Agent 未返回结果"
        blocks = msg_res.get_content_blocks("text") if hasattr(msg_res, 'get_content_blocks') else []
        if blocks:
            return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in blocks)
        return str(msg_res.content) if msg_res.content else "Unity Agent 未返回内容"

    # ==================== 2. Blender 建模 ====================

    def tool_blender_model(self, task: str) -> Any:
        """根据需求完成Blender建模

        Args:
            task: 对Blender模型的需求描述

        Returns:
            Blender操作的执行结果
        """
        try:
            result = _run_async(self._blender_model_async(task))
            return _make_response(result)
        except Exception as e:
            return _make_response(f"Blender操作失败: {e}", success=False)

    async def _blender_model_async(self, task: str) -> str:
        if not AGENTSCOPE_AVAILABLE:
            return "AgentScope 未安装，无法使用 Blender MCP 功能"

        # 严格对应 main.py blender_agent_tool
        toolkit = Toolkit()
        blender_mcp = StdIOStatefulClient(
            name="blender_mcp",
            command="uvx",
            args=["blender-mcp"],
        )

        try:
            await blender_mcp.connect()
        except Exception as e:
            return f"无法连接 Blender MCP 服务(请确保 Blender 已启动且插件已安装): {e}"

        await toolkit.register_mcp_client(blender_mcp)

        blender_agent = ReActAgent(
            name="blender_agent",
            sys_prompt=f"""你是一个blender建模助手,你的任务是帮助用户在blender应用中完成三维建模,注意完成建模后从多个视图进行检查
        """,
            model=OpenAIChatModel(
                model_name=self._llm_name,
                api_key=os.environ["LLM_API_KEY"],
                stream=True,
                enable_thinking=False,
                client_kwargs={"base_url": os.environ["LLM_BASE_URL"]},
                generate_kwargs={"max_tokens": 10240, "max_completion_tokens": 10240},
            ),
            formatter=DeepSeekChatFormatter(),
            toolkit=toolkit,
            memory=InMemoryMemory(),
            max_iters=60
        )

        msg = Msg(name="user", content=task, role="user")
        msg_res = await blender_agent(msg)
        await blender_mcp.close()

        if msg_res is None:
            return "Blender Agent 未返回结果"
        blocks = msg_res.get_content_blocks("text") if hasattr(msg_res, 'get_content_blocks') else []
        if blocks:
            return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in blocks)
        return str(msg_res.content) if msg_res.content else "Blender Agent 未返回内容"

    # ==================== 3. 工艺规划 ====================

    def tool_generate_process(
        self,
        task: str,
        image_path: str = "",
        collection_name: str = "process",
        limit: int = 5,
    ) -> Any:
        """根据任务要求，查询向量数据库，rerank重排序后，由工艺规划Agent生成完整的工序工步文件。
        Agent会使用PlanNotebook制定计划，并使用write_text_file工具将工序工步写入JSON文件。

        Args:
            task: 任务要求（如"创建一份反推堵盖的安装工艺文件"）
            image_path: 参考图像路径(可选)
            collection_name: 向量数据库名称
            limit: 查询向量条数

        Returns:
            工艺规划的执行结果
        """
        try:
            result = _run_async(
                self._process_agent_async(task, image_path or None, collection_name, limit)
            )
            return _make_response(result)
        except Exception as e:
            return _make_response(f"工艺规划失败: {e}", success=False)

    async def _process_agent_async(
        self,
        task: str,
        image_path: str,
        collection_name: str,
        limit: int = 5,
    ) -> str:
        """
        严格对应 main.py process_agent_tool 的完整流程：
        1. 查询向量数据库获取嵌入
        2. Milvus 搜索
        3. 对每条结果调用 rerank 重排序
        4. 按重排序分数排序
        5. 构建包含知识库结果+图片+JSON模板的完整prompt
        6. 创建带 PlanNotebook 的 ReActAgent 执行规划
        """
        if not AGENTSCOPE_AVAILABLE:
            return "AgentScope 未安装，无法使用工艺规划功能"

        requester = self._get_requester()
        milvus_uri = os.environ.get("MILVUS_BASE_URL", "http://localhost:19530")
        client = _MoyuClient(requester, milvus_uri)

        # ---- 1. 查询向量数据库 ----
        query_vector = await client.get_fused_embeddings(text=task, image_path=image_path)

        query_res = client.search(
            data=[query_vector],
            collection_name=collection_name,
            limit=limit,
            output_fields=["text", "subject", "path", "type"],
        )

        # ---- 2. rerank 重排序 ----
        for i in range(len(query_res[0])):
            entity = query_res[0][i]['entity']
            if entity['type'] == "text":
                res = await requester.query_rerank(
                    query_type="text", query_text=task, query_image_path=None,
                    doc_type="text", doc_text=entity['text'], doc_image_path=None,
                )
                query_res[0][i]['score'] = res["score"]
            elif entity['type'] == "image":
                # 获取图片数据
                img_path = f"./data/img/{entity['path']}"
                if not os.path.exists(img_path):
                    image_data = await requester.get_image(entity['path'])
                res = await requester.query_rerank(
                    query_type="text", query_text=task, query_image_path=None,
                    doc_type="image", doc_text=None,
                    doc_image_path=f"./data/img/{entity['path']}",
                )
                query_res[0][i]['score'] = res["score"]

        query_res[0].sort(key=lambda x: x['score'], reverse=True)

        # ---- 3. 构建知识库结果消息 ----
        rerank_num = limit
        query_content_list = []

        for i in range(rerank_num):
            entity = query_res[0][i]['entity']
            if entity['type'] == "text":
                query_content_list.append(
                    TextBlock(type="text", text=f"{i + 1}.{entity['text']}(来源为{entity['path']})\n")
                )
            elif entity['type'] == "image":
                # 获取图片数据
                img_path = f"./data/img/{entity['path']}"
                if not os.path.exists(img_path):
                    image_data = await requester.get_image(entity['path'])
                else:
                    image_data = open(img_path, "rb").read()
                query_content_list.append(
                    TextBlock(type="text", text=f"{i + 1}.{entity['text']}(来源为{entity['path']})\n")
                )
                query_content_list.append(
                    ImageBlock(type="image", source=Base64Source(
                        type="base64",
                        media_type="image/png"
                        if entity['path'] and entity['path'].split(".")[-1] == "png"
                        else "image/jpeg",
                        data=base64.b64encode(image_data).decode("utf-8"),
                    ))
                )
                query_content_list.append(
                    TextBlock(type="text", text=f"{i + 1}.{entity['text']}(来源为{entity['path']})\n")
                )

        # ---- 4. 构建完整prompt（知识库结果 + 用户问题 + 工序/工步JSON模板） ----
        msg = Msg(
            name="user",
            role="user",
            content=[TextBlock(type="text", text="知识库中搜索有如下结果\n")] +
                    query_content_list +
                    [
                        TextBlock(type="text",
                                  text=f"用户的问题是:{task}, 请你根据知识库结果回答用户的问题，在你回答用户问题时，需要过滤掉搜索中无关的项"),
                        TextBlock(type="text", text="对于装配工序请使用以下json格式模板进行回答：\n"),
                        TextBlock(type="text", text="""
                               {
                                    "info":{
                                        "processID":"工序号",
                                        "processName":"工序名称",
                                        "processCharacteristic":"工序特征",
                                        "processType":"工序类型枚举:assemble/measure/postprocess",
                                        "note":"工序备注"
                                    },
                                    "steps":{
                                        "工步名称":"工步文件路径.json"
                                    },
                                    "processResources":[
                                        {
                                            "resourceName":"工艺资源名称",
                                            "resourceID":"工艺资源号",
                                            "specification":"工艺资源规格",
                                            "resourceType":"工艺资源类型枚举:tool/people",
                                            "model":"工艺资源模型路径.step"
                                        }
                                    ],
                                    "parts":[
                                        {
                                            "partID":"装配件代号",
                                            "partName":"装配件名称",
                                            "partNum":1,
                                            "action":"装配动作",
                                            "model":"装配件模型路径.step"
                                        }
                                    ]
                                }
                               """),
                        TextBlock(type="text", text="对于装配工步请使用以下json格式模板进行回答：\n"),
                        TextBlock(type="text", text="""
                               {
                                    "info":{
                                        "stepID":"工步号",
                                        "stepName":"工步名称"
                                    },
                                    "stepContent":[
                                        {
                                            "title":"工步基本内容标题",
                                            "detail":"工步基本内容细节1"
                                        },
                                        {
                                            "title":"测量工步内容标题",
                                            "detail": "测量工步内容细节",
                                            "target":"测量指标",
                                            "inspection_method":"检验方式",
                                            "measure_method":"测量方法",
                                            "times":1,
                                            "resource_name":"资源名称",
                                            "resource_id":"资源代号",
                                            "resource_specification":"资源规格",
                                            "digital":false
                                        }
                                    ],
                                    "annex":"工步附件路径.*",
                                    "animation":"工步装配动画"
                                }
                               """),
                    ],
        )

        # ---- 5. 创建带 PlanNotebook 的工艺规划 Agent ----
        toolkit = Toolkit()
        toolkit.register_tool_function(write_text_file)
        toolkit.register_tool_function(view_text_file)

        plan_notebook = PlanNotebook()

        process_agent = ReActAgent(
            name="process_agent",
            sys_prompt=f"""
        你是一个工艺规划师,你的任务是根据查询到的知识帮助用户进行工艺规划
        在你进行规划前，请先制定一个工艺规划计划，并使用plan工具创建一个工艺编写任务列表,并逐步执行直至计划完成才能结束规划
        每当你完成一个工序或工步文件编写后请按照json模板输出将其完整写入当前文件夹下的文件内进行保存，注意输出文件结构的可读性
        同时你需要编写完成所有规划任务后再结束，请确保所有工序工步均保存，不能提前退出
        """,
            model=OpenAIChatModel(
                model_name=self._vlm_name,
                api_key=os.environ["VLM_API_KEY"],
                stream=True,
                enable_thinking=False,
                client_kwargs={"base_url": os.environ["VLM_BASE_URL"]},
                generate_kwargs={"max_tokens": 30720, "max_completion_tokens": 30720},
            ),
            formatter=OpenAIMultiAgentFormatter(),
            toolkit=toolkit,
            memory=InMemoryMemory(),
            plan_notebook=plan_notebook,
            max_iters=60
        )

        # ---- 6. 执行 ----
        msg_res = await process_agent(msg)
        content = msg_res.get_content_blocks("text") if msg_res is not None and hasattr(msg_res, 'get_content_blocks') else None
        if not content:
            content = process_agent.memory.content if hasattr(process_agent, 'memory') and process_agent.memory else []

        if not content:
            return "工艺规划 Agent 未返回结果"
        return "".join(
            each["text"] if isinstance(each, dict) else str(each) for each in content
        )

    # ==================== 4. ComfyUI 图像生成 ====================

    def tool_generate_image(self, task: str) -> Any:
        """根据需求生成图片资源。Agent会自动细化提示词后调用ComfyUI API生成图像。
        图像默认为2维工程图风格，以指示为主。

        Args:
            task: 对图片资源的需求描述

        Returns:
            图像生成结果
        """
        try:
            result = _run_async(self._comfyui_agent_async(task))
            return _make_response(result)
        except Exception as e:
            return _make_response(f"图像生成失败: {e}", success=False)

    async def _comfyui_agent_async(self, task: str) -> str:
        """
        严格对应 main.py comfyui_agent_tool:
        创建内部 generate_image_from_text 工具函数，注册到 toolkit，
        然后由 ReActAgent 细化提示词后调用。
        """
        if not AGENTSCOPE_AVAILABLE:
            return "AgentScope 未安装，无法使用图像生成功能"

        requester = self._get_requester()

        # 内部工具函数 — 与 main.py 完全一致
        async def generate_image_from_text(prompt: str, output_name: str):
            """
            调用API生成所需的图片

            :param prompt: 生成图片的正向提示词
            :param output_name: 生成图片的保存名称
            :return:
            """
            success = await requester.text_to_image(prompt, output_name)
            return ToolResponse(content=[
                TextBlock(type="text", text=f"图片生成{'成功' if success else '失败'}")
            ])

        toolkit = Toolkit()
        toolkit.register_tool_function(generate_image_from_text)

        comfyui_agent = ReActAgent(
            name="comfyui_agent",
            sys_prompt=f"""
        你是一个ai图片生成助手,你的任务是根据用户的描述，合理细化生成图片细节要求，并调用api进行生成
        注意：请将用户描述往符合图像生成模型要求的方向进行细化，使其包含必要的细节，及要求
        图像应该为2维工程图风格，以指示为主，尽量不要出现人物等元素
        """,
            model=OpenAIChatModel(
                model_name=self._llm_name,
                api_key=os.environ["LLM_API_KEY"],
                stream=True,
                enable_thinking=False,
                client_kwargs={"base_url": os.environ["LLM_BASE_URL"]},
                generate_kwargs={"max_tokens": 4096, "max_completion_tokens": 4096},
            ),
            formatter=DeepSeekChatFormatter(),
            toolkit=toolkit,
            memory=InMemoryMemory(),
        )

        msg = Msg(name="user", content=task, role="user")
        msg_res = await comfyui_agent(msg)

        if msg_res is None:
            return "ComfyUI Agent 未返回结果"
        blocks = msg_res.get_content_blocks("text") if hasattr(msg_res, 'get_content_blocks') else []
        if blocks:
            return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in blocks)
        return str(msg_res.content) if msg_res.content else "ComfyUI Agent 未返回内容"

    # ==================== 5. 提取JSON ====================

    def tool_extract_json(self, text: str) -> Any:
        """从混合文本中提取JSON对象

        Args:
            text: 包含JSON的混合文本

        Returns:
            提取到的JSON内容
        """
        group = []
        result_parts = []
        bracket_count = 0
        for ch in text:
            if ch == "{":
                bracket_count += 1
            elif ch == "}":
                bracket_count -= 1
            if bracket_count > 0:
                group.append(ch)
            elif bracket_count == 0 and ch == "}":
                group.append(ch)
                result_parts.append("".join(group))
                group = []
        combined = "".join(result_parts)
        if combined:
            try:
                parsed = json.loads(combined)
                return _make_response(json.dumps(parsed, ensure_ascii=False, indent=2))
            except json.JSONDecodeError:
                return _make_response(combined)
        return _make_response("未找到JSON内容")

    # ==================== 6. 查询知识库 ====================

    def tool_query_knowledge_base(
        self,
        query: str,
        collection_name: str = "process",
        limit: int = 5,
    ) -> Any:
        """查询向量知识库获取相关文档（仅查询，不生成）

        Args:
            query: 查询文本
            collection_name: 集合名称
            limit: 返回条数

        Returns:
            搜索结果列表
        """
        try:
            result = _run_async(
                self._query_knowledge_base_async(query, collection_name, limit)
            )
            return _make_response(json.dumps(result, ensure_ascii=False, indent=2))
        except Exception as e:
            return _make_response(f"知识库查询失败: {e}", success=False)

    async def _query_knowledge_base_async(
        self,
        query: str,
        collection_name: str,
        limit: int,
    ) -> List[Dict]:
        requester = self._get_requester()
        milvus_uri = os.environ.get("MILVUS_BASE_URL", "http://localhost:19530")
        client = _MoyuClient(requester, milvus_uri)

        query_vector = await client.get_fused_embeddings(text=query)
        search_res = client.search(
            data=[query_vector],
            collection_name=collection_name,
            limit=limit,
            output_fields=["text", "subject", "path", "type"],
        )

        results = []
        for hit in search_res[0]:
            entity = hit["entity"]
            results.append({
                "score": round(hit["distance"], 4),
                "text": entity.get("text", "")[:500],
                "path": entity.get("path", ""),
                "type": entity.get("type", ""),
            })
        return results


# ============================================================
#  插件类
# ============================================================

class AgentExtensionsPlugin(PluginBase):
    """智能体扩展插件"""

    name = "agent_extensions"
    version = "1.0.0"
    description = "为AI助手提供多智能体扩展能力（工艺规划、Unity AR、Blender建模、图像生成等）"
    author = "OfficeTools"

    permissions = PermissionSet.from_list([Permission.AGENT_TOOL, Permission.NETWORK])

    def __init__(self):
        super().__init__()
        self._tools: AgentExtensionTools = None

    def on_enable(self, context) -> None:
        self._tools = AgentExtensionTools()
        tools = self._tools.get_all_tools()
        context.tool_registry.register(TOOL_GROUP_NAME, tools)
        _logger.info(f"AgentExtensionsPlugin 已启用，注册了 {len(tools)} 个工具")

    def on_disable(self, context=None) -> None:
        if context is not None:
            context.tool_registry.unregister(TOOL_GROUP_NAME)
        self._tools = None
        _logger.info("AgentExtensionsPlugin 已禁用")


# 插件元数据（供 PluginManager 发现）
plugin_class = AgentExtensionsPlugin
