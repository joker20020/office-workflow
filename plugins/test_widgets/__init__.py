# -*- coding: utf-8 -*-
"""
内联控件测试插件

提供完整的测试节点集，用于手动测试节点编辑器的所有功能：

输入控件类型:
- 文本输入 (text)
- 数字输入 (number) - 整数和浮点数
- 布尔值复选框 (checkbox)
- 下拉选择框 (dropdown)
- 文件选择器 (file)

输出预览类型:
- 字符串预览
- 数字预览
- 列表/字典预览

使用方式:
    # 在节点面板中拖入测试节点进行测试
    # 或通过代码注册
    from plugins.test_widgets import TestWidgetsPlugin
    plugin = TestWidgetsPlugin()
    plugin.on_load(context)

测试场景:
    1. 单个控件测试: 拖入"文本输入测试"节点，修改输入值， 执行查看输出
    2. 连接线测试: 连接"数据源"和"字符串处理"节点
 移动节点观察连接线更新
    3. 控件禁用测试: 连接后观察输入控件是否被禁用（LiteGraph 模式）
    4. 输出预览测试: 执行"输出预览测试"节点， 观察预览控件显示
    5. 综合测试: 使用"综合测试"节点验证所有控件类型
"""

from src.core.plugin_base import PluginBase
from src.core.permission_manager import Permission, PermissionSet
from src.engine.definitions import NodeDefinition, PortDefinition, PortType
from src.utils.logger import get_logger

_logger = get_logger(__name__)


# =============================================================================
# 基础输入控件测试节点
# =============================================================================

TEXT_INPUT_DEFINITION = NodeDefinition(
    node_type="test.text_input",
    display_name="文本输入测试",
    description="测试文本输入控件",
    category="测试-输入控件",
    icon="📝",
    inputs=[
        PortDefinition(
            name="text",
            type=PortType.STRING,
            description="输入文本",
            default="Hello World",
            widget_type="text",
        ),
    ],
    outputs=[
        PortDefinition(
            name="output",
            type=PortType.STRING,
            description="输出文本",
        ),
        PortDefinition(
            name="length",
            type=PortType.INTEGER,
            description="文本长度",
            show_preview=True,
        ),
    ],
    execute=lambda text: (
        print(f"[文本输入测试] 输入: '{text}', 长度: {len(text)}"),
        {"output": text, "length": len(text)},
    )[-1],
)


MULTI_TEXT_INPUT_DEFINITION = NodeDefinition(
    node_type="test.multi_text_input",
    display_name="多文本输入测试",
    description="测试多个文本输入控件",
    category="测试-输入控件",
    icon="📝📝",
    inputs=[
        PortDefinition(
            name="text1",
            type=PortType.STRING,
            description="第一个文本",
            default="Hello",
            widget_type="text",
        ),
        PortDefinition(
            name="text2",
            type=PortType.STRING,
            description="第二个文本",
            default="World",
            widget_type="text",
        ),
        PortDefinition(
            name="separator",
            type=PortType.STRING,
            description="分隔符",
            default=" ",
            widget_type="text",
        ),
    ],
    outputs=[
        PortDefinition(
            name="combined",
            type=PortType.STRING,
            description="合并后的文本",
            show_preview=True,
        ),
    ],
    execute=lambda text1, text2, separator: (
        print(f"[多文本输入] '{text1}' + '{separator}' + '{text2}' = '{text1}{separator}{text2}'"),
        {"combined": f"{text1}{separator}{text2}"},
    )[-1],
)


INTEGER_INPUT_DEFINITION = NodeDefinition(
    node_type="test.integer_input",
    display_name="整数输入测试",
    description="测试整数输入控件",
    category="测试-输入控件",
    icon="🔢",
    inputs=[
        PortDefinition(
            name="value",
            type=PortType.INTEGER,
            description="整数值",
            default=42,
            widget_type="number",
        ),
    ],
    outputs=[
        PortDefinition(
            name="output",
            type=PortType.INTEGER,
            description="输出值",
        ),
        PortDefinition(
            name="doubled",
            type=PortType.INTEGER,
            description="两倍值",
            show_preview=True,
        ),
        PortDefinition(
            name="squared",
            type=PortType.INTEGER,
            description="平方值",
            show_preview=True,
        ),
    ],
    execute=lambda value: (
        print(f"[整数输入] 值: {value}, 两倍: {value * 2}, 平方: {value * value}"),
        {"output": value, "doubled": value * 2, "squared": value * value},
    )[-1],
)


