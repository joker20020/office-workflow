# -*- coding: utf-8 -*-
"""AgentScope框架集成层"""

import asyncio
import concurrent.futures
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
    from agentscope.permission import PermissionMode
    from agentscope.state import AgentState
    from agentscope.tool import FunctionTool, Toolkit

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
    FunctionTool = None
    ReplyEndEvent = None
    ReplyEndReason = None
    ReplyStartEvent = None
    RequireExternalExecutionEvent = None
    RequireUserConfirmEvent = None
    UserInterruptEvent = None
    PermissionMode = None
    _logger_agent = None

try:
    from agentscope.mcp import MCPClient
except ImportError:
    MCPClient = Any

from src.agent.api_key_manager import ApiKeyManager
from src.agent.async_runtime import AgentAsyncRuntime
from src.agent.chat_history import ChatHistory, serialize_message
from src.agent.tool_registry import AgentToolRegistry
from src.core.change_notifier import ExposureChange
from src.core.permission_manager import Permission
from src.engine.node_engine import NodeEngine
from src.core.config_manager import get_config_manager
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.agent.mcp_server_manager import McpServerManager
    from src.agent.skill_manager import SkillManager
    from src.core.permission_manager import PermissionManager
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
        permission_manager: Optional["PermissionManager"] = None,
    ):
        _logger.info("=" * 50)
        _logger.info("AgentIntegration 开始初始化")
        _logger.info(f"AgentScope可用: {AGENTSCOPE_AVAILABLE}")

        self._api_manager = api_key_manager
        self._node_engine = node_engine
        self._mcp_manager = mcp_manager
        self._skill_manager = skill_manager
        self._history_repository = history_repository
        self._permission_manager = permission_manager
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
        self._async_runtime = AgentAsyncRuntime()
        self._lifecycle_lock: Optional[asyncio.Lock] = None
        self._current_loop: Optional[asyncio.AbstractEventLoop] = None
        self._active_reply_task: Optional[asyncio.Task[Any]] = None
        self._active_reply_cancel_requests: set[asyncio.Task[Any]] = set()
        self._reply_ownership_lock = threading.Lock()
        self._active_reply_owners: List[
            tuple[asyncio.Task[Any], asyncio.AbstractEventLoop]
        ] = []
        self._parked_reply_id: Optional[str] = None
        self._parked_cleanup_future: Optional[concurrent.futures.Future[Any]] = None
        self._last_response_interrupted: bool = False
        self._exposure_change_lock = threading.Lock()
        self._exposure_rebuild_dirty = False
        self._exposure_rebuild_in_progress = False
        self._exposure_rebuild_idle = threading.Event()
        self._exposure_rebuild_idle.set()
        self._exposure_subscriptions: list[tuple[Any, int]] = []
        self._exposure_rebuild_task: Optional[asyncio.Task[Any]] = None
        self._shutdown_started = False

        self._bind_exposure_source(AgentToolRegistry.instance())
        self._bind_exposure_source(self._mcp_manager)
        self._bind_exposure_source(self._skill_manager)
        self._bind_exposure_source(self._permission_manager)

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
                reply.append_event(event)
                self._notify_stream_event(event)
                if isinstance(event, ReplyEndEvent):
                    self._last_response_interrupted = (
                        event.finished_reason == ReplyEndReason.INTERRUPTED
                    )
                    with self._reply_ownership_lock:
                        if getattr(self, "_parked_reply_id", None) == event.reply_id:
                            self._parked_reply_id = None
        except Exception as error:
            raise _ReplyStreamError(error, reply) from error

        return reply

    async def _run_owned_reply_stream(self, inputs: Msg) -> Msg:
        task = asyncio.current_task()
        loop = asyncio.get_running_loop()
        if not hasattr(self, "_reply_ownership_lock"):
            self._reply_ownership_lock = threading.Lock()
            self._active_reply_owners = []
            self._active_reply_cancel_requests = set()
        with self._reply_ownership_lock:
            self._active_reply_owners.append((task, loop))
            self._active_reply_task = task
            self._current_loop = loop
        try:
            return await self._consume_reply_stream(inputs)
        finally:
            with self._reply_ownership_lock:
                self._active_reply_cancel_requests.discard(task)
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

    def _finish_parked_cleanup(
        self,
        cleanup: concurrent.futures.Future[Any],
    ) -> None:
        unsuccessful = cleanup.cancelled()
        if not unsuccessful:
            unsuccessful = cleanup.exception() is not None
        with self._reply_ownership_lock:
            if self._parked_cleanup_future is not cleanup:
                return
            self._parked_cleanup_future = None
            if not unsuccessful:
                self._parked_reply_id = None

    async def _cleanup_parked_reply(self, reply_id: str) -> None:
        await self._agent.reply(inputs=UserInterruptEvent(reply_id=reply_id))
        self._last_response_interrupted = True

    async def _settle_reply_work(self) -> None:
        current = asyncio.current_task()
        with self._reply_ownership_lock:
            active = [
                task
                for task, _loop in self._active_reply_owners
                if task is not current and not task.done()
            ]
            cleanup = self._parked_cleanup_future
            parked_reply_id = self._parked_reply_id
            self._parked_cleanup_future = None

        for task in active:
            task.cancel()
        if active:
            await asyncio.gather(*active, return_exceptions=True)

        had_cleanup = cleanup is not None
        if cleanup is not None and not cleanup.done():
            cleanup.cancel()
        if cleanup is not None:
            try:
                await asyncio.wrap_future(cleanup)
            except (asyncio.CancelledError, Exception):
                pass

        if parked_reply_id is not None and not had_cleanup and self._agent is not None:
            try:
                await self._cleanup_parked_reply(parked_reply_id)
            except Exception as error:
                _logger.warning(f"清理暂停回复失败 ({parked_reply_id}): {error}")

        with self._reply_ownership_lock:
            self._parked_cleanup_future = None
            self._parked_reply_id = None
            self._active_reply_cancel_requests.clear()

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

    def _reject_sync_lifecycle_reentry(self, method_name: str) -> None:
        runtime = getattr(self, "_async_runtime", None)
        if runtime is not None and runtime.in_runtime_thread():
            raise RuntimeError(
                f"{method_name} cannot be called synchronously from the runtime thread"
            )

    def _bind_exposure_source(self, source: Any) -> None:
        if source is None:
            return
        token = source.subscribe_changes(self._on_exposure_change)
        self._exposure_subscriptions.append((source, token))

    def _replace_exposure_source(self, attribute: str, source: Any) -> bool:
        previous = getattr(self, attribute)
        if previous is source:
            return False
        with self._exposure_change_lock:
            for index, (bound_source, token) in enumerate(
                self._exposure_subscriptions
            ):
                if bound_source is previous:
                    previous.unsubscribe_changes(token)
                    self._exposure_subscriptions.pop(index)
                    break
            setattr(self, attribute, source)
            if source is not None and not self._shutdown_started:
                self._bind_exposure_source(source)
        return True

    def _on_exposure_change(self, event: ExposureChange) -> None:
        with self._exposure_change_lock:
            if self._shutdown_started or not self._initialized:
                return
            self._exposure_rebuild_dirty = True
            idle = self._exposure_rebuild_idle
            if self._exposure_rebuild_in_progress:
                owns_drain = False
            else:
                self._exposure_rebuild_in_progress = True
                idle.clear()
                owns_drain = True

        _logger.debug(
            "Agent exposure changed: source=%s action=%s name=%s",
            event.source,
            event.action,
            event.name,
        )
        if not owns_drain:
            if not self._async_runtime.in_runtime_thread():
                idle.wait()
            return

        if self._async_runtime.in_runtime_thread():
            task = asyncio.create_task(self._drain_exposure_rebuilds())
            self._exposure_rebuild_task = task
            task.add_done_callback(self._clear_exposure_rebuild_task)
            return

        try:
            self._async_runtime.run(self._drain_exposure_rebuilds())
        except Exception:
            with self._exposure_change_lock:
                self._exposure_rebuild_dirty = False
                self._exposure_rebuild_in_progress = False
                self._exposure_rebuild_idle.set()
            _logger.exception("Agent exposure rebuild drain failed")

    def _clear_exposure_rebuild_task(self, task: asyncio.Task[Any]) -> None:
        if self._exposure_rebuild_task is task:
            self._exposure_rebuild_task = None
        if not task.cancelled():
            try:
                task.exception()
            except Exception:
                _logger.exception("Agent exposure rebuild task failed")

    async def _drain_exposure_rebuilds(self) -> None:
        transitioned_to_idle = False
        try:
            while True:
                with self._exposure_change_lock:
                    if self._shutdown_started:
                        self._exposure_rebuild_dirty = False
                        self._exposure_rebuild_in_progress = False
                        self._exposure_rebuild_idle.set()
                        transitioned_to_idle = True
                        return
                    self._exposure_rebuild_dirty = False

                try:
                    api_key = self._api_manager.get_key(
                        self._provider,
                        self._model_name,
                    )
                    if not api_key:
                        _logger.error(
                            "Agent exposure rebuild skipped: current API key is unavailable"
                        )
                    else:
                        await self._rebuild_agent_runtime_impl(api_key=api_key)
                except Exception:
                    _logger.exception("Agent exposure rebuild failed")

                with self._exposure_change_lock:
                    if not self._shutdown_started and self._exposure_rebuild_dirty:
                        continue
                    self._exposure_rebuild_dirty = False
                    self._exposure_rebuild_in_progress = False
                    self._exposure_rebuild_idle.set()
                    transitioned_to_idle = True
                    return
        finally:
            if not transitioned_to_idle:
                with self._exposure_change_lock:
                    self._exposure_rebuild_dirty = False
                    self._exposure_rebuild_in_progress = False
                    self._exposure_rebuild_idle.set()

    def _get_lifecycle_lock(self) -> asyncio.Lock:
        lock = getattr(self, "_lifecycle_lock", None)
        if lock is None:
            lock = asyncio.Lock()
            self._lifecycle_lock = lock
        return lock

    def initialize(
        self, provider: str = "dashscope", model_name: str = "", base_url: str = ""
    ) -> bool:
        self._reject_sync_lifecycle_reentry("initialize")
        _logger.info("=" * 50)
        _logger.info(
            f"开始初始化Agent: provider={provider}, model_name={model_name}, base_url={base_url}"
        )

        if not AGENTSCOPE_AVAILABLE:
            _logger.error("AgentScope框架未安装，无法初始化")
            return False
        if provider not in {"openai", "deepseek", "dashscope"}:
            _logger.error(f"不支持的 provider: {provider}")
            return False

        try:
            api_key = self._api_manager.get_key(provider, model_name)
            if not api_key:
                _logger.error(f"未找到 {provider} 的API密钥")
                return False
            config = self._api_manager.get_config(provider)
            if config:
                model_name = model_name or config.get("model_name", "")
                base_url = base_url or config.get("base_url", "")
        except Exception as error:
            _logger.error(f"Agent初始化校验失败: {error}", exc_info=True)
            return False

        try:
            return self._async_runtime.run(
                self._initialize_impl(
                    provider=provider,
                    model_name=model_name,
                    base_url=base_url,
                    api_key=api_key,
                ),
            )
        except Exception as error:
            _logger.error(f"Agent初始化失败: {error}", exc_info=True)
            _logger.error("=" * 50)
            return False

    async def _initialize_impl(
        self,
        *,
        provider: str,
        model_name: str,
        base_url: str,
        api_key: str,
    ) -> bool:
        async with self._get_lifecycle_lock():
            return await self._initialize_transaction(
                provider=provider,
                model_name=model_name,
                base_url=base_url,
                api_key=api_key,
            )

    async def _initialize_transaction(
        self,
        *,
        provider: str,
        model_name: str,
        base_url: str,
        api_key: str,
    ) -> bool:
        await self._settle_reply_work()
        await self._close_published_mcp_clients()
        constructed_agent, toolkit, local_clients = await self._construct_agent_runtime(
            provider=provider,
            model_name=model_name,
            base_url=base_url,
            api_key=api_key,
            state_seed=None,
        )

        self._api_key = "<redacted>"
        self._provider = provider
        self._model_name = model_name
        self._base_url = base_url
        self._publish_agent_runtime(constructed_agent, toolkit, local_clients)
        _logger.info(f"Agent初始化成功: provider={provider}, model={model_name}")
        _logger.info("=" * 50)
        return True

    def _system_prompt(self) -> str:
        return self.config.get(
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

    async def _construct_agent_runtime(
        self,
        *,
        provider: str,
        model_name: str,
        base_url: str,
        api_key: str,
        state_seed: Optional[AgentState],
    ) -> tuple[Any, Any, list[MCPClient]]:
        local_clients: list[MCPClient] = []
        try:
            function_tools = self._build_registry_function_tools()
            local_clients = await self._connect_mcp_clients()
            skill_paths = (
                self._skill_manager.get_enabled_skill_paths()
                if self._skill_manager is not None
                else []
            )
            toolkit = Toolkit(
                tools=function_tools,
                mcps=local_clients,
                skills_or_loaders=skill_paths,
            )
            state = (
                state_seed.model_copy(deep=True)
                if state_seed is not None
                else AgentState(context=self._history.get_messages())
            )
            state.permission_context.mode = PermissionMode.BYPASS
            constructed_agent = Agent(
                name="WorkflowAssistant",
                system_prompt=self._system_prompt(),
                model=self._create_model(provider, model_name, base_url, api_key),
                toolkit=toolkit,
                state=state,
                react_config=ReActConfig(
                    max_iters=50,
                    interruption_raise_cancelled_error=False,
                ),
            )
            return constructed_agent, toolkit, local_clients
        except BaseException:
            await self._close_mcp_clients_cancellation_safe(local_clients)
            raise

    def _publish_agent_runtime(
        self,
        agent: Any,
        toolkit: Any,
        clients: list[MCPClient],
    ) -> None:
        self._agent = agent
        self._toolkit = toolkit
        self._mcp_clients = clients
        self._initialized = True

    def _rebuild_agent_runtime(self) -> bool:
        self._reject_sync_lifecycle_reentry("_rebuild_agent_runtime")
        if (
            not AGENTSCOPE_AVAILABLE
            or not self._initialized
            or self._agent is None
            or not self._provider
        ):
            return False
        try:
            api_key = self._api_manager.get_key(self._provider, self._model_name)
            if not api_key:
                return False
            return self._async_runtime.run(
                self._rebuild_agent_runtime_impl(api_key=api_key),
            )
        except Exception:
            _logger.exception("Agent exposure rebuild failed")
            return False

    async def _rebuild_agent_runtime_impl(self, *, api_key: str) -> bool:
        async with self._get_lifecycle_lock():
            if not self._initialized or self._agent is None:
                return False
            state_seed = self._agent.state.model_copy(deep=True)
            await self._settle_reply_work()
            await self._close_published_mcp_clients()
            constructed_agent, toolkit, local_clients = (
                await self._construct_agent_runtime(
                    provider=self._provider,
                    model_name=self._model_name,
                    base_url=self._base_url,
                    api_key=api_key,
                    state_seed=state_seed,
                )
            )
            self._publish_agent_runtime(constructed_agent, toolkit, local_clients)
            return True

    def _build_registry_function_tools(self) -> List[Any]:
        """Wrap unique registry callables for Toolkit construction."""
        if not AGENTSCOPE_AVAILABLE:
            return []

        function_tools = []
        seen_ids = set()
        for group in AgentToolRegistry.instance().get_group_snapshots():
            if (
                group.owner_name is not None
                and self._permission_manager is not None
                and not self._permission_manager.check(
                    group.owner_name,
                    Permission.AGENT_TOOL,
                )
            ):
                continue
            for tool_func in group.tools:
                tool_id = id(tool_func)
                if tool_id in seen_ids:
                    continue
                seen_ids.add(tool_id)
                function_tools.append(
                    FunctionTool(func=tool_func, is_concurrency_safe=False),
                )

        if function_tools:
            _logger.info(f"已从注册中心加载 {len(function_tools)} 个工具")
        else:
            _logger.info("注册中心无工具可加载")
        return function_tools

    async def _connect_mcp_clients(self) -> list[MCPClient]:
        """Prepare enabled MCP clients in manager order, isolating named failures."""
        if not self._mcp_manager or not AGENTSCOPE_AVAILABLE:
            return []

        clients: list[MCPClient] = []
        try:
            servers = self._mcp_manager.list_servers()
            for server in servers:
                if not server.get("enabled"):
                    continue

                server_name = server["name"]
                client: Optional[MCPClient] = None
                try:
                    client = self._mcp_manager.create_agentscope_client(server_name)
                    if client is None:
                        _logger.warning(
                            f"MCP客户端创建失败 ({server_name}): factory returned None"
                        )
                        continue
                    if client.is_stateful is True:
                        await client.connect()
                    clients.append(client)
                    _logger.info(f"MCP客户端已准备: {server_name}")
                except BaseException as error:
                    client_name = getattr(client, "name", server_name)
                    if not isinstance(error, Exception):
                        if client is not None and client.is_stateful is True:
                            await self._close_mcp_clients_cancellation_safe([client])
                        raise
                    _logger.error(f"MCP客户端准备失败 ({client_name}): {error}")
                    if client is not None and client.is_stateful is True:
                        _, parent_cancellation = (
                            await self._close_mcp_clients_cancellation_safe([client])
                        )
                        if parent_cancellation is not None:
                            raise parent_cancellation
            return clients
        except BaseException:
            await self._close_mcp_clients_cancellation_safe(clients)
            raise

    async def _drain_mcp_clients(
        self,
        clients: list[MCPClient],
    ) -> list[BaseException]:
        errors: list[BaseException] = []
        for client in clients:
            if client.is_stateful is not True:
                continue
            client_name = getattr(client, "name", type(client).__name__)
            try:
                await client.close()
            except BaseException as error:
                errors.append(error)
                _logger.warning(f"关闭MCP客户端失败 ({client_name}): {error}")
        return errors

    async def _await_mcp_client_drain(
        self,
        clients: list[MCPClient],
    ) -> tuple[list[BaseException], Optional[asyncio.CancelledError]]:
        cleanup_task = asyncio.create_task(self._drain_mcp_clients(clients))
        parent_cancellation: Optional[asyncio.CancelledError] = None
        while not cleanup_task.done():
            try:
                await asyncio.shield(cleanup_task)
            except asyncio.CancelledError as error:
                if parent_cancellation is None:
                    parent_cancellation = error
        return cleanup_task.result(), parent_cancellation

    async def _close_mcp_clients_cancellation_safe(
        self,
        clients: list[MCPClient],
    ) -> tuple[list[BaseException], Optional[asyncio.CancelledError]]:
        return await self._await_mcp_client_drain(clients)

    def _detach_published_runtime_state(self) -> list[MCPClient]:
        clients = self._mcp_clients
        self._agent = None
        self._toolkit = None
        self._mcp_clients = []
        self._initialized = False
        return clients

    async def _close_published_mcp_clients(self) -> None:
        clients = self._detach_published_runtime_state()
        errors, parent_cancellation = await self._await_mcp_client_drain(clients)
        if parent_cancellation is not None:
            raise parent_cancellation
        for error in errors:
            if not isinstance(error, Exception):
                raise error

    def chat(self, message: str | List[Dict[str, Any]]) -> str:
        """Send a message through the shared async runtime."""
        _logger.info("=" * 50)
        if not self._initialized:
            _logger.error("Agent未初始化")
            return "Agent未初始化，请先配置API密钥"
        if not self._agent:
            _logger.error("Agent对象为空")
            return "Agent对象为空，请重新初始化"

        try:
            runtime = self._ensure_async_runtime()
            return runtime.run(
                self._chat_impl(message, timeout_as_request_timeout=True),
            )
        except asyncio.TimeoutError:
            return "请求超时，请检查网络连接或API配置"
        except Exception as error:
            _logger.error(f"Agent对话失败: {error}", exc_info=True)
            return f"错误: {error}"

    async def chat_async(self, message: str | List[Dict[str, Any]]) -> str:
        """Await a chat running on the shared async runtime."""
        if not self._initialized or not self._agent:
            return "Agent未初始化，请先配置API密钥"

        try:
            runtime = self._ensure_async_runtime()
            return await runtime.run_async(
                self._chat_impl(message, timeout_as_request_timeout=False),
            )
        except Exception as error:
            _logger.error(f"[异步] Agent对话失败: {error}", exc_info=True)
            return f"错误: {error}"

    def _ensure_async_runtime(self) -> AgentAsyncRuntime:
        """Support legacy instances manually allocated without ``__init__``."""
        runtime = getattr(self, "_async_runtime", None)
        if runtime is None:
            runtime = AgentAsyncRuntime()
            self._async_runtime = runtime
        return runtime

    async def _chat_impl(
        self,
        message: str | List[Dict[str, Any]],
        *,
        timeout_as_request_timeout: bool,
    ) -> str:
        start_time = time.time()
        try:
            if AGENTSCOPE_AVAILABLE and Msg is not None:
                msg = self._create_user_message(message)
                self._history.add_message(msg=msg)
                response_msg = await self._run_owned_reply_stream(msg)
                self._history.add_message(msg=response_msg)
                return (response_msg.get_text_content() or "").strip()
            _logger.error("AgentScope框架未安装")
            return "AgentScope框架未安装"
        except asyncio.CancelledError:
            self._last_response_interrupted = True
            return ""
        except _ReplyStreamError as error:
            self._history.add_message(msg=error.reply)
            if timeout_as_request_timeout and isinstance(
                error.cause,
                asyncio.TimeoutError,
            ):
                elapsed = time.time() - start_time
                return (
                    f"请求超时（{elapsed:.1f}秒），"
                    "请检查网络连接或API配置"
                )
            _logger.error(f"Agent对话失败: {error.cause}", exc_info=True)
            return f"错误: {error.cause}"
        except asyncio.TimeoutError:
            if timeout_as_request_timeout:
                elapsed = time.time() - start_time
                return (
                    f"请求超时（{elapsed:.1f}秒），"
                    "请检查网络连接或API配置"
                )
            return "错误: "
        except Exception as error:
            _logger.error(f"Agent对话失败: {error}", exc_info=True)
            return f"错误: {error}"

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
        cleanup: Optional[concurrent.futures.Future[Any]] = None
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
                    if task in self._active_reply_cancel_requests:
                        return False
                    self._active_reply_cancel_requests.add(task)
                    try:
                        loop.call_soon_threadsafe(task.cancel)
                    except Exception:
                        self._active_reply_cancel_requests.discard(task)
                        raise
                    _logger.info(f"已调度中断: {reason}")
                    return True

                if (
                    self._parked_reply_id is not None
                    and self._parked_cleanup_future is None
                ):
                    cleanup = self._async_runtime.submit(
                        self._cleanup_parked_reply(self._parked_reply_id),
                    )
                    self._parked_cleanup_future = cleanup

            if cleanup is not None:
                cleanup.add_done_callback(self._finish_parked_cleanup)
                _logger.info(f"已调度中断: {reason}")
                return True
        except Exception as error:
            _logger.error(f"中断 Agent 失败: {error}")
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
        self._reject_sync_lifecycle_reentry("reset")
        _logger.info("重置Agent...")
        self._async_runtime.run(self._reset_impl())
        _logger.info("Agent已重置")

    async def _reset_impl(self) -> None:
        async with self._get_lifecycle_lock():
            await self._reset_transaction()

    async def _reset_transaction(self) -> None:
        await self._settle_reply_work()
        await self._close_published_mcp_clients()
        self._history.clear()

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
        self._reject_sync_lifecycle_reentry("switch_session")
        if not self._history_repository:
            _logger.warning("未启用数据库持久化，无法切换会会")
            return False

        try:
            return self._async_runtime.run(self._switch_session_impl(session_id))
        except Exception as error:
            _logger.error(f"切换会话失败: {error}")
            return False

    def _snapshot_history_selection(self) -> tuple[Optional[str], bool, list[Any]]:
        with self._history._lock:
            return (
                self._history._session_id,
                self._history._is_new_session,
                list(self._history._messages),
            )

    def _restore_history_selection(
        self,
        snapshot: tuple[Optional[str], bool, list[Any]],
    ) -> None:
        session_id, is_new_session, messages = snapshot
        with self._history._lock:
            self._history._session_id = session_id
            self._history._is_new_session = is_new_session
            self._history._messages = list(messages)

    async def _switch_session_impl(self, session_id: str) -> bool:
        async with self._get_lifecycle_lock():
            history_snapshot = self._snapshot_history_selection()
            previous_agent_state = getattr(self._agent, "state", None)
            try:
                success = self._history.set_session(session_id)
                if not success:
                    self._restore_history_selection(history_snapshot)
                    return False
                await self._sync_history_to_memory_impl()
            except BaseException as error:
                self._restore_history_selection(history_snapshot)
                if self._agent is not None and hasattr(self._agent, "state"):
                    self._agent.state = previous_agent_state
                if not isinstance(error, Exception):
                    raise
                _logger.error(f"切换会话状态发布失败: {error}")
                return False
            _logger.info(f"切换到会话: {session_id}")
            return True

    def _sync_history_to_memory(self) -> None:
        self._async_runtime.run(self._sync_history_to_memory_impl())

    async def _sync_history_to_memory_impl(self) -> None:
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
        if self._replace_exposure_source("_mcp_manager", manager):
            self._on_exposure_change(
                ExposureChange(source="mcp", action="replaced", name=None),
            )

    def set_skill_manager(self, manager: "SkillManager") -> None:
        if self._replace_exposure_source("_skill_manager", manager):
            self._on_exposure_change(
                ExposureChange(source="skills", action="replaced", name=None),
            )

    def shutdown(self) -> None:
        self._reject_sync_lifecycle_reentry("shutdown")
        exposure_lock = getattr(self, "_exposure_change_lock", None)
        if exposure_lock is not None:
            with exposure_lock:
                self._shutdown_started = True
                subscriptions = self._exposure_subscriptions
                self._exposure_subscriptions = []
                idle = self._exposure_rebuild_idle
            for source, token in subscriptions:
                source.unsubscribe_changes(token)
            idle.wait()
        _logger.info("关闭Agent...")
        self._async_runtime.stop(cleanup_awaitable=self._shutdown_impl())
        self._agent = None
        self._toolkit = None
        self._mcp_clients = []
        self._initialized = False
        _logger.info("Agent已关闭")

    async def _shutdown_impl(self) -> None:
        async with self._get_lifecycle_lock():
            await self._shutdown_transaction()

    async def _shutdown_transaction(self) -> None:
        await self._settle_reply_work()
        await self._close_published_mcp_clients()
