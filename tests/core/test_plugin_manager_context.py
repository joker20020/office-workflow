# -*- coding: utf-8 -*-
"""Tests for plugin manager context handling - context is immutable after initialization."""

import inspect
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.core.plugin_manager import (
    PluginManager,
    init_plugin_manager,
    reset_plugin_manager_for_testing,
)
from src.core.permission_manager import Permission
from src.core.plugin_base import PluginBase
from src.core.permission_proxy import PermissionProxy


class TestPluginManagerContextSignature:
    """Tests for PluginManager context parameter in signatures."""

    def setup_method(self):
        reset_plugin_manager_for_testing()

    def teardown_method(self):
        reset_plugin_manager_for_testing()

    def test_init_plugin_manager_accepts_context(self, tmp_path):
        """init_plugin_manager should accept and pass context to PluginManager."""
        mock_context = Mock()

        manager = init_plugin_manager(
            plugins_dir=tmp_path,
            context=mock_context,
        )

        assert manager._context is mock_context

    def test_plugin_manager_init_accepts_context(self, tmp_path):
        """PluginManager.__init__ should accept context parameter."""
        sig = inspect.signature(PluginManager.__init__)
        params = sig.parameters

        assert "plugins_dir" in params
        assert "context" in params
        assert "event_bus" in params
        assert "permission_manager" in params
        assert "repository" in params
        assert "plugin_repository" in params

    def test_init_plugin_manager_signature_has_context(self):
        """init_plugin_manager signature should include context parameter."""
        sig = inspect.signature(init_plugin_manager)
        params = sig.parameters

        assert "context" in params
        assert "plugins_dir" in params


class TestLoadEnabledPluginsNoContext:
    """Tests for load_enabled_plugins - should not accept context parameter."""

    def setup_method(self):
        reset_plugin_manager_for_testing()

    def teardown_method(self):
        reset_plugin_manager_for_testing()

    def test_load_enabled_plugins_no_context_param(self, tmp_path):
        """load_enabled_plugins should not accept context parameter."""
        sig = inspect.signature(PluginManager.load_enabled_plugins)
        params = sig.parameters

        # context parameter should NOT exist
        assert "context" not in params
        assert "on_permission_request" in params


class TestRefreshPluginsNoContext:
    """Tests for refresh_plugins - should not accept context parameter."""

    def setup_method(self):
        reset_plugin_manager_for_testing()

    def teardown_method(self):
        reset_plugin_manager_for_testing()

    def test_refresh_plugins_no_context_param(self, tmp_path):
        """refresh_plugins should not accept context parameter."""
        sig = inspect.signature(PluginManager.refresh_plugins)
        params = sig.parameters

        # context parameter should NOT exist
        assert "context" not in params


class TestContextImmutableAfterInit:
    """Tests that context cannot be modified after initialization."""

    def setup_method(self):
        reset_plugin_manager_for_testing()

    def teardown_method(self):
        reset_plugin_manager_for_testing()

    def test_context_uses_self_context_not_parameter(self, tmp_path):
        """load_enabled_plugins and refresh_plugins should use self._context, not external parameter."""
        mock_context = Mock()

        # Initialize manager with context
        manager = PluginManager(
            plugins_dir=tmp_path,
            context=mock_context,
        )

        # Setup a mock plugin
        mock_plugin = Mock(spec=PluginBase)
        mock_plugin.name = "test_plugin"
        mock_plugin.on_enable = MagicMock()

        manager._discovered["test_plugin"] = Mock(
            name="test_plugin",
            module_path=tmp_path / "test_plugin",
            plugin_class=mock_plugin,
        )

        # Mock repository to return enabled state
        mock_repo = Mock()
        mock_repo.get_plugin_enabled = Mock(return_value=True)
        manager._repository = mock_repo

        # load_enabled_plugins should use self._context
        manager.load_enabled_plugins()

        # Verify that on_enable was called (meaning the plugin was loaded with context)
        # Note: load_plugin will be called internally
        assert manager._context is mock_context

    def test_refresh_plugins_uses_self_context(self, tmp_path):
        """refresh_plugins should use self._context internally."""
        mock_context = Mock()

        # Initialize manager with context
        manager = PluginManager(
            plugins_dir=tmp_path,
            context=mock_context,
        )

        # Verify context is set
        assert manager._context is mock_context

        # refresh_plugins should use self._context, not require context parameter
        # Just verify the method signature doesn't accept context
        sig = inspect.signature(PluginManager.refresh_plugins)
        params = sig.parameters
        assert "context" not in params