FLOAT_INPUT_DEFINITION = NodeDefinition(
    node_type="test.float_input",
    display_name="浮点数输入测试",
    description="测试浮点数输入控件",
    category="测试-输入控件",
    icon="🔢",
    inputs=[
        PortDefinition(
            name="value",
            type=PortType.FLOAT,
            description="浮点数值",
            default=3.14,
            widget_type="number",
        ),
    ],
    outputs=[
        PortDefinition(
            name="output",
            type=PortType.FLOAT,
            description="输出值",
        ),
        PortDefinition(
            name="squared",
            type=PortType.FLOAT,
            description="平方值",
            show_preview=True,
        ),
        PortDefinition(
            name="rounded",
            type=PortType.INTEGER,
            description="四舍五入",
            show_preview=True,
        ),
    ],
    execute=lambda value: (
        print(f"[浮点数输入] 值: {value}, 平方: {value * value:.4f}, 四舍五入: {round(value)}"),
        {"output": value, "squared": value * value, "rounded": round(value)},
    )[-1],
)


BOOLEAN_INPUT_DEFINITION = NodeDefinition(
    node_type="test.boolean_input",
    display_name="布尔值输入测试",
    description="测试布尔值复选框控件",
    category="测试-输入控件",
    icon="☑️",
    inputs=[
        PortDefinition(
            name="enabled",
            type=PortType.BOOLEAN,
            description="是否启用",
            default=True,
            widget_type="checkbox",
        ),
    ],
    outputs=[
        PortDefinition(
            name="status",
            type=PortType.STRING,
            description="状态文本",
            show_preview=True,
        ),
        PortDefinition(
            name="is_enabled",
            type=PortType.BOOLEAN,
            description="布尔输出",
        ),
    ],
    execute=lambda enabled: (
        print(f"[布尔值输入] 启用状态: {enabled}, 输出: {'✓ 已启用' if enabled else '✗ 已禁用'}"),
        {"status": "✓ 已启用" if enabled else "✗ 已禁用", "is_enabled": enabled},
    )[-1],
)


DROPDOWN_INPUT_DEFINITION = NodeDefinition(
    node_type="test.dropdown_input",
    display_name="下拉选择测试",
    description="测试下拉选择控件",
    category="测试-输入控件",
    icon="📋",
    inputs=[
        PortDefinition(
            name="choice",
            type=PortType.STRING,
            description="选择选项",
            default="是",
            widget_type="dropdown",
        ),
    ],
    outputs=[
        PortDefinition(
            name="selected",
            type=PortType.STRING,
            description="选中的值",
            show_preview=True,
        ),
        PortDefinition(
            name="is_yes",
            type=PortType.BOOLEAN,
            description="是否选择'是'",
        ),
    ],
    execute=lambda choice: (
        print(f"[下拉选择] 选中: '{choice}', 是否选择'是': {choice == '是'}"),
        {"selected": f"您选择了: {choice}", "is_yes": choice == "是"},
    )[-1],
)


FILE_INPUT_DEFINITION = NodeDefinition(
    node_type="test.file_input",
    display_name="文件选择测试",
    description="测试文件选择器控件",
    category="测试-输入控件",
    icon="📁",
    inputs=[
        PortDefinition(
            name="file_path",
            type=PortType.FILE,
            description="选择文件",
            default="",
            widget_type="file",
        ),
    ],
    outputs=[
        PortDefinition(
            name="path",
            type=PortType.STRING,
            description="文件路径",
            show_preview=True,
        ),
        PortDefinition(
            name="filename",
            type=PortType.STRING,
            description="文件名",
        ),
    ],
    execute=lambda file_path: (
        print(
            f"[文件选择] 路径: '{file_path or '(未选择)'}', 文件名: '{file_path.split('/')[-1] if file_path else '(无)'}'"
        ),
        {
            "path": file_path or "未选择文件",
            "filename": file_path.split("/")[-1] if file_path else "",
        },
    )[-1],
)


# =============================================================================
# 输出预览测试节点
# =============================================================================

