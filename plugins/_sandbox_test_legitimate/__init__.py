import json
import math
from pathlib import Path
from src.core.plugin_base import PluginBase
from src.core.permission_manager import Permission, PermissionSet

class GoodPlugin(PluginBase):
    name = "good_plugin"
    version = "1.0.0"
    description = "合法测试插件"
    author = "Test"

    permissions = PermissionSet.from_list([])

    def on_enable(self, context):
        data = json.dumps({"status": "ok"})
        x = math.sqrt(144)

    def on_disable(self, context=None):
        pass
