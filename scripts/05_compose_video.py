"""
阶段 5：音画合成

将动画片段 + 音频合成为无字幕完整视频。
- 音频长度 = 视频长度
- 自动拼接所有场景
- 支持 crossfade 转场
"""

import json
import os
import sys
import subprocess
import logging
import yaml
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_config():
    config_path = PROJECT_ROOT / "config" / "pipeline.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def merge_audio_video_scene(video_path, audio_path, output_path):
    """合并单个场景的音频和视频，以音频时长为准"""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"音画合并失败: {result.stderr[-200:]}")

    return output_path


def concat_videos(video_files, output_path, config):
    """
    拼接所有场景视频

    使用 FFmpeg concat demuxer（无转场）或 filter（有转场）
    """
    video_config = config["video"]
    transition = video_config.get("transition", "none")
    transition_duration = video_config.get("transition_duration", 0.5)

    if transition == "none" or len(video_files) <= 1:
        return concat_simple(video_files, output_path)
    else:
        return concat_with_crossfade(video_files, output_path, transition_duration, video_config)


def concat_simple(video_files, output_path):
    """简单拼接（无转场）"""
    # 创建 concat 文件列表
    list_file = output_path.parent / "concat_list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for vf in video_files:
            f.write(f"file '{vf.resolve().as_posix()}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264",
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    # 清理临时文件
    list_file.unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"视频拼接失败: {result.stderr[-200:]}")

    return output_path


