"""批量生成第41-70章视频 - 跳过已完成的章节"""
import os
import subprocess
from pathlib import Path

workspace = 'workspace'

# 找出已完成的所有章节（有mp4文件的）
completed_chapters = set()
for d in os.listdir(workspace):
    dpath = os.path.join(workspace, d)
    if os.path.isdir(dpath):
        for root, dirs, files in os.walk(dpath):
            if any(f.endswith('.mp4') for f in files):
                completed_chapters.add(d)
                break

print(f"已完成章节: {len(completed_chapters)}")

# 找出需要处理的章节41-70
chapters_to_process = []
for i in range(41, 71):
    # 尝试匹配可能的文件夹名
    found = False
    for d in os.listdir(workspace):
        # 检查是否以第xxx章开头
        if d.startswith(f'第{i:03d}章') or d.startswith(f'第{i}章'):
            if d not in completed_chapters:
                chapters_to_process.append(d)
            found = True
            break
    # 如果没找到对应的已存在文件夹，则需要处理
    if not found and f'第{i:03d}章' not in completed_chapters:
        # 从input获取实际文件名
        for f in os.listdir('input/十日终焉'):
            if f.startswith(f'第{i:03d}章'):
                chapters_to_process.append(f.replace('.txt', ''))
                break

print(f"需要处理: {chapters_to_process}")

# 逐个运行
for chapter_name in chapters_to_process:
    # 查找对应的输入文件
    chapter_num = chapter_name[:chapter_name.find('章')+1]  # e.g., "第041章"
    input_file = None
    for f in os.listdir('input/十日终焉'):
        if f.startswith(chapter_num):
            input_file = f'input/十日终焉/{f}'
            break
    
    if not input_file:
        print(f"❌ 找不到输入文件: {chapter_name}")
        continue
    
    print(f"\n{'='*60}")
    print(f"开始处理: {chapter_name}")
    print(f"{'='*60}")
    
    cmd = f'python run.py "{input_file}" --no-subtitle'
    result = subprocess.run(cmd, shell=True)
    
    if result.returncode != 0:
        print(f"X {chapter_name} 处理失败!")
    else:
        print(f"OK {chapter_name} 处理完成!")

print(f"\n{'='*60}")
print("所有章节处理完成!")
print(f"{'='*60}")
