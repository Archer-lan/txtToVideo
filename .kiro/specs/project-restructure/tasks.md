# 实施计划：项目结构重构与章节化产物管理

## 概述

按照渐进式重构策略，先构建核心模块（ConfigManager、PipelineContext、Cleanup），再扩展配置文件，然后重构 run.py 集成所有模块，最后实现迁移工具。每个核心模块实现后紧跟属性测试和单元测试，确保增量验证。

## 任务

- [x] 1. 实现 ConfigManager 统一配置管理器
  - [x] 1.1 创建 `scripts/config_manager.py`，实现 ConfigManager 类
    - 实现 `__init__` 方法，接收可选的 `config_dir` 参数，默认为 `PROJECT_ROOT / "config"`
    - 实现 `pipeline`、`characters`、`styles` 三个 `@property` 懒加载属性
    - 实现 `_load_yaml` 内部方法，处理文件不存在、YAML 格式错误、文件为空三种异常情况
    - 异常消息必须包含完整文件路径
    - _需求: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 1.2 编写属性测试：配置缓存一致性（Property 4）
    - **Property 4: 配置缓存一致性**
    - 在 `tests/test_config_manager.py` 中使用 hypothesis 验证：连续两次访问同一配置属性返回同一对象引用（`is` 相等）
    - **验证需求: 2.2**

  - [ ]* 1.3 编写属性测试：配置加载错误包含路径信息（Property 5）
    - **Property 5: 配置加载错误包含路径信息**
    - 在 `tests/test_config_manager.py` 中使用 hypothesis 的 `st.text()` 生成随机文件路径，验证异常消息包含该路径字符串
    - **验证需求: 2.3**

  - [ ]* 1.4 编写属性测试：配置默认值回退（Property 14）
    - **Property 14: 配置默认值回退**
    - 在 `tests/test_config_manager.py` 中验证：不包含 `workspace` 或 `cleanup` 配置段的 pipeline.yaml，读取时返回预定义默认值而非抛出异常
    - **验证需求: 8.3**

  - [ ]* 1.5 编写 ConfigManager 单元测试
    - 在 `tests/test_config_manager.py` 中编写单元测试
    - 测试正常加载三个配置文件
    - 测试自定义配置目录
    - 测试 pipeline.yaml 新增 workspace 配置段读取
    - 测试 pipeline.yaml 新增 cleanup 配置段读取
    - _需求: 2.1, 2.4, 8.3_