def concat_with_crossfade(video_files, output_path, fade_duration, video_config):
    """带 crossfade 转场的拼接"""
    if len(video_files) == 1:
        # 只有一个视频，直接拷贝
        import shutil
        shutil.copy2(video_files[0], output_path)
        return output_path

    # 对于多个视频，使用 xfade 滤镜逐步合并
    # 先获取每个视频的时长
    durations = []
    for vf in video_files:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(vf),
            ],
            capture_output=True, text=True, timeout=10,
        )
        try:
            durations.append(float(result.stdout.strip()))
        except ValueError:
            durations.append(5.0)

    # 构建 xfade 滤镜链
    # FFmpeg xfade 需要依次两两合并
    n = len(video_files)

    if n == 2:
        offset = max(0, durations[0] - fade_duration)
        filter_complex = (
            f"[0:v][1:v]xfade=transition=fade:duration={fade_duration}:offset={offset}[outv];"
            f"[0:a][1:a]acrossfade=d={fade_duration}[outa]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_files[0]),
            "-i", str(video_files[1]),
            "-filter_complex", filter_complex,
            "-map", "[outv]", "-map", "[outa]",
            "-c:v", "libx264", "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            logger.warning(f"Crossfade 失败，退回简单拼接: {result.stderr[-200:]}")
            return concat_simple(video_files, output_path)
        return output_path

    # 对于 > 2 个视频，使用简单拼接（xfade 链太复杂容易出错）
    # 改为两两合并的递归策略
    logger.info(f"多场景 crossfade: 共 {n} 个片段，使用分步合并")

    temp_dir = output_path.parent / "_temp_concat"
    temp_dir.mkdir(exist_ok=True)

    current_files = list(video_files)
    step = 0

    while len(current_files) > 1:
        next_files = []
        for i in range(0, len(current_files), 2):
            if i + 1 < len(current_files):
                temp_out = temp_dir / f"step{step}_{i}.mp4"
                # 获取第一个文件时长
                r = subprocess.run(
                    [
                        "ffprobe", "-v", "quiet",
                        "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1",
                        str(current_files[i]),
                    ],
                    capture_output=True, text=True, timeout=10,
                )
                try:
                    d = float(r.stdout.strip())
                except ValueError:
                    d = 5.0

                offset = max(0, d - fade_duration)
                filter_complex = (
                    f"[0:v][1:v]xfade=transition=fade:duration={fade_duration}:offset={offset}[outv];"
                    f"[0:a][1:a]acrossfade=d={fade_duration}[outa]"
                )
                cmd = [
                    "ffmpeg", "-y",
                    "-i", str(current_files[i]),
                    "-i", str(current_files[i + 1]),
                    "-filter_complex", filter_complex,
                    "-map", "[outv]", "-map", "[outa]",
                    "-c:v", "libx264", "-c:a", "aac",
                    "-pix_fmt", "yuv420p",
                    str(temp_out),
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode != 0:
                    # 降级为简单拼接
                    logger.warning("Crossfade 步骤失败，降级为简单拼接")
                    import shutil
                    for f in temp_dir.iterdir():
                        f.unlink()
                    temp_dir.rmdir()
                    return concat_simple(video_files, output_path)

                next_files.append(temp_out)
            else:
                next_files.append(current_files[i])

        current_files = next_files
        step += 1

    # 最终结果
    import shutil
    shutil.move(str(current_files[0]), str(output_path))

    # 清理临时文件
    for f in temp_dir.iterdir():
        f.unlink()
    temp_dir.rmdir()

    return output_path


def compose_video(storyboard_path=None, audio_dir=None, video_dir=None, output_path=None):
    """
    主函数：合成完整视频（无字幕）

    Args:
        storyboard_path: storyboard.json 路径
        audio_dir: 音频目录
        video_dir: 动画视频片段目录
        output_path: 输出视频路径

    Returns:
        输出视频路径
    """
    if storyboard_path is None:
        storyboard_path = PROJECT_ROOT / "assets" / "storyboard.json"
    else:
        storyboard_path = Path(storyboard_path)

    if audio_dir is None:
        audio_dir = PROJECT_ROOT / "assets" / "audio"
    else:
        audio_dir = Path(audio_dir)

    if video_dir is None:
        video_dir = PROJECT_ROOT / "assets" / "video"
    else:
        video_dir = Path(video_dir)

    if output_path is None:
        output_path = PROJECT_ROOT / "assets" / "video" / "composed_no_sub.mp4"
    else:
        output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"读取分镜脚本: {storyboard_path}")
    with open(storyboard_path, "r", encoding="utf-8") as f:
        storyboard = json.load(f)

    config = load_config()

    # 第一步：为每个场景合并音视频
    merged_dir = video_dir / "_merged"
    merged_dir.mkdir(exist_ok=True)

    merged_files = []
    for scene in storyboard["scenes"]:
        scene_id = scene["scene_id"]
        video_clip = video_dir / f"scene_{scene_id:03d}.mp4"
        audio_clip = audio_dir / f"scene_{scene_id:03d}.wav"
        merged_clip = merged_dir / f"scene_{scene_id:03d}_merged.mp4"

        if not video_clip.exists():
            logger.warning(f"视频片段不存在: {video_clip}，跳过")
            continue

        if not audio_clip.exists():
            logger.warning(f"音频不存在: {audio_clip}，使用无音频视频")
            import shutil
            shutil.copy2(video_clip, merged_clip)
            merged_files.append(merged_clip)
            continue

        logger.info(f"合并音视频 scene_{scene_id:03d}...")
        try:
            merge_audio_video_scene(video_clip, audio_clip, merged_clip)
            merged_files.append(merged_clip)
        except Exception as e:
            logger.error(f"  合并失败: {e}，使用无音频视频")
            import shutil
            shutil.copy2(video_clip, merged_clip)
            merged_files.append(merged_clip)

    if not merged_files:
        raise RuntimeError("没有可用的视频片段")

    # 第二步：拼接所有场景
    logger.info(f"拼接 {len(merged_files)} 个场景片段...")
    concat_videos(merged_files, output_path, config)

    # 清理临时合并文件
    for f in merged_dir.iterdir():
        f.unlink()
    merged_dir.rmdir()

    logger.info(f"视频合成完成: {output_path}")
    return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    compose_video()
