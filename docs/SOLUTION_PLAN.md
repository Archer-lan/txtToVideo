# txtToVideo 架构优化方案

## 概述

本方案基于对现有代码库的全面审查，聚焦于三个层面：
1. **工程治理** — 消除技术债务、统一代码规范
2. **管线增强** — 提升分镜质量和角色一致性
3. **批处理能力** — 统一多章节处理流程

当前项目已具备完整的 6 阶段管线（解析→音频→图片→动画→合成→字幕），核心架构合理。
本方案不做推倒重来，而是在现有基础上做针对性优化。

---

## 一、现状问题（按严重程度排序）

### P0 — 安全与工程问题

| 问题 | 位置 | 影响 |
|------|------|------|
| API Key 硬编码在源码中 | `run_chapters_11_40.py` | 已推送到 GitHub，密钥泄露 |
| 批处理脚本散乱且重复 | `run_chapters_11_40.py`, `scripts/run_chapters.py`, `scripts/run_41_70.py` | 每次新章节范围都要写新脚本 |
| 各阶段脚本重复 `load_config()` | `02~06` 每个文件都有 | 违反 DRY，已有 `ConfigManager` 但未全面使用 |
| `generate_cover.py` 硬编码绝对路径 | 根目录 | 不可移植 |
| `split_novel.py` 硬编码文件路径 | `scripts/` | 只能处理特定小说 |

### P1 — 管线质量问题

| 问题 | 影响 |
|------|------|
| 分镜 `visual.prompt` 信息量不足 | SD 生图效果不稳定，缺少光线/氛围/动作细节 |
| 角色外观仅在 `characters.yaml` 静态配置 | 新章节出现新角色时需手动添加 |
| 无角色自动检测机制 | 每次新章节都可能遗漏角色 |
| img2img 链式生图的上下文传递较弱 | 连续场景视觉一致性不够 |

### P2 — 可用性问题

| 问题 | 影响 |
|------|------|
| README 几乎为空 | 新用户无法上手 |
| 无 `.env` 管理 | 环境变量配置不便 |
| 无统一的多章节批处理入口 | 用户体验差 |

---

## 二、目标架构

```
txtToVideo/
├── run.py                        # 单章节入口（保持不变）
├── run_batch.py                  # [新增] 统一批处理入口，替代所有散乱脚本
├── .env.example                  # [新增] 环境变量模板
├── .env                          # [gitignore] 实际密钥
│
├── config/
│   ├── pipeline.yaml             # 管线配置（保持不变）
│   ├── characters.yaml           # 角色配置（扩展结构）
│   └── styles.yaml               # 画风配置（保持不变）
│
├── scripts/
│   ├── config_manager.py         # 统一配置（保持不变）
│   ├── pipeline_context.py       # 管线上下文（保持不变）
│   ├── platform_utils.py         # 跨平台工具（保持不变）
│   ├── cleanup.py                # 清理器（保持不变）
│   ├── migrate.py                # 迁移工具（保持不变）
│   │
│   ├── 00_download_novel.py      # 阶段0: 下载
│   ├── 01_parse_story.py         # 阶段1: 分镜解析 [修改: 增强 prompt + 角色检测]
│   ├── 02_generate_audio.py      # 阶段2: 音频 [修改: 使用 ConfigManager]
│   ├── 03_generate_images.py     # 阶段3: 图片 [修改: 使用 ConfigManager]
│   ├── 04_animate_images.py      # 阶段4: 动画 [修改: 使用 ConfigManager]
│   ├── 05_compose_video.py       # 阶段5: 合成 [修改: 使用 ConfigManager]
│   ├── 06_generate_subtitles.py  # 阶段6: 字幕 [修改: 使用 ConfigManager]
│   │
│   ├── character_detector.py     # [新增] 角色自动检测（轻量级）
│   └── split_novel.py            # [修改] 参数化，支持任意小说
│
├── tools/                        # [新增] 独立工具（不参与管线）
│   └── generate_cover.py         # [移动] 封面生成（参数化）
│
├── workspace/                    # 章节工作区（gitignore）
├── input/                        # 输入文件（gitignore）
├── output/                       # 最终输出（gitignore）
└── docs/
    └── SOLUTION_PLAN.md          # 本文档
```

### 与现有架构的差异

