#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excel 文件对比分析工具
比较两个 Excel 文件中指定列的内容，分析包含和缺失的内容
"""

import pandas as pd
import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import Tuple, Set, Optional


class ExcelComparator:
    """Excel 文件对比器"""
    
    def __init__(self, file1_path: str, file2_path: str):
        """
        初始化对比器
        
        Args:
            file1_path: 基准文件路径（文件1）
            file2_path: 对比文件路径（文件2）
        """
        self.file1_path = Path(file1_path)
        self.file2_path = Path(file2_path)
        self.df1: Optional[pd.DataFrame] = None
        self.df2: Optional[pd.DataFrame] = None
        
    def load_files(self, sheet1: str | int = 0, sheet2: str | int = 0) -> bool:
        """
        加载两个 Excel 文件
        
        Args:
            sheet1: 文件1的工作表名称或索引
            sheet2: 文件2的工作表名称或索引
            
        Returns:
            是否成功加载
        """
        try:
            self.df1 = pd.read_excel(self.file1_path, sheet_name=sheet1)
            self.df2 = pd.read_excel(self.file2_path, sheet_name=sheet2)
            print(f"✓ 成功加载文件1: {self.file1_path.name}")
            print(f"  - 行数: {len(self.df1)}, 列数: {len(self.df1.columns)}")
            print(f"✓ 成功加载文件2: {self.file2_path.name}")
            print(f"  - 行数: {len(self.df2)}, 列数: {len(self.df2.columns)}")
            return True
        except FileNotFoundError as e:
            print(f"✗ 错误: 文件未找到 - {e}")
            return False
        except Exception as e:
            print(f"✗ 错误: 加载文件失败 - {e}")
            return False
    
    def list_columns(self) -> Tuple[list, list]:
        """列出两个文件的所有列名"""
        if self.df1 is None or self.df2 is None:
            raise ValueError("请先加载文件")
        
        cols1 = self.df1.columns.tolist()
        cols2 = self.df2.columns.tolist()
        
        print("\n" + "="*60)
        print("文件1 的列:")
        for i, col in enumerate(cols1, 1):
            print(f"  {i}. {col}")
        
        print("\n文件2 的列:")
        for i, col in enumerate(cols2, 1):
            print(f"  {i}. {col}")
        print("="*60)
        
        return cols1, cols2
    
    def compare_columns(self, col1: str, col2: str) -> dict:
        """
        对比两个文件的指定列
        
        Args:
            col1: 文件1的列名
            col2: 文件2的列名
            
        Returns:
            对比结果字典
        """
        if self.df1 is None or self.df2 is None:
            raise ValueError("请先加载文件")
        
        values1 = set(self.df1[col1].dropna().astype(str).unique())
        values2 = set(self.df2[col2].dropna().astype(str).unique())
        
        only_in_file1 = values1 - values2
        only_in_file2 = values2 - values1
        common = values1 & values2
        
        result = {
            'col1': col1,
            'col2': col2,
            'file1_total': len(values1),
            'file2_total': len(values2),
            'common_count': len(common),
            'only_in_file1_count': len(only_in_file1),
            'only_in_file2_count': len(only_in_file2),
            'common_values': sorted(common),
            'only_in_file1': sorted(only_in_file1),
            'only_in_file2': sorted(only_in_file2),
        }
        
        return result
    
    def print_analysis(self, result: dict):
        """打印分析结果到控制台"""
        print("\n" + "="*70)
        print(" " * 25 + "对比分析结果")
        print("="*70)
        
        print(f"\n【对比列】")
        print(f"  文件1: {result['col1']}")
        print(f"  文件2: {result['col2']}")
        
        print(f"\n【统计概览】")
        print(f"  文件1 唯一值数量: {result['file1_total']}")
        print(f"  文件2 唯一值数量: {result['file2_total']}")
        print(f"  共同拥有: {result['common_count']}")
        print(f"  仅文件1有: {result['only_in_file1_count']}")
        print(f"  仅文件2有: {result['only_in_file2_count']}")
        
        if result['file1_total'] > 0:
            coverage = result['common_count'] / result['file1_total'] * 100
            print(f"\n  文件2对文件1的覆盖率: {coverage:.2f}%")
        
        if result['only_in_file2']:
            print(f"\n【文件2 相对于文件1的新增内容】({result['only_in_file2_count']} 项)")
            for i, val in enumerate(result['only_in_file2'][:20], 1):
                print(f"  {i}. {val}")
            if len(result['only_in_file2']) > 20:
                print(f"  ... 还有 {len(result['only_in_file2']) - 20} 项")
        
        if result['only_in_file1']:
            print(f"\n【文件2 相对于文件1的缺失内容】({result['only_in_file1_count']} 项)")
            for i, val in enumerate(result['only_in_file1'][:20], 1):
                print(f"  {i}. {val}")
            if len(result['only_in_file1']) > 20:
                print(f"  ... 还有 {len(result['only_in_file1']) - 20} 项")
        
        if result['common_values']:
            print(f"\n【共同包含的内容】({result['common_count']} 项)")
            for i, val in enumerate(result['common_values'][:20], 1):
                print(f"  {i}. {val}")
            if len(result['common_values']) > 20:
                print(f"  ... 还有 {len(result['common_values']) - 20} 项")
        
        print("\n" + "="*70)
    
    def export_to_excel(self, result: dict, output_path: str):
        """
        导出对比结果到 Excel 文件
        
        Args:
            result: 对比结果字典
            output_path: 输出文件路径
        """
        output_file = Path(output_path)
        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            summary_data = {
                '指标': [
                    '文件1路径',
                    '文件2路径',
                    '文件1对比列',
                    '文件2对比列',
                    '文件1唯一值数量',
                    '文件2唯一值数量',
                    '共同拥有数量',
                    '仅文件1有数量',
                    '仅文件2有数量',
                    '文件2对文件1覆盖率',
                ],
                '值': [
                    str(self.file1_path),
                    str(self.file2_path),
                    result['col1'],
                    result['col2'],
                    result['file1_total'],
                    result['file2_total'],
                    result['common_count'],
                    result['only_in_file1_count'],
                    result['only_in_file2_count'],
                    f"{result['common_count']/result['file1_total']*100:.2f}%" if result['file1_total'] > 0 else 'N/A',
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='摘要', index=False)
            
            common_df = pd.DataFrame({
                '序号': range(1, len(result['common_values']) + 1),
                '共同包含的内容': result['common_values']
            })
            common_df.to_excel(writer, sheet_name='共同内容', index=False)
            
            new_df = pd.DataFrame({
                '序号': range(1, len(result['only_in_file2']) + 1),
                '文件2新增内容': result['only_in_file2']
            })
            new_df.to_excel(writer, sheet_name='文件2新增', index=False)
            
            missing_df = pd.DataFrame({
                '序号': range(1, len(result['only_in_file1']) + 1),
                '文件2缺失内容': result['only_in_file1']
            })
            missing_df.to_excel(writer, sheet_name='文件2缺失', index=False)
        
        print(f"\n✓ 对比报告已导出到: {output_file.absolute()}")


def interactive_mode():
    """交互式模式"""
    print("\n" + "="*70)
    print(" " * 20 + "Excel 文件对比分析工具")
    print("="*70)
    
    file1_path = input("\n请输入文件1路径（基准文件）: ").strip().strip('"\'')
    file2_path = input("请输入文件2路径（对比文件）: ").strip().strip('"\'')
    
    comparator = ExcelComparator(file1_path, file2_path)
    
    use_sheet1 = input("\n使用文件1的哪个工作表？（默认第一个，直接回车跳过）: ").strip()
    use_sheet2 = input("使用文件2的哪个工作表？（默认第一个，直接回车跳过）: ").strip()
    
    sheet1 = 0 if not use_sheet1 else use_sheet1
    sheet2 = 0 if not use_sheet2 else use_sheet2
    
    if not comparator.load_files(sheet1, sheet2):
        sys.exit(1)
    
    cols1, cols2 = comparator.list_columns()
    
    col1_idx = input("\n选择文件1的对比列（输入序号或列名）: ").strip()
    col2_idx = input("选择文件2的对比列（输入序号或列名）: ").strip()
    
    if col1_idx.isdigit():
        col1 = cols1[int(col1_idx) - 1]
    else:
        col1 = col1_idx
    
    if col2_idx.isdigit():
        col2 = cols2[int(col2_idx) - 1]
    else:
        col2 = col2_idx
    
    result = comparator.compare_columns(col1, col2)
    
    comparator.print_analysis(result)
    
    export_choice = input("\n是否导出详细报告到 Excel？(y/n，默认 y): ").strip().lower()
    if export_choice != 'n':
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_output = f"compare_report_{timestamp}.xlsx"
        output_path = input(f"输出文件名（默认: {default_output}）: ").strip()
        output_path = output_path if output_path else default_output
        
        comparator.export_to_excel(result, output_path)
    
    print("\n✓ 分析完成！")


def main():
    parser = argparse.ArgumentParser(
        description='Excel 文件对比分析工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  交互模式:
    python excel_compare.py
    
  命令行模式:
    python excel_compare.py file1.xlsx file2.xlsx -c "列名1" "列名2"
    python excel_compare.py data1.xlsx data2.xlsx -c "姓名" "姓名" -o report.xlsx
        """
    )
    
    parser.add_argument('file1', nargs='?', help='文件1路径（基准文件）')
    parser.add_argument('file2', nargs='?', help='文件2路径（对比文件）')
    parser.add_argument('-c', '--columns', nargs=2, metavar=('COL1', 'COL2'),
                        help='要对比的列名（文件1列名 文件2列名）')
    parser.add_argument('-s1', '--sheet1', default=0, help='文件1的工作表（默认第一个）')
    parser.add_argument('-s2', '--sheet2', default=0, help='文件2的工作表（默认第一个）')
    parser.add_argument('-o', '--output', help='输出报告文件名')
    parser.add_argument('--no-export', action='store_true', help='不导出 Excel 报告')
    
    args = parser.parse_args()
    
    if not args.file1 or not args.file2:
        interactive_mode()
        return
    
    comparator = ExcelComparator(args.file1, args.file2)
    
    if not comparator.load_files(args.sheet1, args.sheet2):
        sys.exit(1)
    
    if not args.columns:
        cols1, cols2 = comparator.list_columns()
        
        col1_idx = input("\n选择文件1的对比列（输入序号或列名）: ").strip()
        col2_idx = input("选择文件2的对比列（输入序号或列名）: ").strip()
        
        if col1_idx.isdigit():
            col1 = cols1[int(col1_idx) - 1]
        else:
            col1 = col1_idx
        
        if col2_idx.isdigit():
            col2 = cols2[int(col2_idx) - 1]
        else:
            col2 = col2_idx
    else:
        col1, col2 = args.columns
    
    result = comparator.compare_columns(col1, col2)
    
    comparator.print_analysis(result)
    
    if not args.no_export:
        if args.output:
            output_path = args.output
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f"compare_report_{timestamp}.xlsx"
        
        comparator.export_to_excel(result, output_path)
    
    print("\n✓ 分析完成！")


if __name__ == '__main__':
    main()