OUTPUT_PREVIEW_TEST_DEFINITION = NodeDefinition(
    node_type="test.output_preview",
    display_name="输出预览测试",
    description="测试各种输出预览控件（部分启用预览）",
    category="测试-输出预览",
    icon="📊",
    inputs=[
        PortDefinition(
            name="input",
            type=PortType.STRING,
            description="输入文本",
            default="Hello World",
            widget_type="text",
        ),
    ],
    outputs=[
        PortDefinition(
            name="string_output",
            type=PortType.STRING,
            description="字符串输出（启用预览）",
            show_preview=True,
        ),
        PortDefinition(
            name="integer_output",
            type=PortType.INTEGER,
            description="整数输出（启用预览）",
            show_preview=True,
        ),
        PortDefinition(
            name="float_output",
            type=PortType.FLOAT,
            description="浮点数输出（不预览）",
        ),
        PortDefinition(
            name="list_output",
            type=PortType.LIST,
            description="列表输出（启用预览）",
            show_preview=True,
        ),
        PortDefinition(
            name="dict_output",
            type=PortType.DICT,
            description="字典输出（启用预览）",
            show_preview=True,
        ),
    ],
    execute=lambda input: (
        print(f"[输出预览测试] 输入: '{input}'"),
        print(f"  -> 字符串输出: '处理后的: {input}'"),
        print(f"  -> 整数输出: {len(input)}"),
        print(f"  -> 浮点数输出: {len(input) * 1.5}"),
        print(f"  -> 列表输出: {[input, len(input), input.upper(), input.lower()]}"),
        {
            "string_output": f"处理后的: {input}",
            "integer_output": len(input),
            "float_output": len(input) * 1.5,
            "list_output": [input, len(input), input.upper(), input.lower()],
            "dict_output": {
                "original": input,
                "length": len(input),
                "upper": input.upper(),
                "lower": input.lower(),
            },
        },
    )[-1],
)


# =============================================================================
# 数据处理节点（用于连接测试）
# =============================================================================

DATA_SOURCE_DEFINITION = NodeDefinition(
    node_type="test.data_source",
    display_name="数据源",
    description="简单的数据源节点，用于测试连接",
    category="测试-数据处理",
    icon="📤",
    inputs=[],
    outputs=[
        PortDefinition(
            name="text",
            type=PortType.STRING,
            description="文本数据",
        ),
        PortDefinition(
            name="number",
            type=PortType.INTEGER,
            description="数字数据",
        ),
    ],
    execute=lambda: (
        print("[数据源] 生成数据: text='Hello from source!', number=42"),
        {"text": "Hello from source!", "number": 42},
    )[-1],
)


STRING_PROCESSOR_DEFINITION = NodeDefinition(
    node_type="test.string_processor",
    display_name="字符串处理",
    description="处理输入的字符串",
    category="测试-数据处理",
    icon="🔧",
    inputs=[
        PortDefinition(
            name="input",
            type=PortType.STRING,
            description="输入字符串",
        ),
        PortDefinition(
            name="prefix",
            type=PortType.STRING,
            description="前缀",
            default="[处理]",
            widget_type="text",
        ),
    ],
    outputs=[
        PortDefinition(
            name="upper",
            type=PortType.STRING,
            description="大写",
            show_preview=True,
        ),
        PortDefinition(
            name="lower",
            type=PortType.STRING,
            description="小写",
        ),
        PortDefinition(
            name="prefixed",
            type=PortType.STRING,
            description="带前缀",
            show_preview=True,
        ),
    ],
    execute=lambda input, prefix: (
        print(f"[字符串处理] 输入: '{input or '(空)'}', 前缀: '{prefix}'"),
        print(f"  -> 大写: '{input.upper() if input else ''}'"),
        print(f"  -> 小写: '{input.lower() if input else ''}'"),
        print(f"  -> 带前缀: '{prefix} {input if input else ''}'"),
        {
            "upper": input.upper() if input else "",
            "lower": input.lower() if input else "",
            "prefixed": f"{prefix} {input}" if input else prefix,
        },
    )[-1],
)


