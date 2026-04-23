"""
阶段 6：字幕生成

使用 Whisper 从合成音频生成 SRT 字幕，
然后烧录到最终视频中。
"""

import json
import os
import sys
import subprocess
import logging
import yaml
from pathlib import Path

from scripts.platform_utils import get_ffmpeg_subtitle_path, FFMPEG, FFPROBE

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent




def get_audio_duration(audio_path):
    """获取音频文件实际时长（秒）"""
    import wave
    try:
        with wave.open(str(audio_path), "rb") as wf:
            return wf.getnframes() / wf.getframerate()
    except Exception:
        pass
    try:
        result = subprocess.run(
            [
                FFPROBE, "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        return None


# 单行字幕最大字符数（超过则按标点切分）
MAX_LINE_CHARS = 20


def split_text_to_lines(text, max_chars=MAX_LINE_CHARS):
    """
    将长句按标点切分为多个短片段，每段不超过 max_chars 个字符。
    切分点优先选标点符号，保证每段都是完整的语义单元。
    返回片段列表。
    """
    import re
    if len(text) <= max_chars:
        return [text]

    # 优先在这些标点后切分
    break_chars = set("，。！？；：、…—,!?;:")
    segments = []
    current = ""

    for ch in text:
        current += ch
        if ch in break_chars and len(current) >= 6:
            segments.append(current)
            current = ""

    if current:
        # 剩余部分：若上一段存在且合并后不超限，则合并
        if segments and len(segments[-1]) + len(current) <= max_chars:
            segments[-1] += current
        else:
            segments.append(current)

    # 二次检查：仍超长的段强制按 max_chars 截断
    result = []
    for seg in segments:
        while len(seg) > max_chars:
            result.append(seg[:max_chars])
            seg = seg[max_chars:]
        if seg:
            result.append(seg)

    return result if result else [text]


def generate_srt_from_storyboard(storyboard_path, audio_dir, output_srt_path):
    """
    方案 A：直接从 storyboard + 音频时长生成 SRT（不需要 Whisper）

    时间戳基于每个场景音频的实际时长累加，并扣除 crossfade 转场重叠时间。
    长句按标点切分为多个短片段，时间戳按字数比例分配，保证单行显示且音画同步。
    """
    with open(storyboard_path, "r", encoding="utf-8") as f:
        storyboard = json.load(f)

    # 读取 crossfade 转场时长（与 05_compose_video.py 保持一致）
    config_path = PROJECT_ROOT / "config" / "pipeline.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        import yaml as _yaml
        pipeline_cfg = _yaml.safe_load(f)
    video_cfg = pipeline_cfg.get("video", {})
    transition = video_cfg.get("transition", "none")
    fade_duration = video_cfg.get("transition_duration", 0.5) if transition != "none" else 0.0

    srt_entries = []
    current_time = 0.0

    for i, scene in enumerate(storyboard["scenes"]):
        scene_id = scene["scene_id"]
        text = scene["text"]
        audio_path = Path(audio_dir) / f"scene_{scene_id:03d}.wav"

        duration = get_audio_duration(audio_path) if audio_path.exists() else None
        if duration is None:
            duration = scene.get("estimated_duration", 5)

        # 将长句切分为单行片段，按字数比例分配时间
        segments = split_text_to_lines(text)
        total_chars = sum(len(s) for s in segments)
        seg_start = current_time

        for seg in segments:
            seg_ratio = len(seg) / total_chars if total_chars > 0 else 1.0 / len(segments)
            seg_duration = duration * seg_ratio
            seg_end = seg_start + seg_duration

            srt_entries.append({
                "index": len(srt_entries) + 1,
                "start": seg_start,
                "end": seg_end,
                "text": seg,
            })
            seg_start = seg_end

        # 下一场景起始时间：扣除 crossfade 重叠
        if i < len(storyboard["scenes"]) - 1:
            current_time = current_time + duration - fade_duration
        else:
            current_time = current_time + duration

    # 写入 SRT 文件
    output_srt_path = Path(output_srt_path)
    output_srt_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_srt_path, "w", encoding="utf-8") as f:
        for entry in srt_entries:
            f.write(f"{entry['index']}\n")
            f.write(f"{format_srt_time(entry['start'])} --> {format_srt_time(entry['end'])}\n")
            f.write(f"{entry['text']}\n\n")

    logger.info(f"SRT 字幕生成完成: {output_srt_path} ({len(srt_entries)} 条)")
    return output_srt_path


def generate_srt_whisper(video_path, output_srt_path, config):
    """
    方案 B：使用 Whisper 从音频生成字幕（更精准的时间戳）
    """
    subtitle_config = config["subtitle"]
    model_name = subtitle_config.get("whisper_model", "base")
    language = subtitle_config.get("language", "zh")

    try:
        import whisper

        logger.info(f"加载 Whisper 模型: {model_name}")
        model = whisper.load_model(model_name)

        logger.info(f"转写音频...")
        result = model.transcribe(
            str(video_path),
            language=language,
            verbose=False,
        )

        # 写入 SRT
        output_srt_path = Path(output_srt_path)
        output_srt_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_srt_path, "w", encoding="utf-8") as f:
            for i, segment in enumerate(result["segments"], 1):
                f.write(f"{i}\n")
                f.write(
                    f"{format_srt_time(segment['start'])} --> "
                    f"{format_srt_time(segment['end'])}\n"
                )
                f.write(f"{segment['text'].strip()}\n\n")

        logger.info(f"Whisper 字幕生成完成: {output_srt_path}")
        return output_srt_path

    except ImportError:
        logger.warning("Whisper 未安装，将使用 storyboard 方案生成字幕")
        return None


