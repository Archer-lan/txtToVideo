#!/usr/bin/env python3
"""
拆分小说大文件为单独章节

用法:
    python scripts/split_novel.py input/小说.txt input/小说目录/
    python scripts/split_novel.py input/十日终焉.txt input/十日终焉/
"""
import argparse
import re
from pathlib import Path


def split_novel(input_file, output_dir):
    """拆分小说文件为单独章节"""
    input_file = Path(input_file)
    output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    content = input_file.read_text(encoding="utf-8")

    chapter_pattern = r'(第(\d+)章[^\u4e00-\u9fa5]*[^\n]*)'
    matches = list(re.finditer(chapter_pattern, content))

    print(f"共找到 {len(matches)} 个章节")

    for i, match in enumerate(matches):
        chapter_title = match.group(1).strip()
        chapter_num = match.group(2)

        start_pos = match.start()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)

        chapter_content = content[start_pos:end_pos].strip()

        output_file = output_dir / f"第{chapter_num.zfill(3)}章 {chapter_title.replace(f'第{chapter_num}章', '').strip()}.txt"

        output_file.write_text(chapter_content, encoding="utf-8")
        print(f"已保存: {output_file.name}")

    print(f"\n拆分完成！共 {len(matches)} 章")


def main():
    parser = argparse.ArgumentParser(description="拆分小说大文件为单独章节")
    parser.add_argument("input", help="输入小说文件路径")
    parser.add_argument("output", help="输出目录路径")
    args = parser.parse_args()

    split_novel(args.input, args.output)


if __name__ == "__main__":
    main()
