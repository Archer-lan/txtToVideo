# 需求文档：项目结构重构与章节化产物管理

## 简介

AutoNovel2Video 是一个将小说文本自动转换为有声动画视频的管线项目。当前项目存在以下结构性问题：

1. **产物路径硬编码**：所有中间产物（音频、图片、视频片段、字幕、分镜脚本）都存放在固定的 `assets/` 目录下，无法区分不同章节的产物，多章节处理时会互相覆盖。
2. **管线步骤耦合**：各阶段脚本通过硬编码的 `PROJECT_ROOT / "assets"` 路径互相依赖，无法独立运行或灵活组合。
3. **配置加载重复**：每个脚本都独立实现 `load_config()`、`load_characters()`、`load_styles()` 等函数，存在大量重复代码。
4. **无产物清理机制**：管线运行完成后，大量中间产物（单场景音频、单场景图片、动画片段、合并临时文件）残留在磁盘上，占用存储空间。
5. **缺乏统一的上下文管理**：各步骤之间通过文件路径隐式传递数据，没有统一的管线上下文对象来管理章节信息、路径映射和运行状态。

本次重构旨在：以章节为单位组织产物目录，使管线步骤更加独立，引入统一的上下文管理，并在最终视频生成成功后自动清理不需要的中间产物。

## 术语表

- **Pipeline（管线）**：从小说文本到最终视频的完整自动化处理流程，包含下载、解析、音频生成、图片生成、动画生成、视频合成、字幕生成等阶段
- **Pipeline_Context（管线上下文）**：管理单次管线运行的上下文对象，包含章节信息、路径映射、配置数据和运行状态
- **Chapter_Workspace（章节工作区）**：以章节为单位的产物目录结构，格式为 `workspace/{chapter_name}/`，包含该章节所有中间产物和最终产物的子目录
- **Artifact（产物）**：管线各阶段生成的文件，包括分镜脚本、音频文件、图片文件、视频片段、字幕文件等
- **Intermediate_Artifact（中间产物）**：管线过程中生成但最终不需要保留的文件，如单场景音频、单场景图片、动画片段、合并临时文件等
- **Final_Artifact（最终产物）**：管线最终输出的文件，包括最终视频文件和 SRT 字幕文件
- **Config_Manager（配置管理器）**：统一加载和管理 pipeline.yaml、characters.yaml、styles.yaml 等配置文件的模块
- **Step（步骤）**：管线中的一个独立处理阶段，接收 Pipeline_Context 作为输入，输出产物到 Chapter_Workspace
- **Cleanup_Policy（清理策略）**：定义哪些中间产物在最终视频生成成功后应被删除的规则

## 需求

### 需求 1：章节工作区目录结构

**用户故事：** 作为开发者，我希望每个章节的产物都存放在独立的目录中，以便多章节处理时产物不会互相覆盖，且便于管理和查找。

#### 验收标准

1. WHEN 管线开始处理一个章节时，THE Pipeline_Context SHALL 在 `workspace/` 目录下创建以章节名命名的子目录，目录结构为：
   ```
   workspace/{chapter_name}/
   ├── storyboard.json
   ├── audio/
   ├── images/
   ├── video/
   ├── subtitles/
   └── output/
   ```
2. THE Pipeline_Context SHALL 提供方法返回当前章节各类产物的完整路径，包括 storyboard 路径、audio 目录、images 目录、video 目录、subtitles 目录和 output 目录
3. WHEN 章节名包含特殊字符（如空格、中文标点）时，THE Pipeline_Context SHALL 对目录名进行安全转换，保留中文字符但替换文件系统不允许的字符
4. IF 指定的 Chapter_Workspace 目录已存在，THEN THE Pipeline_Context SHALL 复用该目录而非报错，以支持断点续跑场景

### 需求 2：统一配置管理器

**用户故事：** 作为开发者，我希望有一个统一的配置加载模块，避免每个脚本重复实现配置加载逻辑，减少代码冗余。

#### 验收标准

1. THE Config_Manager SHALL 提供统一的接口加载 pipeline.yaml、characters.yaml 和 styles.yaml 三个配置文件
2. THE Config_Manager SHALL 在首次加载后缓存配置数据，后续调用直接返回缓存结果，避免重复读取文件
3. WHEN 配置文件不存在或格式错误时，THE Config_Manager SHALL 抛出包含文件路径和错误详情的异常信息
4. THE Config_Manager SHALL 支持通过参数指定配置文件目录，默认为项目根目录下的 `config/` 目录

### 需求 3：管线上下文对象

**用户故事：** 作为开发者，我希望有一个统一的上下文对象在管线步骤之间传递信息，替代当前通过硬编码路径隐式传递数据的方式。

#### 验收标准

1. THE Pipeline_Context SHALL 包含以下信息：章节名称、Chapter_Workspace 路径映射、Config_Manager 实例、当前运行状态和各步骤的完成标记
2. WHEN 一个 Step 执行完成后，THE Pipeline_Context SHALL 记录该步骤的完成状态和产物路径
3. THE Pipeline_Context SHALL 提供序列化方法，将当前状态保存为 JSON 文件到 Chapter_Workspace 根目录，以支持断点续跑
4. WHEN 从已有的状态文件恢复时，THE Pipeline_Context SHALL 验证所有已标记完成的步骤对应的产物文件确实存在

