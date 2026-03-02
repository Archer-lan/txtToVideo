# 实现计划：Windows 兼容性改造

## 概述

将 AutoNovel2Video 项目改造为可在 Windows 上运行，通过创建跨平台工具模块 `scripts/platform_utils.py` 集中管理平台差异，然后逐步改造各阶段脚本中的平台相关代码。改造遵循"最小侵入"原则，保持 macOS/Linux 上的现有行为不变。

## 任务

- [x] 1. 创建跨平台工具模块 `scripts/platform_utils.py`
  - [x] 1.1 实现平台检测与字体路径函数
    - 创建 `scripts/platform_utils.py` 文件
    - 实现 `is_windows()` 函数，使用 `platform.system()` 检测当前平台
    - 实现 `get_default_font_path()` 函数，根据平台返回默认中文字体路径（Windows: `C:/Windows/Fonts/msyh.ttc`，macOS: `/System/Library/Fonts/Helvetica.ttc`，Linux: `/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc`）
    - _需求: 1.1, 1.2_

  - [x] 1.2 实现 FFmpeg 字幕路径转义函数
    - 实现 `get_ffmpeg_subtitle_path(srt_path: Path) -> str`
    - Windows 上将反斜杠替换为正斜杠，转义盘符冒号为 `\\:`
    - POSIX 上保持现有转义逻辑（双重反斜杠转义、冒号转义、单引号转义）
    - 处理中文字符和空格路径
    - _需求: 1.3, 4.1, 4.2, 4.3, 4.4_

  - [x] 1.3 实现跨平台超时执行函数
    - 实现 `run_with_timeout(func, args, kwargs, timeout_seconds)` 函数
    - Windows 上使用 `threading.Thread` + `thread.join(timeout)` 实现超时
    - Unix 上使用 `signal.SIGALRM` 保持现有行为
    - 超时时抛出 `TimeoutError`，正常完成时返回函数返回值
    - _需求: 1.4, 2.1, 2.2, 2.3, 2.4_

  - [ ]* 1.4 为 `platform_utils.py` 编写属性测试
    - **属性 1: FFmpeg 字幕路径转义正确性**
    - 对任意包含中文、空格、反斜杠、盘符冒号的路径字符串，`get_ffmpeg_subtitle_path()` 转换后不应包含未转义的反斜杠，盘符冒号应被正确转义
    - **验证需求: 1.3, 4.1, 4.2, 4.3**

  - [ ]* 1.5 为 `run_with_timeout` 编写属性测试
    - **属性 2: 超时函数等价性**
    - 对任意可调用对象和超时时间，若函数在超时内完成，返回值应与直接调用一致
    - **验证需求: 1.4, 2.2**

  - [ ]* 1.6 为 `platform_utils.py` 编写单元测试
    - 使用 `unittest.mock.patch` 模拟 `platform.system()` 返回不同平台值
    - 测试 `is_windows()` 在各平台下的返回值
    - 测试 `get_default_font_path()` 在各平台下返回正确路径
    - 测试 `get_ffmpeg_subtitle_path()` 对 Windows 路径（如 `C:\Users\张三\project\subs.srt`）的处理
    - 测试 `run_with_timeout()` 的超时和正常完成场景
    - _需求: 1.1, 1.2, 1.3, 1.4_

- [x] 2. 检查点 - 确保平台工具模块测试通过
  - 确保所有测试通过，如有问题请询问用户。

- [x] 3. 改造下载模块 `scripts/00_download_novel.py`
  - [x] 3.1 替换信号超时机制为跨平台实现
    - 导入 `scripts.platform_utils.run_with_timeout`
    - 将 `download_novel()` 函数中的 `signal.SIGALRM` 超时逻辑替换为调用 `run_with_timeout()`
    - 移除 `_TimeoutError` 类和 `_timeout_handler` 函数（由 `platform_utils` 统一提供）
    - 确保 macOS/Linux 上保持 SIGALRM 行为，Windows 上使用 threading 超时
    - _需求: 2.1, 2.2, 2.3, 2.4_

  - [x] 3.2 添加平台自适应 User-Agent
    - 将 `FanqieDownloaderAdapter.HEADERS` 中硬编码的 macOS User-Agent 替换为根据平台动态生成
    - Windows 使用 `Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...`
    - macOS 保持现有 User-Agent
    - _需求: 6.1, 6.2_

  - [x] 3.3 添加 asyncio 事件循环兼容
    - 在 `NovelDownloaderAdapter.download()` 中 `asyncio.run()` 调用前，检测 Windows 平台并设置 `asyncio.WindowsSelectorEventLoopPolicy()`
    - 确保 `edge-tts` 和 `novel-downloader` 等异步库在 Windows 上正常工作
    - _需求: 9.1, 9.2_

- [x] 4. 改造图片生成模块 `scripts/03_generate_images.py`
  - [x] 4.1 替换硬编码字体路径为跨平台实现
    - 在 `generate_placeholder_image()` 函数中，将 `/System/Library/Fonts/Helvetica.ttc` 替换为 `get_default_font_path()` 调用
    - 保留 `except` 降级到 `ImageFont.load_default()` 的逻辑
    - _需求: 3.1, 3.2, 3.3_

- [x] 5. 改造视频合成模块 `scripts/05_compose_video.py`
  - [x] 5.1 修复 concat 文件列表路径格式
    - 在 `concat_simple()` 函数中，将 `f.write(f"file '{vf.resolve()}'\n")` 改为 `f.write(f"file '{vf.resolve().as_posix()}'\n")`
    - 确保 Windows 上 FFmpeg concat demuxer 能正确识别路径
    - _需求: 5.1, 5.2_

  - [ ]* 5.2 为 concat 路径编写属性测试
    - **属性 3: concat 路径 POSIX 格式**
    - 对任意文件路径，经 `Path.resolve().as_posix()` 转换后不应包含反斜杠字符
    - **验证需求: 5.1, 5.2**

- [x] 6. 改造字幕生成模块 `scripts/06_generate_subtitles.py`
  - [x] 6.1 替换字幕路径转义为跨平台实现
    - 在 `burn_subtitles()` 函数中，将现有的手动路径转义逻辑替换为调用 `get_ffmpeg_subtitle_path(srt_path)`
    - 确保 Windows 和 macOS/Linux 上都能正确生成 FFmpeg subtitles 滤镜参数
    - _需求: 4.1, 4.2, 4.3, 4.4_

- [x] 7. 更新依赖安装指引和 FFmpeg 检测
  - [x] 7.1 更新 `requirements.txt` 中的安装说明
    - 将 FFmpeg 安装说明从仅 macOS/Linux 扩展为包含 Windows（`winget install ffmpeg` / `choco install ffmpeg` / 官网下载）
    - _需求: 8.1_

  - [x] 7.2 在 `run.py` 中添加 asyncio 事件循环策略设置
    - 在 `main()` 函数入口处，检测 Windows 平台并设置 `asyncio.WindowsSelectorEventLoopPolicy()`
    - 确保整个管线中所有异步调用都使用兼容的事件循环
    - _需求: 9.1, 9.2_

- [x] 8. 检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请询问用户。
  - 验证改造后的代码在 macOS/Linux 上保持与改造前一致的行为
  - _需求: 7.1, 7.2_

## 备注

- 标记 `*` 的任务为可选任务，可跳过以加快 MVP 进度
- 每个任务引用了具体的需求编号以确保可追溯性
- 检查点用于增量验证，确保每个阶段的改造正确
- 属性测试使用 hypothesis 库验证通用正确性属性
- 单元测试使用 `unittest.mock.patch` 模拟不同平台环境
