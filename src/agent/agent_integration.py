# -*- coding: utf-8 -*-
"""AgentScope框架集成层"""

import asyncio
import threading
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

try:
    from agentscope.credential import (
        DashScopeCredential,
        DeepSeekCredential,
        OpenAICredential,
    )
    from agentscope.model import (
        DashScopeChatModel,
        DeepSeekChatModel,
        OpenAIChatModel,
    )
except ImportError:
    DashScopeCredential = None
    DeepSeekCredential = None
    OpenAICredential = None
    DashScopeChatModel = None
    DeepSeekChatModel = None
    OpenAIChatModel = None

try:
    from agentscope.agent import Agent, ReActConfig
    from agentscope.message import (
        AssistantMsg,
        Base64Source,
        DataBlock,
        Msg,
        TextBlock,
        URLSource,
        UserMsg,
    )
    from agentscope.event import (
        ReplyEndEvent,
        ReplyEndReason,
        ReplyStartEvent,
        RequireExternalExecutionEvent,
        RequireUserConfirmEvent,
        UserInterruptEvent,
    )
    from agentscope.state import AgentState
    from agentscope.tool import Toolkit

    AGENTSCOPE_AVAILABLE = True
    _logger_agent = __import__("src.utils.logger", fromlist=["get_logger"]).get_logger(__name__)
    _logger_agent.info("AgentScope框架加载成功")
except ImportError as e:
    AGENTSCOPE_AVAILABLE = False
    Agent = None
    ReActConfig = None
    AgentState = None
    AssistantMsg = None
    Msg = None
    TextBlock = None
    UserMsg = None
    URLSource = None
    Base64Source = None
    DataBlock = None
    Toolkit = None
    ReplyEndEvent = None
    ReplyEndReason = None
    ReplyStartEvent = None
    RequireExternalExecutionEvent = None
    RequireUserConfirmEvent = None
    UserInterruptEvent = None
    _logger_agent = None

try:
    from agentscope.mcp import HttpStatelessClient, StdIOStatefulClient
except ImportError:
    HttpStatelessClient = None
    StdIOStatefulClient = None

from src.agent.api_key_manager import ApiKeyManager
from src.agent.chat_history import ChatHistory, serialize_message
from src.agent.tool_registry import AgentToolRegistry
from src.engine.node_engine import NodeEngine
from src.core.config_manager import get_config_manager
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.agent.mcp_server_manager import McpServerManager
    from src.agent.skill_manager import SkillManager
    from src.storage.repositories import ChatHistoryRepository

_logger = get_logger(__name__)

StreamingCallback = Callable[[Any, dict[str, Any], Any], None]


