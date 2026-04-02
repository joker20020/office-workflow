# -*- coding: utf-8 -*-
"""
沙箱安全限制测试

通过构造恶意插件代码，验证沙箱各层安全机制是否生效：
  层级 1: AST 代码扫描 — 检测危险 import、exec/eval 调用、__dunder__ 访问
  层级 2: 受限命名空间 — 危险 builtins 被移除
  层级 3: 导入控制 — 黑名单模块被阻止，非白名单模块被阻止
  层级 4: 执行超时 — 无限循环被超时机制终止
  层级 5: 合法插件 — 正常插件可在沙箱中加载运行

运行方式:
    .venv/bin/python tests/test_sandbox.py
"""

import ast
import importlib.util
import shutil
import sys
import textwrap
import threading
from pathlib import Path

# 确保项目根目录在 sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.plugin_base import PluginBase
from src.core.plugin_manager import PluginManager
from src.core.plugin_manifest import PluginManifest
from src.core.plugin_sandbox import (
    ALLOWED_MODULES,
    DANGEROUS_IMPORTS,
    PluginSandbox,
    SandboxWarning,
)
from src.core.permission_manager import Permission, PermissionSet

# ============================================================================
# 测试基础设施
# ============================================================================

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
WARN = "\033[93mWARN\033[0m"

_results: list = []
_tmpdirs: list = []


def _make_tmp_plugin(name: str, code: str) -> Path:
    """在临时目录中创建一个插件并返回其目录路径"""
    tmp = ROOT / "plugins" / f"_sandbox_test_{name}"
    tmp.mkdir(parents=True, exist_ok=True)
    _tmpdirs.append(tmp)

    (tmp / "__init__.py").write_text(textwrap.dedent(code), encoding="utf-8")
    (tmp / "plugin.json").write_text(
        f'{{"name":"{name}","version":"1.0.0","permissions":[]}}', encoding="utf-8"
    )
    return tmp


def _cleanup():
    """清理所有临时插件目录"""
    for d in _tmpdirs:
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
    _tmpdirs.clear()


def record(test_name: str, passed: bool, detail: str = ""):
    tag = PASS if passed else FAIL
    _results.append((test_name, passed, detail))
    print(f"  [{tag}] {test_name}" + (f" — {detail}" if detail else ""))


# ============================================================================
# 层级 1: AST 代码扫描测试
# ============================================================================

def test_ast_scan_dangerous_imports():
    """AST 扫描应检测到危险模块导入"""
    print("\n[层级 1] AST 代码扫描 — 危险模块导入")

    dangerous_cases = {
        "import_os": "import os",
        "import_subprocess": "import subprocess",
        "import_socket": "import socket",
        "import_ctypes": "import ctypes",
        "import_pickle": "import pickle",
        "from_os_import": "from os import path",
        "from_subprocess_import": "from subprocess import Popen",
    }

    sandbox = PluginSandbox(permissions=PermissionSet.empty())

    for case_name, code_line in dangerous_cases.items():
        tmp = _make_tmp_plugin(f"ast_{case_name}", f"{code_line}\n")
        warnings = sandbox.validate_source(tmp)
        has_warning = any(case_name.split("_", 1)[-1] in str(w) for w in warnings) or len(warnings) > 0
        record(f"检测 '{code_line}'", has_warning,
               f"{len(warnings)} warning(s)" if has_warning else "未被检测到!")


def test_ast_scan_dangerous_calls():
    """AST 扫描应检测到 exec/eval/compile 调用"""
    print("\n[层级 1] AST 代码扫描 — 危险函数调用")

    call_cases = {
        "exec_call": "exec('print(1)')",
        "eval_call": "eval('1+1')",
        "compile_call": "compile('x=1', '', 'exec')",
        "dunder_import": "__import__('os')",
    }

    sandbox = PluginSandbox(permissions=PermissionSet.empty())

    for case_name, code_line in call_cases.items():
        tmp = _make_tmp_plugin(f"ast_{case_name}", f"{code_line}\n")
        warnings = sandbox.validate_source(tmp)
        record(f"检测 '{code_line}'", len(warnings) > 0,
               f"{len(warnings)} warning(s)" if warnings else "未被检测到!")


