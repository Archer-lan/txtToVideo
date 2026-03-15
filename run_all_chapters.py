"""Batch run pipeline for chapters 3-10."""
import os
import subprocess
import sys

os.environ["MINIMAX_API_KEY"] = (
    "sk-cp-tBm7dw8K4qRjykS3q7958_-6fnFu80r-hUu2J37kIJuimE8cj2aBKEB5aPXMXCHqmHwyJwY18oi7VseI2bi_8eWdEkowKX8wMvyydBcG_7uPeLvbjVsVTWU"
)

START = int(sys.argv[1]) if len(sys.argv) > 1 else 3
END = int(sys.argv[2]) if len(sys.argv) > 2 else 10

for i in range(START, END + 1):
    chapter = f"input/十日终焉_第{i}章.txt"
    print(f"\n{'='*40}")
    print(f"Processing: {chapter}")
    print(f"{'='*40}")
    ret = subprocess.run([sys.executable, "run.py", chapter])
    if ret.returncode != 0:
        print(f"Chapter {i} FAILED (exit code {ret.returncode})")
    else:
        print(f"Chapter {i} done")

print("\nAll chapters done!")
