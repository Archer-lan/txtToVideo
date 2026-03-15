"""
中间产物清理器

根据清理策略删除章节工作区中的中间产物。
最终视频成功生成后自动清理不需要的中间文件，释放磁盘空间。
"""

from __future__ import annotations

import fnmatch
import logging
from pathlib import Path

from scripts.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)


class ArtifactCleaner:
    """中间产物清理器

    根据清理策略删除章节工作区中的中间产物。
    """

    def __init__(self, context: PipelineContext):
        self.context = context
        cleanup_config = context.config.pipeline.get("cleanup", {})
        self.enabled = cleanup_config.get("enabled", True)
        self.keep_patterns = cleanup_config.get(
            "keep_patterns",
            [
                "output/**",
                "subtitles/*.srt",
                "storyboard.json",
                "pipeline_state.json",
            ],
        )
        self.delete_patterns = cleanup_config.get(
            "delete_patterns",
            [
                "audio/scene_*.wav",
                "images/scene_*.png",
                "video/scene_*.mp4",
                "video/composed_no_sub.mp4",
            ],
        )

    def clean(self, dry_run: bool = False) -> list[Path]:
        """执行清理

        Args:
            dry_run: 仅记录不实际删除

        Returns:
            已删除（或将要删除）的文件列表
        """
        if not self.enabled:
            logger.info("清理功能已禁用，跳过清理")
            return []

        chapter_dir = self.context.chapter_dir
        output_dir = self.context.output_dir

        # 检查最终视频是否存在且大小 > 0
        final_videos = list(output_dir.glob("*.mp4"))
        valid_video = any(v.is_file() and v.stat().st_size > 0 for v in final_videos)
        if not valid_video:
            logger.warning("最终视频不存在或大小为 0，跳过清理")
            return []

        # 收集匹配 delete_patterns 的文件
        candidates: set[Path] = set()
        for pattern in self.delete_patterns:
            matched = list(chapter_dir.glob(pattern))
            for f in matched:
                if f.is_file():
                    candidates.add(f)

        # 过滤掉匹配 keep_patterns 的文件
        to_delete = [f for f in sorted(candidates) if self._should_delete(f)]

        if not to_delete:
            logger.info("没有需要清理的文件")
            return []

        # 清理前记录将要删除的文件列表
        logger.info(
            "将要删除 %d 个文件:%s",
            len(to_delete),
            "".join(f"\n  - {f}" for f in to_delete),
        )

        if dry_run:
            logger.info("dry_run 模式，不实际删除文件")
            return to_delete

        deleted: list[Path] = []
        for f in to_delete:
            try:
                f.unlink()
                deleted.append(f)
            except OSError as e:
                logger.warning("删除文件失败: %s, 错误: %s", f, e)

        logger.info("清理完成，已删除 %d 个文件", len(deleted))
        return deleted

    def _should_delete(self, file_path: Path) -> bool:
        """判断文件是否应被删除：匹配删除模式且不匹配保留模式"""
        chapter_dir = self.context.chapter_dir
        try:
            rel_path = file_path.relative_to(chapter_dir)
        except ValueError:
            return False

        rel_str = str(rel_path).replace("\\", "/")

        # 检查是否匹配保留模式
        for pattern in self.keep_patterns:
            if fnmatch.fnmatch(rel_str, pattern):
                return False

        # 检查是否匹配删除模式
        for pattern in self.delete_patterns:
            if fnmatch.fnmatch(rel_str, pattern):
                return True

        return False