def test_ast_scan_dunder_access():
    """AST 扫描应检测到危险 __dunder__ 属性访问"""
    print("\n[层级 1] AST 代码扫描 — 危险 __dunder__ 属性")

    dunder_cases = {
        "__class__": "x = obj.__class__",
        "__subclasses__": "x = obj.__subclasses__()",
        "__globals__": "x = func.__globals__",
        "__builtins__": "x = obj.__builtins__",
    }

    sandbox = PluginSandbox(permissions=PermissionSet.empty())

    for case_name, code_line in dunder_cases.items():
        tmp = _make_tmp_plugin(f"ast_dunder_{case_name}", f"{code_line}\n")
        warnings = sandbox.validate_source(tmp)
        record(f"检测 '{code_line}'", len(warnings) > 0,
               f"{len(warnings)} warning(s)" if warnings else "未被检测到!")


def test_ast_scan_clean_code():
    """AST 扫描应对合法代码返回 0 警告"""
    print("\n[层级 1] AST 代码扫描 — 合法代码")

    clean_code = """\
    import json
    import math
    from datetime import datetime

    x = json.dumps({"a": 1})
    y = math.sqrt(16)
    z = datetime.now()
    """
    tmp = _make_tmp_plugin("ast_clean", clean_code)
    sandbox = PluginSandbox(permissions=PermissionSet.empty())
    warnings = sandbox.validate_source(tmp)
    record(f"合法代码无警告", len(warnings) == 0,
           f"{len(warnings)} warning(s)" if warnings else "")


# ============================================================================
# 层级 2: 受限命名空间测试
# ============================================================================

def test_restricted_builtins_removed():
    """受限命名空间应移除 exec/eval/compile/open/__import__"""
    print("\n[层级 2] 受限命名空间 — 危险 builtins 移除")

    sandbox = PluginSandbox(permissions=PermissionSet.empty())
    builtins = sandbox.create_restricted_builtins()

    # __import__ 特殊：被替换为受控版本而非移除
    truly_removed = ["exec", "eval", "compile", "globals", "locals", "dir"]
    for name in truly_removed:
        present = name in builtins
        record(f"'{name}' 已移除", not present,
               "仍存在于 builtins 中!" if present else "")

    # __import__ 应被替换为受控版本（阻止危险模块）
    import builtins as real_builtins
    original_import = real_builtins.__import__
    controlled = builtins.get("__import__")
    is_replaced = controlled is not None and controlled is not original_import
    record(f"'__import__' 已替换为受控版本", is_replaced,
           "未替换!" if not is_replaced else "")


def test_restricted_builtins_safe_ones_preserved():
    """受限命名空间应保留安全的 builtins"""
    print("\n[层级 2] 受限命名空间 — 安全 builtins 保留")

    sandbox = PluginSandbox(permissions=PermissionSet.empty())
    builtins = sandbox.create_restricted_builtins()

    safe_builtins = ["print", "len", "range", "int", "str", "list", "dict", "set",
                     "isinstance", "type", "super", "property", "Exception"]
    for name in safe_builtins:
        present = name in builtins
        record(f"'{name}' 可用", present,
               "缺失!" if not present else "")


def test_restricted_builtins_no_open_without_permission():
    """无 FILE_READ 权限时 open 应不可用"""
    print("\n[层级 2] 受限命名空间 — open 权限控制")

    # 无权限
    sandbox_no_perm = PluginSandbox(permissions=PermissionSet.empty())
    builtins_no = sandbox_no_perm.create_restricted_builtins()
    record(f"无权限时 'open' 不可用", "open" not in builtins_no,
           "open 不应存在!" if "open" in builtins_no else "")

    # 有 FILE_READ 权限
    sandbox_read = PluginSandbox(permissions=PermissionSet.from_list([Permission.FILE_READ]))
    builtins_read = sandbox_read.create_restricted_builtins()
    record(f"有 FILE_READ 时 'open' 可用", "open" in builtins_read,
           "open 应该存在!" if "open" not in builtins_read else "")