- [x] 2. 实现 PipelineContext 管线上下文
  - [x] 2.1 创建 `scripts/pipeline_context.py`，实现 StepStatus 数据类和 PipelineContext 类
    - 实现 `StepStatus` dataclass，包含 `completed` 和 `artifacts` 字段
    - 实现 `__init__` 方法，接收 `chapter_name`、`config_manager`、可选 `workspace_root`
    - 实现 `_sanitize_dirname` 静态方法：保留中文和字母数字，替换文件系统不安全字符为下划线
    - 实现 `_ensure_directories` 方法：创建章节工作区完整目录结构（audio、images、video、subtitles、output）
    - 实现所有路径属性：`chapter_dir`、`storyboard_path`、`audio_dir`、`images_dir`、`video_dir`、`subtitles_dir`、`output_dir`、`state_file`
    - _需求: 1.1, 1.2, 1.3, 1.4, 3.1_

  - [x] 2.2 实现步骤状态管理和状态持久化
    - 实现 `mark_step_complete(step_name, artifacts)` 方法：标记步骤完成并记录产物路径
    - 实现 `is_step_complete(step_name)` 方法：查询步骤完成状态
    - 实现 `save_state()` 方法：将状态序列化为 JSON 保存到 `pipeline_state.json`
    - 实现 `restore()` 类方法：从状态文件恢复上下文，验证已完成步骤的产物文件存在性，缺失时重置为未完成
    - _需求: 3.2, 3.3, 3.4_

  - [ ]* 2.3 编写属性测试：章节工作区路径正确性（Property 1）
    - **Property 1: 章节工作区路径正确性**
    - 在 `tests/test_pipeline_context.py` 中使用 hypothesis 的 `st.text()` 生成随机章节名，验证所有路径属性都位于 `workspace/{sanitized_name}/` 下且目录已创建
    - **验证需求: 1.1, 1.2**

  - [ ]* 2.4 编写属性测试：目录名安全转换（Property 2）
    - **Property 2: 目录名安全转换**
    - 在 `tests/test_pipeline_context.py` 中使用 hypothesis 生成包含特殊字符的字符串，验证 `_sanitize_dirname` 返回值不包含不安全字符且保留中文和字母数字
    - **验证需求: 1.3**

  - [ ]* 2.5 编写属性测试：上下文创建幂等性（Property 3）
    - **Property 3: 上下文创建幂等性**
    - 在 `tests/test_pipeline_context.py` 中验证：连续两次创建 PipelineContext 不抛异常，目录结构一致
    - **验证需求: 1.4**

  - [ ]* 2.6 编写属性测试：步骤状态记录与查询一致性（Property 6）
    - **Property 6: 步骤状态记录与查询一致性**
    - 在 `tests/test_pipeline_context.py` 中使用 hypothesis 生成随机步骤名和产物路径列表，验证 `mark_step_complete` 后 `is_step_complete` 返回 True
    - **验证需求: 3.2, 4.4**

  - [ ]* 2.7 编写属性测试：管线状态序列化往返（Property 7）
    - **Property 7: 管线状态序列化往返**
    - 在 `tests/test_pipeline_context.py` 中验证：`save_state` 后 `restore` 恢复的上下文包含相同的章节名、步骤状态和产物路径
    - **验证需求: 3.3, 5.3**

  - [ ]* 2.8 编写属性测试：状态恢复时产物存在性验证（Property 8）
    - **Property 8: 状态恢复时产物存在性验证**
    - 在 `tests/test_pipeline_context.py` 中验证：已完成步骤的产物文件不存在时，`restore` 后该步骤被重置为未完成
    - **验证需求: 3.4**

  - [ ]* 2.9 编写属性测试：章节名称从文件名推断（Property 10）
    - **Property 10: 章节名称从文件名推断**
    - 在 `tests/test_pipeline_context.py` 中使用 hypothesis 生成随机文件名，验证推断的章节名等于 `Path(p).stem`
    - **验证需求: 5.1**

  - [ ]* 2.10 编写 PipelineContext 单元测试
    - 在 `tests/test_pipeline_context.py` 中编写单元测试
    - 测试 PipelineContext 恢复（--resume 场景）
    - 测试空字符串章节名返回 "unnamed"
    - 测试中文章节名的目录创建
    - _需求: 1.1, 1.3, 3.3, 3.4_

- [x] 3. 检查点 - 确保核心模块测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 4. 实现 ArtifactCleaner 产物清理模块
  - [x] 4.1 创建 `scripts/cleanup.py`，实现 ArtifactCleaner 类
    - 实现 `__init__` 方法：从 PipelineContext 获取清理配置（enabled、keep_patterns、delete_patterns）
    - 实现 `clean(dry_run)` 方法：根据 delete_patterns 匹配文件并删除，dry_run 模式仅记录不删除
    - 实现 `_should_delete(file_path)` 方法：判断文件是否匹配删除模式且不匹配保留模式
    - 清理前记录将要删除的文件列表到日志
    - 单个文件删除失败时记录警告并继续，不中断清理
    - 最终视频不存在或大小为 0 时跳过清理并记录警告
    - _需求: 6.1, 6.2, 6.3, 6.5, 6.6_

  - [ ]* 4.2 编写属性测试：清理后产物分类正确性（Property 11）
    - **Property 11: 清理后产物分类正确性**
    - 在 `tests/test_cleanup.py` 中随机生成工作区文件结构，验证清理后保留文件存在、删除文件不存在
    - **验证需求: 6.1, 6.2, 6.3**

  - [ ]* 4.3 编写属性测试：清理容错性（Property 12）
    - **Property 12: 清理容错性**
    - 在 `tests/test_cleanup.py` 中模拟文件删除失败，验证清理不抛异常且其他文件正常删除
    - **验证需求: 6.5**

  - [ ]* 4.4 编写 ArtifactCleaner 单元测试
    - 在 `tests/test_cleanup.py` 中编写单元测试
    - 测试 `--keep-artifacts` 跳过清理
    - 测试清理前日志记录文件列表
    - 测试 dry_run 模式不实际删除文件
    - _需求: 6.4, 6.6_

