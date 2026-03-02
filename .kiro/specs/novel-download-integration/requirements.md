# 需求文档

## 简介

本功能为 AutoNovel2Video 管线新增「阶段 0：小说下载」，在现有阶段 1（文本解析）之前，集成 `novel-downloader` 和 `fanqienovel-downloader` 两个开源下载器，使用户可以通过 URL 或书籍 ID 直接从起点中文网、番茄小说、笔趣阁等平台下载小说文本，下载完成后自动保存到 `input/` 目录并衔接后续管线。

## 术语表

- **Pipeline**: AutoNovel2Video 管线，将小说文本转换为有声动画视频的自动化流程
- **PlatformRouter**: 平台路由器，根据用户输入的 URL 或书籍 ID 自动识别目标平台并返回对应下载器
- **BaseDownloader**: 下载器抽象基类，定义统一的下载接口
- **NovelDownloaderAdapter**: 封装 `novel-downloader` 库的适配器，支持起点中文网、笔趣阁等平台
- **FanqieDownloaderAdapter**: 封装 `fanqienovel-downloader` 的适配器，支持番茄小说平台
- **PlatformInfo**: 平台信息数据类，包含平台名称、下载器类型、书籍 ID
- **DownloadResult**: 下载结果数据类，包含输出文件路径、书名、章节数、总字数
- **ChapterRange**: 章节范围数据类，指定下载的起始和结束章节号
- **InputClassifier**: 输入分类器，判断用户输入是 URL、书籍 ID 还是本地文件路径

## 需求

### 需求 1：输入类型识别

**用户故事：** 作为用户，我希望管线能自动识别我的输入是 URL、书籍 ID 还是本地文件路径，这样我不需要手动指定输入类型。

#### 验收标准

1.1. WHEN 用户输入以 `http://` 或 `https://` 开头时，THE InputClassifier SHALL 将其分类为 `"url"` 类型

1.2. WHEN 用户输入为纯数字字符串时，THE InputClassifier SHALL 将其分类为 `"book_id"` 类型

1.3. WHEN 用户输入不满足 URL 或纯数字条件时，THE InputClassifier SHALL 将其分类为 `"file"` 类型

1.4. THE InputClassifier SHALL 对任意非空字符串恰好返回 `"url"`、`"book_id"`、`"file"` 三者之一


### 需求 2：平台路由

**用户故事：** 作为用户，我希望系统能根据 URL 自动识别小说所属平台并选择正确的下载器，这样我只需提供链接即可下载。

#### 验收标准

2.1. WHEN 用户输入匹配番茄小说 URL 模式（如 `fanqienovel.com/page/{id}` 或 `changdunovel.com/page/{id}`）时，THE PlatformRouter SHALL 返回 `downloader_type` 为 `"fanqie"` 的 PlatformInfo

2.2. WHEN 用户输入匹配起点中文网 URL 模式（如 `book.qidian.com/info/{id}`）时，THE PlatformRouter SHALL 返回 `downloader_type` 为 `"novel-downloader"` 的 PlatformInfo

2.3. WHEN 用户输入匹配笔趣阁 URL 模式时，THE PlatformRouter SHALL 返回 `downloader_type` 为 `"novel-downloader"` 的 PlatformInfo

2.4. WHEN 用户输入为纯数字书籍 ID 时，THE PlatformRouter SHALL 默认将其路由到番茄小说平台

2.5. WHEN 用户输入的 URL 不匹配任何已知平台模式时，THE PlatformRouter SHALL 抛出 `UnsupportedPlatformError` 并提示支持的平台列表

2.6. THE PlatformRouter SHALL 从 URL 中正确提取书籍 ID 并存入 `PlatformInfo.book_id`

### 需求 3：小说下载

**用户故事：** 作为用户，我希望系统能自动下载指定小说并保存为 TXT 文件到 `input/` 目录，这样我可以直接进入后续管线处理。

#### 验收标准

3.1. WHEN 下载成功时，THE BaseDownloader SHALL 在指定 `output_dir` 中生成一个非空的 UTF-8 编码 `.txt` 文件

3.2. WHEN 下载成功时，THE BaseDownloader SHALL 返回包含 `output_path`、`title`、`chapter_count`、`total_chars` 的 DownloadResult 对象

3.3. WHEN 指定了 ChapterRange 时，THE BaseDownloader SHALL 仅下载指定范围内的章节，且下载章节数不超过 `end - start + 1`

