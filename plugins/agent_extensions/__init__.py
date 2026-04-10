# -*- coding: utf-8 -*-
"""
智能体扩展插件

为AI助手提供多智能体扩展能力：
- Unity AR 工具：通过 MCP 连接 Unity 编辑器，自动创建 AR 辅助装配程序
- Blender 建模工具：通过 MCP 连接 Blender，完成三维建模任务
- 工艺规划工具：基于RAG知识库生成工艺文件
- 图像生成工具：通过ComfyUI生成图像资源
- 文本提取工具：从混合文本中提取JSON

启用此插件后，AI助手将获得以上扩展能力。
"""

import asyncio
import json
import os
from typing import Any, Dict, List

from src.core.permission_manager import Permission, PermissionSet
from src.core.plugin_base import PluginBase
from src.utils.logger import get_logger

try:
    from agentscope.tool import ToolResponse
    from agentscope.message import Msg, TextBlock

    AGENTSCOPE_AVAILABLE = True
except ImportError:
    AGENTSCOPE_AVAILABLE = False
    ToolResponse = None

_logger = get_logger(__name__)

TOOL_GROUP_NAME = "agent_extensions"


def _make_response(content: str, success: bool = True) -> Any:
    if AGENTSCOPE_AVAILABLE and ToolResponse is not None:
        return ToolResponse(content=[{"type": "text", "text": content}])
    return content


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
        t.join(timeout=310)
        if result[1]:
            raise result[1]
        return result[0]
    else:
        return asyncio.run(coro)


class AgentExtensionTools:
    """智能体扩展工具集"""

    def get_all_tools(self) -> list:
        return [
            self.tool_unity_ar,
            self.tool_blender_model,
            self.tool_generate_process,
            self.tool_generate_image,
            self.tool_extract_json,
            self.tool_query_knowledge_base,
        ]

    def tool_unity_ar(
        self,
        task: str,
        info: str = "{}",
    ) -> Any:
        """连接Unity编辑器，通过MCP自动创建AR辅助装配程序。
        会自动完成：添加XR Rig、XR Simulator、主界面、工序组等。

        Args:
            task: 对Unity程序的需求描述，需包含工序工步的详细描述
            info: 工序工步信息的JSON字符串，格式为 {{"工序名": ["工步1", "工步2"]}}，默认为空

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

        from agentscope.agent import ReActAgent
        from agentscope.model import OpenAIChatModel
        from agentscope.tool import Toolkit
        from agentscope.mcp import HttpStatefulClient
        from agentscope.formatter import DeepSeekChatFormatter
        from agentscope.memory import InMemoryMemory
        from dotenv import load_dotenv
        from pydantic.networks import AnyUrl
        load_dotenv()

        llm_name = os.environ.get("LLM_MODEL_NAME", "deepseek-reasoner")
        llm_base_url = os.environ.get("LLM_BASE_URL", "")
        llm_api_key = os.environ.get("LLM_API_KEY", "")

        if not llm_api_key:
            return "未配置 LLM_API_KEY 环境变量"

        # 连接 Unity MCP
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

        # 获取可用实例和自定义工具
        custom_tools = []
        try:
            instances_response = await unity_mcp.session.read_resource(AnyUrl("mcpforunity://instances"))
            instances = json.loads(instances_response.contents[0].text)["instances"]
            if not instances:
                await unity_mcp.close()
                return "未找到运行中的 Unity 编辑器实例"
            instance_hash = instances[0]["hash"]
            await unity_mcp.session.call_tool("set_active_instance", {"instance": instance_hash})

            custom_tools_response = await unity_mcp.session.read_resource(AnyUrl("mcpforunity://custom-tools"))
            custom_tools = json.loads(custom_tools_response.contents[0].text)["data"]["tools"]
            useful_tools = ["addXRRig", "addXRSimulator", "addMainCanvas", "addProcess"]
            custom_tools = [t for t in custom_tools if t["name"] in useful_tools]
        except Exception as e:
            _logger.warning(f"获取Unity自定义工具失败: {e}")

        await toolkit.register_mcp_client(unity_mcp)

        # 解析 info
        info_dict = json.loads(info) if isinstance(info, str) else info

        unity_agent = ReActAgent(
            name="unity_agent",
            sys_prompt=f"""你是顶尖的Unity AR程序开发助手，你的任务是使用工具直接帮助用户完成AR程序的开发。
