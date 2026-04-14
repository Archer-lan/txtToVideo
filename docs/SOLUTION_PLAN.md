# txtToVideo 架构优化 — 完整实施计划

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
├── .env.example                  # [已创建] 环境变量模板
├── .env                          # [gitignore] 实际密钥
│
├── config/
│   ├── pipeline.yaml             # 管线配置（保持不变）
│   ├── characters.yaml           # 角色配置（保持不变）
│   └── styles.yaml               # 画风配置（保持不变）
│
├── scripts/
│   ├── config_manager.py         # 统一配置 [修改: 加载 .env]
│   ├── pipeline_context.py       # 管线上下文（保持不变）
│   ├── platform_utils.py         # 跨平台工具（保持不变）
│   ├── cleanup.py                # 清理器（保持不变）
│   ├── migrate.py                # 迁移工具（保持不变）
│   │
│   ├── 00_download_novel.py      # 阶段0: 下载（保持不变）
│   ├── 01_parse_story.py         # 阶段1: 分镜解析 [修改: 增强 prompt]
│   ├── 02_generate_audio.py      # 阶段2: 音频 [修改: 使用 ConfigManager]
│   ├── 03_generate_images.py     # 阶段3: 图片 [修改: 使用 ConfigManager + prompt增强]
│   ├── 04_animate_images.py      # 阶段4: 动画 [修改: 使用 ConfigManager]
│   ├── 05_compose_video.py       # 阶段5: 合成 [修改: 使用 ConfigManager]
│   ├── 06_generate_subtitles.py  # 阶段6: 字幕 [修改: 使用 ConfigManager]
│   │
│   ├── character_detector.py     # [新增] 角色自动检测
│   └── split_novel.py            # [修改] 参数化
│
├── tools/                        # [新增] 独立工具目录
│   └── generate_cover.py         # [移动+修改] 封面生成（参数化）
│
├── workspace/                    # 章节工作区（gitignore）
├── input/                        # 输入文件（gitignore）
└── docs/
    └── SOLUTION_PLAN.md          # 本文档