# ============================================================================
# 层级 3: 导入控制测试
# ============================================================================

def test_import_blacklist():
    """沙箱应阻止导入黑名单模块"""
    print("\n[层级 3] 导入控制 — 黑名单阻止")

    sandbox = PluginSandbox(permissions=PermissionSet.empty())
    builtins = sandbox.create_restricted_builtins()
    controlled_import = builtins["__import__"]

    blocked_modules = ["os", "subprocess", "socket", "ctypes", "pickle",
                       "shutil", "signal", "http", "urllib", "importlib"]
    for mod in blocked_modules:
        try:
            controlled_import(mod)
            record(f"阻止 import {mod}", False, "未被阻止!")
        except ImportError as e:
            record(f"阻止 import {mod}", True, str(e)[:60])


def test_import_whitelist():
    """沙箱应允许导入白名单模块"""
    print("\n[层级 3] 导入控制 — 白名单放行")

    sandbox = PluginSandbox(permissions=PermissionSet.empty())
    builtins = sandbox.create_restricted_builtins()
    controlled_import = builtins["__import__"]

    allowed_modules = ["json", "math", "re", "datetime", "collections",
                       "functools", "typing", "pathlib", "dataclasses",
                       "hashlib", "base64", "uuid", "copy", "enum"]
    for mod in allowed_modules:
        try:
            controlled_import(mod)
            record(f"允许 import {mod}", True)
        except ImportError as e:
            record(f"允许 import {mod}", False, str(e))


def test_import_framework_modules():
    """沙箱应允许导入 src.* 框架模块"""
    print("\n[层级 3] 导入控制 — 框架模块放行")

    sandbox = PluginSandbox(permissions=PermissionSet.empty())
    builtins = sandbox.create_restricted_builtins()
    controlled_import = builtins["__import__"]

    framework_modules = [
        "src.core.plugin_base",
        "src.core.permission_manager",
        "src.core.event_bus",
        "src.utils.logger",
    ]
    for mod in framework_modules:
        try:
            controlled_import(mod)
            record(f"允许 import {mod}", True)
        except ImportError as e:
            record(f"允许 import {mod}", False, str(e))


def test_import_unknown_module_blocked():
    """沙箱应阻止导入非白名单的第三方模块"""
    print("\n[层级 3] 导入控制 — 非白名单模块阻止")

    sandbox = PluginSandbox(permissions=PermissionSet.empty())
    builtins = sandbox.create_restricted_builtins()
    controlled_import = builtins["__import__"]

    unknown_modules = ["numpy", "pandas", "requests", "flask", "django"]
    for mod in unknown_modules:
        try:
            controlled_import(mod)
            # 可能未安装，ImportError 不代表沙箱生效
            record(f"阻止 import {mod}", False, "未被沙箱阻止（但可能模块未安装）")
        except ImportError as e:
            msg = str(e)
            blocked = "沙箱" in msg or "无权" in msg
            record(f"阻止 import {mod}", True if blocked else WARN,
                   f"沙箱阻止" if blocked else f"模块未安装: {msg[:50]}")


# ============================================================================
# 层级 4: 执行超时测试
# ============================================================================

def test_execution_timeout():
    """沙箱应终止超时的插件执行"""
    print("\n[层级 4] 执行超时 — 无限循环阻止")

    sandbox = PluginSandbox(permissions=PermissionSet.empty(), timeout=2)

    def infinite_loop():
        while True:
            pass

    try:
        sandbox.run_with_timeout(infinite_loop, timeout=1)
        record("超时阻止无限循环", False, "未超时!")
    except TimeoutError as e:
        record("超时阻止无限循环", True, str(e)[:60])


def test_execution_normal_function():
    """正常函数应在超时内完成"""
    print("\n[层级 4] 执行超时 — 正常函数完成")

    sandbox = PluginSandbox(permissions=PermissionSet.empty(), timeout=5)

    def normal_func():
        return sum(range(1000))

    try:
        result = sandbox.run_with_timeout(normal_func)
        record("正常函数执行成功", result == 499500, f"结果: {result}")
    except Exception as e:
        record("正常函数执行成功", False, str(e))