MATH_CALCULATOR_DEFINITION = NodeDefinition(
    node_type="test.math_calculator",
    display_name="数学计算",
    description="简单的数学运算",
    category="测试-数据处理",
    icon="🧮",
    inputs=[
        PortDefinition(
            name="a",
            type=PortType.FLOAT,
            description="数值A",
            default=10,
            widget_type="number",
        ),
        PortDefinition(
            name="b",
            type=PortType.FLOAT,
            description="数值B",
            default=5,
            widget_type="number",
        ),
    ],
    outputs=[
        PortDefinition(
            name="sum",
            type=PortType.FLOAT,
            description="和 (A+B)",
            show_preview=True,
        ),
        PortDefinition(
            name="difference",
            type=PortType.FLOAT,
            description="差 (A-B)",
        ),
        PortDefinition(
            name="product",
            type=PortType.FLOAT,
            description="积 (A*B)",
            show_preview=True,
        ),
        PortDefinition(
            name="quotient",
            type=PortType.FLOAT,
            description="商 (A/B)",
        ),
    ],
    execute=lambda a, b: (
        print(f"[数学计算] A={a}, B={b}"),
        print(f"  -> 和 (A+B): {a + b}"),
        print(f"  -> 差 (A-B): {a - b}"),
        print(f"  -> 积 (A*B): {a * b}"),
        print(f"  -> 商 (A/B): {a / b if b != 0 else '除零错误'}"),
        {
            "sum": a + b,
            "difference": a - b,
            "product": a * b,
            "quotient": a / b if b != 0 else 0,
        },
    )[-1],
)


# =============================================================================
# 综合测试节点
# =============================================================================


def _comprehensive_execute(
    text_input,
    integer_input,
    float_input,
    bool_input,
    dropdown_input,
    file_input,
    external_input=None,
):
    """综合测试节点执行函数"""
    print("=" * 50)
    print("[综合测试] 执行参数:")
    print(f"  文本输入: '{text_input}'")
    print(f"  整数输入: {integer_input}")
    print(f"  浮点数输入: {float_input}")
    print(f"  布尔输入: {bool_input}")
    print(f"  下拉选择: '{dropdown_input}'")
    print(f"  文件选择: '{file_input or '(未选择)'}'")
    print(f"  外部输入: '{external_input or '(无)'}'")
    print("-" * 50)
    print("输出结果:")
    text_output = f"{text_input} ({dropdown_input})"
    number_output = integer_input * float_input
    list_output = [text_input, integer_input, float_input, bool_input, dropdown_input]
    dict_output = {
        "text": text_input,
        "int": integer_input,
        "float": float_input,
        "bool": bool_input,
        "dropdown": dropdown_input,
        "file": file_input,
        "external": external_input,
    }
    print(f"  文本输出: '{text_output}'")
    print(f"  数字输出: {number_output}")
    print(f"  列表输出: {list_output}")
    print(f"  字典输出: {dict_output}")
    print("=" * 50)
    return {
        "text_output": text_output,
        "number_output": number_output,
        "list_output": list_output,
        "dict_output": dict_output,
    }


COMPREHENSIVE_TEST_DEFINITION = NodeDefinition(
    node_type="test.comprehensive",
    display_name="综合测试",
    description="测试所有控件类型的综合节点",
    category="测试-综合",
    icon="🧪",
    inputs=[
        PortDefinition(
            name="text_input",
            type=PortType.STRING,
            description="文本输入",
            default="测试文本",
            widget_type="text",
        ),
        PortDefinition(
            name="integer_input",
            type=PortType.INTEGER,
            description="整数输入",
            default=100,
            widget_type="number",
        ),
        PortDefinition(
            name="float_input",
            type=PortType.FLOAT,
            description="浮点数输入",
            default=1.5,
            widget_type="number",
        ),
        PortDefinition(
            name="bool_input",
            type=PortType.BOOLEAN,
            description="布尔输入",
            default=True,
            widget_type="checkbox",
        ),
        PortDefinition(
            name="dropdown_input",
            type=PortType.STRING,
            description="下拉选择",
            default="是",
            widget_type="dropdown",
        ),
        PortDefinition(
            name="file_input",
            type=PortType.FILE,
            description="文件选择",
            default="",
            widget_type="file",
        ),
        PortDefinition(
            name="external_input",
            type=PortType.STRING,
            description="外部输入（无控件）",
        ),
    ],
    outputs=[
        PortDefinition(
            name="text_output",
            type=PortType.STRING,
            description="文本输出",
            show_preview=True,
        ),
        PortDefinition(
            name="number_output",
            type=PortType.FLOAT,
            description="数字输出",
            show_preview=True,
        ),
        PortDefinition(
            name="list_output",
            type=PortType.LIST,
            description="列表输出",
            show_preview=True,
        ),
        PortDefinition(
            name="dict_output",
            type=PortType.DICT,
            description="字典输出",
            show_preview=True,
        ),
    ],
    execute=_comprehensive_execute,
)


