# -*- coding: utf-8 -*-
"""
插件沙箱模块

为插件代码提供多层安全隔离：
1. AST 代码扫描 — 加载前静态分析，检测危险模式
2. 受限命名空间 — 运行时限制内置函数
3. 导入白名单 — 控制 import 可用的模块
4. 执行超时 — 防止无限循环或长时间阻塞

使用方式：
    from src.core.plugin_sandbox import PluginSandbox
    from src.core.permission_manager import PermissionSet

    sandbox = PluginSandbox(permissions=PermissionSet.from_list([...]))
    warnings = sandbox.validate_source(plugin_dir)
    sandbox.safe_exec_module(spec, module)
    sandbox.run_with_timeout(plugin.on_enable, args=(proxy,), timeout=30)
"""

import ast
import builtins
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from src.core.permission_manager import Permission, PermissionSet
from src.utils.logger import get_logger

_logger = get_logger(__name__)

# =============================================================================
# 危险模块黑名单 — 禁止插件导入
# =============================================================================

DANGEROUS_IMPORTS: Set[str] = {
    # 系统操作
    "os",
    "subprocess",
    "ctypes",
    "signal",
    "multiprocessing",
    "threading",  # 插件不应自行管理线程
    "shutil",
    # 网络
    "socket",
    "http",
    "urllib",
    "ftplib",
    "smtplib",
    "telnetlib",
    "xmlrpc",
    "asyncio",
    # 序列化（代码注入风险）
    "pickle",
    "shelve",
    "marshal",
    "code",
    "codeop",
    "codecs",
    # 其他危险
    "importlib",  # 防止动态导入绕过
    "pkgutil",
    "webbrowser",
    "antigravity",
    "this",
}

# =============================================================================
# 允许导入的模块白名单
# =============================================================================

ALLOWED_MODULES: Set[str] = {
    # 标准库（安全）
    "math",
    "json",
    "re",
    "datetime",
    "collections",
    "itertools",
    "functools",
    "typing",
    "pathlib",
    "dataclasses",
    "abc",
    "enum",
    "copy",
    "string",
    "textwrap",
    "operator",
    "hashlib",
    "base64",
    "decimal",
    "fractions",
    "statistics",
    "random",
    "uuid",
    "pprint",
    "traceback",
    "inspect",
    # 框架模块（src.* 全部允许）
    "src",
    # Qt
    "PySide6",
    # 第三方（常见安全库）
    "agentscope",
}

# =============================================================================
# 安全的内置函数
# =============================================================================

SAFE_BUILTINS: Dict[str, Any] = {
    # 基本类型
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "list": list,
    "dict": dict,
    "set": set,
    "tuple": tuple,
    "bytes": bytes,
    "bytearray": bytearray,
    "type": type,
    "object": object,
    # 类构建（Python class 语句内部需要）
    "__build_class__": __build_class__,
    "__name__": __name__,
    # 类型检查
    "isinstance": isinstance,
    "issubclass": issubclass,
    "hasattr": hasattr,
    "getattr": getattr,
    "setattr": setattr,
    "callable": callable,
    # 内置函数（安全）
    "print": print,
    "len": len,
    "range": range,
    "abs": abs,
    "min": min,
    "max": max,
    "sum": sum,
    "round": round,
    "sorted": sorted,
    "reversed": reversed,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
    "any": any,
    "all": all,
    "chr": chr,
    "ord": ord,
    "hex": hex,
    "oct": oct,
    "bin": bin,
    "id": id,
    "hash": hash,
    "repr": repr,
    "format": format,
    "ascii": ascii,
    "divmod": divmod,
    "pow": pow,
    "input": input,
    # 面向对象
    "property": property,
    "classmethod": classmethod,
    "staticmethod": staticmethod,
    "super": super,
    # 异常
    "Exception": Exception,
    "ValueError": ValueError,
    "TypeError": TypeError,
    "KeyError": KeyError,
    "IndexError": IndexError,
    "AttributeError": AttributeError,
    "RuntimeError": RuntimeError,
    "NotImplementedError": NotImplementedError,
    "StopIteration": StopIteration,
    "FileNotFoundError": FileNotFoundError,
    "PermissionError": PermissionError,
    "OSError": OSError,
    "AssertionError": AssertionError,
    "ImportError": ImportError,
    # 常量
    "True": True,
    "False": False,
    "None": None,
    # typing 相关（模块级别可用）
    "Optional": Optional,
    "List": List,
    "Dict": Dict,
    "Set": Set,
    "Tuple": Tuple,
    "Any": Any,
    "Callable": Callable,
}

