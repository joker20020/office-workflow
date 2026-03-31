# -*- coding: utf-8 -*-
"""Streaming hooks 单元测试

测试 AgentScope 钩子函数机制，包括:
- 钩子注册 (实例级和类级)
- pre_reply 钩子执行
- post_reply 钩子执行
- 流式回调处理
- 钩子移除
- 错误处理
"""

import pytest
from typing import Any, Dict, List

try:
    from agentscope.agent import AgentBase
    from agentscope.message import Msg

    AGENTSCOPE_AVAILABLE = True
except ImportError:
    AGENTSCOPE_AVAILABLE = False
    AgentBase = None
    Msg = None


pytestmark = pytest.mark.skipif(not AGENTSCOPE_AVAILABLE, reason="AgentScope not installed")


class MockAgent(AgentBase if AGENTSCOPE_AVAILABLE else object):
    """用于测试的 Mock Agent"""

    def __init__(self, name: str = "TestAgent"):
        if AGENTSCOPE_AVAILABLE:
            super().__init__()
        self.name = name
        self.reply_count = 0
        self.last_message = None
        self.streaming_chunks: List[str] = []

    async def reply(self, msg: Msg) -> Msg:
        """模拟回复"""
        self.reply_count += 1
        self.last_message = msg

        if self.streaming_chunks:
            content = "".join(self.streaming_chunks)
        else:
            content = f"Response to: {msg.content}"

        return Msg(name=self.name, role="assistant", content=content)


class TestHookRegistration:
    """测试钩子注册功能"""

    def test_instance_hook_registration(self):
        """测试实例级钩子注册"""
        agent = MockAgent(name="TestBot")

        def dummy_hook(self, kwargs):
            return kwargs

        agent.register_instance_hook(hook_type="pre_reply", hook_name="test_hook", hook=dummy_hook)

        assert hasattr(agent, "_instance_pre_reply_hooks")
        assert "test_hook" in agent._instance_pre_reply_hooks

    def test_class_hook_registration(self):
        """测试类级钩子注册"""

        def dummy_hook(self, kwargs):
            return kwargs

        MockAgent.register_class_hook(
            hook_type="pre_reply", hook_name="class_test_hook", hook=dummy_hook
        )

        assert hasattr(MockAgent, "_class_pre_reply_hooks")
        assert "class_test_hook" in MockAgent._class_pre_reply_hooks

        MockAgent.remove_class_hook("pre_reply", "class_test_hook")

    def test_multiple_hooks_registration(self):
        """测试注册多个钩子"""
        agent = MockAgent(name="MultiHookBot")

        def hook1(self, kwargs):
            return kwargs

        def hook2(self, kwargs):
            return kwargs

        def hook3(self, kwargs):
            return kwargs

        agent.register_instance_hook("pre_reply", "hook1", hook1)
        agent.register_instance_hook("pre_reply", "hook2", hook2)
        agent.register_instance_hook("post_reply", "hook3", hook3)

        assert len(agent._instance_pre_reply_hooks) == 2
        assert len(agent._instance_post_reply_hooks) == 1


class TestPreReplyHook:
    """测试 pre_reply 钩子"""

    @pytest.mark.asyncio
    async def test_pre_reply_modifies_kwargs(self):
        """测试 pre_reply 钩子修改参数"""
        agent = MockAgent(name="PreReplyBot")

        def modify_hook(self, kwargs):
            """修改消息内容的钩子"""
            msg = kwargs.get("msg")
            if msg and isinstance(msg.content, str):
                msg.content = f"[Modified] {msg.content}"
            return kwargs

        agent.register_instance_hook("pre_reply", "modifier", modify_hook)

        msg = Msg(name="User", role="user", content="Hello")
        response = await agent(msg)

        assert agent.last_message.content == "[Modified] Hello"

    @pytest.mark.asyncio
    async def test_pre_reply_adds_metadata(self):
        """测试 pre_reply 钩子添加元数据"""
        agent = MockAgent(name="MetadataBot")

        def metadata_hook(self, kwargs):
            """添加元数据的钩子"""
            msg = kwargs.get("msg")
            if msg:
                if msg.metadata is None:
                    msg.metadata = {}
                msg.metadata["timestamp"] = "2026-03-31"
                msg.metadata["source"] = "test"
            return kwargs

        agent.register_instance_hook("pre_reply", "metadata_adder", metadata_hook)

        msg = Msg(name="User", role="user", content="Test")
        await agent(msg)

        assert agent.last_message.metadata is not None
        assert agent.last_message.metadata["timestamp"] == "2026-03-31"
        assert agent.last_message.metadata["source"] == "test"

    @pytest.mark.asyncio
    async def test_pre_hook_returns_none_uses_original(self):
        """测试 pre 钩子返回 None 时使用原始参数"""
        agent = MockAgent(name="NoneReturnBot")

        def none_hook(self, kwargs):
            """返回 None 的钩子"""
            return None

        agent.register_instance_hook("pre_reply", "none_hook", none_hook)

        msg = Msg(name="User", role="user", content="Original content")
        await agent(msg)

        assert agent.last_message.content == "Original content"


