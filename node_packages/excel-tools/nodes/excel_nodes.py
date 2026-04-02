# -*- coding: utf-8 -*-
"""
Excel 处理节点定义

提供 Excel 文件对比和预览功能
节点在节点编辑器中展示对比结果,用户可以直观查看统计信息
"""

from pathlib import Path
from typing import Any, Dict

from src.engine.definitions import NodeDefinition, PortDefinition, PortType


def _excel_compare(
    file1_path: str,
    file2_path: str,
    col1: str,
    col2: str,
    sheet1: str = "0",
    sheet2: str = "0",
) -> Dict[str, Any]:
    """
    对比两个 Excel 文件中指定列的内容

    Args:
        file1_path: 基准文件路径
        file2_path: 对比文件路径
        col1: 文件1的对比列名
        col2: 文件2的对比列名
        sheet1: 文件1的工作表（名称或索引，默认第一个）
        sheet2: 文件2的工作表（名称或索引，默认第一个）

    Returns:
        包含对比结果的字典
    """
    import pandas as pd

    path1 = Path(file1_path)
    path2 = Path(file2_path)

    def parse_sheet(sheet: str):
        """将工作表参数转换为 read_excel 可接受的格式"""
        if sheet.isdigit():
            return int(sheet)
        return sheet

    if not path1.exists():
        raise FileNotFoundError(f"文件不存在: {file1_path}")
    if not path2.exists():
        raise FileNotFoundError(f"文件不存在: {file2_path}")

    df1 = pd.read_excel(path1, sheet_name=parse_sheet(sheet1))
    df2 = pd.read_excel(path2, sheet_name=parse_sheet(sheet2))

    if col1 not in df1.columns:
        raise ValueError(f"文件1中不存在列: {col1}")
    if col2 not in df2.columns:
        raise ValueError(f"文件2中不存在列: {col2}")

    values1 = set(df1[col1].dropna().astype(str).unique())
    values2 = set(df2[col2].dropna().astype(str).unique())

    common = values1 & values2
    only_in_file1 = values1 - values2
    only_in_file2 = values2 - values1

    coverage = len(common) / len(values1) * 100 if values1 else 0

    # 生成文本报告
    lines = []
    lines.append("=" * 60)
    lines.append("              Excel 对比分析报告")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"【对比列】")
    lines.append(f"  文件1 ({path1.name}): {col1}")
    lines.append(f"  文件2 ({path2.name}): {col2}")
    lines.append("")
    lines.append(f"【统计概览】")
    lines.append(f"  文件1 唯一值数量: {len(values1)}")
    lines.append(f"  文件2 唯一值数量: {len(values2)}")
    lines.append(f"  共同拥有: {len(common)}")
    lines.append(f"  仅文件1有: {len(only_in_file1)}")
    lines.append(f"  仅文件2有: {len(only_in_file2)}")
    lines.append(f"  文件2对文件1的覆盖率: {coverage:.2f}%")

    if only_in_file2:
        lines.append("")
        lines.append(f"【文件2 新增内容】({len(only_in_file2)} 项)")
        for i, val in enumerate(sorted(only_in_file2), 1):
            lines.append(f"  {i}. {val}")

    if only_in_file1:
        lines.append("")
        lines.append(f"【文件2 缺失内容】({len(only_in_file1)} 项)")
        for i, val in enumerate(sorted(only_in_file1), 1):
            lines.append(f"  {i}. {val}")

    if common:
        lines.append("")
        lines.append(f"【共同包含的内容】({len(common)} 项)")
        for i, val in enumerate(sorted(common), 1):
            lines.append(f"  {i}. {val}")

    lines.append("")
    lines.append("=" * 60)

    return {
        "file1_total": len(values1),
        "file2_total": len(values2),
        "common_count": len(common),
        "only_in_file1_count": len(only_in_file1),
        "only_in_file2_count": len(only_in_file2),
        "coverage_percent": round(coverage, 2),
        "common_values": sorted(common),
        "only_in_file1": sorted(only_in_file1),
        "only_in_file2": sorted(only_in_file2),
        "report_text": "\n".join(lines),
    }


