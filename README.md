# TxtToVideo

一键将小说文本转换为带配音、字幕的短视频。

自动完成全流程：文本解析 → 分镜脚本 → 语音合成 → AI 绘图 → 镜头动画 → 视频合成 → 字幕烧录。

## 功能特性

- 6 阶段自动化 Pipeline，支持断点恢复和单阶段跳过
- LLM 智能分镜：自动拆分场景、标注情绪、生成画面描述
- 多角色 TTS 配音：支持火山引擎 TTS，角色语音映射 + 情绪 prosody 调节
- AI 绘图：Stable Diffusion WebUI 生成关键帧，支持 IP-Adapter 角色一致性
- Ken Burns 镜头动画：zoom / pan 等运动效果
- 自动字幕：基于时间轴的 SRT 生成，支持 Whisper 语音识别
- 跨平台：macOS / Windows / Linux
- 小说下载：支持番茄小说、起点中文网等平台自动下载

## Pipeline 流程

```
小说文本 (.txt)
  │
  ├─ 阶段 0: 下载小说（可选，支持 URL/书籍ID）
  ├─ 阶段 1: LLM 分镜 → storyboard.json
  ├─ 阶段 2: TTS 语音合成 → scene_*.wav
  ├─ 阶段 3: Stable Diffusion 生图 → scene_*.png
  ├─ 阶段 4: Ken Burns 动画 → scene_*.mp4
  ├─ 阶段 5: 音画合成 → composed_no_sub.mp4
  └─ 阶段 6: 字幕烧录 → 最终视频.mp4
```

## 环境要求

- Python 3.8+
- FFmpeg（需在 PATH 中可用）
- Stable Diffusion WebUI（本地运行，提供 API 接口）

### 可选依赖

- 火山引擎 TTS 账号（不配置则降级为 edge-tts）
- Whisper（不配置则使用基于 storyboard 的字幕方案）

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入你的 API 密钥：

```env
MINIMAX_API_KEY=your_minimax_key       # LLM 分镜（必需）
VOLCANO_APP_ID=your_app_id             # 火山引擎 TTS（可选）
VOLCANO_ACCESS_TOKEN=your_token        # 火山引擎 TTS（可选）
SD_API_URL=http://127.0.0.1:7860      # SD WebUI 地址（可选，默认 localhost）
```

### 3. 启动 Stable Diffusion WebUI

确保 SD WebUI 以 `--api` 模式运行：

```bash
cd stable-diffusion-webui
./webui.sh --api
```

### 4. 运行

```bash
# 单章处理
python run.py input/chapter01.txt

# 指定输出路径
python run.py input/chapter01.txt -o output/chapter01.mp4

# 跳过某些阶段
python run.py input/chapter01.txt --skip-images    # 跳过图片生成
python run.py input/chapter01.txt --skip-audio     # 跳过音频生成

# 使用 Whisper 字幕
python run.py input/chapter01.txt --whisper

# 断点恢复
python run.py input/chapter01.txt --resume workspace/chapter01

# 从 URL 下载并处理
python run.py "https://fanqienovel.com/page/123456"
```

### 5. 批量处理

```bash
# 处理第 1-10 章
python run_batch.py --input-dir input/小说目录/ --start 1 --end 10

# 失败自动重试 5 次
python run_batch.py --input-dir input/小说目录/ --start 1 --end 10 --max-retries 5

# 跳过已完成的章节
python run_batch.py --input-dir input/小说目录/ --start 1 --end 70 --skip-completed

# 按文件名模式匹配
python run_batch.py --input-dir input/小说目录/ --pattern "第0*.txt"
```

## 项目结构

```
TxtToVideo/
├── run.py                  # 主入口：单章 pipeline
├── run_batch.py            # 批量运行脚本
├── requirements.txt
├── .env.example            # 环境变量模板
├── config/
│   ├── pipeline.yaml       # Pipeline 全局配置（LLM/TTS/SD/动画/视频/字幕参数）
│   ├── characters.yaml     # 角色语音映射 + 外观描述
│   └── styles.yaml         # SD 绘图风格配置
├── scripts/
│   ├── 00_download_novel.py          # 阶段 0: 小说下载
│   ├── 01_parse_story.py             # 阶段 1: LLM 分镜
│   ├── 02_generate_audio.py          # 阶段 2: TTS 语音合成
│   ├── 03_generate_images.py         # 阶段 3: SD 生图
│   ├── 04_animate_images.py          # 阶段 4: Ken Burns 动画
│   ├── 05_compose_video.py           # 阶段 5: 音画合成
│   ├── 06_generate_subtitles.py      # 阶段 6: 字幕生成与烧录
│   ├── config_manager.py             # 统一配置管理
│   ├── pipeline_context.py           # Pipeline 上下文（工作区管理）
│   ├── platform_utils.py             # 跨平台工具（FFmpeg 路径等）
│   ├── cleanup.py                    # 中间产物清理
│   ├── migrate.py                    # 旧版资源迁移工具
│   ├── split_novel.py                # 小说拆分工具
│   ├── generate_cover.py             # 封面生成工具
│   └── generate_reference_portraits.py  # 角色定妆照生成
├── tests/                  # 测试
├── input/                  # 小说输入文件（不提交）
├── workspace/              # 中间产物工作区（不提交）
└── output/                 # 最终输出（不提交）
```

## 配置说明

所有配置集中在 `config/` 目录下，详见各文件内的注释。

### 角色配置 (`characters.yaml`)

为每个角色定义语音类型、情绪映射和外观描述：

```yaml
角色名:
  voice_type: "BV123_streaming"       # 火山引擎 voice type
  description: "角色描述"
  appearance: "young man, short dark hair, black jacket"  # SD 生图用
  emotion_map:
    default: { rate: "1.0", pitch: "0" }
    紧张:    { rate: "1.2", pitch: "2" }
```

### 风格配置 (`styles.yaml`)

定义 SD 绘图风格的 prompt 前缀、负向提示词和生成参数。

## 工具脚本

```bash
# 拆分小说大文件为单独章节
python scripts/split_novel.py input/小说.txt input/小说目录/

# 生成角色定妆照（需要 SD WebUI）
python -m scripts.generate_reference_portraits

# 生成封面图片
python scripts/generate_cover.py -o output/cover.png
```

## 常见问题

### SD WebUI 连接失败

确保 SD WebUI 以 `--api` 模式启动，默认地址为 `http://127.0.0.1:7860`。可通过环境变量 `SD_API_URL` 修改。

### TTS 不可用

未配置火山引擎 TTS 时，会自动降级为 edge-tts 或静音占位。配置方法见 `.env.example`。

### 字幕乱码

检查 `config/pipeline.yaml` 中的 `subtitle.font` 是否为系统已安装的中文字体。macOS 推荐 `PingFang SC`，Windows 推荐 `Microsoft YaHei`。

## License

[MIT](LICENSE)
