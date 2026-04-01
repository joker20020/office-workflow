# -*- coding: utf-8 -*-
"""AgentScope框架集成层"""

import asyncio
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

try:
    from agentscope.agent import ReActAgent
    from agentscope.message import Msg
    from agentscope.model import DashScopeChatModel, OpenAIChatModel
    from agentscope.formatter import (
        DashScopeChatFormatter,
        DeepSeekChatFormatter,
        OpenAIChatFormatter,
    )
    from agentscope.memory import InMemoryMemory
    from agentscope.tool import Toolkit
    from agentscope.mcp import HttpStatelessClient, StdIOStatefulClient

    AGENTSCOPE_AVAILABLE = True
    _logger_agent = __import__("src.utils.logger", fromlist=["get_logger"]).get_logger(__name__)
    _logger_agent.info("AgentScope框架加载成功")
except ImportError as e:
    AGENTSCOPE_AVAILABLE = False
    ReActAgent = None
    Msg = None
    DashScopeChatModel = None
    OpenAIChatModel = None
    DashScopeChatFormatter = None
    DeepSeekChatFormatter = None
    OpenAIChatFormatter = None
    InMemoryMemory = None
    Toolkit = None
    StdIOStatelessClient = None
    HttpStatelessClient = None
    _logger_agent = None

from src.agent.api_key_manager import ApiKeyManager
from src.agent.chat_history import ChatHistory
from src.agent.workflow_tools import WorkflowTools
from src.agent.node_formatter import NodeFormatter
from src.engine.node_engine import NodeEngine
from src.core.config_manager import get_config_manager
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.agent.mcp_server_manager import McpServerManager
    from src.agent.skill_manager import SkillManager
    from src.storage.repositories import ChatHistoryRepository

_logger = get_logger(__name__)


