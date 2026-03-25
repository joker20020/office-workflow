# -*- UTF-8 -*-
# @author   : 40599
# @time     : 2025/7/15 16:09
# @version  : V1

import pandas as pd
import numpy as np


class TableProcessor(object):

    def __init__(self):
        self.data = None

    def load_excel(self, file: str, sheet_name=0):
        self.data = pd.read_excel(file, sheet_name=sheet_name)

    def find_same(self, other, this_col, other_col):
        col_data = self.data[this_col].values
        other_data = other.data[other_col].values
        result = []
        for row in col_data:
            for other_row in other_data:
                if row == other_row:
                    result = np.append(result, row)

        return result

    def merge_excel_sheets(
            self,
            file_to_merge,
            ref_col1: str,
            ref_col2: str,
            ignore_columns: list = None,
            column_mapping: dict = None
    ) -> pd.DataFrame:
        """
        合并两个Excel表格，基于参考列匹配行，并支持列过滤和映射

        参数:
        file_to_merge (Tp): 第二个TableProcessor
        ref_col1 (str): 表格一的参考列名（用于行匹配）
        ref_col2 (str): 表格二的参考列名（用于行匹配）
        ignore_columns (list): 表格二中需要忽略的列列表
        column_mapping (dict): 列映射字典 {表格二列名: 表格一列名}

        返回:
        pandas.DataFrame: 合并后的DataFrame
        """
        if ignore_columns is None:
            ignore_columns = []
        if column_mapping is None:
            column_mapping = {}

        # 读取Excel文件
        df1 = self.data
        df2: pd.DataFrame = file_to_merge.data

        # 验证参考列存在性
        if ref_col1 not in df1.columns:
            raise ValueError(f"表格一不存在参考列: {ref_col1}")
        if ref_col2 not in df2.columns:
            raise ValueError(f"表格二不存在参考列: {ref_col2}")

        # 忽略大小写
        df1[ref1] = df1[ref1].str.upper()
        df2[ref2] = df2[ref2].str.upper()

        # 处理表格二：移除忽略列
        df2 = df2.drop(columns=[col for col in ignore_columns if col in df2.columns],
                       errors='ignore')

        # 基于参考列进行左连接（以表格一为主表）
        merged = pd.merge(
            df1,
            df2,
            left_on=ref_col1,
            right_on=ref_col2,
            how='left',
            suffixes=('', '_table2')  # 避免列名冲突
        )

        # 清理冗余列
        merged = merged.drop(columns=[ref_col2], errors='ignore')

        # 应用列映射（将表格二的列覆盖到表格一的指定列）
        for target_col, src_col in column_mapping.items():
            # 构建可能的列名（考虑suffixes处理）
            possible_src_cols = [
                src_col,
                f"{src_col}_table2"
            ]

            for col_name in possible_src_cols:
                if col_name in merged.columns and target_col in merged.columns:
                    merged[target_col] = merged[col_name]
                    break

        return merged


if __name__ == "__main__":
    tp1 = TableProcessor()
    tp1.load_excel(r"C:\Users\40599\Desktop\沈元学院2025年兼职辅导员报名材料-贾玳语\学生信息\24级学生宿舍情况.xlsx")
    tp2 = TableProcessor()
    # tp2.load_excel(r"C:\Users\40599\Desktop\沈元学院2025年兼职辅导员报名材料-贾玳语\学生信息\321565018_按文本_保留宿舍申请_66_66.xlsx")
    tp2.load_excel(r"C:\Users\40599\Desktop\沈元学院2025年兼职辅导员报名材料-贾玳语\学生信息\24级学生宿舍情况.xlsx", 1)
    # print(tp2.find_same(tp1, "学生姓名", "姓名"))

    ref1 = "学号"
    ref2 = "研究生学号"
    ignore_col = ["2、学号：",
                  "3、您的性别：",
                  "4、请输入您的手机号码：",
                  "序号"
                  "16、请上传保留宿舍申请表PDF扫描件，命名为“学号-姓名”，需校内导师、企业导师、二三级单位人力部门签字或盖章（仅学院意见为空）"]

    col_mapping = {"姓名": "1、您的姓名：",
                   "申请保留原因类型": "14、申请原因",
                   "原因": "15、详细原因：",
                   "二三级单位": "6、联培企业",
                   "住宿校区": "10、所在校区：",
                   "宿舍号（含校区-楼号-房间号）": "11、校内宿舍地址：X公寓X单元X层XXX房间",
                   "专业实践地址": "8、企业地址：XX省XX市XXXX（精确到门牌号）"}

    tp1.merge_excel_sheets(tp2, ref1, ref2, ignore_col, col_mapping).to_excel(r"test.xlsx", index=False)
