"""
批量运行第2-10章的pipeline
"""
import subprocess
import time
from pathlib import Path

# 第2-10章的文件
chapters = [
    "第002章 说谎.txt",
    "第003章 有技术的人.txt",
    "第004章 灾难？.txt",
    "第005章 医生.txt",
    "第006章 警官.txt",
    "第007章 赢面.txt",
    "第008章 摊牌.txt",
    "第009章 难以接受的真相.txt",
    "第010章 结束了？.txt",
]

input_dir = Path("input/十日终焉")

for i, chapter_file in enumerate(chapters):
    chapter_path = input_dir / chapter_file
    print(f"\n{'='*60}")
    print(f"开始处理: {chapter_file}")
    print(f"{'='*60}")

    # 先删除旧的workspace和storyboard
    chapter_name = chapter_file.replace(".txt", "")
    workspace_dir = Path(f"workspace/{chapter_name}")

    # 运行pipeline
    cmd = f'python run.py "{chapter_path}" --no-subtitle'
    print(f"执行命令: {cmd}")

    result = subprocess.run(cmd, shell=True, capture_output=False)

    if result.returncode != 0:
        print(f"❌ {chapter_file} 处理失败!")
    else:
        print(f"✅ {chapter_file} 处理完成!")

print(f"\n{'='*60}")
print("所有章节处理完成!")
print(f"{'='*60}")