### 需求 4：步骤接口标准化

**用户故事：** 作为开发者，我希望每个管线步骤都遵循统一的接口规范，使步骤之间解耦，可以独立测试和灵活组合。

#### 验收标准

1. THE Step SHALL 定义统一的调用接口，接收 Pipeline_Context 作为唯一参数，从中获取输入路径、输出路径和配置信息
2. WHEN 一个 Step 需要前置步骤的产物时，THE Step SHALL 通过 Pipeline_Context 获取产物路径，而非硬编码路径
3. THE Step SHALL 在执行前验证所需的输入产物是否存在，IF 输入产物缺失，THEN THE Step SHALL 抛出明确的错误信息，指出缺失的文件路径
4. WHEN 一个 Step 执行成功后，THE Step SHALL 通过 Pipeline_Context 注册其输出产物的路径
5. THE Step SHALL 保留当前各脚本的独立可执行能力，支持通过命令行参数直接指定输入输出路径运行

### 需求 5：主管线编排器重构

**用户故事：** 作为用户，我希望主管线入口（run.py）能够基于新的上下文机制编排各步骤，支持按章节处理和断点续跑。

#### 验收标准

1. WHEN 用户指定输入文件时，THE Pipeline SHALL 自动从文件名推断章节名称，创建对应的 Chapter_Workspace
2. WHEN 用户使用 `--skip-*` 参数跳过某个步骤时，THE Pipeline SHALL 检查该步骤的产物是否已存在于 Chapter_Workspace 中，IF 产物不存在，THEN THE Pipeline SHALL 发出警告信息
3. THE Pipeline SHALL 在每个步骤完成后将 Pipeline_Context 状态持久化到 Chapter_Workspace，以支持中断后恢复
4. WHEN 用户指定 `--resume` 参数时，THE Pipeline SHALL 从 Chapter_Workspace 中的状态文件恢复，跳过已完成的步骤
5. THE Pipeline SHALL 保持与当前命令行参数的向后兼容性，现有的 `--skip-parse`、`--skip-audio`、`--skip-images`、`--skip-animate`、`--whisper` 等参数继续有效

### 需求 6：中间产物清理

**用户故事：** 作为用户，我希望在最终视频成功生成后，管线能自动清理不需要的中间产物，释放磁盘空间。

#### 验收标准

1. WHEN 最终视频文件成功生成且文件大小大于 0 字节时，THE Pipeline SHALL 根据 Cleanup_Policy 删除 Chapter_Workspace 中的中间产物
2. THE Cleanup_Policy SHALL 默认保留以下文件：最终视频文件（output 目录）、SRT 字幕文件、storyboard.json 和管线状态文件
3. THE Cleanup_Policy SHALL 默认删除以下文件：单场景音频文件（audio 目录）、单场景图片文件（images 目录）、动画视频片段（video 目录中的 scene_*.mp4）和合成中间视频（composed_no_sub.mp4）
4. WHEN 用户指定 `--keep-artifacts` 参数时，THE Pipeline SHALL 跳过清理步骤，保留所有中间产物
5. IF 清理过程中某个文件删除失败，THEN THE Pipeline SHALL 记录警告日志并继续清理其他文件，不中断管线执行
6. THE Pipeline SHALL 在清理前记录将要删除的文件列表到日志中，以便用户追溯

### 需求 7：旧产物目录迁移兼容

**用户故事：** 作为现有用户，我希望重构后的项目能兼容旧的 `assets/` 目录结构，平滑过渡到新的章节工作区模式。

#### 验收标准

1. WHEN `assets/` 目录下存在旧产物且未指定 Chapter_Workspace 时，THE Pipeline SHALL 发出迁移提示信息，告知用户新的目录结构
2. THE Pipeline SHALL 提供 `--migrate` 命令行参数，将 `assets/` 目录下的现有产物迁移到指定章节名的 Chapter_Workspace 中
3. WHEN 执行迁移操作时，THE Pipeline SHALL 使用移动而非复制操作，避免磁盘空间翻倍占用
4. IF 迁移目标目录已存在同名文件，THEN THE Pipeline SHALL 跳过该文件并记录警告日志

### 需求 8：配置文件扩展

**用户故事：** 作为开发者，我希望 pipeline.yaml 中新增工作区和清理相关的配置项，使行为可配置。

#### 验收标准

1. THE pipeline.yaml SHALL 新增 `workspace` 配置段，包含工作区根目录路径（默认 `workspace`）和默认章节名模板
2. THE pipeline.yaml SHALL 新增 `cleanup` 配置段，包含是否启用自动清理（默认 true）、保留文件模式列表和删除文件模式列表
3. WHEN 配置文件中未包含新增配置段时，THE Config_Manager SHALL 使用默认值，保持向后兼容
