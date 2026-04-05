#!/usr/bin/env python3
"""
AutoNovel2Video - 一键执行管线

用法:
    python run.py input/chapter01.txt
    python run.py input/chapter01.txt --output output/chapter01.mp4
    python run.py input/chapter01.txt --skip-images  # 跳过图片生成（使用已有图片）
    python run.py input/chapter01.txt --whisper       # 使用 Whisper 生成字幕
    python run.py "https://fanqienovel.com/page/123456" --chapters 1-10  # 从番茄小说下载
    python run.py 7143038691944959011  # 通过书籍 ID 下载（默认番茄小说）
    python run.py input/chapter01.txt --resume workspace/chapter01  # 从断点恢复
    python run.py input/chapter01.txt --keep-artifacts  # 保留中间产物
    python run.py --migrate chapter01  # 迁移旧 assets/ 产物到章节工作区
"""

import argparse
import asyncio
import importlib.util
import logging
import sys
import time
import traceback
from pathlib import Path

from scripts.cleanup import ArtifactCleaner
from scripts.config_manager import ConfigManager
from scripts.migrate import migrate_assets_to_workspace
from scripts.pipeline_context import PipelineContext

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent


def load_script(script_name):
    """动态导入 scripts/ 下的模块（文件名含数字前缀）"""
    script_path = PROJECT_ROOT / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(script_name.replace(".py", ""), script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def setup_logging(log_file=None):
    """配置日志"""
    handlers = [logging.StreamHandler(sys.stdout)]

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=handlers,
    )


def run_step(step_name, func, *args, max_retries=2, **kwargs):
    """
    执行一个管线步骤，支持失败重试

    Args:
        step_name: 步骤名称（用于日志）
        func: 要执行的函数
        max_retries: 最大重试次数
    """
    logger = logging.getLogger("pipeline")

    for attempt in range(max_retries + 1):
        try:
            logger.info(f"{'='*60}")
            logger.info(f"▶ 开始: {step_name}" + (f" (重试 {attempt})" if attempt > 0 else ""))
            logger.info(f"{'='*60}")

            start = time.time()
            result = func(*args, **kwargs)
            elapsed = time.time() - start

            logger.info(f"✓ 完成: {step_name} ({elapsed:.1f}s)")
            return result

        except Exception as e:
            logger.error(f"✗ 失败: {step_name} - {e}")
            if attempt < max_retries:
                logger.info(f"  等待 3 秒后重试...")
                time.sleep(3)
            else:
                logger.error(f"  已达到最大重试次数 ({max_retries})")
                logger.error(traceback.format_exc())
                raise