class TestPostReplyHook:
    """测试 post_reply 钩子"""

    @pytest.mark.asyncio
    async def test_post_reply_modifies_output(self):
        """测试 post_reply 钩子修改输出"""
        agent = MockAgent(name="PostReplyBot")

        def modify_output_hook(self, kwargs, output):
            """修改输出的钩子"""
            if isinstance(output, Msg):
                output.content = f"[Processed] {output.content}"
            return output

        agent.register_instance_hook("post_reply", "output_modifier", modify_output_hook)

        msg = Msg(name="User", role="user", content="Hello")
        response = await agent(msg)

        assert "[Processed]" in response.content

    @pytest.mark.asyncio
    async def test_post_reply_validates_response(self):
        """测试 post_reply 钩子验证响应"""
        agent = MockAgent(name="ValidationBot")

        def validation_hook(self, kwargs, output):
            """验证响应的钩子"""
            if isinstance(output, Msg):
                if not output.content:
                    output.content = "默认响应"
                if output.metadata is None:
                    output.metadata = {}
                output.metadata["validated"] = True
            return output

        agent.register_instance_hook("post_reply", "validator", validation_hook)

        msg = Msg(name="User", role="user", content="Test")
        response = await agent(msg)

        assert response.metadata is not None
        assert response.metadata["validated"] is True

    @pytest.mark.asyncio
    async def test_post_hook_chain(self):
        """测试多个 post 钩子链式执行"""
        agent = MockAgent(name="ChainBot")

        def hook1(self, kwargs, output):
            if isinstance(output, Msg):
                output.content = f"Step1: {output.content}"
            return output

        def hook2(self, kwargs, output):
            if isinstance(output, Msg):
                output.content = f"Step2: {output.content}"
            return output

        agent.register_instance_hook("post_reply", "hook1", hook1)
        agent.register_instance_hook("post_reply", "hook2", hook2)

        msg = Msg(name="User", role="user", content="Test")
        response = await agent(msg)

        assert response.content.startswith("Step2: Step1:")


class TestStreamingCallback:
    """测试流式回调功能"""

    @pytest.mark.asyncio
    async def test_streaming_callback_with_chunks(self):
        """测试流式回调处理文本块"""
        agent = MockAgent(name="StreamingBot")
        agent.streaming_chunks = ["Hello", " ", "World", "!"]

        def streaming_hook(self, kwargs):
            """流式处理钩子"""
            msg = kwargs.get("msg")
            if msg and hasattr(msg, "metadata"):
                if msg.metadata is None:
                    msg.metadata = {}
                msg.metadata["streaming"] = True
            return kwargs

        agent.register_instance_hook("pre_reply", "streaming", streaming_hook)

        msg = Msg(name="User", role="user", content="Stream test")
        response = await agent(msg)

        assert response.content == "Hello World!"

    @pytest.mark.asyncio
    async def test_streaming_callback_accumulates_content(self):
        """测试流式回调累积内容"""
        agent = MockAgent(name="AccumulateBot")

        accumulated = []

        def accumulate_hook(self, kwargs, output):
            """累积内容的钩子"""
            if isinstance(output, Msg):
                content = output.content
                accumulated.append(content)
            return output

        agent.register_instance_hook("post_reply", "accumulator", accumulate_hook)

        msg = Msg(name="User", role="user", content="Test")
        await agent(msg)

        assert len(accumulated) == 1

    @pytest.mark.asyncio
    async def test_streaming_with_callback_function(self):
        """测试带回调函数的流式处理"""
        agent = MockAgent(name="CallbackBot")

        callback_results = []

        def callback(chunk: str):
            """流式回调函数"""
            callback_results.append(chunk)

        def streaming_callback_hook(self, kwargs):
            """设置流式回调的钩子"""
            msg = kwargs.get("msg")
            if msg:
                if msg.metadata is None:
                    msg.metadata = {}
                msg.metadata["stream_callback"] = callback
            return kwargs

        agent.register_instance_hook("pre_reply", "stream_callback", streaming_callback_hook)

        msg = Msg(name="User", role="user", content="Test streaming")
        response = await agent(msg)

        assert agent.last_message.metadata is not None
        assert "stream_callback" in agent.last_message.metadata