class AgentIntegration:
    """
    AgentScope框架集成层，管理Agent的生命周期和对话交互

    支持会话历史持久化
    - 通过 repository 参数启用数据库持久化
    - 支持创建新会话、加载现有会话
    - 支持列出所有历史会话
    """

    def __init__(
        self,
        api_key_manager: ApiKeyManager,
        node_engine: NodeEngine,
        workflow_tools: Optional[WorkflowTools] = None,
        mcp_manager: Optional["McpServerManager"] = None,
        skill_manager: Optional["SkillManager"] = None,
        history_repository: Optional["ChatHistoryRepository"] = None,
        session_id: Optional[str] = None,
    ):
        _logger.info("=" * 50)
        _logger.info("AgentIntegration 开始初始化")
        _logger.info(f"AgentScope可用: {AGENTSCOPE_AVAILABLE}")

        self._api_manager = api_key_manager
        self._node_engine = node_engine
        self._workflow_tools = workflow_tools
        self._mcp_manager = mcp_manager
        self._skill_manager = skill_manager
        self._history_repository = history_repository
        self.config = get_config_manager()

        self._agent: Optional[Any] = None
        self._toolkit: Optional[Any] = None
        self._mcp_clients: List[Any] = []
        self._api_key: str = ""
        self._streaming_callbacks: List[Callable] = []
        self._initialized: bool = False
        self._provider: str = ""
        self._model_name: str = ""
        self._base_url: str = ""
        self._mcp_clients: List[Any] = []
        self._api_key: str = ""
        self._streaming_callbacks: List[Callable] = []
        self._initialized: bool = False
        self._provider: str = ""
        self._model_name: str = ""
        self._base_url: str = ""

        if history_repository:
            if session_id:
                self._history = ChatHistory.create_from_session(
                    session_id=session_id,
                    repository=history_repository,
                    max_messages=100,
                )
                _logger.info(f"加载指定会话: {session_id[:8]}...")
            else:
                existing_sessions = history_repository.list_sessions(limit=1)
                if existing_sessions:
                    latest_session_id = existing_sessions[0]["id"]
                    self._history = ChatHistory.create_from_session(
                        session_id=latest_session_id,
                        repository=history_repository,
                        max_messages=100,
                    )
                    _logger.info(f"自动加载最新会话: {latest_session_id[:8]}...")
                else:
                    self._history = ChatHistory(max_messages=100, repository=history_repository)
                    _logger.info("无现有会话，将在首次对话时创建新会话")
        else:
            self._history = ChatHistory(max_messages=100)
            _logger.info("使用内存模式存储会话历史")

        _logger.info("AgentIntegration 初始化完成")
        _logger.info("=" * 50)

    def register_streaming_callback(self, callback: Callable[[str], None]) -> None:
        self._streaming_callbacks.append(callback)

    def unregister_streaming_callback(self, callback: Callable[[str], None]) -> None:
        if callback in self._streaming_callbacks:
            self._streaming_callbacks.remove(callback)

    def _create_streaming_hook(self) -> Callable:
        def streaming_hook(agent_self: Any, kwargs: dict, output: Any) -> Any:
            for callback in self._streaming_callbacks:
                try:
                    callback(agent_self, kwargs, output)
                except Exception as e:
                    _logger.error(f"Streaming callback error: {e}")
            return output

        return streaming_hook

    def initialize(
        self, provider: str = "dashscope", model_name: str = "", base_url: str = ""
    ) -> bool:
        _logger.info("=" * 50)
        _logger.info(
            f"开始初始化Agent: provider={provider}, model_name={model_name}, base_url={base_url}"
        )

        if not AGENTSCOPE_AVAILABLE:
            _logger.error("AgentScope框架未安装，无法初始化")
            return False

        try:
            api_key = self._api_manager.get_key(provider, model_name)
            if not api_key:
                _logger.error(f"未找到 {provider} 的API密钥")
                return False

            self._api_key = api_key[:10] + "..." if len(api_key) > 10 else api_key
            _logger.info(f"获取到API密钥: {self._api_key}")

            config = self._api_manager.get_config(provider)
            if config:
                _logger.info(f"获取到配置: {config}")
                model_name = model_name or config.get("model_name", "")
                base_url = base_url or config.get("base_url", "")

            self._provider = provider
            self._model_name = model_name
            self._base_url = base_url

            self._toolkit = Toolkit()
            _logger.info("Toolkit创建成功")

            # Define variables for model configuration
            config = self._api_manager.get_config(provider)
            if config:
                _logger.info(f"获取到配置: {config}")
                model_name = model_name or config.get("model_name", "")
                base_url = base_url or config.get("base_url", "")

            self._provider = provider
            self._model_name = model_name
            self._base_url = base_url

            # Create model based on provider
            if provider == "dashscope":
                model_name = model_name or "qwen-turbo"
                base_url = base_url or "https://api.dashscope.com"
                _logger.info(f"创建DashScope模型: model_name={model_name}, base_url={base_url}")
                model = DashScopeChatModel(
                    model_name=model_name, api_key=api_key, client_kwargs={"base_url": base_url}
                )
                formatter = DashScopeChatFormatter()
            elif provider == "deepseek":
                final_model = model_name or "deepseek-chat"
                final_url = base_url or "https://api.deepseek.com"
                _logger.info(f"创建DeepSeek模型: model_name={final_model}, base_url={final_url}")
                model = OpenAIChatModel(
                    model_name=final_model, api_key=api_key, client_kwargs={"base_url": final_url}
                )
                formatter = DeepSeekChatFormatter()
            elif provider == "openai":
                final_model = model_name or "gpt-4o"
                final_url = base_url or "https://api.openai.com/v1"
                _logger.info(f"创建OpenAI模型: model_name={final_model}, base_url={final_url}")
                model = OpenAIChatModel(
                    model_name=final_model, api_key=api_key, client_kwargs={"base_url": final_url}
                )
                formatter = OpenAIChatFormatter()
            else:
                _logger.error(f"不支持的provider: {provider}")
                return False

            _logger.info("模型创建成功")

            system_prompt = self.config.get("system_prompt",
                                            """
                            你是一个智能工作流助手。

                            你的能力:
                            1. 理解用户需求，分析需要哪些节点
                            2. 使用工具创建和配置节点
                            3. 连接节点形成工作流
                            4. 执行工作流

                            使用建议:
                            1. 首先使用 get_node_types 查看有哪些节点可用
                            2. 使用 get_node_info 了解特定节点的详细信息
                            3. 使用 search_nodes 按关键词查找相关节点

                            请用自然语言与用户交流。使用工具完成工作流设计。"""
                            )
            
            _logger.info(f"系统提示词长度: {len(system_prompt)} 字符")

            _logger.info("创建ReActAgent...")
            self._agent = ReActAgent(
                name="WorkflowAssistant",
                sys_prompt=system_prompt,
                model=model,
                formatter=formatter,
                memory=InMemoryMemory(),
                toolkit=self._toolkit,
                max_iters=50,
            )
            _logger.info("ReActAgent创建成功")

            # Register streaming hook (unconditionally)
            self._agent.register_instance_hook(
                hook_type="post_print",
                hook_name="streaming_output",
                hook=self._create_streaming_hook(),
            )

            if self._workflow_tools:
                self._register_workflow_tools()
                _logger.info("工作流工具注册完成")

            self._register_mcp_tools()
            self._register_skills()

            self._agent.register_instance_hook(
                hook_type="post_print",
                hook_name="streaming_output",
                hook=self._create_streaming_hook(),
            )

            self._initialized = True
            _logger.info(f"Agent初始化成功: provider={provider}, model={self._model_name}")
            _logger.info("=" * 50)
            return True

        except Exception as e:
            _logger.error(f"Agent初始化失败: {e}", exc_info=True)
            _logger.error("=" * 50)
            return False

    def _register_workflow_tools(self) -> None:
        if not self._workflow_tools or not AGENTSCOPE_AVAILABLE:
            return

        tools = self._workflow_tools.get_all_tools()
        for tool_func in tools:
            self._toolkit.register_tool_function(tool_func)

        _logger.info(f"已注册 {len(tools)} 个工作流工具")

    def _register_mcp_tools(self) -> None:
        if not self._mcp_manager or not AGENTSCOPE_AVAILABLE:
            return

        enabled_servers = [s for s in self._mcp_manager.list_servers() if s.get("enabled")]

        registered_count = 0
        for server in enabled_servers:
            try:
                config = self._mcp_manager.get_agentscope_config(server["name"])
                if not config:
                    continue

                server_type = server.get("server_type", "stdio")

                if server_type == "stdio":
                    client = StdIOStatefulClient(
                        name=config["name"],
                        command=config["command"],
                        args=config.get("args", []),
                        env=config.get("env", {}),
                        timeout=config.get("timeout", 30),
                    )
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(client.connect())
                    loop.run_until_complete(self._toolkit.register_mcp_client(client))
                    loop.close()
                    self._mcp_clients.append(client)
                    registered_count += 1
                    _logger.info(f"已注册MCP服务(stdio): {server['name']}")
                else:
                    client = HttpStatelessClient(
                        name=config["name"],
                        transport=config.get("transport", "streamable_http"),
                        url=config["url"],
                    )
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(self._toolkit.register_mcp_client(client))
                    loop.close()
                    self._mcp_clients.append(client)
                    registered_count += 1
                    _logger.info(f"已注册MCP服务(http): {server['name']}")
            except Exception as e:
                _logger.error(f"注册MCP服务失败 ({server['name']}): {e}")

        _logger.info(f"共注册 {registered_count} 个MCP服务")

    def _register_skills(self) -> None:
        if not self._skill_manager or not AGENTSCOPE_AVAILABLE:
            return

        enabled_skills = self._skill_manager.get_enabled_skills()

        for skill in enabled_skills:
            try:
                skill_path = skill.get("path")
                if skill_path:
                    self._toolkit.register_agent_skill(skill_path)
                    _logger.info(f"注册Skill: {skill['name']}")
            except Exception as e:
                _logger.error(f"注册Skill失败: {e}")

    def chat(self, message: str) -> str:
        _logger.info("=" * 50)
        _logger.info(f"开始处理对话: message='{message[:50]}...' (长度: {len(message)})")

        if not self._initialized:
            _logger.error("Agent未初始化")
            return "Agent未初始化，请先配置API密钥"

        if not self._agent:
            _logger.error("Agent对象为空")
            return "Agent对象为空，请重新初始化"

        start_time = time.time()

        try:
            self._history.add_message("user", message)
            _logger.info(f"用户消息已添加到历史记录")

            if AGENTSCOPE_AVAILABLE and Msg is not None:
                _logger.info("创建Msg对象...")
                msg = Msg(name="User", content=message, role="user")
                _logger.info(f"Msg对象创建成功: {msg}")

                _logger.info("开始调用Agent...")
                _logger.info(f"Provider: {self._provider}")
                _logger.info(f"Model: {self._model_name}")
                _logger.info(f"Base URL: {self._base_url}")

                loop = asyncio.new_event_loop()
                try:
                    _logger.info("执行异步调用...")
                    response_msg = loop.run_until_complete(self._agent(msg))
                    _logger.info(f"异步调用完成，响应类型: {type(response_msg)}")

                    text_blocks = response_msg.get_content_blocks("text")
                    _logger.info(f"响应内容块: {text_blocks}")
                    response = "".join([text_block["text"] for text_block in text_blocks])
                    _logger.info(f"响应内容类型: {type(response)}")
                    _logger.info(f"响应内容长度: {len(str(response)) if response else 0}")
                finally:
                    loop.close()
                    _logger.info("事件循环已关闭")

                result = response.strip()

                _logger.info(f"最终响应: '{result[:100]}...' (长度: {len(result)})")

                # Extract all messages from agent's short-term memory
                memory_messages = self.extract_agent_memory()
                print(memory_messages)
                if memory_messages:
                    _logger.info(f"从agent memory获取 {len(memory_messages)} 条消息")
                    self._history.clear()
                    for mem_msg_dict in memory_messages:
                        try:
                            restored_msg = Msg.from_dict(mem_msg_dict)
                            self._history.add_message(msg=restored_msg)
                        except Exception as e:
                            _logger.warning(f"存储消息失败: {e}")
                else:
                    # Fallback: store response directly if memory retrieval fails
                    if hasattr(response_msg, "content"):
                        from agentscope.message import Msg as ASMsg

                        full_msg = ASMsg(
                            name="Assistant",
                            role="assistant",
                            content=response_msg.content,
                            metadata=getattr(response_msg, "metadata", None),
                        )
                        self._history.add_message(msg=full_msg)
                    else:
                        self._history.add_message("assistant", result)
            else:
                result = "AgentScope框架未安装"
                _logger.error(result)
                self._history.add_message("assistant", result)

            elapsed = time.time() - start_time
            _logger.info(f"对话处理完成，耗时: {elapsed:.2f}秒")
            _logger.info("=" * 50)
            return result

        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            _logger.error(f"对话超时，耗时: {elapsed:.2f}秒")
            _logger.error("=" * 50)
            return f"请求超时（{elapsed:.1f}秒），请检查网络连接或API配置"
        except Exception as e:
            elapsed = time.time() - start_time
            _logger.error(f"Agent对话失败: {e}", exc_info=True)
            _logger.error(f"耗时: {elapsed:.2f}秒")
            _logger.error("=" * 50)
            return f"错误: {e}"

    async def chat_async(self, message: str) -> str:
        _logger.info(f"[异步] 开始处理对话: {message[:50]}...")

        if not self._initialized or not self._agent:
            return "Agent未初始化，请先配置API密钥"

        start_time = time.time()

        try:
            self._history.add_message("user", message)

            if AGENTSCOPE_AVAILABLE and Msg is not None:
                msg = Msg(name="User", content=message, role="user")
                _logger.info("[异步] 调用Agent...")

                response_msg = await self._agent(msg)
                response = response_msg.content

                if isinstance(response, list):
                    text_parts = []
                    for block in response:
                        if hasattr(block, "text"):
                            text_parts.append(block.text)
                    result = "\n".join(text_parts)
                else:
                    result = str(response)
            else:
                result = "AgentScope框架未安装"

            self._history.add_message("assistant", result)

            elapsed = time.time() - start_time
            _logger.info(f"[异步] 对话处理完成，耗时: {elapsed:.2f}秒")
            return result

        except Exception as e:
            elapsed = time.time() - start_time
            _logger.error(f"[异步] Agent对话失败: {e}", exc_info=True)
            return f"错误: {e}"

    def reset(self) -> None:
        _logger.info("重置Agent...")
        self._history.clear()

        if self._agent and hasattr(self._agent, "memory"):
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self._agent.memory.clear())
                loop.close()
            except Exception as e:
                _logger.warning(f"清空Agent记忆失败: {e}")

        _logger.info("Agent已重置")

    def get_history(self) -> List[Dict]:
        if self._history_repository:
            return self._history.get_all_messages_persisted()
        return self._history.to_dict_list()

    def extract_agent_memory(self) -> List[Dict]:
        if not self._agent or not hasattr(self._agent, "memory"):
            _logger.warning("Agent memory not available")
            return []

        loop = asyncio.new_event_loop()
        try:
            memory = loop.run_until_complete(self._agent.memory.get_memory())

            messages = []
            for msg in reversed(memory):
                msg_dict = msg.to_dict() if hasattr(msg, "to_dict") else msg

                role = msg_dict.get("role", "unknown")
                if role not in ["user", "assistant", "system"]:
                    continue
                if role == "user":
                    break

                messages.append(msg_dict)

            _logger.info(f"Extracted {len(messages)} messages from agent memory")
            messages.reverse()
            return messages

        except Exception as e:
            _logger.error(f"Failed to extract agent memory: {e}")
            return []
        finally:
            loop.close()

    def create_new_session(self, title: Optional[str] = None) -> Optional[str]:
        if not self._history_repository:
            _logger.warning("未启用数据库持久化，无法创建新会话")
            return None

        session_id = self._history.create_new_session(title)
        _logger.info(f"创建新会话: {session_id}")
        return session_id

    def switch_session(self, session_id: str) -> bool:
        if not self._history_repository:
            _logger.warning("未启用数据库持久化，无法切换会会")
            return False

        success = self._history.set_session(session_id)
        if success:
            _logger.info(f"切换到会话: {session_id}")
            self._sync_history_to_memory()
        return success

    def _sync_history_to_memory(self) -> None:
        if not self._agent or not hasattr(self._agent, "memory"):
            _logger.warning("Agent或memory不存在")
            return

        if not AGENTSCOPE_AVAILABLE:
            return

        loop = asyncio.new_event_loop()
        try:
            _logger.info("清空Agent memory...")
            loop.run_until_complete(self._agent.memory.clear())
            _logger.info("Agent memory已清空")

            messages = self._history.get_messages()
            _logger.info(f"从内存加载 {len(messages)} 条历史消息")

            sync_count = 0
            for msg in messages:
                if hasattr(msg, "role") and hasattr(msg, "content"):
                    loop.run_until_complete(self._agent.memory.add(msg))
                    sync_count += 1
                elif isinstance(msg, dict):
                    try:
                        reconstructed_msg = Msg.from_dict(msg)
                        loop.run_until_complete(self._agent.memory.add(reconstructed_msg))
                        sync_count += 1
                    except Exception as e:
                        _logger.warning(f"Failed to reconstruct Msg: {e}")
                        role = msg.get("role", "user")
                        content = msg.get("content", "")
                        if role in ("user", "assistant"):
                            fallback_msg = Msg(
                                name=msg.get("name", "User" if role == "user" else "Assistant"),
                                content=content,
                                role=role,
                                metadata=msg.get("metadata", {}),
                            )
                            loop.run_until_complete(self._agent.memory.add(fallback_msg))
                            sync_count += 1

            _logger.info(f"已同步 {sync_count} 条消息到Agent memory")

        except Exception as e:
            _logger.warning(f"同步历史到Memory失败: {e}")
        finally:
            loop.close()

    def list_sessions(self, limit: int = 20) -> List[Dict]:
        if not self._history_repository:
            _logger.warning("未启用数据库持久化，无法列出会话")
            return []

        return self._history_repository.list_sessions(limit=limit)

    def delete_session(self, session_id: str) -> bool:
        if not self._history_repository:
            _logger.warning("未启用数据库持久化，无法删除会话")
            return False

        result = self._history_repository.delete_session(session_id)
        if result:
            _logger.info(f"删除会话: {session_id}")
        return result

    @property
    def current_session_id(self) -> Optional[str]:
        return self._history.session_id

    @property
    def is_persisted(self) -> bool:
        return self._history_repository is not None

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def provider(self) -> str:
        return self._provider

    def set_mcp_manager(self, manager: "McpServerManager") -> None:
        self._mcp_manager = manager

    def set_skill_manager(self, manager: "SkillManager") -> None:
        self._skill_manager = manager

    def shutdown(self) -> None:
        _logger.info("关闭Agent...")
        for client in self._mcp_clients:
            try:
                if hasattr(client, "close"):
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(client.close())
                    loop.close()
            except Exception as e:
                _logger.warning(f"关闭MCP客户端失败: {e}")

        self._mcp_clients.clear()
        self._agent = None
        self._initialized = False
        _logger.info("Agent已关闭")
