"""
角色自动检测

从 storyboard.json 中检测未在 characters.yaml 中定义的角色，
输出警告并生成建议配置。
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def detect_new_characters(
    storyboard_path: Path,
    characters_config: Dict,
) -> List[str]:
    """
    从 storyboard 中检测未在 characters.yaml 中定义的角色名。

    Args:
        storyboard_path: storyboard.json 路径
        characters_config: 已加载的 characters.yaml 内容

    Returns:
        未配置的角色名列表（去重、排序）
    """
    with open(storyboard_path, "r", encoding="utf-8") as f:
        storyboard = json.load(f)

    known = set(characters_config.keys())
    unknown = set()

    for scene in storyboard["scenes"]:
        speaker = scene.get("speaker", "")
        if speaker and speaker != "narrator" and speaker not in known:
            unknown.add(speaker)

    return sorted(unknown)


def suggest_voice_type(name: str, storyboard: Dict = None) -> str:
    """
    根据角色名推荐 voice_type。

    简单启发式：
    - 如果名字包含"女"/"姐"/"妈"/"娘" → 女声
    - 否则 → 男声
    """
    female_keywords = ["女", "姐", "妈", "娘", "婆", "姑", "嫂", "甜", "美", "丽", "花"]
    if any(kw in name for kw in female_keywords):
        return "BV104_streaming"  # 女声
    return "BV123_streaming"  # 男声


def suggest_gender(name: str) -> str:
    """根据角色名推测性别"""
    female_keywords = ["女", "姐", "妈", "娘", "婆", "姑", "嫂", "甜", "美", "丽", "花"]
    male_keywords = ["男", "哥", "爸", "爷", "叔", "伯", "兄", "弟", "强", "壮", "虎"]

    if any(kw in name for kw in female_keywords):
        return "female"
    elif any(kw in name for kw in male_keywords):
        return "male"
    return "unknown"


def generate_yaml_suggestion(
    new_characters: List[str],
    storyboard: Dict = None,
) -> str:
    """
    为未配置的角色生成 YAML 配置建议文本，
    用户可直接复制到 characters.yaml。
    """
    lines = ["# === 以下为自动检测到的新角色，请补充 appearance 后粘贴到 characters.yaml ==="]

    for name in new_characters:
        voice = suggest_voice_type(name, storyboard)
        gender = suggest_gender(name)

        lines.append("")
        lines.append(f"{name}:")
        lines.append(f'  voice_type: "{voice}"')
        lines.append(f'  description: "待补充 - {gender}"')
        lines.append(f'  appearance: "TODO: add English appearance description"')
        lines.append(f'  appearance_cn: "待补充 - 请用中文描述角色外貌"')
        if gender != "unknown":
            lines.append(f'  gender: "{gender}"')
        lines.append(f"  emotion_map:")
        lines.append(f"    default:")
        lines.append(f'      rate: "1.5"')
        lines.append(f'      pitch: "0"')

    return "\n".join(lines)


def check_and_warn_characters(
    storyboard_path: Path,
    characters_config: Dict,
    logger_inst: logging.Logger = None,
) -> Tuple[List[str], str]:
    """
    检查角色并输出警告。

    Args:
        storyboard_path: storyboard.json 路径
        characters_config: 已加载的角色配置
        logger_inst: 可选的 logger 实例

    Returns:
        (新角色列表, 建议的YAML配置)
    """
    log = logger_inst or logger

    new_chars = detect_new_characters(storyboard_path, characters_config)

    if not new_chars:
        return [], ""

    log.warning(f"⚠ 检测到 {len(new_chars)} 个未配置的角色: {new_chars}")
    log.warning("  这些角色将使用 narrator 语音和无外观描述")
    log.warning("  建议在 config/characters.yaml 中添加配置后重新运行")

    # 生成建议配置
    with open(storyboard_path, "r", encoding="utf-8") as f:
        sb = json.load(f)
    suggestion = generate_yaml_suggestion(new_chars, sb)

    log.info(f"建议配置:\n{suggestion}")

    return new_chars, suggestion


if __name__ == "__main__":
    import sys
    import argparse
    from scripts.config_manager import ConfigManager

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="检测 storyboard 中的新角色")
    parser.add_argument("storyboard", type=Path, help="storyboard.json 路径")
    parser.add_argument("--output", "-o", type=Path, default=None, help="输出建议配置到文件")
    args = parser.parse_args()

    cfg = ConfigManager()
    new_chars, suggestion = check_and_warn_characters(args.storyboard, cfg.characters)

    if args.output and new_chars:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(suggestion)
        logger.info(f"建议配置已保存到: {args.output}")

    sys.exit(1 if new_chars else 0)