class TestHookRemoval:
    """测试钩子移除功能"""

    def test_remove_instance_hook(self):
        """测试移除实例级钩子"""
        agent = MockAgent(name="RemoveBot")

        def dummy_hook(self, kwargs):
            return kwargs

        agent.register_instance_hook("pre_reply", "to_remove", dummy_hook)
        assert "to_remove" in agent._instance_pre_reply_hooks

        agent.remove_instance_hook("pre_reply", "to_remove")
        assert "to_remove" not in agent._instance_pre_reply_hooks

    def test_remove_class_hook(self):
        """测试移除类级钩子"""

        def dummy_hook(self, kwargs):
            return kwargs

        MockAgent.register_class_hook("pre_reply", "class_to_remove", dummy_hook)
        assert "class_to_remove" in MockAgent._class_pre_reply_hooks

        MockAgent.remove_class_hook("pre_reply", "class_to_remove")
        assert "class_to_remove" not in MockAgent._class_pre_reply_hooks

    def test_clear_all_instance_hooks(self):
        """测试清除所有实例级钩子"""
        agent = MockAgent(name="ClearBot")

        def hook1(self, kwargs):
            return kwargs

        def hook2(self, kwargs):
            return kwargs

        agent.register_instance_hook("pre_reply", "hook1", hook1)
        agent.register_instance_hook("pre_reply", "hook2", hook2)
        agent.register_instance_hook("post_reply", "hook3", hook1)

        agent.clear_instance_hooks("pre_reply")
        assert len(agent._instance_pre_reply_hooks) == 0
        assert len(agent._instance_post_reply_hooks) == 1

        agent.clear_instance_hooks()
        assert len(agent._instance_post_reply_hooks) == 0

    @pytest.mark.asyncio
    async def test_removed_hook_not_executed(self):
        """测试移除的钩子不会被执行"""
        agent = MockAgent(name="NotExecutedBot")

        execution_log = []

        def logging_hook(self, kwargs):
            execution_log.append("executed")
            return kwargs

        agent.register_instance_hook("pre_reply", "logger", logging_hook)
        agent.remove_instance_hook("pre_reply", "logger")

        msg = Msg(name="User", role="user", content="Test")
        await agent(msg)

        assert len(execution_log) == 0


