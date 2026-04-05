"""Run chapters 11-40."""
import subprocess
import sys
import os
import glob

os.environ["MINIMAX_API_KEY"] = (
    "sk-cp-tBm7dw8K4qRjykS3q7958_-6fnFu80r-hUu2J37kIJuimE8cj2aBKEB5aPXMXCHqmHwyJwY18oi7VseI2bi_8eWdEkowKX8wMvyydBcG_7uPeLvbjVsVTWU"
)

# Find all chapter files in the directory
chapter_files = sorted(glob.glob("input/十日终焉/第0*.txt")) + sorted(glob.glob("input/十日终焉/第[1-3]*.txt"))

for chapter in chapter_files:
    # Extract chapter number from filename
    filename = os.path.basename(chapter)
    if "第" in filename:
        # Extract chapter number (e.g., "第011章 继续吧.txt" -> 11)
        try:
            num_part = filename.split("第")[1].split("章")[0]
            chapter_num = int(num_part)
        except:
            continue

        # Only process chapters 11-40
        if 11 <= chapter_num <= 40:
            print(f"\n{'='*40}")
            print(f"Processing: {chapter}")
            print(f"{'='*40}")
            ret = subprocess.run([sys.executable, "run.py", chapter])
            if ret.returncode != 0:
                print(f"Chapter {chapter_num} FAILED (exit code {ret.returncode})")
                break
            else:
                print(f"Chapter {chapter_num} done")

print("\nAll chapters done!")
