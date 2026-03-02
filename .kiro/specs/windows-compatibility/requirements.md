# 需求文档

## 简介

AutoNovel2Video 项目当前仅在 macOS 上运行。本需求文档定义了将项目改造为可在 Windows 上正常运行所需的全部功能需求，同时确保 macOS/Linux 上的现有行为不受影响。需求覆盖信号处理、文件路径、字体加载、FFmpeg 命令构建、HTTP 请求头及事件循环兼容性六个领域。

## 术语表

- **Platform_Utils**：跨平台工具模块（`scripts/platform_utils.py`），集中管理所有平台差异逻辑
- **Download_Module**：小说下载模块（`scripts/00_download_novel.py`），负责从各平台下载小说文本
- **Image_Module**：图片生成模块（`scripts/03_generate_images.py`），负责生成场景关键帧图片
- **Compose_Module**：视频合成模块（`scripts/05_compose_video.py`），负责拼接音视频片段
- **Subtitle_Module**：字幕生成模块（`scripts/06_generate_subtitles.py`），负责生成并烧录字幕
- **FFmpeg**：外部多媒体处理工具，用于视频编码、拼接和字幕烧录
- **SIGALRM**：Unix 信号，用于实现超时机制，Windows 不支持
- **PUA 码点**：Unicode 私有使用区码点，番茄小说用于字体混淆
- **concat demuxer**：FFmpeg 的文件拼接模式，通过文件列表指定输入
- **SRT**：SubRip 字幕格式

## 需求

### 需求 1：跨平台工具模块

**用户故事：** 作为开发者，我希望有一个集中的跨平台工具模块，以便各阶段脚本可以通过统一接口处理平台差异，而无需各自实现平台判断逻辑。

#### 验收标准

1. THE Platform_Utils SHALL 提供 `is_windows()` 函数，返回当前平台是否为 Windows 的布尔值
2. THE Platform_Utils SHALL 提供 `get_default_font_path()` 函数，根据当前平台返回对应的默认中文字体路径
3. THE Platform_Utils SHALL 提供 `get_ffmpeg_subtitle_path()` 函数，将文件路径转换为 FFmpeg subtitles 滤镜可接受的格式
4. THE Platform_Utils SHALL 提供 `run_with_timeout()` 函数，在所有平台上实现带超时的函数执行

### 需求 2：跨平台超时机制

**用户故事：** 作为用户，我希望在 Windows 上下载小说时也能有超时保护，以便在网络异常时不会无限等待。

#### 验收标准

1. WHEN 在 Windows 平台执行下载操作时，THE Download_Module SHALL 使用 `threading.Timer` 实现超时控制，替代 `signal.SIGALRM`
2. WHEN 被调用函数在超时时间内完成时，THE `run_with_timeout` 函数 SHALL 返回该函数的正常返回值
3. WHEN 被调用函数超过指定超时时间未完成时，THE `run_with_timeout` 函数 SHALL 抛出 `TimeoutError` 异常
4. WHILE 在 macOS 或 Linux 平台运行时，THE Download_Module SHALL 保持使用 `signal.SIGALRM` 的现有超时行为

### 需求 3：跨平台字体加载

**用户故事：** 作为用户，我希望在 Windows 上生成占位图时能正确加载中文字体，以便占位图上的文字能正常显示。

#### 验收标准

1. WHEN 在 Windows 平台生成占位图时，THE Image_Module SHALL 使用 Windows 系统中文字体（如 `C:/Windows/Fonts/msyh.ttc`）
2. WHEN 在 macOS 平台生成占位图时，THE Image_Module SHALL 继续使用 macOS 系统字体（`/System/Library/Fonts/Helvetica.ttc`）
3. IF 平台默认字体文件不存在，THEN THE Image_Module SHALL 降级使用 Pillow 默认字体，确保占位图仍可正常生成

### 需求 4：FFmpeg 字幕路径转义

**用户故事：** 作为用户，我希望在 Windows 上烧录字幕时 FFmpeg 能正确识别字幕文件路径，以便字幕能正常烧录到视频中。

#### 验收标准

1. WHEN 在 Windows 平台构建 FFmpeg subtitles 滤镜参数时，THE Subtitle_Module SHALL 将路径中的反斜杠替换为正斜杠
2. WHEN Windows 路径包含盘符冒号（如 `C:`）时，THE Subtitle_Module SHALL 对冒号进行正确转义
3. WHEN 路径包含中文字符或空格时，THE Subtitle_Module SHALL 生成 FFmpeg 可正确解析的转义路径
4. WHILE 在 macOS 或 Linux 平台运行时，THE Subtitle_Module SHALL 保持现有的路径转义逻辑不变

### 需求 5：FFmpeg concat 文件路径格式

**用户故事：** 作为用户，我希望在 Windows 上拼接视频时 FFmpeg concat demuxer 能正确识别文件列表中的路径。

#### 验收标准

1. WHEN 生成 FFmpeg concat 文件列表时，THE Compose_Module SHALL 使用 POSIX 格式的正斜杠路径（通过 `Path.as_posix()`）
2. WHEN concat 文件列表中的路径包含中文字符或空格时，THE Compose_Module SHALL 确保路径格式正确且 FFmpeg 可识别

### 需求 6：HTTP User-Agent 适配

**用户故事：** 作为用户，我希望在 Windows 上下载小说时使用与平台匹配的 User-Agent，以降低被目标网站拒绝的风险。

#### 验收标准

1. WHEN 在 Windows 平台发起 HTTP 请求时，THE Download_Module SHALL 使用 Windows 风格的 User-Agent 字符串
2. WHEN 在 macOS 平台发起 HTTP 请求时，THE Download_Module SHALL 继续使用 macOS 风格的 User-Agent 字符串

### 需求 7：向后兼容性

**用户故事：** 作为 macOS/Linux 用户，我希望 Windows 兼容性改造不影响现有功能，以便我的工作流程不受干扰。

#### 验收标准

1. THE 改造后的代码 SHALL 在 macOS 和 Linux 平台上保持与改造前完全一致的行为
2. WHEN 在 macOS 或 Linux 上运行现有测试套件时，THE 所有测试 SHALL 继续通过

### 需求 8：外部依赖安装指引

**用户故事：** 作为 Windows 用户，我希望有清晰的 FFmpeg 安装指引，以便我能快速配置运行环境。

#### 验收标准

1. THE `requirements.txt` SHALL 包含 Windows 平台的 FFmpeg 安装说明（winget、choco 或官网下载）
2. IF FFmpeg 未安装，THEN THE 视频处理阶段（阶段 4/5/6）SHALL 在开始前给出明确的错误提示和安装指引

### 需求 9：Windows asyncio 事件循环兼容

**用户故事：** 作为 Windows 用户，我希望使用 `edge-tts` 和 `novel-downloader` 等异步库时不会因事件循环策略不兼容而报错。

#### 验收标准

1. WHEN 在 Windows 平台使用 `asyncio.run()` 调用异步库时，THE 系统 SHALL 确保使用兼容的事件循环策略
2. IF Windows 上的 `ProactorEventLoop` 与依赖库不兼容，THEN THE 系统 SHALL 切换到 `WindowsSelectorEventLoopPolicy`
