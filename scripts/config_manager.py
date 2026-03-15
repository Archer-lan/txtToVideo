"""
统一配置管理器

加载并缓存 pipeline.yaml、characters.yaml、styles.yaml，
替代各脚本中重复的 load_config() / load_characters() / load_styles()。
"""

from pathlib import Path

import yaml

# scripts/ 的上一级即项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ConfigManager:
    """统一配置管理器

    加载并缓存 pipeline.yaml、characters.yaml、styles.yaml。
    支持自定义配置目录，默认为 PROJECT_ROOT / "config"。
    """

    def __init__(self, config_dir: Path = None):
        """
        Args:
            config_dir: 配置文件目录路径，默认 PROJECT_ROOT / "config"
        """
        self._config_dir = config_dir or (PROJECT_ROOT / "config")
        self._pipeline: dict | None = None
        self._characters: dict | None = None
        self._styles: dict | None = None

    @property
    def pipeline(self) -> dict:
        """加载并缓存 pipeline.yaml"""
        if self._pipeline is None:
            self._pipeline = self._load_yaml("pipeline.yaml")
        return self._pipeline

    @property
    def characters(self) -> dict:
        """加载并缓存 characters.yaml"""
        if self._characters is None:
            self._characters = self._load_yaml("characters.yaml")
        return self._characters

    @property
    def styles(self) -> dict:
        """加载并缓存 styles.yaml"""
        if self._styles is None:
            self._styles = self._load_yaml("styles.yaml")
        return self._styles

    def _load_yaml(self, filename: str) -> dict:
        """加载 YAML 文件，文件不存在或格式错误时抛出异常"""
        path = self._config_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {path}")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if data is None:
                raise ValueError(f"配置文件为空: {path}")
            return data
        except yaml.YAMLError as e:
            raise ValueError(f"配置文件格式错误: {path}\n{e}") from e
