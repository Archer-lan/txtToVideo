# 任务列表

## 任务 1: 创建数据模型和基础类

- [x] 1.1 在 `scripts/00_download_novel.py` 中创建数据模型：`PlatformInfo`、`DownloadResult`、`ChapterRange` dataclass，以及 `UnsupportedPlatformError` 异常类
- [x] 1.2 创建 `BaseDownloader` 抽象基类，定义 `download()` 和 `validate_source()` 抽象方法
- [x] 1.3 实现 `is_url_or_file(input_str: str) -> str` 函数，根据输入字符串返回 `"url"`、`"book_id"` 或 `"file"`
- [x] 1.4 实现 `parse_chapter_range(chapters_str: str | None) -> ChapterRange | None` 函数，解析 `"1-10"`、`"5-"`、`"-20"`、`None` 等格式

## 任务 2: 实现平台路由器

- [x] 2.1 在 `scripts/00_download_novel.py` 中实现 `PlatformRouter` 类，包含 `PLATFORM_PATTERNS` 和 `DOWNLOADER_MAP` 配置
- [x] 2.2 实现 `detect_platform(source: str) -> PlatformInfo` 方法，支持番茄小说、起点中文网、笔趣阁 URL 模式匹配和纯数字 ID 默认路由
- [x] 2.3 实现 `get_downloader(platform_info: PlatformInfo) -> BaseDownloader` 方法，根据 `downloader_type` 返回对应适配器实例

## 任务 3: 实现下载器适配器

- [x] 3.1 实现 `NovelDownloaderAdapter(BaseDownloader)`，封装 `novel-downloader` 库的 Python API，实现 `download()` 和 `validate_source()` 方法
- [x] 3.2 实现 `FanqieDownloaderAdapter(BaseDownloader)`，封装 `fanqienovel-downloader` 的调用逻辑，实现 `download()` 和 `validate_source()` 方法
- [x] 3.3 在两个适配器中添加 `ImportError` 捕获逻辑，当依赖未安装时提示用户安装命令

## 任务 4: 实现阶段 0 入口函数

- [x] 4.1 在 `scripts/00_download_novel.py` 中实现 `download_novel(source, output_dir, config, chapter_range)` 入口函数，编排路由→验证→下载→校验流程
- [x] 4.2 添加下载超时和重试逻辑，读取 `config` 中的 `timeout` 和 `retry` 配置

## 任务 5: 集成到管线

- [x] 5.1 修改 `run.py`，新增 `--chapters` 和 `--skip-download` 命令行参数
- [x] 5.2 在 `run.py` 的 `main()` 中添加输入类型判断逻辑：URL/书籍ID 触发阶段 0，本地文件直接进入阶段 1
- [x] 5.3 在 `run.py` 中通过 `load_script("00_download_novel.py")` 和 `run_step()` 调用阶段 0

## 任务 6: 更新配置文件

- [x] 6.1 在 `config/pipeline.yaml` 中新增 `download` 配置段，包含 `enabled`、`output_dir`、`output_format`、`chapter_range`、`timeout`、`retry`、`fanqie` 子段
- [x] 6.2 在 `requirements.txt` 中添加 `novel-downloader` 和 `fanqienovel-downloader` 依赖

## 任务 7: 编写测试

- [x] 7.1 创建 `tests/test_novel_download.py`，编写 `is_url_or_file()` 的 property-based 测试（hypothesis）：任意非空字符串返回三者之一，URL 前缀返回 "url"，纯数字返回 "book_id"
- [x] 7.2 编写 `detect_platform()` 的 property-based 测试：已知模式 URL 返回正确平台和 book_id，未知 URL 抛出 UnsupportedPlatformError
- [x] 7.3 编写 `parse_chapter_range()` 的 property-based 测试：随机正整数对格式化后解析结果一致
- [x] 7.4 编写单元测试：mock 下载器测试 `download_novel()` 流程编排、错误处理、向后兼容性
