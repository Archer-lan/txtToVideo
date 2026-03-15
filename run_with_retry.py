"""批量运行章节，支持失败重试"""
import os
import subprocess
import sys
import shutil
from pathlib import Path

# 修复Windows编码问题
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

os.environ["MINIMAX_API_KEY"] = (
    "sk-cp-tBm7dw8K4qRjykS3q7958_-6fnFu80r-hUu2J37kIJuimE8cj2aBKEB5aPXMXCHqmHwyJwY18oi7VseI2bi_8eWdEkowKX8wMvyydBcG_7uPeLvbjVsVTWU"
)

START = int(sys.argv[1]) if len(sys.argv) > 1 else 2
END = int(sys.argv[2]) if len(sys.argv) > 2 else 10
MAX_RETRIES = 3

def clean_chapter(chapter_num):
    """删除章节产物目录"""
    workspace_dir = Path("workspace")
    chapter_dir = workspace_dir / f"十日终焉_第{chapter_num}章"
    if chapter_dir.exists():
        shutil.rmtree(chapter_dir)
        print(f"已删除: {chapter_dir}")

def check_success(chapter_num):
    """检查章节是否成功生成"""
    output_file = Path(f"workspace/十日终焉_第{chapter_num}章/output/十日终焉_第{chapter_num}章.mp4")
    if output_file.exists():
        size = output_file.stat().st_size
        if size > 1000000:  # 大于1MB才算成功
            return True
    return False

def run_chapter(chapter_num):
    """运行单个章节"""
    chapter_file = f"input/十日终焉_第{chapter_num}章.txt"
    print(f"\n{'='*50}")
    print(f"开始处理第 {chapter_num} 章")
    print(f"{'='*50}")

    # 删除旧产物
    clean_chapter(chapter_num)

    # 运行
    ret = subprocess.run([sys.executable, "run.py", chapter_file])
    return ret.returncode == 0

for i in range(START, END + 1):
    success = False
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n[第 {i} 章] 第 {attempt} 次尝试")

        if run_chapter(i):
            if check_success(i):
                print(f"[第 {i} 章] ✓ 成功")
                success = True
                break
            else:
                print(f"[第 {i} 章] ✗ 视频文件异常，将重试...")
        else:
            print(f"[第 {i} 章] ✗ 运行失败，将重试...")

    if not success:
        print(f"[第 {i} 章] ❌ 多次重试后仍然失败，跳过")

print("\n" + "="*50)
print("所有章节处理完成!")
print("="*50)