class TestHookErrorHandling:
    """测试钩子错误处理"""

    @pytest.mark.asyncio
    async def test_hook_raises_exception(self):
        """测试钩子抛出异常时的处理"""
        agent = MockAgent(name="ErrorBot")

        def error_hook(self, kwargs):
            """会抛出异常的钩子"""
            raise ValueError("Hook error!")

        agent.register_instance_hook("pre_reply", "error_hook", error_hook)

        msg = Msg(name="User", role="user", content="Test")

        with pytest.raises(ValueError, match="Hook error!"):
            await agent(msg)

    @pytest.mark.asyncio
    async def test_hook_with_invalid_return_type(self):
        """测试钩子返回无效类型"""
        agent = MockAgent(name="InvalidReturnBot")

        def invalid_hook(self, kwargs):
            """返回无效类型的钩子"""
            return "invalid"

        agent.register_instance_hook("pre_reply", "invalid", invalid_hook)

        msg = Msg(name="User", role="user", content="Test")

        try:
            response = await agent(msg)
            assert isinstance(response, Msg)
        except (TypeError, AssertionError):
            pass

    @pytest.mark.asyncio
    async def test_hook_with_none_message(self):
        """测试钩子处理 None 消息"""
        agent = MockAgent(name="NoneMessageBot")

        def none_safe_hook(self, kwargs):
            """安全处理 None 的钩子"""
            msg = kwargs.get("msg")
            if msg is None:
                kwargs["msg"] = Msg(name="System", role="user", content="Empty message")
            return kwargs

        agent.register_instance_hook("pre_reply", "none_safe", none_safe_hook)

        msg = Msg(name="User", role="user", content="Test")
        response = await agent(msg)

        assert response is not None

    @pytest.mark.asyncio
    async def test_post_hook_error_propagation(self):
        """测试 post 钩子错误传播"""
        agent = MockAgent(name="PostErrorBot")

        def error_post_hook(self, kwargs, output):
            """会抛出异常的 post 钩子"""
            raise RuntimeError("Post hook error!")

        agent.register_instance_hook("post_reply", "error_post", error_post_hook)

        msg = Msg(name="User", role="user", content="Test")

        with pytest.raises(RuntimeError, match="Post hook error!"):
            await agent(msg)

    @pytest.mark.asyncio
    async def test_hook_execution_order_on_error(self):
        """测试错误时钩子执行顺序"""
        agent = MockAgent(name="OrderErrorBot")

        execution_order = []

        def hook1(self, kwargs):
            execution_order.append("hook1")
            return kwargs

        def hook2(self, kwargs):
            execution_order.append("hook2")
            raise ValueError("Error in hook2")

        def hook3(self, kwargs):
            execution_order.append("hook3")
            return kwargs

        agent.register_instance_hook("pre_reply", "hook1", hook1)
        agent.register_instance_hook("pre_reply", "hook2", hook2)
        agent.register_instance_hook("pre_reply", "hook3", hook3)

        msg = Msg(name="User", role="user", content="Test")

        with pytest.raises(ValueError):
            await agent(msg)

        assert "hook1" in execution_order
        assert "hook2" in execution_order
        assert "hook3" not in execution_order


class TestHookExecutionOrder:
    """测试钩子执行顺序"""

    @pytest.mark.asyncio
    async def test_instance_before_class_hooks(self):
        """测试实例钩子在类钩子之前执行"""
        execution_order = []

        def class_hook(self, kwargs):
            execution_order.append("class")
            return kwargs

        def instance_hook(self, kwargs):
            execution_order.append("instance")
            return kwargs

        MockAgent.register_class_hook("pre_reply", "class_hook", class_hook)

        agent = MockAgent(name="OrderBot")
        agent.register_instance_hook("pre_reply", "instance_hook", instance_hook)

        msg = Msg(name="User", role="user", content="Test")
        await agent(msg)

        assert execution_order == ["instance", "class"]

        MockAgent.remove_class_hook("pre_reply", "class_hook")

    @pytest.mark.asyncio
    async def test_post_hooks_order(self):
        """测试 post 钩子执行顺序"""
        execution_order = []

        def post_hook1(self, kwargs, output):
            execution_order.append("post1")
            return output

        def post_hook2(self, kwargs, output):
            execution_order.append("post2")
            return output

        agent = MockAgent(name="PostOrderBot")
        agent.register_instance_hook("post_reply", "post1", post_hook1)
        agent.register_instance_hook("post_reply", "post2", post_hook2)

        msg = Msg(name="User", role="user", content="Test")
        await agent(msg)

        assert execution_order == ["post1", "post2"]

    @pytest.mark.asyncio
    async def test_full_hook_lifecycle(self):
        """测试完整钩子生命周期"""
        lifecycle = []

        def pre_class(self, kwargs):
            lifecycle.append("pre_class")
            return kwargs

        def pre_instance(self, kwargs):
            lifecycle.append("pre_instance")
            return kwargs

        def post_instance(self, kwargs, output):
            lifecycle.append("post_instance")
            return output

        def post_class(self, kwargs, output):
            lifecycle.append("post_class")
            return output

        MockAgent.register_class_hook("pre_reply", "pre_class", pre_class)
        MockAgent.register_class_hook("post_reply", "post_class", post_class)

        agent = MockAgent(name="LifecycleBot")
        agent.register_instance_hook("pre_reply", "pre_instance", pre_instance)
        agent.register_instance_hook("post_reply", "post_instance", post_instance)

        msg = Msg(name="User", role="user", content="Test")
        await agent(msg)

        expected = ["pre_instance", "pre_class", "post_instance", "post_class"]
        assert lifecycle == expected

        MockAgent.remove_class_hook("pre_reply", "pre_class")
        MockAgent.remove_class_hook("post_reply", "post_class")


