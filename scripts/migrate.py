"""
旧产物目录迁移工具

将旧 assets/ 目录下的产物迁移到章节工作区，
使用 shutil.move 实现移动语义，避免磁盘空间翻倍。
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from scripts.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 迁移映射：(assets 下的 glob 模式, 章节工作区下的目标子目录, 是否为单文件)
_MIGRATION_MAP: list[tuple[str, str, bool]] = [
    ("storyboard.json", ".", True),
    ("audio/*.wav", "audio", False),
    ("images/*.png", "images", False),
    ("video/*.mp4", "video", False),
    ("subtitles/*.srt", "subtitles", False),
]


def _safe_move(src: Path, dst: Path) -> None:
    """移动文件，跨设备时降级为复制+删除。"""
    try:
        shutil.move(str(src), str(dst))
    except OSError:
        logger.info("跨设备移动失败，降级为复制+删除: %s -> %s", src, dst)
        shutil.copy2(str(src), str(dst))
        os.remove(src)


def migrate_assets_to_workspace(
    chapter_name: str,
    assets_dir: Path,
    workspace_root: Path,
) -> Path:
    """将旧 assets/ 目录下的产物迁移到章节工作区

    使用 shutil.move 而非 copy，避免磁盘空间翻倍。
    目标文件已存在时跳过并记录警告。

    Args:
        chapter_name: 目标章节名
        assets_dir: 旧产物目录（如 PROJECT_ROOT / "assets"）
        workspace_root: 工作区根目录

    Returns:
        新章节工作区路径
    """
    if not assets_dir.exists():
        logger.info("assets 目录不存在，跳过迁移: %s", assets_dir)
        safe_name = PipelineContext._sanitize_dirname(chapter_name)
        return workspace_root / safe_name

    safe_name = PipelineContext._sanitize_dirname(chapter_name)
    chapter_dir = workspace_root / safe_name

    # 创建目标目录结构
    for subdir in ("audio", "images", "video", "subtitles", "output"):
        (chapter_dir / subdir).mkdir(parents=True, exist_ok=True)
    chapter_dir.mkdir(parents=True, exist_ok=True)

    for pattern, target_subdir, is_single in _MIGRATION_MAP:
        matched = list(assets_dir.glob(pattern))
        if not matched:
            continue

        if is_single:
            dst_dir = chapter_dir
        else:
            dst_dir = chapter_dir / target_subdir
            dst_dir.mkdir(parents=True, exist_ok=True)

        for src_file in matched:
            dst_file = dst_dir / src_file.name
            if dst_file.exists():
                logger.warning("目标文件已存在，跳过: %s", dst_file)
                continue
            logger.info("迁移: %s -> %s", src_file, dst_file)
            _safe_move(src_file, dst_file)

    return chapter_dir