class _ReplyStreamError(Exception):
    def __init__(self, cause: Exception, reply: Msg) -> None:
        super().__init__(str(cause))
        self.cause = cause
        self.reply = reply


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
        self._mcp_manager = mcp_manager
        self._skill_manager = skill_manager
        self._history_repository = history_repository
        self.config = get_config_manager()

        self._agent: Optional[Any] = None
        self._toolkit: Optional[Any] = None
        self._mcp_clients: List[Any] = []
        self._api_key: str = ""
        self._streaming_callbacks: List[StreamingCallback] = []
        self._initialized: bool = False
        self._provider: str = ""
        self._model_name: str = ""
        self._base_url: str = ""
        self._current_loop: Optional[asyncio.AbstractEventLoop] = None
        self._active_reply_task: Optional[asyncio.Task[Any]] = None
        self._reply_ownership_lock = threading.Lock()
        self._active_reply_owners: List[
            tuple[asyncio.Task[Any], asyncio.AbstractEventLoop]
        ] = []
        self._parked_reply_id: Optional[str] = None
        self._parked_reply_loop: Optional[asyncio.AbstractEventLoop] = None
        self._parked_reply_loop_thread: Optional[threading.Thread] = None
        self._parked_cleanup_future: Optional[Any] = None
        self._last_response_interrupted: bool = False

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

    def register_streaming_callback(self, callback: StreamingCallback) -> None:
        self._streaming_callbacks.append(callback)

    def unregister_streaming_callback(self, callback: StreamingCallback) -> None:
        if callback in self._streaming_callbacks:
            self._streaming_callbacks.remove(callback)

    def _notify_stream_event(self, event: Any) -> None:
        for callback in self._streaming_callbacks:
            try:
                callback(self._agent, {"event": event}, event)
            except Exception as e:
                _logger.error(f"Streaming callback error: {e}")

    async def _consume_reply_stream(self, inputs: Msg) -> Msg:
        self._last_response_interrupted = False
        provisional_id = getattr(getattr(self._agent, "state", None), "reply_id", None)
        reply = AssistantMsg(name="Assistant", content=[], id=provisional_id)

        try:
            async for event in self._agent.reply_stream(inputs=inputs):
                if isinstance(event, ReplyStartEvent):
                    reply.id = event.reply_id
                if isinstance(
                    event,
                    (RequireUserConfirmEvent, RequireExternalExecutionEvent),
                ):
                    with self._reply_ownership_lock:
                        self._parked_reply_id = event.reply_id
                        self._parked_reply_loop = asyncio.get_running_loop()
                reply.append_event(event)
                self._notify_stream_event(event)
                if isinstance(event, ReplyEndEvent):
                    self._last_response_interrupted = (
                        event.finished_reason == ReplyEndReason.INTERRUPTED
                    )
                    with self._reply_ownership_lock:
                        if getattr(self, "_parked_reply_id", None) == event.reply_id:
                            self._parked_reply_id = None
                            self._parked_reply_loop = None
        except Exception as error:
            raise _ReplyStreamError(error, reply) from error

        return reply

    async def _run_owned_reply_stream(self, inputs: Msg) -> Msg:
        task = asyncio.current_task()
        loop = asyncio.get_running_loop()
        if not hasattr(self, "_reply_ownership_lock"):
            self._reply_ownership_lock = threading.Lock()
            self._active_reply_owners = []
        with self._reply_ownership_lock:
            self._active_reply_owners.append((task, loop))
            self._active_reply_task = task
            self._current_loop = loop
        try:
            return await self._consume_reply_stream(inputs)
        finally:
            with self._reply_ownership_lock:
                self._active_reply_owners[:] = [
                    owner
                    for owner in self._active_reply_owners
                    if owner[0] is not task
                ]
                if self._active_reply_task is task:
                    if self._active_reply_owners:
                        (
                            self._active_reply_task,
                            self._current_loop,
                        ) = self._active_reply_owners[-1]
                    else:
                        self._active_reply_task = None
                        self._current_loop = None

    def _retain_sync_parked_loop(
        self,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        ready = threading.Event()

        def run_parked_loop() -> None:
            asyncio.set_event_loop(loop)
            loop.call_soon(ready.set)
            try:
                loop.run_forever()
            finally:
                loop.close()

        thread = threading.Thread(
            target=run_parked_loop,
            name="agent-parked-reply-loop",
            daemon=True,
        )
        self._parked_reply_loop_thread = thread
        thread.start()
        ready.wait()

    def _stop_retained_parked_loop(
        self,
        cleanup: Any,
        loop: asyncio.AbstractEventLoop,
        thread: threading.Thread,
    ) -> None:
        if not cleanup.cancelled() and cleanup.exception() is None:
            loop.call_soon_threadsafe(loop.stop)
            with self._reply_ownership_lock:
                if self._parked_reply_loop_thread is thread:
                    self._parked_reply_loop_thread = None

    async def _cleanup_parked_reply(self, reply_id: str) -> None:
        await self._agent.reply(inputs=UserInterruptEvent(reply_id=reply_id))
        self._last_response_interrupted = True
        with self._reply_ownership_lock:
            if self._parked_reply_id == reply_id:
                self._parked_reply_id = None
                self._parked_reply_loop = None

    def _dispose_parked_reply_runtime(self) -> None:
        with self._reply_ownership_lock:
            cleanup = self._parked_cleanup_future
            parked_loop = self._parked_reply_loop
            parked_thread = self._parked_reply_loop_thread
            self._parked_reply_id = None
            self._parked_reply_loop = None
            self._parked_reply_loop_thread = None
            self._parked_cleanup_future = None

        if cleanup is not None and not cleanup.done():
            cleanup.cancel()
        if (
            parked_loop is not None
            and parked_thread is not None
            and parked_thread.is_alive()
        ):
            parked_loop.call_soon_threadsafe(parked_loop.stop)
            if threading.current_thread() is not parked_thread:
                parked_thread.join(timeout=2)

    def _create_model(
        self,
        provider: str,
        model_name: str,
        base_url: str,
        api_key: str,
    ) -> Any:
        if provider == "openai":
            credential = OpenAICredential(
                api_key=api_key,
                base_url=base_url or "https://api.openai.com/v1",
            )
            return OpenAIChatModel(
                credential=credential,
                model=model_name or "gpt-4o",
                stream=True,
            )
        if provider == "deepseek":
            credential = DeepSeekCredential(
                api_key=api_key,
                base_url=base_url or "https://api.deepseek.com",
            )
            return DeepSeekChatModel(
                credential=credential,
                model=model_name or "deepseek-chat",
                stream=True,
            )
        if provider == "dashscope":
            credential = DashScopeCredential(
                api_key=api_key,
                base_url=base_url or "https://api.dashscope.com",
            )
            return DashScopeChatModel(
                credential=credential,
                model=model_name or "qwen-turbo",
                stream=True,
            )
        raise ValueError(f"unsupported provider: {provider}")

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

            model = self._create_model(provider, model_name, base_url, api_key)

            _logger.info("模型创建成功")
            system_prompt = self.config.get(
                "system_prompt",
                """
                            你是一个智能工作流助手。

                            你的能力:
                            1. 理解用户需求，分析需要哪些节点
                            2. 使用工具创建和配置节点
                            3. 连接节点形成工作流
                            4. 执行工作流

                            请用自然语言与用户交流。使用工具完成工作流设计。""",
            )

            self._register_registry_tools()
            self._register_mcp_tools()
            self._register_skills()
            
            _logger.info(f"系统提示词长度: {len(system_prompt)} 字符")

            _logger.info("创建Agent...")
            state = AgentState(context=self._history.get_messages())
            react_config = ReActConfig(
                max_iters=50,
                interruption_raise_cancelled_error=False,
            )
            self._agent = Agent(
                name="WorkflowAssistant",
                system_prompt=system_prompt,
                model=model,
                toolkit=self._toolkit,
                state=state,
                react_config=react_config,
            )
            _logger.info("Agent创建成功")

            self._initialized = True
            _logger.info(f"Agent初始化成功: provider={provider}, model={self._model_name}")
            _logger.info("=" * 50)
            return True

        except Exception as e:
            _logger.error(f"Agent初始化失败: {e}", exc_info=True)
            _logger.error("=" * 50)
            return False

    def _register_registry_tools(self) -> None:
        """从 AgentToolRegistry 注册所有已注册的工具函数"""
        if not AGENTSCOPE_AVAILABLE:
            return

        tools = AgentToolRegistry.instance().get_all_tools()
        
        for tool_func in tools:
            self._toolkit.register_tool_function(tool_func)

        if tools:
            _logger.info(f"已从注册中心加载 {len(tools)} 个工具")
        else:
            _logger.info("注册中心无工具可加载")

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

    def chat(self, message: str | List[Dict[str, Any]]) -> str:
        """Send message to agent and get response.

        Args:
            message: Either a text string or list of content blocks.
                     Content blocks format:
                     - {"type": "text", "text": "..."}
                     - {"type": "image", "url": "file:///path/to/image.jpg"}
                     - {"type": "audio", "url": "file:///path/to/audio.mp3"}
                     - {"type": "video", "url": "file:///path/to/video.mp4"}

        Returns:
            Agent response text
        """
        _logger.info("=" * 50)
        if isinstance(message, str):
            _logger.info(f"开始处理对话: message='{message[:50]}...' (长度: {len(message)})")
        else:
            _logger.info(f"开始处理多模态对话: {len(message)} 个内容块")

        if not self._initialized:
            _logger.error("Agent未初始化")
            return "Agent未初始化，请先配置API密钥"

        if not self._agent:
            _logger.error("Agent对象为空")
            return "Agent对象为空，请重新初始化"

        start_time = time.time()

        try:
            if AGENTSCOPE_AVAILABLE and Msg is not None:
                msg = self._create_user_message(message)
                self._history.add_message(msg=msg)

                loop = asyncio.new_event_loop()
                try:
                    response_msg = loop.run_until_complete(self._run_owned_reply_stream(msg))
                finally:
                    if self._current_loop is loop:
                        self._current_loop = None
                    with self._reply_ownership_lock:
                        retain_parked_loop = (
                            self._parked_reply_id is not None
                            and self._parked_reply_loop is loop
                        )
                    if retain_parked_loop:
                        self._retain_sync_parked_loop(loop)
                    else:
                        loop.close()

                self._history.add_message(msg=response_msg)
                result = (response_msg.get_text_content() or "").strip()
            else:
                result = "AgentScope框架未安装"
                _logger.error(result)

            elapsed = time.time() - start_time
            _logger.info(f"对话处理完成，耗时: {elapsed:.2f}秒")
            _logger.info("=" * 50)
            return result

        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            _logger.error(f"对话超时，耗时: {elapsed:.2f}秒")
            _logger.error("=" * 50)
            return f"请求超时（{elapsed:.1f}秒），请检查网络连接或API配置"
        except _ReplyStreamError as error:
            self._history.add_message(msg=error.reply)
            elapsed = time.time() - start_time
            if isinstance(error.cause, asyncio.TimeoutError):
                _logger.error(f"对话超时，耗时: {elapsed:.2f}秒")
                return f"请求超时（{elapsed:.1f}秒），请检查网络连接或API配置"
            _logger.error(f"Agent对话失败: {error.cause}", exc_info=True)
            return f"错误: {error.cause}"
        except Exception as e:
            elapsed = time.time() - start_time
            _logger.error(f"Agent对话失败: {e}", exc_info=True)
            _logger.error(f"耗时: {elapsed:.2f}秒")
            _logger.error("=" * 50)
            return f"错误: {e}"

    async def chat_async(self, message: str | List[Dict[str, Any]]) -> str:
        """Async implementation of chat with multimodal support."""
        if isinstance(message, str):
            _logger.info(f"[异步] 开始处理对话: {message[:50]}...")
        else:
            _logger.info(f"[异步] 开始处理多模态对话: {len(message)} 个内容块")

        if not self._initialized or not self._agent:
            return "Agent未初始化，请先配置API密钥"

        start_time = time.time()

        try:
            if AGENTSCOPE_AVAILABLE and Msg is not None:
                msg = self._create_user_message(message)
                self._history.add_message(msg=msg)
                response_msg = await self._run_owned_reply_stream(msg)
                self._history.add_message(msg=response_msg)
                result = (response_msg.get_text_content() or "").strip()
            else:
                result = "AgentScope框架未安装"

            elapsed = time.time() - start_time
            _logger.info(f"[异步] 对话处理完成，耗时: {elapsed:.2f}秒")
            return result

        except _ReplyStreamError as error:
            self._history.add_message(msg=error.reply)
            elapsed = time.time() - start_time
            _logger.error(f"[异步] Agent对话失败: {error.cause}", exc_info=True)
            return f"错误: {error.cause}"
        except Exception as e:
            elapsed = time.time() - start_time
            _logger.error(f"[异步] Agent对话失败: {e}", exc_info=True)
            return f"错误: {e}"

    def _create_user_message(self, message: str | List[Dict[str, Any]]) -> Msg:
        if isinstance(message, str):
            return UserMsg(name="User", content=message)

        content_blocks = []
        for block in message:
            block_type = block.get("type")
            if block_type == "text":
                content_blocks.append(TextBlock(text=block.get("text", "")))
            elif block_type in ("image", "audio", "video"):
                content_blocks.append(self._create_data_block(block, block_type))
        return UserMsg(name="User", content=content_blocks)

    def _create_data_block(self, block: Dict[str, Any], media_kind: str) -> Any:
        default_media_types = {
            "image": "image/png",
            "audio": "audio/mpeg",
            "video": "video/mp4",
        }
        media_type = block.get("media_type", default_media_types[media_kind])
        if "url" in block:
            url = block["url"]
            if url.startswith("file://"):
                url = url[7:]
            source = URLSource(url=url, media_type=media_type)
        elif "data" in block:
            source = Base64Source(data=block["data"], media_type=media_type)
        else:
            raise ValueError(f"{media_kind.title()} block must have 'url' or 'data' field")
        return DataBlock(source=source, name=media_kind)

    def interrupt(self, reason: str = "用户中断") -> bool:
        """Thread-safely cancel active work or clean up a parked reply."""
        try:
            with self._reply_ownership_lock:
                task = self._active_reply_task
                loop = self._current_loop
                if (
                    task is not None
                    and not task.done()
                    and loop is not None
                    and loop.is_running()
                ):
                    loop.call_soon_threadsafe(task.cancel)
                    _logger.info(f"已调度中断: {reason}")
                    return True

                parked_reply_id = self._parked_reply_id
                parked_loop = self._parked_reply_loop or self._current_loop
                cleanup = self._parked_cleanup_future
                if (
                    parked_reply_id is not None
                    and parked_loop is not None
                    and parked_loop.is_running()
                    and (cleanup is None or cleanup.done())
                ):
                    retained_thread = self._parked_reply_loop_thread
                    coroutine = self._cleanup_parked_reply(parked_reply_id)
                    try:
                        cleanup = asyncio.run_coroutine_threadsafe(
                            coroutine,
                            parked_loop,
                        )
                    except Exception:
                        coroutine.close()
                        raise
                    self._parked_cleanup_future = cleanup
                    if retained_thread is not None:
                        cleanup.add_done_callback(
                            lambda done: self._stop_retained_parked_loop(
                                done,
                                parked_loop,
                                retained_thread,
                            ),
                        )
                    _logger.info(f"已调度中断: {reason}")
                    return True
        except Exception as e:
            _logger.error(f"中断 Agent 失败: {e}")
        return False

    @property
    def is_running(self) -> bool:
        """Agent 是否正在处理请求"""
        with self._reply_ownership_lock:
            task = self._active_reply_task
            cleanup = self._parked_cleanup_future
        return bool(
            (task is not None and not task.done())
            or (cleanup is not None and not cleanup.done())
        )

    def reset(self) -> None:
        _logger.info("重置Agent...")
        self._history.clear()
        self._dispose_parked_reply_runtime()

        if self._agent and AGENTSCOPE_AVAILABLE:
            self._agent.state = AgentState(context=[])

        _logger.info("Agent已重置")

    def get_history(self) -> List[Dict]:
        if self._history_repository:
            return self._history.get_all_messages_persisted()
        return self._history.to_dict_list()

    def extract_agent_memory(self) -> List[Dict]:
        if not self._agent or not hasattr(self._agent, "state"):
            _logger.warning("Agent state not available")
            return []

        try:
            messages = []
            for msg in reversed(self._agent.state.context):
                role = getattr(msg, "role", "unknown")
                if role not in ["user", "assistant", "system"]:
                    continue
                if role == "user":
                    # user message is add, skip here
                    break

                messages.append(serialize_message(msg))

            _logger.info(f"Extracted {len(messages)} messages from agent memory")
            messages.reverse()
            return messages

        except Exception as e:
            _logger.error(f"Failed to extract agent memory: {e}")
            return []

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
        if not self._agent or not hasattr(self._agent, "state"):
            _logger.warning("Agent或state不存在")
            return

        if not AGENTSCOPE_AVAILABLE:
            return

        messages = self._history.get_messages()
        self._agent.state = AgentState(context=messages)
        _logger.info(f"已同步 {len(messages)} 条消息到Agent state")

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
        self._dispose_parked_reply_runtime()
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