# =============================================================================
# 数据处理节点（用于连接测试）
# =============================================================================

DATA_SOURCE_DEFINITION = NodeDefinition(
    node_type="test.data_source",
    display_name="数据源",
    description="简单的数据源节点，用于测试连接",
    category="测试-数据处理",
    icon="📤",
    inputs=[],
    outputs=[
        PortDefinition(
            name="text",
            type=PortType.STRING,
            description="文本数据",
        ),
        PortDefinition(
            name="number",
            type=PortType.INTEGER,
            description="数字数据",
        ),
    ],
    execute=lambda: {
        "text": "Hello from source!",
        "number": 42,
    },
)


STRING_PROCESSOR_DEFINITION = NodeDefinition(
    node_type="test.string_processor",
    display_name="字符串处理",
    description="处理输入的字符串",
    category="测试-数据处理",
    icon="🔧",
    inputs=[
        PortDefinition(
            name="input",
            type=PortType.STRING,
            description="输入字符串",
        ),
        PortDefinition(
            name="prefix",
            type=PortType.STRING,
            description="前缀",
            default="[处理]",
            widget_type="text",
        ),
    ],
    outputs=[
        PortDefinition(
            name="upper",
            type=PortType.STRING,
            description="大写",
            show_preview=True,
        ),
        PortDefinition(
            name="lower",
            type=PortType.STRING,
            description="小写",
        ),
        PortDefinition(
            name="prefixed",
            type=PortType.STRING,
            description="带前缀",
            show_preview=True,
        ),
    ],
    execute=lambda input, prefix: {
        "upper": input.upper() if input else "",
        "lower": input.lower() if input else "",
        "prefixed": f"{prefix} {input}" if input else prefix,
    },
)


MATH_CALCULATOR_DEFINITION = NodeDefinition(
    node_type="test.math_calculator",
    display_name="数学计算",
    description="简单的数学运算",
    category="测试-数据处理",
    icon="🧮",
    inputs=[
        PortDefinition(
            name="a",
            type=PortType.FLOAT,
            description="数值A",
            default=10,
            widget_type="number",
        ),
        PortDefinition(
            name="b",
            type=PortType.FLOAT,
            description="数值B",
            default=5,
            widget_type="number",
        ),
    ],
    outputs=[
        PortDefinition(
            name="sum",
            type=PortType.FLOAT,
            description="和 (A+B)",
            show_preview=True,
        ),
        PortDefinition(
            name="difference",
            type=PortType.FLOAT,
            description="差 (A-B)",
        ),
        PortDefinition(
            name="product",
            type=PortType.FLOAT,
            description="积 (A*B)",
            show_preview=True,
        ),
        PortDefinition(
            name="quotient",
            type=PortType.FLOAT,
            description="商 (A/B)",
        ),
    ],
    execute=lambda a, b: {
        "sum": a + b,
        "difference": a - b,
        "product": a * b,
        "quotient": a / b if b != 0 else 0,
    },
)


# =============================================================================
# 综合测试节点
# =============================================================================