```

---

## 三、完整实施计划

---

### 任务 1: 密钥泄露修复 + .env 集成

**优先级**: 🔴 紧急  
**预估**: 30min  
**状态**: ⬜ 未开始

#### 背景
`run_chapters_11_40.py` 中硬编码了 MiniMax API Key 并已推送到 GitHub。需要立即撤销密钥并引入 `.env` 管理。

#### 具体步骤

- [ ] **1.1** 登录 MiniMax 控制台，撤销/轮换已泄露的 API Key `sk-cp-tBm7dw8K...`
- [ ] **1.2** 在 `requirements.txt` 中添加 `python-dotenv>=1.0.0`
- [ ] **1.3** 修改 `scripts/config_manager.py`，在 `__init__` 中加载 `.env`：
  ```python
  # 在 __init__ 方法开头添加
  from dotenv import load_dotenv
  load_dotenv()
  ```
- [ ] **1.4** 确认 `.gitignore` 已包含 `.env`（已完成 ✅）
- [ ] **1.5** 确认 `.env.example` 已创建（已完成 ✅）
- [ ] **1.6** 创建本地 `.env` 文件，填入新的 API Key
- [ ] **1.7** 使用 `git filter-branch` 或 `BFG Repo-Cleaner` 从 git 历史中清除泄露的密钥

#### 验收
- `git log -p | grep "sk-cp-"` 无结果
- 所有脚本通过 `os.environ.get()` 读取密钥，源码中无硬编码

---

### 任务 2: 清理散乱的批处理脚本

**优先级**: 🔴 高  
**预估**: 1h  
**状态**: ⬜ 未开始

#### 背景
当前有 3 个功能重复的批处理脚本，每个只处理特定章节范围，每次新范围都要写新脚本。

#### 具体步骤

- [ ] **2.1** 删除以下文件：
  - `run_chapters_11_40.py`（含泄露密钥）
  - `scripts/run_chapters.py`（硬编码第2-10章）
  - `scripts/run_41_70.py`（硬编码第41-70章）

- [ ] **2.2** 创建 `run_batch.py`，实现统一批处理入口：

  **命令行接口**：
  ```bash
  python run_batch.py <input_dir> [选项]

  位置参数:
    input_dir              章节文件所在目录 (如 input/十日终焉/)

  选项:
    --range START-END      章节范围 (如 1-10, 11-40, 50-)
    --chapters LIST        指定章节列表 (如 5,12,37)
    --all                  处理所有章节
    --skip-completed       跳过已有输出视频的章节
    --fail-fast            遇到失败立即停止（默认继续下一章）
    --no-subtitle          不生成字幕（透传给 run.py）
    --keep-artifacts       保留中间产物（透传给 run.py）
  ```

  **核心逻辑**：
  ```python
  def find_chapter_files(input_dir: Path, chapter_range=None, chapter_list=None) -> list[Path]:
      """扫描目录，按章节号排序，过滤指定范围"""
      # 匹配 "第XXX章" 模式，提取章节号
      # 按章节号排序
      # 根据 --range 或 --chapters 过滤

  def is_chapter_completed(chapter_name: str, workspace_root: Path) -> bool:
      """检查 workspace/{chapter_name}/output/ 下是否有 .mp4 文件"""

  def run_single_chapter(chapter_path: Path, extra_args: list[str]) -> bool:
      """调用 subprocess.run([sys.executable, "run.py", str(chapter_path)] + extra_args)"""

  def main():
      # 1. 解析参数
      # 2. 扫描章节文件
      # 3. 过滤已完成（如果 --skip-completed）
      # 4. 逐个执行，记录成功/失败
      # 5. 输出批处理报告
  ```

- [ ] **2.3** 测试：`python run_batch.py input/十日终焉/ --range 1-3 --skip-completed`

#### 验收
- 3 个旧脚本已删除
- `python run_batch.py input/十日终焉/ --range 1-5 --skip-completed` 正常运行
- 失败章节不阻断后续章节（除非 `--fail-fast`）

---

### 任务 3: 统一 ConfigManager 使用

**优先级**: 🟡 中  
**预估**: 2h  
**状态**: ⬜ 未开始

#### 背景
`02~06` 每个阶段脚本都有自己的 `load_config()` / `load_characters()` / `load_styles()`，而 `ConfigManager` 已经实现了统一加载和缓存，但只在 `run.py` 和 `pipeline_context.py` 中使用。

#### 具体步骤

改造模式统一为：在主函数签名中添加 `config_manager=None` 参数，内部 fallback 到自建实例。这样既支持 `run.py` 注入，也支持独立运行。

- [ ] **3.1** 修改 `scripts/02_generate_audio.py`：
  - 删除文件顶部的 `load_config()` 和 `load_characters()` 函数
  - 修改 `generate_all_audio` 签名：
    ```python
    def generate_all_audio(storyboard_path=None, output_dir=None, config_manager=None):
        if config_manager is None:
            from scripts.config_manager import ConfigManager
            config_manager = ConfigManager()
        config = config_manager.pipeline
        characters = config_manager.characters
        ...
    ```
  - 删除函数体内的 `config = load_config()` 和 `characters = load_characters()`

- [ ] **3.2** 修改 `scripts/03_generate_images.py`：
  - 删除 `load_config()`, `load_styles()`, `load_characters()` 三个函数
  - 修改 `generate_all_images` 签名：
    ```python
    def generate_all_images(storyboard_path=None, output_dir=None, config_manager=None):
        if config_manager is None:
            from scripts.config_manager import ConfigManager
            config_manager = ConfigManager()
        config = config_manager.pipeline
        styles_config = config_manager.styles
        characters_config = config_manager.characters
        ...
    ```
  - `build_sd_prompt` 不变（它接收的是已加载的 dict，不直接依赖 load 函数）

- [ ] **3.3** 修改 `scripts/04_animate_images.py`：
  - 删除 `load_config()` 函数
  - 修改 `animate_all_images` 签名：
    ```python
    def animate_all_images(storyboard_path=None, audio_dir=None, image_dir=None, output_dir=None, config_manager=None):
        if config_manager is None:
            from scripts.config_manager import ConfigManager
            config_manager = ConfigManager()
        config = config_manager.pipeline
        ...
    ```

- [ ] **3.4** 修改 `scripts/05_compose_video.py`：
  - 删除 `load_config()` 函数
  - 修改 `compose_video` 签名：
    ```python
    def compose_video(storyboard_path=None, audio_dir=None, video_dir=None, output_path=None, config_manager=None):
        if config_manager is None:
            from scripts.config_manager import ConfigManager
            config_manager = ConfigManager()
        config = config_manager.pipeline
        ...
    ```

- [ ] **3.5** 修改 `scripts/06_generate_subtitles.py`：
  - 删除 `load_config()` 函数
  - 修改 `generate_subtitles` 签名：
    ```python
    def generate_subtitles(storyboard_path=None, audio_dir=None, video_path=None, output_path=None, use_whisper=False, config_manager=None):
        if config_manager is None:
            from scripts.config_manager import ConfigManager
            config_manager = ConfigManager()
        config = config_manager.pipeline
        ...
    ```

- [ ] **3.6** 修改 `scripts/01_parse_story.py`：
  - 删除 `load_config()` 函数
  - 修改 `parse_story` 签名：
    ```python
    def parse_story(input_path, output_path=None, config_manager=None):
        if config_manager is None:
            from scripts.config_manager import ConfigManager
            config_manager = ConfigManager()
        config = config_manager.pipeline
        ...
    ```

- [ ] **3.7** 修改 `run.py`，将 `cfg` 实例透传给各阶段：
  ```python
  # 当前:
  mod.parse_story(input_path, storyboard_path)
  # 改为:
  mod.parse_story(input_path, storyboard_path, config_manager=cfg)

  # 当前:
  mod.generate_all_audio(storyboard_path, audio_dir)
  # 改为:
  mod.generate_all_audio(storyboard_path, audio_dir, config_manager=cfg)

  # 同理修改阶段 3~6 的调用
  ```

- [ ] **3.8** 验证各脚本独立运行仍正常（`python scripts/01_parse_story.py input/test.txt`）

#### 验收
- `grep -r "def load_config" scripts/0*.py` 无结果（01~06 中不再有独立的 load_config）
- `run.py` 正常运行完整管线
- 各脚本 `__main__` 独立运行正常（自动创建 ConfigManager）

---

### 任务 4: 参数化工具脚本

**优先级**: 🟡 中  
**预估**: 1h  
**状态**: ⬜ 未开始

#### 具体步骤

- [ ] **4.1** 修改 `scripts/split_novel.py`，添加 argparse：
  ```python
  # 当前: 硬编码 input_file 和 output_dir
  # 改为:
  import argparse

  def split_novel(input_file: Path, output_dir: Path):
      """拆分大文件为单独章节（现有逻辑不变）"""
      ...

  if __name__ == "__main__":
      parser = argparse.ArgumentParser(description="拆分小说为单独章节文件")
      parser.add_argument("input", type=Path, help="输入小说文件路径")
      parser.add_argument("--output", "-o", type=Path, default=None,
                          help="输出目录（默认: input/{小说名}/）")
      args = parser.parse_args()
      output = args.output or args.input.parent / args.input.stem
      split_novel(args.input, output)
  ```

- [ ] **4.2** 创建 `tools/` 目录，移动并重写 `generate_cover.py` → `tools/generate_cover.py`：
  ```python
  # 当前: 硬编码 prompt、绝对输出路径
  # 改为:
  import argparse

  def generate_cover(prompt: str, output_path: Path, sd_url: str = "http://127.0.0.1:7860"):
      """调用 SD WebUI 生成封面图"""
      ...

  if __name__ == "__main__":
      parser = argparse.ArgumentParser(description="生成小说封面图")
      parser.add_argument("--prompt", "-p", required=True, help="封面画面描述")
      parser.add_argument("--output", "-o", type=Path, default=Path("workspace/cover.png"))
      parser.add_argument("--sd-url", default="http://127.0.0.1:7860")
      args = parser.parse_args()
      generate_cover(args.prompt, args.output, args.sd_url)
  ```

- [ ] **4.3** 删除根目录的 `generate_cover.py`

#### 验收
- `python scripts/split_novel.py input/your_novel.txt` 正常工作
- `python tools/generate_cover.py --prompt "test" --output test.png` 正常工作
- 根目录无 `generate_cover.py`

---

### 任务 5: 增强分镜 System Prompt

**优先级**: 🟡 中  
**预估**: 1h  
**状态**: ⬜ 未开始

#### 背景
当前 `SYSTEM_PROMPT` 中对 `visual.prompt` 的要求是 "英文画面描述，20-40个词"，但缺少对光线、氛围、人物动作的具体要求，导致 SD 生图效果不稳定。

#### 具体步骤

- [ ] **5.1** 修改 `scripts/01_parse_story.py` 中的 `SYSTEM_PROMPT`，将 `visual.prompt` 的描述要求从：
  ```
  "prompt": "英文画面描述，用于AI绘图，20-40个词",
  ```
  改为：
  ```
  "prompt": "英文画面描述，用于AI绘图，30-60个词，必须包含：1)场景环境(室内/室外/天气/时间) 2)人物动作和姿态 3)光线和氛围 4)关键物件",
  ```

- [ ] **5.2** 在 `SYSTEM_PROMPT` 的规则部分追加 visual.prompt 质量要求：
  ```
  7. visual.prompt 质量要求：
     - 必须包含具体的环境描述（不能只写 "a room"，要写 "dimly lit concrete room with fluorescent lights"）
     - 必须包含人物的动作/姿态（不能只写 "a man"，要写 "young man standing tensely with clenched fists"）
     - 必须包含光线描述（如 "harsh overhead light", "warm sunset glow", "cold moonlight"）
     - 多角色场景必须描述空间关系（如 "facing each other", "standing behind"）
     - 禁止使用抽象词汇（如 "mysterious", "beautiful"），改用具体视觉描述
  ```

- [ ] **5.3** 在 `SUMMARY_PROMPT` 中增加对 `characters_in_chapter` 的要求：
  ```
  - characters_in_chapter 的 appearance 必须包含：发型、发色、体型、服装、显著特征
  ```

- [ ] **5.4** 用 1-2 个测试章节验证效果，对比改前改后的 `visual.prompt` 质量

#### 验收
- 生成的 storyboard.json 中，`visual.prompt` 平均长度 > 30 词
- prompt 中包含环境、动作、光线三要素
- 不改变 JSON 结构，下游脚本无需修改

---

### 任务 6: 角色自动检测

**优先级**: 🟡 中  
**预估**: 1.5h  
**状态**: ⬜ 未开始

#### 具体步骤

- [ ] **6.1** 创建 `scripts/character_detector.py`：
  ```python
  """
  角色自动检测

  从 storyboard.json 中检测未在 characters.yaml 中定义的角色，
  输出警告并生成建议配置。
  """
  import json
  import logging
  from pathlib import Path
  from typing import Optional

  logger = logging.getLogger(__name__)


  def detect_new_characters(
      storyboard_path: Path,
      characters_config: dict,
  ) -> list[str]:
      """
      从 storyboard 中检测未在 characters.yaml 中定义的角色名。

      Args:
          storyboard_path: storyboard.json 路径
          characters_config: 已加载的 characters.yaml 内容

      Returns:
          未配置的角色名列表（去重、排序）
      """
      with open(storyboard_path, "r", encoding="utf-8") as f:
          storyboard = json.load(f)

      known = set(characters_config.keys())
      unknown = set()

      for scene in storyboard["scenes"]:
          speaker = scene.get("speaker", "")
          if speaker and speaker != "narrator" and speaker not in known:
              unknown.add(speaker)

      return sorted(unknown)


  def suggest_voice_type(name: str, storyboard: dict) -> str:
      """
      根据角色在分镜中的上下文推荐 voice_type。

      简单启发式：
      - 分析角色对话中的情绪分布
      - 如果名字包含"女"/"姐"/"妈"/"娘" → 女声
      - 否则 → 男声
      """
      female_keywords = ["女", "姐", "妈", "娘", "婆", "姑", "嫂"]
      if any(kw in name for kw in female_keywords):
          return "BV104_streaming"  # 女声
      return "BV123_streaming"  # 男声


  def generate_yaml_suggestion(
      new_characters: list[str],
      storyboard: dict,
  ) -> str:
      """
      为未配置的角色生成 YAML 配置建议文本，
      用户可直接复制到 characters.yaml。
      """
      lines = ["# === 以下为自动检测到的新角色，请补充 appearance 后粘贴到 characters.yaml ==="]
      for name in new_characters:
          voice = suggest_voice_type(name, storyboard)
          lines.append(f"")
          lines.append(f"{name}:")
          lines.append(f'  voice_type: "{voice}"')
          lines.append(f'  description: "待补充"')
          lines.append(f'  appearance: "TODO: add English appearance description"')
          lines.append(f"  emotion_map:")
          lines.append(f"    default:")
          lines.append(f'      rate: "1.5"')
          lines.append(f'      pitch: "0"')
      return "\n".join(lines)
  ```

- [ ] **6.2** 在 `run.py` 的阶段 1 完成后集成检测逻辑：
  ```python
  # 在 "阶段 1: 文本 → 分镜脚本" 完成后、"阶段 2" 开始前，添加：
  from scripts.character_detector import detect_new_characters, generate_yaml_suggestion

  new_chars = detect_new_characters(storyboard_path, cfg.characters)
  if new_chars:
      logger.warning(f"⚠ 检测到 {len(new_chars)} 个未配置的角色: {new_chars}")
      logger.warning("  这些角色将使用 narrator 语音和无外观描述")
      logger.warning("  建议在 config/characters.yaml 中添加配置后用 --skip-parse 重新运行")
      # 生成建议配置到日志
      with open(storyboard_path, "r", encoding="utf-8") as f:
          sb = json.load(f)
      suggestion = generate_yaml_suggestion(new_chars, sb)
      logger.info(f"建议配置:\n{suggestion}")
  ```

- [ ] **6.3** 测试：用包含新角色的章节运行，确认警告正常输出

#### 验收
- 新章节出现未知角色时，管线输出警告但不中断
- 警告信息包含角色名列表和建议的 YAML 配置
- 管线继续使用 narrator 配置完成生成

---

### 任务 7: 增强 SD Prompt 构建逻辑

**优先级**: 🟢 低  
**预估**: 1h  
**状态**: ⬜ 未开始

#### 背景
`03_generate_images.py` 的 `build_sd_prompt()` 中，`location_anchor` 逻辑仅在前后场景情绪一致时注入，过于保守。

#### 具体步骤

- [ ] **7.1** 修改 `scripts/03_generate_images.py` 中 `build_sd_prompt()` 的 `location_anchor` 逻辑：
  ```python
  # 当前: 仅在 prev_emotion == curr_emotion 时注入
  # 改为: 在场景 ID 连续（相差 1）时注入，不再要求情绪一致
  if prev_scene is not None:
      prev_id = prev_scene.get("scene_id", 0)
      curr_id = scene.get("scene_id", 0)
      if curr_id - prev_id == 1:  # 连续场景
          prev_prompt = prev_scene["visual"].get("prompt", "")
          prev_words = prev_prompt.split(",")[0].strip()
          if prev_words and len(prev_words) < 80:
              location_anchor = f"same location as previous scene: {prev_words}"
  ```

- [ ] **7.2** 为未配置 `appearance` 的角色添加 fallback：
  ```python
  # 在 build_sd_prompt 中，appearance 为空时的处理：
  if not appearance and scene.get("speaker") != "narrator":
      # 从 visual.prompt 中提取人物相关描述作为 fallback
      # 不注入 appearance，让 visual.prompt 自身的人物描述生效
      pass  # visual.prompt 已包含人物描述（任务5增强后）
  ```

#### 验收
- 连续场景的 SD prompt 包含 location_anchor
- 未配置角色不会导致空 appearance 注入

---

### 任务 8: 完善 README

**优先级**: 🟢 低  
**预估**: 30min  
**状态**: ⬜ 未开始

#### 具体步骤

- [ ] **8.1** 重写 `README.md`，包含以下内容：
  - 项目简介（一句话）
  - 管线流程图（文字版）
  - 前置依赖（Python 3.10+, FFmpeg, SD WebUI 可选）
  - 快速开始（4 步）
  - 批量处理用法
  - 配置说明（pipeline.yaml, characters.yaml, styles.yaml 各自的作用）
  - 环境变量说明（.env.example 中的每个变量）
  - 项目结构概览

#### 验收
- README 包含完整的快速开始指南
- 新用户按 README 操作可以跑通管线

---

## 四、不做的事情

以下功能在当前阶段属于过度设计，暂不实施：

| 功能 | 原因 |
|------|------|
| 角色历史记录/版本管理 | 项目规模不需要，YAML + git 已足够 |
| 交互式画风预览选择 | CLI 工具中交互体验差，直接改 `styles.yaml` 更高效 |
| GUI/Web 界面 | 投入产出比太低，当前 CLI 够用 |
| 分镜 JSON 结构大改 | 会导致下游所有脚本需要适配，风险大收益小 |
| 多章节并行处理 | SD WebUI 是单实例瓶颈，并行无意义 |
| `storyboard_enhancer.py` 后处理器 | 直接在 System Prompt 中提升质量更简单有效 |

---

## 五、任务依赖关系与执行顺序

```
任务 1 (密钥修复)  ──→  任务 2 (清理脚本)  ──→  任务 3 (ConfigManager)
                                                       │
                                                       ├──→  任务 4 (参数化工具)
                                                       ├──→  任务 5 (增强 Prompt)
                                                       ├──→  任务 6 (角色检测)
                                                       └──→  任务 7 (SD Prompt)

