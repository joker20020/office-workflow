import os
from src.core.plugin_base import PluginBase
class EvilPlugin(PluginBase):
    name='evil'; version='1.0'
    def on_enable(self,ctx):pass
    def on_disable(self,ctx=None):pass
