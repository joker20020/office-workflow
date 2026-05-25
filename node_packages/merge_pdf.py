# -*- UTF-8 -*-
# @author   : 40599
# @time     : 2026/4/29 10:02
# @version  : V1
#!/usr/bin/env python3
"""
batch_images_to_pdf.py

递归扫描指定根文件夹下的所有子文件夹，
将每个子文件夹内的图片（按文件名排序）合并为一个 PDF，
PDF 文件以子文件夹的名称命名，保存在对应的子文件夹内。
根文件夹本身的图片不会被处理（仅处理子文件夹）。

支持常见图片格式：.jpg, .jpeg, .png, .bmp, .gif, .tiff, .webp
"""

import os
import sys
import argparse
from PIL import Image

# 支持的图片扩展名（小写）
SUPPORTED_EXT = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}

def get_image_files(folder):
    """获取文件夹下所有支持的图片文件，按文件名排序"""
    files = []
    for f in os.listdir(folder):
        ext = os.path.splitext(f)[1].lower()
        if ext in SUPPORTED_EXT:
            files.append(os.path.join(folder, f))
    files.sort(key=os.path.basename)  # 按文件名排序
    return files

def images_to_pdf(image_paths, output_pdf):
    """将图片列表合并为 PDF（使用 format='PDF' 显式保存）"""
    if not image_paths:
        return False

    images = []
    for path in image_paths:
        try:
            img = Image.open(path)
            # 转换为 RGB 模式（PDF 不支持透明通道）
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            images.append(img)
        except Exception as e:
            print(f"  警告：无法加载 {os.path.basename(path)} - {e}")
            continue

    if not images:
        return False

    # 显式保存为 PDF
    try:
        with open(output_pdf, 'wb') as f:
            first = images[0]
            others = images[1:]
            first.save(f, format='PDF', save_all=True, append_images=others)
        print(f"  ✓ 已生成：{output_pdf} (共 {len(images)} 页)")
        return True
    except Exception as e:
        print(f"  ✗ 保存失败：{output_pdf} - {e}")
        return False

def process_batch(root_folder):
    """批量处理 root_folder 下的所有子文件夹（递归）"""
    if not os.path.isdir(root_folder):
        print(f"错误：根文件夹不存在 - {root_folder}")
        return False

    print(f"扫描根目录：{os.path.abspath(root_folder)}")
    processed_count = 0
    skipped_count = 0

    # os.walk 递归遍历所有子文件夹
    for current_dir, subdirs, files in os.walk(root_folder):
        # 跳过根文件夹本身（只处理子文件夹）
        if current_dir == root_folder:
            continue

        # 获取当前文件夹中的图片
        image_files = get_image_files(current_dir)
        if not image_files:
            skipped_count += 1
            continue

        # 生成 PDF 路径：以当前文件夹名称命名，放在该文件夹内
        folder_name = os.path.basename(current_dir)
        output_pdf = os.path.join(current_dir, f"{folder_name}.pdf")

        print(f"\n处理文件夹：{current_dir}")
        print(f"  找到 {len(image_files)} 张图片")

        if images_to_pdf(image_files, output_pdf):
            processed_count += 1

    print(f"\n批量处理完成：成功生成 {processed_count} 个 PDF，{skipped_count} 个文件夹无图片")
    return True

def main():
    parser = argparse.ArgumentParser(
        description="将根文件夹下每个子文件夹内的图片合并为单独的 PDF（以子文件夹名命名）"
    )
    parser.add_argument(
        "root_folder", nargs="?", default=".",
        help="根文件夹路径（默认为当前目录）"
    )
    args = parser.parse_args()

    success = process_batch(args.root_folder)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()