任务 8 (README) 可随时进行，无依赖
```

**建议执行顺序**: 1 → 2 → 3 → 5 → 6 → 4 → 7 → 8

---

## 六、总工作量

| 任务 | 预估 | 风险 |
|------|------|------|
| 1. 密钥修复 + .env | 30min | 低 |
| 2. 清理脚本 + run_batch.py | 1h | 低 |
| 3. 统一 ConfigManager | 2h | 低（向后兼容） |
| 4. 参数化工具脚本 | 1h | 低 |
| 5. 增强 System Prompt | 1h | 中（需测试效果） |
| 6. 角色自动检测 | 1.5h | 低 |
| 7. 增强 SD Prompt 构建 | 1h | 低 |
| 8. 完善 README | 30min | 低 |
| **总计** | **~8.5h** | |

---

## 七、验收清单

- [ ] 源码中无硬编码 API Key，`.env.example` 存在
- [ ] 散乱的批处理脚本已删除，`run_batch.py` 可用
- [ ] 所有阶段脚本（01~06）支持 `config_manager` 参数注入
- [ ] `split_novel.py` 和 `generate_cover.py` 已参数化
- [ ] 分镜 `visual.prompt` 包含环境、动作、光线描述（30+ 词）
- [ ] 新章节出现未知角色时输出警告但不中断
- [ ] 连续场景的 SD prompt 包含 location_anchor
- [ ] README 包含完整的快速开始指南
- [ ] `python run.py input/test.txt` 完整管线跑通
- [ ] `python run_batch.py input/dir/ --range 1-3 --skip-completed` 正常运行

---

**文档版本**: 2.1  
**最后更新**: 2026-04-14  
**状态**: 待实施