excel_compare = NodeDefinition(
    node_type="excel.compare",
    display_name="Excel对比",
    description="对比两个 Excel 文件中指定列的内容，分析包含和缺失项",
    category="excel",
    icon="📊",
    inputs=[
        PortDefinition("file1_path", PortType.FILE, "基准文件路径", widget_type="file_picker"),
        PortDefinition("file2_path", PortType.FILE, "对比文件路径", widget_type="file_picker"),
        PortDefinition("col1", PortType.STRING, "文件1对比列名", widget_type="line_edit"),
        PortDefinition("col2", PortType.STRING, "文件2对比列名", widget_type="line_edit"),
        PortDefinition(
            "sheet1",
            PortType.STRING,
            "文件1工作表",
            default="0",
            required=False,
            widget_type="line_edit",
        ),
        PortDefinition(
            "sheet2",
            PortType.STRING,
            "文件2工作表",
            default="0",
            required=False,
            widget_type="line_edit",
        ),
    ],
    outputs=[
        PortDefinition("report_text", PortType.STRING, "对比报告", show_preview=True),
        PortDefinition("file1_total", PortType.INTEGER, "文件1唯一值数量"),
        PortDefinition("file2_total", PortType.INTEGER, "文件2唯一值数量"),
        PortDefinition("common_count", PortType.INTEGER, "共同拥有数量"),
        PortDefinition("only_in_file1_count", PortType.INTEGER, "仅文件1有数量"),
        PortDefinition("only_in_file2_count", PortType.INTEGER, "仅文件2有数量"),
        PortDefinition("coverage_percent", PortType.FLOAT, "覆盖率(%)"),
        PortDefinition("common_values", PortType.LIST, "共同内容列表", show_preview=True),
        PortDefinition("only_in_file1", PortType.LIST, "文件1独有内容", show_preview=True),
        PortDefinition("only_in_file2", PortType.LIST, "文件2独有内容", show_preview=True),
    ],
    execute=_excel_compare,
)


def _excel_preview(
    file_path: str,
    sheet: str = "0",
    preview_rows: int = 10,
) -> Dict[str, Any]:
    """
    预览 Excel 文件内容

    Args:
        file_path: Excel 文件路径
        sheet: 工作表（名称或索引，默认第一个）
        preview_rows: 预览行数（默认10行）

    Returns:
        包含预览信息的字典
    """
    import pandas as pd

    path = Path(file_path)

    def parse_sheet(sheet_param: str):
        """将工作表参数转换为 read_excel 可接受的格式"""
        if sheet_param.isdigit():
            return int(sheet_param)
        return sheet_param

    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    df = pd.read_excel(path, sheet_name=parse_sheet(sheet))

    columns = df.columns.tolist()

    preview_df = df.head(preview_rows)
    preview_data = preview_df.to_dict(orient="records")

    for row in preview_data:
        for key, value in row.items():
            if pd.isna(value):
                row[key] = None
            elif hasattr(value, "item"):
                row[key] = value.item()

    # 获取工作表信息
    xl_file = pd.ExcelFile(path)
    sheet_names = xl_file.sheet_names
    current_sheet = parse_sheet(sheet)
    if isinstance(current_sheet, int):
        current_sheet_name = (
            sheet_names[current_sheet] if current_sheet < len(sheet_names) else str(current_sheet)
        )
    else:
        current_sheet_name = current_sheet

    return {
        "file_name": path.name,
        "sheet_name": current_sheet_name,
        "sheet_names": sheet_names,
        "total_rows": len(df),
        "total_columns": len(columns),
        "columns": columns,
        "preview_rows": len(preview_data),
        "preview_data": preview_data,
    }


excel_preview = NodeDefinition(
    node_type="excel.preview",
    display_name="Excel预览",
    description="预览 Excel 文件内容，显示列名、行数和前几行数据",
    category="excel",
    icon="📄",
    inputs=[
        PortDefinition("file_path", PortType.FILE, "文件路径", widget_type="file_picker"),
        PortDefinition(
            "sheet",
            PortType.STRING,
            "工作表",
            default="0",
            required=False,
            widget_type="line_edit",
        ),
        PortDefinition(
            "preview_rows",
            PortType.INTEGER,
            "预览行数",
            default=10,
            required=False,
            widget_type="line_edit",
        ),
    ],
    outputs=[
        PortDefinition("file_name", PortType.STRING, "文件名", show_preview=True),
        PortDefinition("sheet_name", PortType.STRING, "当前工作表名", show_preview=True),
        PortDefinition("sheet_names", PortType.LIST, "所有工作表名", show_preview=True),
        PortDefinition("total_rows", PortType.INTEGER, "总行数", show_preview=True),
        PortDefinition("total_columns", PortType.INTEGER, "总列数", show_preview=True),
        PortDefinition("columns", PortType.LIST, "列名列表", show_preview=True),
        PortDefinition("preview_rows_count", PortType.INTEGER, "预览行数", show_preview=True),
        PortDefinition("preview_data", PortType.LIST, "预览数据", show_preview=True),
    ],
    execute=_excel_preview,
)