- 删除: `run_chapters_11_40.py`, `scripts/run_chapters.py`, `scripts/run_41_70.py` → 统一为 `run_batch.py`
- 移动: `generate_cover.py` → `tools/generate_cover.py`
- 新增: `run_batch.py`, `.env.example`, `scripts/character_detector.py`
- 修改: 6 个阶段脚本统一使用 `ConfigManager`

---

## 三、实施计划

### 阶段 1: 安全与工程治理（优先级: 紧急）

#### 1.1 密钥管理

立即撤销已泄露的 API Key，引入 `.env` 管理：

```bash
# .env.example
MINIMAX_API_KEY=your_minimax_api_key_here
VOLCANO_APP_ID=your_volcano_app_id_here
VOLCANO_ACCESS_TOKEN=your_volcano_access_token_here
```

在 `config_manager.py` 中加载 `.env`：

```python
from dotenv import load_dotenv
load_dotenv()
```

#### 1.2 统一批处理入口 (`run_batch.py`)

替代所有散乱的批处理脚本，提供统一接口：

```bash
# 处理第 1-10 章
python run_batch.py input/十日终焉/ --range 1-10

# 处理第 11-40 章，跳过已完成的
python run_batch.py input/十日终焉/ --range 11-40 --skip-completed

# 处理所有章节
python run_batch.py input/十日终焉/ --all --skip-completed

# 处理指定章节列表
python run_batch.py input/十日终焉/ --chapters 5,12,37
```

