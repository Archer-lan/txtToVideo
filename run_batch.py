#!/usr/bin/env python3
"""
批量运行章节 Pipeline

用法:
    python run_batch.py --input-dir input/十日终焉 --start 1 --end 10
    python run_batch.py --input-dir input/十日终焉 --start 11 --end 40 --max-retries 5
    python run_batch.py --input-dir input/十日终焉 --pattern "第0*.txt"
    python run_batch.py --input-dir input/十日终焉 --start 1 --end 70 --skip-completed
    python run_batch.py --input-dir input/十日终焉 --start 1 --end 10 --no-subtitle
"""

import argparse
import fnmatch
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def extract_chapter_num(filename):
    """从文件名提取章节号，如 '第011章 继续吧.txt' -> 11"""
    match = re.search(r"第(\d+)章", filename)
    if match:
        return int(match.group(1))
    return None


def find_chapter_files(input_dir, start=None, end=None, pattern=None):
    """查找并筛选章节文件"""
    input_path = Path(input_dir)
    if not input_path.exists():
        print(f"错误: 输入目录不存在: {input_dir}")
        sys.exit(1)

    files = sorted(input_path.glob("*.txt"))

    if pattern:
        files = [f for f in files if fnmatch.fnmatch(f.name, pattern)]

    if start is not None or end is not None:
        filtered = []
        for f in files:
            num = extract_chapter_num(f.name)
            if num is None:
                continue
            if start is not None and num < start:
                continue
            if end is not None and num > end:
                continue
            filtered.append(f)
        files = filtered

    return files


def is_chapter_completed(chapter_file):
    """检查章节是否已完成（workspace 中存在 >1MB 的 mp4）"""
    workspace = Path("workspace")
    chapter_name = chapter_file.stem
    # 尝试多种可能的目录名
    for d in workspace.iterdir() if workspace.exists() else []:
        if not d.is_dir():
            continue
        # 检查目录名是否包含章节名
        if chapter_name in d.name or d.name == chapter_name:
            for mp4 in d.rglob("*.mp4"):
                if mp4.stat().st_size > 1_000_000:
                    return True
    return False


def run_chapter(chapter_file, extra_args, max_retries=3):
    """运行单个章节，支持重试"""
    for attempt in range(1, max_retries + 1):
        print(f"\n{'='*60}")
        print(f"处理: {chapter_file.name}" + (f" (第 {attempt} 次尝试)" if attempt > 1 else ""))
        print(f"{'='*60}")

        cmd = [sys.executable, "run.py", str(chapter_file)] + extra_args
        result = subprocess.run(cmd)

        if result.returncode == 0:
            print(f"✅ {chapter_file.name} 处理完成!")
            return True
        else:
            print(f"✗ {chapter_file.name} 失败 (exit code {result.returncode})")
            if attempt < max_retries:
                print(f"  将进行第 {attempt + 1} 次重试...")

    print(f"❌ {chapter_file.name} 多次重试后仍然失败，跳过")
    return False


def main():
    parser = argparse.ArgumentParser(description="批量运行章节 Pipeline")
    parser.add_argument("--input-dir", default="input/", help="输入目录 (默认: input/)")
    parser.add_argument("--start", type=int, default=None, help="起始章节号")
    parser.add_argument("--end", type=int, default=None, help="结束章节号")
    parser.add_argument("--pattern", default=None, help="文件名匹配模式，如 '第0*.txt'")
    parser.add_argument("--max-retries", type=int, default=3, help="失败重试次数 (默认: 3)")
    parser.add_argument("--skip-completed", action="store_true", help="跳过已完成的章节")
    parser.add_argument("--no-subtitle", action="store_true", help="不生成字幕")
    args, unknown_args = parser.parse_known_args()

    chapters = find_chapter_files(args.input_dir, args.start, args.end, args.pattern)

    if not chapters:
        print("未找到匹配的章节文件")
        sys.exit(1)

    if args.skip_completed:
        before = len(chapters)
        chapters = [c for c in chapters if not is_chapter_completed(c)]
        skipped = before - len(chapters)
        if skipped:
            print(f"跳过 {skipped} 个已完成章节")

    print(f"共 {len(chapters)} 个章节待处理:")
    for c in chapters:
        print(f"  - {c.name}")

    extra_args = unknown_args[:]
    if args.no_subtitle:
        extra_args.append("--no-subtitle")

    success_count = 0
    fail_count = 0

    for chapter in chapters:
        if run_chapter(chapter, extra_args, args.max_retries):
            success_count += 1
        else:
            fail_count += 1

    print(f"\n{'='*60}")
    print(f"批量处理完成! 成功: {success_count}, 失败: {fail_count}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