3.4. WHEN ChapterRange 的 `end` 超过实际章节数时，THE BaseDownloader SHALL 下载到最后一章为止并在日志中提示实际下载范围

3.5. WHEN ChapterRange 的 `start` 和 `end` 均为 None 时，THE BaseDownloader SHALL 下载全部章节

3.6. WHEN `validate_source()` 返回 False 时，THE BaseDownloader SHALL 在下载前终止并抛出明确错误信息

### 需求 4：章节范围解析

**用户故事：** 作为用户，我希望通过 `--chapters` 参数指定下载的章节范围（如 `1-10`、`5-`、`-20`），这样我可以只下载需要的部分。

#### 验收标准

4.1. WHEN 用户输入格式为 `"start-end"`（如 `"1-10"`）时，THE Pipeline SHALL 解析为 `ChapterRange(start=1, end=10)`

4.2. WHEN 用户输入格式为 `"start-"`（如 `"5-"`）时，THE Pipeline SHALL 解析为 `ChapterRange(start=5, end=None)`

4.3. WHEN 用户输入格式为 `"-end"`（如 `"-20"`）时，THE Pipeline SHALL 解析为 `ChapterRange(start=None, end=20)`

4.4. WHEN 用户未提供 `--chapters` 参数时，THE Pipeline SHALL 使用 `None` 表示下载全部章节

### 需求 5：管线集成

**用户故事：** 作为用户，我希望下载功能无缝集成到现有管线中，这样我可以用一条命令完成从下载到视频生成的全流程。

#### 验收标准

5.1. WHEN 输入为 URL 或书籍 ID 且未指定 `--skip-download` 时，THE Pipeline SHALL 执行阶段 0（小说下载）后自动将下载文件路径传递给阶段 1

5.2. WHEN 输入为本地文件路径时，THE Pipeline SHALL 跳过阶段 0 直接进入阶段 1，行为与修改前完全一致

5.3. WHEN 用户指定 `--skip-download` 时，THE Pipeline SHALL 跳过阶段 0 即使输入为 URL

5.4. THE Pipeline SHALL 在 `run.py` 中新增 `--chapters` 和 `--skip-download` 命令行参数

5.5. WHEN 阶段 0 下载失败时，THE Pipeline SHALL 终止执行且不进入阶段 1-6，并输出明确的错误信息

### 需求 6：配置管理

**用户故事：** 作为用户，我希望通过 `pipeline.yaml` 配置下载相关参数（超时、重试、输出目录等），这样我可以灵活调整下载行为。

#### 验收标准

6.1. THE Pipeline SHALL 在 `pipeline.yaml` 中新增 `download` 配置段，包含 `enabled`、`output_dir`、`output_format`、`chapter_range`、`timeout`、`retry` 字段

6.2. WHEN `download.enabled` 设为 `false` 时，THE Pipeline SHALL 跳过阶段 0

6.3. WHEN 命令行指定了 `--chapters` 参数时，THE Pipeline SHALL 优先使用命令行参数覆盖 `pipeline.yaml` 中的 `chapter_range` 配置

### 需求 7：错误处理

**用户故事：** 作为用户，我希望下载过程中的错误能被清晰地报告，这样我可以快速定位和解决问题。

#### 验收标准

7.1. IF 下载器依赖（`novel-downloader` 或 `fanqienovel-downloader`）未安装，THEN THE Pipeline SHALL 捕获 `ImportError` 并提示用户安装对应依赖的具体命令

7.2. IF 下载过程超过配置的 `timeout` 秒数，THEN THE Pipeline SHALL 按 `retry` 次数重试，全部失败后终止并输出超时日志

7.3. IF 书籍不存在或已下架，THEN THE Pipeline SHALL 在下载前终止并提示书籍 ID/URL 无效

### 需求 8：下载脚本文件

**用户故事：** 作为开发者，我希望下载逻辑封装在独立的脚本文件 `scripts/00_download_novel.py` 中，这样与现有管线脚本的命名和组织方式保持一致。

#### 验收标准

8.1. THE Pipeline SHALL 将下载逻辑实现在 `scripts/00_download_novel.py` 文件中

8.2. THE `scripts/00_download_novel.py` SHALL 导出 `download_novel()` 函数作为阶段 0 的入口

8.3. THE `scripts/00_download_novel.py` SHALL 包含 PlatformRouter、BaseDownloader、NovelDownloaderAdapter、FanqieDownloaderAdapter 的完整实现
