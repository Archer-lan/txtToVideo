# txtToVideo

小说转视频 — 自动将小说文本转换为带配音、字幕的视频。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

系统还需安装 `ffmpeg`（见 requirements.txt 注释）。

### 2. 配置 API 密钥

```bash
cp .env.example .env
# 编辑 .env，填入你的 MINIMAX_API_KEY
```

### 3. 运行单章

```bash
python run.py input/chapter01.txt
python run.py input/chapter01.txt --output output/chapter01.mp4
python run.py input/chapter01.txt --skip-images   # 跳过图片生成
python run.py input/chapter01.txt --whisper        # 使用 Whisper 字幕
python run.py input/chapter01.txt --resume workspace/chapter01  # 断点恢复
```

### 4. 批量运行

```bash
python run_batch.py --input-dir input/十日终焉 --start 1 --end 10
python run_batch.py --input-dir input/十日终焉 --start 11 --end 40 --max-retries 5
python run_batch.py --input-dir input/十日终焉 --pattern "第0*.txt"
python run_batch.py --input-dir input/十日终焉 --start 1 --end 70 --skip-completed
```

### 5. 生成封面（可选，需本地 SD WebUI）

```bash
python scripts/generate_cover.py -o output/cover.png
```

## 项目结构

```
TxtToVideo/
├── run.py                 # 主入口：单章 pipeline
├── run_batch.py           # 批量运行脚本
├── requirements.txt
├── .env.example           # API 密钥模板
├── config/                # 配置文件 (pipeline.yaml, characters.yaml, styles.yaml)
├── scripts/               # 管线阶段脚本 (00-06) 及工具脚本
├── input/                 # 小说输入文件
├── output/                # 最终输出
└── workspace/             # 中间产物工作区
```
