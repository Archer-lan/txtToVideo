#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
拆分小说大文件为单独章节

用法:
    python scripts/split_novel.py input/小说.txt --output input/小说章节
    python scripts/split_novel.py input/小说.txt --pattern "第(\d+)章"
"""

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def split_novel(
    input_file: Path,
    output_dir: Path,
    chapter_pattern: str = r'(第(\d+)章[^\u4e00-\u9fa5]*[^\n]*)',
    filename_template: str = "第{num:03d}章 {title}.txt",
    dry_run: bool = False,
):
    """
    拆分小说文件为单独章节

    Args:
        input_file: 输入小说文件路径
        output_dir: 输出目录
        chapter_pattern: 章节匹配正则，需包含两个分组：(完整标题, 章节号)
        filename_template: 输出文件名模板，支持 {num} 和 {title}
        dry_run: 只打印不实际写入
    """
    # 创建输出目录
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    # 读取文件
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 查找所有章节位置
    matches = list(re.finditer(chapter_pattern, content))

    print(f"共找到 {len(matches)} 个章节")

    if not matches:
        print("警告: 未找到任何章节，请检查章节匹配模式")
        return 0

    # 拆分并保存每个章节
    saved_count = 0
    for i, match in enumerate(matches):
        full_title = match.group(1).strip()
        chapter_num = match.group(2)

        # 获取章节内容
        start_pos = match.start()
        if i + 1 < len(matches):
            end_pos = matches[i + 1].start()
        else:
            end_pos = len(content)

        chapter_content = content[start_pos:end_pos].strip()

        # 清理标题用于文件名
        clean_title = full_title.replace(f'第{chapter_num}章', '').strip()
        # 移除文件名非法字符
        clean_title = re.sub(r'[<>:"/\\|?*]', '_', clean_title)

        # 生成输出文件名
        try:
            output_file = output_dir / filename_template.format(
                num=int(chapter_num),
                title=clean_title,
            )
        except (ValueError, KeyError) as e:
            print(f"  文件名模板错误: {e}，使用默认格式")
            output_file = output_dir / f"chapter_{chapter_num.zfill(3)}.txt"

        if dry_run:
            print(f"  [预览] 第{chapter_num}章: {full_title} -> {output_file.name}")
        else:
            # 写入文件
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(chapter_content)
            print(f"  已保存: {output_file.name}")

        saved_count += 1

    print(f"\n拆分完成！共 {saved_count} 章")
    if not dry_run:
        print(f"输出目录: {output_dir.resolve()}")

    return saved_count


def main():
    parser = argparse.ArgumentParser(
        description="拆分小说大文件为单独章节",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本用法
  python scripts/split_novel.py input/小说.txt

  # 指定输出目录
  python scripts/split_novel.py input/小说.txt --output input/章节

  # 自定义章节匹配模式 (匹配 "第一章 标题" 格式)
  python scripts/split_novel.py input/小说.txt --pattern "第([一二三四五六七八九十百千]+)章\\s+([^\\n]*)"

  # 自定义文件名模板
  python scripts/split_novel.py input/小说.txt --filename "chapter_{num:02d}.txt"

  # 预览模式（不实际写入文件）
  python scripts/split_novel.py input/小说.txt --dry-run
        """
    )

    parser.add_argument(
        "input",
        type=str,
        help="输入小说文件路径 (.txt)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="输出目录 (默认: 输入文件同目录下的同名文件夹)",
    )
    parser.add_argument(
        "--pattern", "-p",
        type=str,
        default=r'(第(\d+)章[^\u4e00-\u9fa5]*[^\n]*)',
        help="章节匹配正则表达式，需包含两个分组: (完整标题, 章节号)",
    )
    parser.add_argument(
        "--filename", "-f",
        type=str,
        default="第{num:03d}章 {title}.txt",
        help="输出文件名模板，支持 {num} (章节号) 和 {title} (标题)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，只打印不实际写入文件",
    )

    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        print(f"错误: 输入文件不存在: {input_path}")
        return 1

    # 确定输出目录
    if args.output:
        output_path = Path(args.output).resolve()
    else:
        output_path = input_path.parent / input_path.stem

    # 执行拆分
    count = split_novel(
        input_file=input_path,
        output_dir=output_path,
        chapter_pattern=args.pattern,
        filename_template=args.filename,
        dry_run=args.dry_run,
    )

    return 0 if count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