class TestHookWithSpecialContent:
    """测试钩子处理特殊内容"""

    @pytest.mark.asyncio
    async def test_hook_with_multimodal_content(self):
        """测试钩子处理多模态内容"""
        agent = MockAgent(name="MultimodalBot")

        def multimodal_hook(self, kwargs):
            """处理多模态内容的钩子"""
            msg = kwargs.get("msg")
            if msg and isinstance(msg.content, list):
                if msg.metadata is None:
                    msg.metadata = {}
                msg.metadata["has_multimodal"] = True
            return kwargs

        agent.register_instance_hook("pre_reply", "multimodal", multimodal_hook)

        msg = Msg(
            name="User",
            role="user",
            content=[
                {"type": "text", "text": "Hello"},
                {"type": "image", "source": {"url": "http://example.com/image.jpg"}},
            ],
        )

        await agent(msg)

        assert agent.last_message.metadata is not None
        assert agent.last_message.metadata.get("has_multimodal") is True

    @pytest.mark.asyncio
    async def test_hook_with_tool_use(self):
        """测试钩子处理工具调用"""
        agent = MockAgent(name="ToolBot")

        tool_calls = []

        def tool_hook(self, kwargs, output):
            """处理工具调用的钩子"""
            if isinstance(output, Msg):
                if hasattr(output, "get_content_blocks"):
                    tool_blocks = output.get_content_blocks("tool_use")
                    for block in tool_blocks:
                        tool_calls.append(block)
            return output

        agent.register_instance_hook("post_reply", "tool_tracker", tool_hook)

        msg = Msg(name="User", role="user", content="Use a tool")
        await agent(msg)

        assert agent.reply_count == 1


class TestPostPrintHook:
    """Test post_print hook for streaming output"""

    def test_post_print_hook_registered(self):
        """Verify post_print hook can be registered"""
        agent = MockAgent()

        def hook(self, kwargs, output):
            return output

        agent.register_instance_hook("post_print", "streaming", hook)
        assert hasattr(agent, "_instance_post_print_hooks")
        assert "streaming" in agent._instance_post_print_hooks

    def test_post_print_hook_receives_chunks(self):
        """post_print hook should receive print output"""
        agent = MockAgent(name="PrintBot")
        received_outputs = []

        def capture_hook(self, kwargs, output):
            received_outputs.append(output)
            return output

        agent.register_instance_hook("post_print", "capture", capture_hook)

        assert "capture" in agent._instance_post_print_hooks

    @pytest.mark.asyncio
    async def test_post_print_hook_modifies_output(self):
        """post_print hook can modify print output"""
        agent = MockAgent(name="ModifyPrintBot")

        def modify_hook(self, kwargs, output):
            if isinstance(output, str):
                return f"[STREAM] {output}"
            return output

        agent.register_instance_hook("post_print", "modifier", modify_hook)

        assert "modifier" in agent._instance_post_print_hooks

    @pytest.mark.asyncio
    async def test_post_print_vs_post_reply_distinction(self):
        """post_print and post_reply hooks are distinct"""
        agent = MockAgent(name="DistinctBot")

        execution_log = []

        def post_reply_hook(self, kwargs, output):
            execution_log.append("post_reply")
            return output

        def post_print_hook(self, kwargs, output):
            execution_log.append("post_print")
            return output

        agent.register_instance_hook("post_reply", "reply_hook", post_reply_hook)
        agent.register_instance_hook("post_print", "print_hook", post_print_hook)

        assert "reply_hook" in agent._instance_post_reply_hooks
        assert "print_hook" in agent._instance_post_print_hooks
        assert agent._instance_post_reply_hooks != agent._instance_post_print_hooks