def main():
    # Windows 上 ProactorEventLoop 与部分异步库不兼容，切换到 SelectorEventLoop
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    parser = argparse.ArgumentParser(
        description="AutoNovel2Video: 小说 → 有声 → 动画视频（一键生成）",
    )
    parser.add_argument(
        "input",
        type=str,
        nargs="?",
        default=None,
        help="输入的小说文本文件路径 (.txt / .md) / URL / 书籍ID",
    )
    parser.add_argument(
        "--chapters",
        type=str,
        default=None,
        help="章节范围，如 1-10, 5-, -20（仅下载模式有效）",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="跳过下载阶段（即使输入为 URL）",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="输出视频路径 (默认: output/<输入文件名>.mp4)",
    )
    parser.add_argument(
        "--skip-parse",
        action="store_true",
        help="跳过文本解析（使用已有 storyboard.json）",
    )
    parser.add_argument(
        "--skip-audio",
        action="store_true",
        help="跳过音频生成（使用已有音频）",
    )
    parser.add_argument(
        "--skip-images",
        action="store_true",
        help="跳过图片生成（使用已有图片）",
    )
    parser.add_argument(
        "--skip-animate",
        action="store_true",
        help="跳过动画生成（使用已有视频片段）",
    )
    parser.add_argument(
        "--whisper",
        action="store_true",
        help="使用 Whisper 生成字幕（默认使用 storyboard 方案）",
    )
    parser.add_argument(
        "--no-subtitle",
        action="store_true",
        help="不生成字幕",
    )
    parser.add_argument(
        "--resume",
        type=str,
        default=None,
        metavar="CHAPTER_DIR",
        help="从章节工作区状态文件恢复，跳过已完成步骤",
    )
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="跳过清理步骤，保留所有中间产物",
    )
    parser.add_argument(
        "--migrate",
        type=str,
        default=None,
        metavar="CHAPTER_NAME",
        help="将 assets/ 目录下的旧产物迁移到指定章节工作区",
    )

    args = parser.parse_args()

    # 加载配置
    cfg = ConfigManager()
    config = cfg.pipeline

    # --migrate: 迁移旧产物并退出
    if args.migrate:
        ws_config = config.get("workspace", {})
        workspace_root = PROJECT_ROOT / Path(ws_config.get("root", "workspace"))
        assets_dir = PROJECT_ROOT / "assets"
        chapter_dir = migrate_assets_to_workspace(
            chapter_name=args.migrate,
            assets_dir=assets_dir,
            workspace_root=workspace_root,
        )
        print(f"迁移完成! 章节工作区: {chapter_dir}")
        sys.exit(0)

    download_config = config.get("download", {})

    # input 参数在非 --migrate 模式下必须提供
    if args.input is None:
        parser.error("请提供输入文件路径、URL 或书籍ID")

    # 判断输入类型（内联判断，避免提前加载 00_download_novel.py 导致 requests 库干扰 httpx）
    _input = args.input.strip()
    if _input.startswith("http://") or _input.startswith("https://"):
        input_type = "url"
    elif _input.isdigit():
        input_type = "book_id"
    else:
        input_type = "file"

    download_enabled = download_config.get("enabled", True)

    if input_type in ("url", "book_id") and not args.skip_download and download_enabled:
        # 阶段 0: 下载小说（此时才加载下载模块）
        mod_helpers = load_script("00_download_novel.py")
        chapter_range_str = args.chapters
        # 命令行 --chapters 优先，否则用配置文件中的
        if chapter_range_str is None:
            cr_config = download_config.get("chapter_range", {})
            if cr_config and (cr_config.get("start") or cr_config.get("end")):
                s = cr_config.get("start", "")
                e = cr_config.get("end", "")
                chapter_range_str = f"{s or ''}-{e or ''}"

        chapter_range = mod_helpers.parse_chapter_range(chapter_range_str)

        result = run_step(
            "阶段 0: 小说下载",
            mod_helpers.download_novel,
            args.input,
            PROJECT_ROOT / download_config.get("output_dir", "input"),
            download_config,
            chapter_range,
        )
        input_path = result.output_path
    else:
        # 本地文件模式
        input_path = Path(args.input).resolve()
        if not input_path.exists():
            print(f"错误: 输入文件不存在: {input_path}")
            sys.exit(1)

    # 创建 PipelineContext（在 input_path 确定之后）
    if args.resume:
        # --resume: 从状态文件恢复上下文
        chapter_dir = Path(args.resume).resolve()
        ctx = PipelineContext.restore(chapter_dir, cfg)
    else:
        chapter_name = input_path.stem
        ctx = PipelineContext(chapter_name=chapter_name, config_manager=cfg)

    # 确定输出路径
    if args.output:
        output_path = Path(args.output).resolve()
    else:
        output_path = ctx.output_dir / f"{input_path.stem}.mp4"

    # 设置日志
    log_file = ctx.output_dir / "pipeline.log"
    setup_logging(log_file)

    logger = logging.getLogger("pipeline")
    logger.info(f"AutoNovel2Video Pipeline 启动")
    logger.info(f"输入: {input_path}")
    logger.info(f"输出: {output_path}")
    logger.info(f"章节工作区: {ctx.chapter_dir}")

    pipeline_start = time.time()

    # 中间产物路径（从 PipelineContext 获取）
    storyboard_path = ctx.storyboard_path
    audio_dir = ctx.audio_dir
    image_dir = ctx.images_dir
    video_dir = ctx.video_dir
    composed_video = ctx.video_dir / "composed_no_sub.mp4"

    # ========== 阶段 1: 文本 → 分镜脚本 ==========
    if args.resume and ctx.is_step_complete("parse"):
        logger.info("跳过阶段 1 (已完成 --resume)")
    elif not args.skip_parse:
        mod = load_script("01_parse_story.py")
        run_step(
            "阶段 1: 小说 → 分镜脚本",
            mod.parse_story,
            input_path,
            storyboard_path,
        )
        ctx.mark_step_complete("parse", [storyboard_path])
    else:
        logger.info("跳过阶段 1 (--skip-parse)")

    # ========== 阶段 2: 分镜 → 音频 ==========
    if args.resume and ctx.is_step_complete("audio"):
        logger.info("跳过阶段 2 (已完成 --resume)")
    elif not args.skip_audio:
        mod = load_script("02_generate_audio.py")
        run_step(
            "阶段 2: 分镜 → 有声朗读",
            mod.generate_all_audio,
            storyboard_path,
            audio_dir,
        )
        audio_artifacts = list(audio_dir.glob("*.wav"))
        ctx.mark_step_complete("audio", audio_artifacts)
    else:
        logger.info("跳过阶段 2 (--skip-audio)")

    # ========== 阶段 3: 分镜 → 图片 ==========
    if args.resume and ctx.is_step_complete("images"):
        logger.info("跳过阶段 3 (已完成 --resume)")
    elif not args.skip_images:
        mod = load_script("03_generate_images.py")
        run_step(
            "阶段 3: 分镜 → 关键画面",
            mod.generate_all_images,
            storyboard_path,
            image_dir,
        )
        image_artifacts = list(image_dir.glob("*.png"))
        ctx.mark_step_complete("images", image_artifacts)
    else:
        logger.info("跳过阶段 3 (--skip-images)")

    # ========== 阶段 4: 图片 → 动画 ==========
    if args.resume and ctx.is_step_complete("animate"):
        logger.info("跳过阶段 4 (已完成 --resume)")
    elif not args.skip_animate:
        mod = load_script("04_animate_images.py")
        run_step(
            "阶段 4: 图片 → 动画",
            mod.animate_all_images,
            storyboard_path,
            audio_dir,
            image_dir,
            video_dir,
        )
        animate_artifacts = list(video_dir.glob("scene_*.mp4"))
        ctx.mark_step_complete("animate", animate_artifacts)
    else:
        logger.info("跳过阶段 4 (--skip-animate)")

    # ========== 阶段 5: 音画合成 ==========
    if args.resume and ctx.is_step_complete("compose"):
        logger.info("跳过阶段 5 (已完成 --resume)")
    else:
        mod = load_script("05_compose_video.py")
        run_step(
            "阶段 5: 音画合成",
            mod.compose_video,
            storyboard_path,
            audio_dir,
            video_dir,
            composed_video,
        )
        ctx.mark_step_complete("compose", [composed_video])

    # ========== 阶段 6: 字幕生成 & 烧录 ==========
    if args.no_subtitle:
        logger.info("跳过阶段 6 (用户选择不生成字幕)")
    elif args.resume and ctx.is_step_complete("subtitles"):
        logger.info("跳过阶段 6 (已完成 --resume)")
    else:
        mod = load_script("06_generate_subtitles.py")
        run_step(
            "阶段 6: 字幕生成 & 烧录",
            mod.generate_subtitles,
            storyboard_path,
            audio_dir,
            composed_video,
            output_path,
            args.whisper,
        )
        ctx.mark_step_complete("subtitles", [output_path])

    # ========== 清理中间产物 ==========
    if not args.keep_artifacts:
        cleaner = ArtifactCleaner(ctx)
        cleaner.clean()

    # 完成
    total_time = time.time() - pipeline_start
    logger.info(f"{'='*60}")
    logger.info(f"Pipeline 完成!")
    logger.info(f"输出视频: {output_path}")
    logger.info(f"总耗时: {total_time:.1f}s")
    logger.info(f"{'='*60}")

    print(f"\n完成! 视频已输出到: {output_path}")


if __name__ == "__main__":
    main()
