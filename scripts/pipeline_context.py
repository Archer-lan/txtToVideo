"""
管线上下文

管理单次管线运行的所有状态：章节信息、路径映射、配置、步骤完成状态。
支持状态持久化和从状态文件恢复，以实现断点续跑。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from scripts.config_manager import ConfigManager

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class StepStatus:
    """步骤状态"""

    completed: bool = False
    artifacts: list[str] = field(default_factory=list)


class PipelineContext:
    """管线上下文

    管理单次管线运行的所有状态：章节信息、路径映射、配置、步骤完成状态。
    """

    def __init__(
        self,
        chapter_name: str,
        config_manager: ConfigManager,
        workspace_root: Path | None = None,
    ):
        """
        Args:
            chapter_name: 章节名称（用于创建工作区目录）
            config_manager: 配置管理器实例
            workspace_root: 工作区根目录，默认从 pipeline.yaml 读取或使用 "workspace"
        """
        self.chapter_name = chapter_name
        self.config = config_manager
        self._safe_name = self._sanitize_dirname(chapter_name)

        # 工作区根目录
        ws_config = config_manager.pipeline.get("workspace", {})
        self._workspace_root = workspace_root or PROJECT_ROOT / Path(
            ws_config.get("root", "workspace")
        )

        # 章节工作区路径
        self._chapter_dir = self._workspace_root / self._safe_name

        # 步骤状态
        self._steps: dict[str, StepStatus] = {}

        # 创建目录结构
        self._ensure_directories()

    # --- 路径访问接口 ---

    @property
    def chapter_dir(self) -> Path:
        """章节工作区根目录"""
        return self._chapter_dir

    @property
    def storyboard_path(self) -> Path:
        return self._chapter_dir / "storyboard.json"

    @property
    def audio_dir(self) -> Path:
        return self._chapter_dir / "audio"

    @property
    def images_dir(self) -> Path:
        return self._chapter_dir / "images"

    @property
    def video_dir(self) -> Path:
        return self._chapter_dir / "video"

    @property
    def subtitles_dir(self) -> Path:
        return self._chapter_dir / "subtitles"

    @property
    def output_dir(self) -> Path:
        return self._chapter_dir / "output"

    @property
    def state_file(self) -> Path:
        return self._chapter_dir / "pipeline_state.json"

    # --- 步骤状态管理 ---

    def mark_step_complete(self, step_name: str, artifacts: list[Path]):
        """标记步骤完成并记录产物路径"""
        self._steps[step_name] = StepStatus(
            completed=True,
            artifacts=[str(p) for p in artifacts],
        )
        self.save_state()

    def is_step_complete(self, step_name: str) -> bool:
        """检查步骤是否已完成"""
        status = self._steps.get(step_name)
        return status is not None and status.completed

    # --- 状态持久化 ---

    def save_state(self):
        """将当前状态序列化为 JSON 保存到章节工作区"""
        state = {
            "chapter_name": self.chapter_name,
            "safe_name": self._safe_name,
            "steps": {
                name: {"completed": s.completed, "artifacts": s.artifacts}
                for name, s in self._steps.items()
            },
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    @classmethod
    def restore(
        cls, chapter_dir: Path, config_manager: ConfigManager
    ) -> PipelineContext:
        """从状态文件恢复上下文，验证已完成步骤的产物是否存在"""
        state_file = chapter_dir / "pipeline_state.json"
        if not state_file.exists():
            raise FileNotFoundError(f"状态文件不存在: {state_file}")

        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)

        ctx = cls(
            chapter_name=state["chapter_name"],
            config_manager=config_manager,
            workspace_root=chapter_dir.parent,
        )

        # 恢复步骤状态，验证产物存在性
        for name, step_data in state.get("steps", {}).items():
            if step_data["completed"]:
                missing = [
                    p for p in step_data["artifacts"] if not Path(p).exists()
                ]
                if missing:
                    logger.warning(
                        "步骤 '%s' 标记为完成但产物缺失: %s，重置为未完成",
                        name,
                        missing,
                    )
                    ctx._steps[name] = StepStatus(
                        completed=False, artifacts=[]
                    )
                    continue
            ctx._steps[name] = StepStatus(
                completed=step_data["completed"],
                artifacts=step_data["artifacts"],
            )

        return ctx

    # --- 内部方法 ---

    @staticmethod
    def _sanitize_dirname(name: str) -> str:
        """安全转换目录名：保留中文和字母数字，替换不安全字符为下划线"""
        # 替换文件系统不允许的字符: / \ : * ? " < > | 以及空白字符
        safe = re.sub(r'[\\/:*?"<>|\s]+', "_", name)
        # 去除首尾下划线
        safe = safe.strip("_")
        return safe or "unnamed"

    def _ensure_directories(self):
        """创建章节工作区目录结构"""
        for d in [
            self._chapter_dir,
            self.audio_dir,
            self.images_dir,
            self.video_dir,
            self.subtitles_dir,
            self.output_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)