你可以使用的custom tools包括{custom_tools}，
当你使用custom tools中的工具时，不要直接使用，必须通过调用execute_custom_tool工具来使用。
一个常用的AR应用初始化流程如下：
1.检查场景中是否有XR Rig对象，若不存在则添加
2.检查场景中是否有XR Simulator对象，若不存在则添加
3.检查场景中是否有MainCanvas，若不存在则添加一个主界面
4.根据工序工步信息向主界面中添加工序组
5.在unity中运行AR程序""",
            model=OpenAIChatModel(
                model_name=llm_name,
                api_key=llm_api_key,
                stream=True,
                enable_thinking=False,
                client_kwargs={"base_url": llm_base_url},
                generate_kwargs={"max_tokens": 4096, "max_completion_tokens": 4096},
            ),
            formatter=DeepSeekChatFormatter(),
            toolkit=toolkit,
            memory=InMemoryMemory(),
        )

        msg = Msg(
            name="user",
            content=f"请完成以下任务：{task}，可用的工艺信息为：{info_dict}",
            role="user",
        )

        msg_res = await unity_agent(msg)
        await unity_mcp.close()

        blocks = msg_res.get_content_blocks("text") if hasattr(msg_res, 'get_content_blocks') else []
        return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in blocks) if blocks else str(msg_res.content)

    def tool_blender_model(self, task: str) -> Any:
        """连接Blender，通过MCP完成三维建模任务

        Args:
            task: 对Blender建模的需求描述，例如"创建一个1x1x1的立方体"

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

        from agentscope.agent import ReActAgent
        from agentscope.model import OpenAIChatModel
        from agentscope.tool import Toolkit
        from agentscope.mcp import StdIOStatefulClient
        from agentscope.formatter import DeepSeekChatFormatter
        from agentscope.memory import InMemoryMemory
        from dotenv import load_dotenv
        load_dotenv()

        llm_name = os.environ.get("LLM_MODEL_NAME", "deepseek-reasoner")
        llm_base_url = os.environ.get("LLM_BASE_URL", "")
        llm_api_key = os.environ.get("LLM_API_KEY", "")

        if not llm_api_key:
            return "未配置 LLM_API_KEY 环境变量"

        # 连接 Blender MCP (通过 uvx 启动)
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
            sys_prompt="你是一个Blender建模助手，你的任务是帮助用户在Blender应用中完成三维建模。",
            model=OpenAIChatModel(
                model_name=llm_name,
                api_key=llm_api_key,
                stream=True,
                enable_thinking=False,
                client_kwargs={"base_url": llm_base_url},
                generate_kwargs={"max_tokens": 4096, "max_completion_tokens": 4096},
            ),
            formatter=DeepSeekChatFormatter(),
            toolkit=toolkit,
            memory=InMemoryMemory(),
        )

        msg = Msg(name="user", content=task, role="user")
        msg_res = await blender_agent(msg)
        await blender_mcp.close()

        blocks = msg_res.get_content_blocks("text") if hasattr(msg_res, 'get_content_blocks') else []
        return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in blocks) if blocks else str(msg_res.content)

    def tool_generate_process(
        self,
        task: str,
        image_path: str = "",
        collection_name: str = "process",
        limit: int = 5,
    ) -> Any:
        """根据任务要求查询知识库并生成工艺规划文件

        Args:
            task: 工艺规划任务描述
            image_path: 参考图像路径(可选)
            collection_name: 向量数据库名称
            limit: 返回结果数量

        Returns:
            生成的工艺规划结果
        """
        try:
            result = _run_async(
                self._generate_process_async(task, image_path, collection_name, limit)
            )
            return _make_response(json.dumps(result, ensure_ascii=False, indent=2))
        except Exception as e:
            return _make_response(f"工艺规划生成失败: {e}", success=False)

    async def _generate_process_async(
        self,
        task: str,
        image_path: str,
        collection_name: str,
        limit: int,
    ) -> Dict[str, Any]:
        import aiohttp
        from dotenv import load_dotenv
        load_dotenv()

        base_url = os.environ.get("RAG_BASE_URL", "http://localhost:8000/api/v1")
        milvus_uri = os.environ.get("MILVUS_BASE_URL", "http://localhost:19530")

        # 1. 获取嵌入向量
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field("text", task)
            if image_path and os.path.exists(image_path):
                with open(image_path, "rb") as f:
                    data.add_field("image", f.read(), filename="image.png", content_type="image/png")
            else:
                data.add_field("image", b"", filename="image.png", content_type="image/png")

            async with session.post(f"{base_url}/embed", data=data) as resp:
                if resp.status != 200:
                    return {"error": f"嵌入查询失败: {resp.status}"}
                embed_result = await resp.json()
                query_vector = embed_result["vector"]

        # 2. 向量搜索
        from pymilvus import MilvusClient
        client = MilvusClient(uri=milvus_uri)
        if not client.has_collection(collection_name):
            return {"error": f"集合 {collection_name} 不存在"}

        search_res = client.search(
            collection_name=collection_name,
            data=[query_vector],
            limit=limit,
            output_fields=["text", "subject", "path", "type"],
        )

        results = []
        for hit in search_res[0]:
            entity = hit["entity"]
            results.append({
                "score": hit["distance"],
                "text": entity.get("text", ""),
                "path": entity.get("path", ""),
                "type": entity.get("type", ""),
            })

        return {
            "task": task,
            "search_results": results,
            "message": f"从知识库中检索到 {len(results)} 条相关记录，请根据这些结果编写工艺文件",
        }

    def tool_generate_image(
        self,
        prompt: str,
        output_name: str = "output.png",
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 20,
    ) -> Any:
        """使用AI生成图片资源

        Args:
            prompt: 图像生成提示词
            output_name: 输出文件名
            negative_prompt: 负向提示词
            width: 图像宽度
            height: 图像高度
            steps: 采样步数

        Returns:
            生成结果和图像路径
        """
        try:
            result = _run_async(
                self._generate_image_async(prompt, output_name, negative_prompt, width, height, steps)
            )
            return _make_response(json.dumps(result, ensure_ascii=False, indent=2))
        except Exception as e:
            return _make_response(f"图像生成失败: {e}", success=False)

    async def _generate_image_async(
        self,
        prompt: str,
        output_name: str,
        negative_prompt: str,
        width: int,
        height: int,
        steps: int,
    ) -> Dict[str, Any]:
        import aiohttp
        from dotenv import load_dotenv
        load_dotenv()

        base_url = os.environ.get("RAG_BASE_URL", "http://localhost:8050")
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "steps": steps,
            "cfg_scale": 3.5,
            "sampler_name": "dpmpp_2m",
            "scheduler": "simple",
            "checkpoint": "flux1-dev.safetensors",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}/api/v1/text-to-image",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=300),
            ) as resp:
                if resp.status == 200:
                    image_data = await resp.read()
                    output_dir = os.path.join("output", "agent")
                    os.makedirs(output_dir, exist_ok=True)
                    output_path = os.path.join(output_dir, output_name)
                    with open(output_path, "wb") as f:
                        f.write(image_data)
                    return {"success": True, "image_path": output_path}
                else:
                    error = await resp.text()
                    return {"success": False, "error": f"HTTP {resp.status}: {error}"}

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

    def tool_query_knowledge_base(
        self,
        query: str,
        collection_name: str = "process",
        limit: int = 5,
    ) -> Any:
        """查询向量知识库获取相关文档

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
        import aiohttp
        from dotenv import load_dotenv
        load_dotenv()

        base_url = os.environ.get("RAG_BASE_URL", "http://localhost:8000/api/v1")
        milvus_uri = os.environ.get("MILVUS_BASE_URL", "http://localhost:19530")

        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field("text", query)
            data.add_field("image", b"", filename="image.png", content_type="image/png")
            async with session.post(f"{base_url}/embed", data=data) as resp:
                if resp.status != 200:
                    return [{"error": f"嵌入查询失败: {resp.status}"}]
                embed_result = await resp.json()

        from pymilvus import MilvusClient
        client = MilvusClient(uri=milvus_uri)
        if not client.has_collection(collection_name):
            return [{"error": f"集合 {collection_name} 不存在"}]

        search_res = client.search(
            collection_name=collection_name,
            data=[embed_result["vector"]],
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


class AgentExtensionsPlugin(PluginBase):
    """智能体扩展插件"""

    name = "agent_extensions"
    version = "1.0.0"
    description = "为AI助手提供多智能体扩展能力（工艺规划、图像生成等）"
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
