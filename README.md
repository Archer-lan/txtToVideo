# AutoNovel2Video

小说 → 有声 → 动画视频 一键生成工具

## 功能特性

- 📖 **小说下载** - 支持番茄小说、起点中文网等平台
- 🎬 **智能分镜** - LLM 自动拆解小说为分镜脚本
- 🔊 **多角色配音** - 火山引擎 TTS，支持情绪调节
- 🖼️ **AI 绘图** - Stable Diffusion 生成关键画面
- 🎞️ **镜头动画** - Ken Burns 效果，图片动起来
- 📝 **自动字幕** - 基于 storyboard 或 Whisper 生成
- 🎭 **角色管理** - 自动检测新角色，推荐语音配置
- 📦 **批量处理** - 支持多章节连续生成

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填入你的 API 密钥：

```bash
cp .env.example .env
# 编辑 .env 文件
```

### 3. 运行单章生成

```bash
python run.py input/第1章.txt
```

### 4. 批量处理多章节

```bash
# 处理第 1-10 章
python run_batch.py --range 1-10

# 处理指定章节
python run_batch.py --list 1,3,5,7,9

# 处理 input/ 目录下所有章节
python run_batch.py --all
```

## 配置说明

### 主要配置文件

| 文件 | 说明 |
|------|------|
| `config/pipeline.yaml` | 管线全局配置（LLM、TTS、SD 参数等） |
| `config/characters.yaml` | 角色 → 语音/外观映射 |
| `config/styles.yaml` | Stable Diffusion 画风预设 |

### 角色配置示例 (`config/characters.yaml`)

```yaml
齐夏:
  voice_type: "BV123_streaming"
  description: "男主角，年轻男声"
  appearance: "young man, short black hair, sharp eyes"
  emotion_map:
    default:
      rate: "1.5"
      pitch: "0"
```

## 命令行参数

### `run.py` 单章模式

```bash
python run.py <input> [选项]

选项:
  --output, -o OUTPUT    输出视频路径
  --skip-parse            跳过文本解析
  --skip-audio            跳过音频生成
  --skip-images           跳过图片生成
  --skip-animate          跳过动画生成
  --whisper               使用 Whisper 生成字幕
  --no-subtitle           不生成字幕
  --resume CHAPTER_DIR    从断点恢复
  --keep-artifacts        保留中间产物
```

### `run_batch.py` 批量模式

```bash
python run_batch.py [选项]

选项:
  --range RANGE          章节范围，如 1-10, 5-, -20
  --list LIST            章节列表，如 1,3,5
  --all                  处理所有章节
  --input-dir DIR        输入目录 (默认: input/)
  --output-dir DIR       输出目录 (默认: output/)
  --resume               跳过已完成章节
  --stop-on-error        出错时停止
```

### 工具脚本

```bash
# 拆分小说大文件
python scripts/split_novel.py input/小说.txt --output input/章节

# 生成封面图
python generate_cover.py --prompt "epic cover..." --output cover.png
```

## 项目结构

```
txtToVideo/
├── run.py              # 单章入口
├── run_batch.py        # 批量入口
├── generate_cover.py   # 封面生成
├── input/              # 输入小说目录
├── output/             # 输出视频目录
├── workspace/          # 章节工作区
├── config/             # 配置文件
│   ├── pipeline.yaml
│   ├── characters.yaml
│   └── styles.yaml
├── scripts/            # 管线脚本
│   ├── 00_download_novel.py
│   ├── 01_parse_story.py
│   ├── 02_generate_audio.py
│   ├── 03_generate_images.py
│   ├── 04_animate_images.py
│   ├── 05_compose_video.py
│   ├── 06_generate_subtitles.py
│   ├── split_novel.py
│   ├── character_detector.py
│   ├── config_manager.py
│   └── ...
└── requirements.txt
```

## 管线流程

```
小说文本
   ↓
[0] 下载小说 (可选)
   ↓
[1] 文本 → 分镜脚本 (storyboard.json)
   ↓
[2] 分镜 → 音频 (scene_xxx.wav)
   ↓
[3] 分镜 → 图片 (scene_xxx.png)
   ↓
[4] 图片 → 动画 (scene_xxx.mp4)
   ↓
[5] 音画合成 (composed_no_sub.mp4)
   ↓
[6] 字幕生成 & 烧录 (final.mp4)
```

## 常见问题

### Q: 如何添加新角色？

A: 运行管线时会自动检测未配置的角色，并在控制台输出建议的 YAML 配置。复制到 `config/characters.yaml` 并补充 `appearance` 描述即可。

### Q: 如何自定义 Stable Diffusion 画风？

A: 在 `config/styles.yaml` 中添加新的风格配置，然后在 `pipeline.yaml` 的 `image.style` 中指定。

### Q: 如何从断点恢复？

A: 使用 `--resume` 参数指定章节工作区目录：
```bash
python run.py input/第1章.txt --resume workspace/第1章
```

## 许可证

MIT License