def test_execution_exception_propagation():
    """插件异常应正确传播"""
    print("\n[层级 4] 执行超时 — 异常传播")

    sandbox = PluginSandbox(permissions=PermissionSet.empty(), timeout=5)

    def failing_func():
        raise ValueError("插件内部错误")

    try:
        sandbox.run_with_timeout(failing_func)
        record("异常传播", False, "异常未被抛出!")
    except ValueError as e:
        record("异常传播", "插件内部错误" in str(e), str(e))
    except Exception as e:
        record("异常传播", False, f"异常类型错误: {type(e).__name__}: {e}")


# ============================================================================
# 层级 5: 完整插件加载测试
# ============================================================================

def test_malicious_plugin_blocked():
    """包含危险代码的插件应被沙箱阻止加载"""
    print("\n[层级 5] 完整流程 — 恶意插件阻止")

    malicious_codes = {
        "import_os": (
            "import os\nfrom src.core.plugin_base import PluginBase\n"
            "class EvilPlugin(PluginBase):\n"
            "    name='evil'; version='1.0'\n"
            "    def on_enable(self,ctx):pass\n"
            "    def on_disable(self,ctx=None):pass\n"
        ),
        "exec_call": (
            "exec('import os')\nfrom src.core.plugin_base import PluginBase\n"
            "class EvilPlugin(PluginBase):\n"
            "    name='evil2'; version='1.0'\n"
            "    def on_enable(self,ctx):pass\n"
            "    def on_disable(self,ctx=None):pass\n"
        ),
        "importlib_bypass": (
            "import importlib\nfrom src.core.plugin_base import PluginBase\n"
            "class EvilPlugin(PluginBase):\n"
            "    name='evil3'; version='1.0'\n"
            "    def on_enable(self,ctx):pass\n"
            "    def on_disable(self,ctx=None):pass\n"
        ),
    }

    for case_name, code in malicious_codes.items():
        tmp = _make_tmp_plugin(f"evil_{case_name}", code)

        # 通过 PluginManager 尝试发现
        pm = PluginManager(ROOT / "plugins")
        try:
            # 直接调用 _discover_plugin_class 测试沙箱
            sandbox = PluginSandbox(permissions=PermissionSet.empty())
            plugin_class = pm._discover_plugin_class(tmp, sandbox)
            record(f"恶意插件 '{case_name}' 被阻止", plugin_class is None,
                   "插件类仍被加载!" if plugin_class else "加载失败，沙箱生效")
        except Exception as e:
            record(f"恶意插件 '{case_name}' 被阻止", True, f"异常: {type(e).__name__}: {str(e)[:50]}")

        # 检查 AST 警告
        sandbox_check = PluginSandbox(permissions=PermissionSet.empty())
        warnings = sandbox_check.validate_source(tmp)
        record(f"恶意插件 '{case_name}' AST 警告", len(warnings) > 0,
               f"{len(warnings)} warning(s)" if warnings else "AST 未检测到问题!")


def test_legitimate_plugin_loads():
    """合法插件应能在沙箱中正常加载"""
    print("\n[层级 5] 完整流程 — 合法插件加载")

    legitimate_code = """\
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
    """

    tmp = _make_tmp_plugin("legitimate", legitimate_code)

    # AST 扫描应无警告
    sandbox = PluginSandbox(permissions=PermissionSet.empty())
    warnings = sandbox.validate_source(tmp)
    record(f"合法插件 AST 无警告", len(warnings) == 0,
           f"{len(warnings)} warning(s): {[str(w) for w in warnings]}" if warnings else "")

    # 沙箱执行应成功
    pm = PluginManager(ROOT / "plugins")
    plugin_class = pm._discover_plugin_class(tmp, sandbox)
    record(f"合法插件沙箱加载成功", plugin_class is not None,
           "加载失败!" if plugin_class is None else f"class={plugin_class.__name__}")

    # 实例化和生命周期应正常
    if plugin_class:
        try:
            instance = plugin_class()
            sandbox.run_with_timeout(instance.on_enable, args=(None,), timeout=5)
            record(f"合法插件 on_enable 执行", True)
        except Exception as e:
            record(f"合法插件 on_enable 执行", False, str(e))