COMPREHENSIVE_TEST_DEFINITION = NodeDefinition(
    node_type="test.comprehensive",
    display_name="综合测试",
    description="测试所有控件类型的综合节点",
    category="测试-综合",
    icon="🧪",
    inputs=[
        PortDefinition(
            name="text_input",
            type=PortType.STRING,
            description="文本输入",
            default="测试文本",
            widget_type="text",
        ),
        PortDefinition(
            name="integer_input",
            type=PortType.INTEGER,
            description="整数输入",
            default=100,
            widget_type="number",
        ),
        PortDefinition(
            name="float_input",
            type=PortType.FLOAT,
            description="浮点数输入",
            default=1.5,
            widget_type="number",
        ),
        PortDefinition(
            name="bool_input",
            type=PortType.BOOLEAN,
            description="布尔输入",
            default=True,
            widget_type="checkbox",
        ),
        PortDefinition(
            name="dropdown_input",
            type=PortType.STRING,
            description="下拉选择",
            default="是",
            widget_type="dropdown",
        ),
        PortDefinition(
            name="file_input",
            type=PortType.FILE,
            description="文件选择",
            default="",
            widget_type="file",
        ),
        PortDefinition(
            name="external_input",
            type=PortType.STRING,
            description="外部输入（无控件）",
            required=False,
        ),
    ],
    outputs=[
        PortDefinition(
            name="text_output",
            type=PortType.STRING,
            description="文本输出",
            show_preview=True,
        ),
        PortDefinition(
            name="number_output",
            type=PortType.FLOAT,
            description="数字输出",
            show_preview=True,
        ),
        PortDefinition(
            name="list_output",
            type=PortType.LIST,
            description="列表输出",
            show_preview=True,
        ),
        PortDefinition(
            name="dict_output",
            type=PortType.DICT,
            description="字典输出",
            show_preview=True,
        ),
    ],
    execute=lambda text_input,
    integer_input,
    float_input,
    bool_input,
    dropdown_input,
    file_input,
    external_input=None: {
        "text_output": f"{text_input} ({dropdown_input})",
        "number_output": integer_input * float_input,
        "list_output": [text_input, integer_input, float_input, bool_input, dropdown_input],
        "dict_output": {
            "text": text_input,
            "int": integer_input,
            "float": float_input,
            "bool": bool_input,
            "dropdown": dropdown_input,
            "file": file_input,
            "external": external_input,
        },
    },
)


# =============================================================================
# 所有节点定义
# =============================================================================

_ALL_DEFINITIONS = [
    # 输入控件测试
    TEXT_INPUT_DEFINITION,
    MULTI_TEXT_INPUT_DEFINITION,
    INTEGER_INPUT_DEFINITION,
    FLOAT_INPUT_DEFINITION,
    BOOLEAN_INPUT_DEFINITION,
    DROPDOWN_INPUT_DEFINITION,
    FILE_INPUT_DEFINITION,
    # 输出预览测试
    OUTPUT_PREVIEW_TEST_DEFINITION,
    # 数据处理
    DATA_SOURCE_DEFINITION,
    STRING_PROCESSOR_DEFINITION,
    MATH_CALCULATOR_DEFINITION,
    # 综合测试
    COMPREHENSIVE_TEST_DEFINITION,
]


# =============================================================================
# 插件类
# =============================================================================


class TestWidgetsPlugin(PluginBase):
    """
    内联控件测试插件

    提供完整的测试节点集，用于手动测试节点编辑器的所有功能

    Nodes:
        - test.text_input: 文本输入测试
        - test.multi_text_input: 多文本输入测试
        - test.integer_input: 整数输入测试
        - test.float_input: 浮点数输入测试
        - test.boolean_input: 布尔值输入测试
        - test.dropdown_input: 下拉选择测试
        - test.file_input: 文件选择测试
        - test.output_preview: 输出预览测试
        - test.data_source: 数据源
        - test.string_processor: 字符串处理
        - test.math_calculator: 数学计算
        - test.comprehensive: 综合测试

    Example:
        >>> from plugins.test_widgets import TestWidgetsPlugin
        >>> plugin = TestWidgetsPlugin()
        >>> plugin.on_enable(context)
    """

    name = "test_widgets"
    version = "1.0.0"
    description = "提供内联控件测试节点"
    author = "OfficeTools"

    permissions = PermissionSet.from_list(
        [
            Permission.NODE_REGISTER,
        ]
    )

    def on_enable(self, context):
        """插件启用时注册所有测试节点"""
        try:
            for node_def in _ALL_DEFINITIONS:
                context.node_engine.register_node_type(node_def)
                _logger.info(f"注册测试节点: {node_def.node_type}")

            _logger.info(f"共注册 {len(_ALL_DEFINITIONS)} 个测试节点")
        except Exception as e:
            _logger.error(f"注册测试节点失败: {e}")

    def on_disable(self, context):
        """插件禁用时清理"""
        pass


# =============================================================================
# 便捷函数
# =============================================================================


def get_test_widget_definitions() -> list:
    """获取所有测试控件节点定义"""
    return _ALL_DEFINITIONS.copy()


def get_test_categories() -> dict:
    """获取测试节点的分类信息"""
    categories: dict[str, list[str]] = {}
    for defn in _ALL_DEFINITIONS:
        if defn.category not in categories:
            categories[defn.category] = []
        categories[defn.category].append(defn.node_type)
    return categories