def format_srt_time(seconds):
    """将秒数转换为 SRT 时间格式 HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def burn_subtitles(video_path, srt_path, output_path, config):
    """将字幕烧录到视频中"""
    subtitle_config = config["subtitle"]
    font_size = subtitle_config.get("font_size", 20)
    margin_v = subtitle_config.get("margin_v", 30)

    # FFmpeg subtitles 滤镜的路径需要特殊转义（跨平台处理）
    srt_escaped = get_ffmpeg_subtitle_path(srt_path)

    # 方案 1：带样式的字幕
    force_style = (
        f"FontSize={font_size},"
        f"PrimaryColour=&H0000FFFF,"
        f"OutlineColour=&H00000000,"
        f"BorderStyle=1,Outline=2,Shadow=0,"
        f"WrapStyle=2,"
        f"MarginV={margin_v}"
    )
    subtitle_filter = f"subtitles={srt_escaped}:force_style='{force_style}'"

    cmd = [
        FFMPEG, "-y",
        "-i", str(video_path),
        "-vf", subtitle_filter,
        "-c:v", "libx264",
        "-c:a", "copy",
        "-preset", "medium",
        str(output_path),
    ]

    logger.debug(f"字幕命令: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)

    if result.returncode != 0:
        logger.warning(f"带样式字幕烧录失败，尝试简单模式...")
        logger.debug(f"FFmpeg stderr: {result.stderr[-300:]}")

        # 方案 2：将 SRT 复制到视频同目录，用相对路径
        import shutil
        temp_srt = Path(video_path).parent / "subs.srt"
        shutil.copy2(srt_path, temp_srt)

        cmd_simple = [
            FFMPEG, "-y",
            "-i", str(video_path),
            "-vf", f"subtitles=subs.srt",
            "-c:v", "libx264",
            "-c:a", "copy",
            str(output_path),
        ]
        result = subprocess.run(
            cmd_simple, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
            cwd=str(Path(video_path).parent),
        )
        temp_srt.unlink(missing_ok=True)

        if result.returncode != 0:
            logger.warning(f"简单字幕也失败，尝试 drawtext 方案...")
            logger.debug(f"FFmpeg stderr: {result.stderr[-300:]}")

            # 方案 3：用 drawtext 代替 subtitles 滤镜（不需要 libass）
            # 直接输出无字幕视频，但附带 SRT 文件
            shutil.copy2(video_path, output_path)
            # 把 SRT 复制到输出目录
            output_srt = output_path.parent / (output_path.stem + ".srt")
            shutil.copy2(srt_path, output_srt)
            logger.info(f"字幕文件已输出到: {output_srt}（可用播放器加载外挂字幕）")

    return output_path


def generate_subtitles(
    storyboard_path=None,
    audio_dir=None,
    video_path=None,
    output_path=None,
    use_whisper=False,
    config_manager=None,
):
    """
    主函数：生成字幕并烧录到视频

    Args:
        storyboard_path: storyboard.json 路径
        audio_dir: 音频目录
        video_path: 输入视频路径（无字幕）
        output_path: 最终输出视频路径
        use_whisper: 是否使用 Whisper（默认用 storyboard 方案）
        config_manager: ConfigManager 实例（可选，不传则自建）

    Returns:
        最终视频路径
    """
    if config_manager is None:
        from scripts.config_manager import ConfigManager
        config_manager = ConfigManager()

    config = config_manager.pipeline

    if storyboard_path is None:
        storyboard_path = PROJECT_ROOT / "assets" / "storyboard.json"
    else:
        storyboard_path = Path(storyboard_path)

    if audio_dir is None:
        audio_dir = PROJECT_ROOT / "assets" / "audio"
    else:
        audio_dir = Path(audio_dir)

    if video_path is None:
        video_path = PROJECT_ROOT / "assets" / "video" / "composed_no_sub.mp4"
    else:
        video_path = Path(video_path)

    srt_path = PROJECT_ROOT / "assets" / "subtitles" / "chapter.srt"

    # 生成 SRT
    if use_whisper:
        result = generate_srt_whisper(video_path, srt_path, config)
        if result is None:
            # Whisper 不可用，降级
            generate_srt_from_storyboard(storyboard_path, audio_dir, srt_path)
    else:
        generate_srt_from_storyboard(storyboard_path, audio_dir, srt_path)

    # 确定输出路径
    if output_path is None:
        # 从输入文件名推断
        output_path = PROJECT_ROOT / "output" / "chapter01.mp4"
    else:
        output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 烧录字幕
    logger.info("烧录字幕到视频...")
    burn_subtitles(video_path, srt_path, output_path, config)

    logger.info(f"最终视频输出: {output_path}")
    return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    generate_subtitles()