# ============================================================================
# 层级 6: 沙箱边界测试
# ============================================================================

def test_controlled_open_readonly():
    """受控 open 应限制写入模式"""
    print("\n[层级 6] 边界测试 — 文件写入限制")

    import tempfile

    sandbox_readonly = PluginSandbox(
        permissions=PermissionSet.from_list([Permission.FILE_READ])
    )
    controlled_open = sandbox_readonly._create_controlled_open()

    tmp_file = Path(tempfile.mktemp(suffix=".txt"))

    # 只读模式应允许
    try:
        # 先创建文件
        tmp_file.write_text("test")
        f = controlled_open(tmp_file, "r")
        f.close()
        record("FILE_READ 允许只读 open('r')", True)
    except Exception as e:
        record("FILE_READ 允许只读 open('r')", False, str(e))
    finally:
        tmp_file.unlink(missing_ok=True)

    # 写入模式应阻止
    try:
        f = controlled_open(tmp_file, "w")
        f.close()
        record("FILE_READ 阻止写入 open('w')", False, "未被阻止!")
    except PermissionError:
        record("FILE_READ 阻止写入 open('w')", True)
    except Exception as e:
        record("FILE_READ 阻止写入 open('w')", False, str(e))

    # FILE_WRITE 权限应允许写入
    sandbox_write = PluginSandbox(
        permissions=PermissionSet.from_list([Permission.FILE_READ, Permission.FILE_WRITE])
    )
    write_open = sandbox_write._create_controlled_open()
    try:
        f = write_open(tmp_file, "w")
        f.write("hello")
        f.close()
        record("FILE_WRITE 允许写入 open('w')", True)
    except Exception as e:
        record("FILE_WRITE 允许写入 open('w')", False, str(e))
    finally:
        tmp_file.unlink(missing_ok=True)


def test_timeout_with_args_kwargs():
    """超时执行应正确传递参数"""
    print("\n[层级 6] 边界测试 — 参数传递")

    sandbox = PluginSandbox(permissions=PermissionSet.empty(), timeout=5)

    def add(a, b, extra=0):
        return a + b + extra

    result = sandbox.run_with_timeout(add, args=(1, 2), kwargs={"extra": 10})
    record("参数传递正确", result == 13, f"结果: {result}")


# ============================================================================
# 主测试入口
# ============================================================================

def main():
    print("=" * 60)
    print("  插件沙箱安全限制测试")
    print("=" * 60)

    try:
        # 层级 1: AST 扫描
        test_ast_scan_dangerous_imports()
        test_ast_scan_dangerous_calls()
        test_ast_scan_dunder_access()
        test_ast_scan_clean_code()

        # 层级 2: 受限命名空间
        test_restricted_builtins_removed()
        test_restricted_builtins_safe_ones_preserved()
        test_restricted_builtins_no_open_without_permission()

        # 层级 3: 导入控制
        test_import_blacklist()
        test_import_whitelist()
        test_import_framework_modules()
        test_import_unknown_module_blocked()

        # 层级 4: 执行超时
        test_execution_timeout()
        test_execution_normal_function()
        test_execution_exception_propagation()

        # 层级 5: 完整插件加载
        test_malicious_plugin_blocked()
        test_legitimate_plugin_loads()

        # 层级 6: 边界测试
        test_controlled_open_readonly()
        test_timeout_with_args_kwargs()

    finally:
        _cleanup()

    # 汇总
    print("\n" + "=" * 60)
    total = len(_results)
    passed = sum(1 for _, p, _ in _results if p)
    failed = total - passed
    print(f"  测试结果: {passed}/{total} 通过", end="")
    if failed:
        print(f"  ({failed} 失败)")
    else:
        print("  全部通过!")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
