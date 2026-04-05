"""
拆分十日终焉大文件为单独章节
"""
import re
from pathlib import Path

input_file = Path("input/十日终焉+作者：杀虫队队员（完结）.txt")
output_dir = Path("input/十日终焉")

# 创建输出目录
output_dir.mkdir(exist_ok=True)

# 读取文件
with open(input_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 查找所有章节位置
chapter_pattern = r'(第(\d+)章[^\u4e00-\u9fa5]*[^\n]*)'
matches = list(re.finditer(chapter_pattern, content))

print(f"共找到 {len(matches)} 个章节")

# 拆分并保存每个章节
for i, match in enumerate(matches):
    chapter_title = match.group(1).strip()
    chapter_num = match.group(2)

    # 获取章节内容
    start_pos = match.start()
    if i + 1 < len(matches):
        end_pos = matches[i + 1].start()
    else:
        end_pos = len(content)

    chapter_content = content[start_pos:end_pos].strip()

    # 创建文件名：第01章 空屋.txt
    output_file = output_dir / f"第{chapter_num.zfill(3)}章 {chapter_title.replace(f'第{chapter_num}章', '').strip()}.txt"

    # 写入文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(chapter_content)

    print(f"已保存: {output_file.name}")

print(f"\n拆分完成！共 {len(matches)} 章")
