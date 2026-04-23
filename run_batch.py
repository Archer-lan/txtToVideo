"""
统一批处理入口

替代所有散乱的批处理脚本，支持按范围、列表或全部处理章节。

用法:
    python run_batch.py <input_dir> [选项]

示例:
    python run_batch.py input/十日终焉/ --range 1-10
    python run_batch.py input/十日终焉/ --chapters 5,12,37
    python run_batch.py input/十日终焉/ --all --skip-completed
"""

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent


def setup_logging():
    """配置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler()],
    )


def parse_chapter_number(filename: str) -> Optional[int]:
    """
    从文件名中解析章节号。

    支持格式:
        - "第001章 标题.txt" -> 1
        - "第12章 标题.txt" -> 12
        - "chapter_001.txt" -> 1
    """
    import re

    # 匹配 "第XXX章" 模式
    match = re.search(r"第[0零一二三四五六七八九十百千万]*(\d+)[章回]", filename)
    if match:
        return int(match.group(1))

    # 匹配 "chapter_XXX" 模式
    match = re.search(r"chapter[_-]?(\d+)", filename, re.IGNORECASE)
    if match:
        return int(match.group(1))

    # 匹配纯数字前缀
    match = re.search(r"^(\d+)", filename)
    if match:
        return int(match.group(1))

    return None


def find_chapter_files(
    input_dir: Path,
    chapter_range: Optional[str] = None,
    chapter_list: Optional[str] = None,
) -> List[Tuple[int, Path]]:
    """
    扫描目录，查找章节文件并按章节号排序。

    Args:
        input_dir: 输入目录
        chapter_range: 章节范围，如 "1-10", "5-"
        chapter_list: 章节列表，如 "5,12,37"

    Returns:
        排序后的 (章节号, 文件路径) 列表
    """
    if not input_dir.exists():
        raise FileNotFoundError(f"输入目录不存在: {input_dir}")

    # 查找所有 .txt 文件
    chapter_files = []
    for txt_file in input_dir.glob("*.txt"):
        chapter_num = parse_chapter_number(txt_file.name)
        if chapter_num is not None:
            chapter_files.append((chapter_num, txt_file))

    # 按章节号排序
    chapter_files.sort(key=lambda x: x[0])

    if not chapter_files:
        logger.warning(f"在 {input_dir} 中未找到可识别的章节文件")
        return []

    logger.info(f"找到 {len(chapter_files)} 个章节文件 (章节 {chapter_files[0][0]}-{chapter_files[-1][0]})")

    # 应用范围过滤
    filtered = []

    if chapter_list:
        # 指定章节列表
        selected = set(int(x.strip()) for x in chapter_list.split(","))
        filtered = [(num, path) for num, path in chapter_files if num in selected]
        logger.info(f"选择章节列表: {sorted(selected)}")
    elif chapter_range:
        # 范围过滤
        if "-" in chapter_range:
            start_str, end_str = chapter_range.split("-", 1)
            start = int(start_str) if start_str else None
            end = int(end_str) if end_str else None
        else:
            start = int(chapter_range)
            end = int(chapter_range)

        for num, path in chapter_files:
            if (start is None or num >= start) and (end is None or num <= end):
                filtered.append((num, path))

        range_str = f"{start or '开始'}-{end or '结束'}"
        logger.info(f"选择章节范围: {range_str}")
    else:
        # 默认使用所有章节
        filtered = chapter_files
        logger.info("使用所有章节")

    if not filtered:
        logger.warning("没有符合条件的章节")
    else:
        logger.info(f"将处理 {len(filtered)} 个章节: {[num for num, _ in filtered]}")

    return filtered


def is_chapter_completed(chapter_name: str, workspace_root: Path = None) -> bool:
    """检查章节是否已完成（有输出视频）"""
    workspace_root = workspace_root or (PROJECT_ROOT / "workspace")
    chapter_dir = workspace_root / chapter_name

    if not chapter_dir.exists():
        return False

    # 检查 output 目录下是否有 .mp4 文件
    output_dir = chapter_dir / "output"
    if output_dir.exists():
        for mp4_file in output_dir.glob("*.mp4"):
            return True

    return False


def run_single_chapter(
    chapter_path: Path,
    extra_args: List[str] = None,
    workspace_root: Path = None,
) -> bool:
    """
    运行单个章节的 pipeline。

    Args:
        chapter_path: 章节文件路径
        extra_args: 额外传递给 run.py 的参数
        workspace_root: 工作区根目录

    Returns:
        是否成功
    """
    extra_args = extra_args or []

    cmd = [sys.executable, str(PROJECT_ROOT / "run.py"), str(chapter_path)] + extra_args

    logger.info(f"执行命令: {' '.join(cmd)}")

    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(
        description="批量处理小说章节",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_batch.py input/十日终焉/ --range 1-10
  python run_batch.py input/十日终焉/ --chapters 5,12,37
  python run_batch.py input/十日终焉/ --all --skip-completed
  python run_batch.py input/十日终焉/ --range 11-40 --no-subtitle
        """,
    )

    parser.add_argument("input_dir", type=Path, help="章节文件所在目录")

    # 章节选择选项（互斥）
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--range", "-r", help="章节范围，如 1-10, 11-, -20")
    group.add_argument("--chapters", "-c", help="指定章节列表，如 5,12,37")
    group.add_argument("--all", "-a", action="store_true", help="处理所有章节")

    # 其他选项
    parser.add_argument(
        "--skip-completed",
        "-s",
        action="store_true",
        help="跳过已有输出视频的章节",
    )
    parser.add_argument(
        "--fail-fast",
        "-f",
        action="store_true",
        help="遇到失败立即停止（默认继续下一章）",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="工作区根目录（默认: workspace/）",
    )

    # 透传给 run.py 的选项
    parser.add_argument("--no-subtitle", action="store_true", help="不生成字幕")
    parser.add_argument("--keep-artifacts", action="store_true", help="保留中间产物")
    parser.add_argument("--whisper", action="store_true", help="使用 Whisper 生成字幕")

    args = parser.parse_args()

    setup_logging()

    # 构建透传参数
    extra_args = []
    if args.no_subtitle:
        extra_args.append("--no-subtitle")
    if args.keep_artifacts:
        extra_args.append("--keep-artifacts")
    if args.whisper:
        extra_args.append("--whisper")

    # 确定章节范围
    chapter_range = args.range
    chapter_list = args.chapters
    if args.all:
        chapter_range = None
        chapter_list = None

    # 查找章节文件
    try:
        chapter_files = find_chapter_files(
            args.input_dir,
            chapter_range=chapter_range,
            chapter_list=chapter_list,
        )
    except Exception as e:
        logger.error(f"查找章节文件失败: {e}")
        return 1

    if not chapter_files:
        return 0

    # 逐个执行
    success_count = 0
    failed_chapters = []

    for chapter_num, chapter_path in chapter_files:
        chapter_name = chapter_path.stem

        logger.info(f"\n{'='*60}")
        logger.info(f"章节 {chapter_num}: {chapter_name}")
        logger.info(f"{'='*60}")

        # 检查是否跳过已完成
        if args.skip_completed and is_chapter_completed(chapter_name, args.workspace):
            logger.info(f"跳过已完成章节: {chapter_name}")
            success_count += 1
            continue

        # 运行
        try:
            success = run_single_chapter(
                chapter_path,
                extra_args=extra_args,
                workspace_root=args.workspace,
            )
            if success:
                logger.info(f"✅ 章节 {chapter_num} 完成")
                success_count += 1
            else:
                logger.error(f"❌ 章节 {chapter_num} 失败")
                failed_chapters.append((chapter_num, chapter_name))
                if args.fail_fast:
                    logger.error("遇到失败，停止后续处理")
                    break
        except Exception as e:
            logger.error(f"❌ 章节 {chapter_num} 执行异常: {e}")
            failed_chapters.append((chapter_num, chapter_name))
            if args.fail_fast:
                break

    # 输出总结
    logger.info(f"\n{'='*60}")
    logger.info("批处理完成")
    logger.info(f"{'='*60}")
    logger.info(f"总计: {len(chapter_files)} 章")
    logger.info(f"成功: {success_count} 章")
    if failed_chapters:
        logger.warning(f"失败: {len(failed_chapters)} 章")
        for num, name in failed_chapters:
            logger.warning(f"  - 章节 {num}: {name}")

    return 0 if not failed_chapters else 1


if __name__ == "__main__":
    sys.exit(main())