# 危险的内置函数 — 从 safe_builtins 中排除
_BLOCKED_BUILTINS = {
    "exec",
    "eval",
    "compile",
    "open",
    "__import__",
    "globals",
    "locals",
    "dir",
    "vars",
    "delattr",
    "breakpoint",
    "memoryview",
    "execfile",
    "reload",
}


class SandboxWarning:
    """沙箱警告"""

    def __init__(self, file: str, line: int, code: str, message: str):
        self.file = file
        self.line = line
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"{self.file}:{self.line} — {self.message} ({self.code})"

    def __repr__(self) -> str:
        return f"SandboxWarning({self.file!r}, {self.line!r}, {self.code!r})"


class PluginSandbox:
    """插件沙箱

    为插件代码提供多层安全隔离。

    Args:
        permissions: 插件被授予的权限集合
        timeout: 插件 on_enable/on_disable 的执行超时（秒）
    """

    def __init__(
        self,
        permissions: PermissionSet,
        timeout: int = 30,
    ):
        self.permissions = permissions
        self.timeout = timeout
        self._warnings: List[SandboxWarning] = []

    # =========================================================================
    # 层级 1: AST 代码扫描
    # =========================================================================

    def validate_source(self, plugin_dir: Path) -> List[SandboxWarning]:
        """AST 级别验证插件源码

        扫描插件目录下所有 .py 文件，检测危险模式：
        - 导入危险模块（os, subprocess, socket 等）
        - 调用 exec()/eval()/compile()
        - 调用 __import__()
        - 访问 __dunder__ 属性（继承链逃逸风险）

        Args:
            plugin_dir: 插件目录路径

        Returns:
            警告列表，空列表表示通过验证
        """
        self._warnings = []

        py_files = list(plugin_dir.rglob("*.py"))
        if not py_files:
            _logger.warning(f"插件目录无 Python 文件: {plugin_dir}")
            return self._warnings

        for py_file in py_files:
            rel_path = str(py_file.relative_to(plugin_dir))
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
                self._check_ast(tree, rel_path)
            except SyntaxError as e:
                self._warnings.append(
                    SandboxWarning(rel_path, e.lineno or 0, "", f"语法错误: {e.msg}")
                )
            except Exception as e:
                self._warnings.append(
                    SandboxWarning(rel_path, 0, "", f"解析失败: {e}")
                )

        _logger.info(
            f"AST 扫描完成: {len(py_files)} 个文件, {len(self._warnings)} 个警告"
        )
        return self._warnings

    def _check_ast(self, tree: ast.AST, file_path: str) -> None:
        """遍历 AST 检查危险模式"""
        for node in ast.walk(tree):
            # 检查 import 语句
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_module = alias.name.split(".")[0]
                    if root_module in DANGEROUS_IMPORTS:
                        self._warnings.append(
                            SandboxWarning(
                                file_path,
                                node.lineno,
                                f"import {alias.name}",
                                f"禁止导入危险模块: {alias.name}",
                            )
                        )

            # 检查 from ... import 语句
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_module = node.module.split(".")[0]
                    if root_module in DANGEROUS_IMPORTS:
                        self._warnings.append(
                            SandboxWarning(
                                file_path,
                                node.lineno,
                                f"from {node.module} import ...",
                                f"禁止从危险模块导入: {node.module}",
                            )
                        )

            # 检查函数调用
            elif isinstance(node, ast.Call):
                func_name = self._get_call_name(node)
                if func_name:
                    # exec/eval/compile
                    if func_name in ("exec", "eval", "compile"):
                        self._warnings.append(
                            SandboxWarning(
                                file_path,
                                node.lineno,
                                f"{func_name}(...)",
                                f"禁止调用 {func_name}()",
                            )
                        )
                    # __import__
                    elif func_name == "__import__":
                        self._warnings.append(
                            SandboxWarning(
                                file_path,
                                node.lineno,
                                "__import__(...)",
                                "禁止调用 __import__()",
                            )
                        )

            # 检查属性访问（继承链逃逸）
            elif isinstance(node, ast.Attribute):
                attr_name = node.attr
                if attr_name.startswith("__") and attr_name.endswith("__"):
                    # 允许 __init__, __name__ 等常用属性
                    allowed_dunders = {
                        "__init__",
                        "__name__",
                        "__all__",
                        "__doc__",
                        "__version__",
                        "__author__",
                        "__file__",
                        "__str__",
                        "__repr__",
                    }
                    if attr_name not in allowed_dunders:
                        self._warnings.append(
                            SandboxWarning(
                                file_path,
                                node.lineno,
                                f".{attr_name}",
                                f"访问特殊属性 {attr_name} 可能存在安全风险",
                            )
                        )

    @staticmethod
    def _get_call_name(node: ast.Call) -> Optional[str]:
        """获取函数调用的名称"""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr
        return None

    @property
    def warnings(self) -> List[SandboxWarning]:
        """获取最近的验证警告"""
        return self._warnings

    def has_errors(self) -> bool:
        """是否存在阻止加载的错误"""
        return len(self._warnings) > 0

    # =========================================================================
    # 层级 2: 受限命名空间
    # =========================================================================

    def create_restricted_builtins(self) -> Dict[str, Any]:
        """创建受限的 __builtins__ 字典

        移除危险内置函数，注入受控的 __import__ 和 open。

        Returns:
            受限的 builtins 字典
        """
        safe = dict(SAFE_BUILTINS)

        # 注入受控的 import
        original_import = builtins.__import__
        safe["__import__"] = self._create_controlled_import(original_import)

        # 如果有 FILE_READ 权限，注入受控的 open
        if self.permissions.has(Permission.FILE_READ):
            safe["open"] = self._create_controlled_open()

        return safe

    def _create_controlled_import(self, original_import: Callable) -> Callable:
        """创建受控的 import 函数"""

        def controlled_import(name: str, *args, **kwargs):
            root_module = name.split(".")[0]

            # 检查黑名单
            if root_module in DANGEROUS_IMPORTS:
                raise ImportError(
                    f"[沙箱] 插件无权导入危险模块: {name}"
                )

            # 检查白名单
            is_allowed = root_module in ALLOWED_MODULES or any(
                name.startswith(allowed + ".") for allowed in ALLOWED_MODULES
            )

            # 允许白名单内的模块和子模块
            if is_allowed:
                return original_import(name, *args, **kwargs)

            # 允许插件内部模块（plugins.* 相对导入）
            if root_module == "plugins":
                return original_import(name, *args, **kwargs)

            # 非白名单模块：阻止导入
            raise ImportError(
                f"[沙箱] 插件无权导入非白名单模块: {name}"
            )

        return controlled_import

    def _create_controlled_open(self) -> Callable:
        """创建受控的 open 函数（只读模式）"""
        original_open = builtins.open

        if self.permissions.has(Permission.FILE_WRITE):
            # 有写权限，不限制
            return original_open

        # 无写权限，限制为只读
        def controlled_open(file, mode="r", *args, **kwargs):
            if isinstance(mode, str) and any(c in mode for c in "wa+x"):
                raise PermissionError(
                    f"[沙箱] 插件无文件写入权限，无法以模式 '{mode}' 打开文件"
                )
            return original_open(file, mode, *args, **kwargs)

        return controlled_open

    # =========================================================================
    # 层级 3: 安全执行
    # =========================================================================

    def safe_exec_module(self, spec, module) -> None:
        """在受限环境中执行模块

        替代直接调用 spec.loader.exec_module(module)，
        在执行前注入受限的 globals。

        Args:
            spec: importlib 模块规格
            module: 已创建的空模块对象
        """
        # 注入受限 builtins 到模块
        restricted_builtins = self.create_restricted_builtins()
        module.__builtins__ = restricted_builtins

        _logger.info(f"[沙箱] 在受限环境中执行模块: {spec.name}")
        spec.loader.exec_module(module)

    # =========================================================================
    # 层级 4: 执行超时
    # =========================================================================

    def run_with_timeout(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: Optional[dict] = None,
        timeout: Optional[int] = None,
    ) -> Any:
        """带超时的函数执行

        在守护线程中执行函数，超时后抛出 TimeoutError。

        Args:
            func: 要执行的函数
            args: 位置参数
            kwargs: 关键字参数
            timeout: 超时秒数，None 使用默认值

        Returns:
            函数返回值

        Raises:
            TimeoutError: 执行超时
            Exception: 函数内部异常
        """
        if timeout is None:
            timeout = self.timeout

        result_holder: list = [None]
        exception_holder: list = [None]

        def target():
            try:
                result_holder[0] = func(*args, **(kwargs or {}))
            except Exception as e:
                exception_holder[0] = e

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            raise TimeoutError(
                f"[沙箱] 插件执行超时 ({timeout}s)，函数: {func.__name__}"
            )

        if exception_holder[0] is not None:
            raise exception_holder[0]

        return result_holder[0]