核心逻辑：
- 扫描 `workspace/` 判断已完成章节（存在 output/*.mp4）
- 按章节号排序，顺序执行 `run.py`
- 失败时记录并继续下一章（`--fail-fast` 可选立即停止）
- 生成批处理报告

#### 1.3 统一 ConfigManager 使用

将 `02~06` 各脚本中重复的 `load_config()` / `load_characters()` / `load_styles()` 替换为接收 `ConfigManager` 实例。

改造模式（以 `02_generate_audio.py` 为例）：

```python
# Before:
def load_config():
    config_path = PROJECT_ROOT / "config" / "pipeline.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def generate_all_audio(storyboard_path, audio_dir):
    config = load_config()
    ...

# After:
def generate_all_audio(storyboard_path, audio_dir, config_manager=None):
    if config_manager is None:
        config_manager = ConfigManager()
    config = config_manager.pipeline
    ...
```

向后兼容：`config_manager` 参数默认 `None`，不传时自动创建。

#### 1.4 清理散乱脚本

- 删除 `run_chapters_11_40.py`（含泄露密钥）
- 删除 `scripts/run_chapters.py`
- 删除 `scripts/run_41_70.py`
- 参数化 `scripts/split_novel.py`（接受命令行参数）
- 移动 `generate_cover.py` → `tools/generate_cover.py`（参数化）

---

### 阶段 2: 分镜解析增强（优先级: 高）

#### 2.1 增强 System Prompt

当前 `01_parse_story.py` 的 prompt 输出结构已经合理，但 `visual.prompt` 的描述质量不够。

优化方向（在现有 System Prompt 基础上追加要求）：

```
visual.prompt 要求：
1. 必须包含场景环境描述（室内/室外、天气、时间）
2. 必须包含人物动作和姿态
3. 必须包含光线和氛围描述
4. 使用具体的视觉词汇，避免抽象描述
5. 如果场景有多个角色，描述他们的空间关系

示例：
  差: "a man talking in a room"
  好: "young man with messy black hair standing tensely in a dimly lit concrete room, 
       facing a tall muscular figure, harsh overhead fluorescent light casting sharp shadows, 
       abandoned warehouse interior, dust particles in the air"
```

不改变 JSON 结构，只提升 prompt 内容质量。这样下游所有脚本无需修改。

#### 2.2 角色自动检测 (`scripts/character_detector.py`)

轻量级方案，不做复杂的角色管理系统：

```python
def detect_new_characters(storyboard_path: Path, characters_config: dict) -> list[str]:
    """从 storyboard 中检测未在 characters.yaml 中定义的角色名"""
    with open(storyboard_path) as f:
        storyboard = json.load(f)
    
    known = set(characters_config.keys())
    found = set()
    for scene in storyboard["scenes"]:
        speaker = scene.get("speaker", "")
        if speaker and speaker != "narrator" and speaker not in known:
            found.add(speaker)
    return sorted(found)


def suggest_character_config(name: str, storyboard: dict) -> dict:
    """根据角色在分镜中的上下文，生成建议配置"""
    # 分析角色的对话内容和情绪分布，推荐 voice_type
    ...
```

集成到 `run.py` 的阶段 1 之后：

```python
# 阶段 1 完成后，检测新角色
new_chars = character_detector.detect_new_characters(storyboard_path, cfg.characters)
if new_chars:
    logger.warning(f"检测到未配置的角色: {new_chars}")
    logger.warning("这些角色将使用 narrator 的语音和默认外观")
    logger.warning("建议在 config/characters.yaml 中添加配置后重新运行")
```

不阻断管线，只做警告。用户可以选择先跑完再补充角色配置。

#### 2.3 增强 Prompt 构建逻辑

在 `03_generate_images.py` 的 `build_sd_prompt()` 中：

- 当角色没有 `appearance` 配置时，从 `visual.prompt` 中提取人物描述作为 fallback
- 增强 `location_anchor` 逻辑，不仅看情绪是否一致，还看场景 ID 是否连续

---

### 阶段 3: 批处理与可用性（优先级: 中）

#### 3.1 完善 README

```markdown
# txtToVideo — 小说转有声动画视频

将小说文本自动转换为带配音、画面、字幕的动画视频。

## 管线流程
小说文本 → LLM分镜 → TTS配音 → SD生图 → Ken Burns动画 → 音画合成 → 字幕烧录

## 快速开始
1. 安装依赖: `pip install -r requirements.txt`
2. 配置环境变量: `cp .env.example .env` 并填入 API Key
3. 启动 SD WebUI（可选）
4. 运行: `python run.py input/your_novel.txt`

## 批量处理
python run_batch.py input/your_novel_dir/ --range 1-50 --skip-completed
```

#### 3.2 参数化工具脚本

`split_novel.py` 改为接受命令行参数：

```bash
python scripts/split_novel.py input/your_novel.txt --output input/your_novel/
```

`tools/generate_cover.py` 改为接受参数：

```bash
python tools/generate_cover.py --prompt "your prompt" --output workspace/cover.png
```

---

## 四、不做的事情

以下功能在当前阶段属于过度设计，暂不实施：

| 功能 | 原因 |
|------|------|
| 角色历史记录/版本管理 | 项目规模不需要，YAML 配置 + git 已足够 |
| 交互式画风预览选择 | CLI 工具中交互体验差，直接改 `styles.yaml` 更高效 |
| GUI/Web 界面 | 投入产出比太低，当前 CLI 够用 |
| 分镜 JSON 结构大改 | 会导致下游所有脚本需要适配，风险大收益小 |
| 多章节并行处理 | SD WebUI 是单实例瓶颈，并行无意义 |
| `storyboard_enhancer.py` 后处理器 | 直接在 System Prompt 中提升质量更简单有效 |

---

## 五、实施优先级与工作量估算

| 阶段 | 任务 | 预估工作量 | 风险 |
|------|------|-----------|------|
| 1.1 | 密钥管理 + `.env` | 0.5h | 低 |
| 1.2 | `run_batch.py` | 2h | 低 |
| 1.3 | 统一 ConfigManager | 2h | 低（向后兼容） |
| 1.4 | 清理散乱脚本 | 1h | 低 |
| 2.1 | 增强 System Prompt | 1h | 中（需要测试效果） |
| 2.2 | 角色自动检测 | 1.5h | 低 |
| 2.3 | 增强 Prompt 构建 | 1h | 低 |
| 3.1 | 完善 README | 0.5h | 低 |
| 3.2 | 参数化工具脚本 | 1h | 低 |

总计约 10.5h，建议按阶段顺序执行。

---

## 六、验收标准

- [ ] `.env.example` 存在，所有 API Key 通过环境变量读取，源码中无硬编码密钥
- [ ] `python run_batch.py input/dir/ --range 1-5` 可正常批量处理
- [ ] 所有阶段脚本支持 `config_manager` 参数注入
- [ ] 散乱的批处理脚本已删除
- [ ] 新章节出现未知角色时，管线输出警告但不中断
- [ ] 分镜 `visual.prompt` 包含环境、动作、光线描述
- [ ] README 包含完整的快速开始指南

---

**文档版本**: 2.0  
**最后更新**: 2026-04-14  
**状态**: 待实施