- [x] 5. 实现迁移工具
  - [x] 5.1 创建 `scripts/migrate.py`，实现 `migrate_assets_to_workspace` 函数
    - 接收 `chapter_name`、`assets_dir`、`workspace_root` 参数
    - 按映射关系将 assets/ 下的产物移动到章节工作区对应目录
    - 使用 `shutil.move` 实现移动语义，避免磁盘空间翻倍
    - assets/ 目录不存在时记录提示信息并返回
    - 目标文件已存在时跳过并记录警告
    - 跨设备移动失败时降级为复制+删除
    - _需求: 7.1, 7.2, 7.3, 7.4_

  - [ ]* 5.2 编写属性测试：迁移移动语义（Property 13）
    - **Property 13: 迁移移动语义**
    - 在 `tests/test_migrate.py` 中随机生成 assets 文件结构，验证迁移后文件存在于目标位置且不在原位置
    - **验证需求: 7.2, 7.3**

  - [ ]* 5.3 编写迁移工具单元测试
    - 在 `tests/test_migrate.py` 中编写单元测试
    - 测试旧 assets/ 存在时的迁移提示
    - 测试迁移时目标文件已存在跳过
    - 测试 assets/ 不存在时的处理
    - _需求: 7.1, 7.4_

- [x] 6. 检查点 - 确保所有新模块测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 7. 扩展 pipeline.yaml 配置文件
  - [x] 7.1 在 `config/pipeline.yaml` 中新增 `workspace` 和 `cleanup` 配置段
    - 新增 `workspace` 段：包含 `root`（默认 "workspace"）和 `chapter_name_template`（默认 "{stem}"）
    - 新增 `cleanup` 段：包含 `enabled`（默认 true）、`keep_patterns` 列表和 `delete_patterns` 列表
    - 确保不修改现有配置内容，仅追加新配置段
    - _需求: 8.1, 8.2_

- [x] 8. 重构 run.py 集成所有新模块
  - [x] 8.1 在 run.py 中集成 ConfigManager 和 PipelineContext
    - 导入 ConfigManager、PipelineContext
    - 在管线启动时创建 ConfigManager 实例
    - 从输入文件名推断章节名称（使用 `Path(input).stem`）
    - 创建 PipelineContext 实例，替代原有硬编码路径
    - 将各步骤调用中的路径参数替换为从 PipelineContext 获取
    - _需求: 3.1, 4.1, 4.2, 5.1_

  - [x] 8.2 实现步骤执行后的状态持久化
    - 每个步骤执行完成后调用 `ctx.mark_step_complete()` 记录状态和产物路径
    - 每个步骤完成后调用 `ctx.save_state()` 持久化状态到 JSON 文件
    - _需求: 3.2, 3.3, 5.3_

  - [x] 8.3 新增命令行参数并集成清理和迁移功能
    - 新增 `--resume` 参数：从状态文件恢复 PipelineContext，跳过已完成步骤
    - 新增 `--keep-artifacts` 参数：跳过清理步骤
    - 新增 `--migrate` 参数：调用迁移工具将 assets/ 产物迁移到章节工作区
    - 在管线末尾集成 ArtifactCleaner，根据配置和参数决定是否清理
    - 保持现有 `--skip-*`、`--whisper` 等参数完全向后兼容
    - _需求: 5.2, 5.4, 5.5, 6.4, 7.1, 7.2_

  - [ ]* 8.4 编写属性测试：输入产物缺失时抛出明确错误（Property 9）
    - **Property 9: 输入产物缺失时抛出明确错误**
    - 在 `tests/test_step_validation.py` 中验证：步骤所需输入产物不存在时，抛出包含缺失文件路径的异常
    - **验证需求: 4.3**

  - [ ]* 8.5 编写 run.py 集成测试
    - 在 `tests/test_run.py` 中编写集成测试
    - 测试跳过步骤时产物不存在的警告
    - 测试 `--resume` 恢复流程
    - 测试命令行参数向后兼容性
    - _需求: 5.2, 5.4, 5.5_

- [x] 9. 最终检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请向用户确认。

## 备注

- 标记 `*` 的任务为可选任务，可跳过以加速 MVP 开发
- 每个任务引用了具体的需求编号，确保可追溯性
- 检查点任务用于增量验证，确保每个阶段的正确性
- 属性测试使用 hypothesis 库验证通用正确性属性
- 单元测试验证具体示例和边缘情况
