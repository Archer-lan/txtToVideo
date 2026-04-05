"""
阶段 4：图片 → 动画（Ken Burns 镜头运动效果）

只做镜头运动，不做内容变化：
- Zoom in / out
- Pan left / right
- Slow fade

工具：MoviePy / FFmpeg
"""

import json
import os
import sys
import subprocess
import logging
import wave
from pathlib import Path
from scripts.platform_utils import FFMPEG, FFPROBE
from scripts.config_manager import ConfigManager

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_config():
    return ConfigManager().pipeline


def get_audio_duration(audio_path):
    """获取 WAV 文件时长（秒）"""
    try:
        with wave.open(str(audio_path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return frames / rate
    except Exception:
        # 尝试用 ffprobe
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
            return 5.0  # 默认 5 秒


def animate_image_ffmpeg(image_path, output_path, duration, motion_type, intensity, fps, resolution):
    """
    使用 FFmpeg 对静态图片添加 Ken Burns 效果

    motion_type: zoom_in, zoom_out, pan_left, pan_right, pan_up, pan_down
    intensity: 运动幅度 (0.0 - 0.2)
    """
    w, h = resolution
    total_frames = int(duration * fps)

    # 确保最少 2 帧
    if total_frames < 2:
        total_frames = 2
        duration = total_frames / fps

    # 根据运动类型构建 zoompan 滤镜
    # zoompan 滤镜参数：z=缩放, x=x偏移, y=y偏移
    if motion_type == "zoom_in":
        # 从 1.0 缩放到 1.0 + intensity
        zoom_expr = f"min(1+{intensity}*on/{total_frames},1+{intensity})"
        x_expr = f"iw/2-(iw/zoom/2)"
        y_expr = f"ih/2-(ih/zoom/2)"

    elif motion_type == "zoom_out":
        # 从 1.0 + intensity 缩放到 1.0
        zoom_expr = f"if(eq(on,1),1+{intensity},max(1,1+{intensity}-{intensity}*on/{total_frames}))"
        x_expr = f"iw/2-(iw/zoom/2)"
        y_expr = f"ih/2-(ih/zoom/2)"

    elif motion_type == "pan_left":
        # 从右向左平移
        zoom_expr = f"1+{intensity}"
        pan_pixels = intensity * w
        x_expr = f"(iw-iw/zoom)*({total_frames}-on)/{total_frames}"
        y_expr = f"ih/2-(ih/zoom/2)"

    elif motion_type == "pan_right":
        # 从左向右平移
        zoom_expr = f"1+{intensity}"
        pan_pixels = intensity * w
        x_expr = f"(iw-iw/zoom)*on/{total_frames}"
        y_expr = f"ih/2-(ih/zoom/2)"

    elif motion_type == "pan_up":
        zoom_expr = f"1+{intensity}"
        x_expr = f"iw/2-(iw/zoom/2)"
        y_expr = f"(ih-ih/zoom)*({total_frames}-on)/{total_frames}"

    elif motion_type == "pan_down":
        zoom_expr = f"1+{intensity}"
        x_expr = f"iw/2-(iw/zoom/2)"
        y_expr = f"(ih-ih/zoom)*on/{total_frames}"

    else:
        # 默认 zoom_in
        zoom_expr = f"min(1+{intensity}*on/{total_frames},1+{intensity})"
        x_expr = f"iw/2-(iw/zoom/2)"
        y_expr = f"ih/2-(ih/zoom/2)"

    # 构建 FFmpeg 命令
    filter_complex = (
        f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}'"
        f":d={total_frames}:s={w}x{h}:fps={fps}"
    )

    cmd = [
        FFMPEG, "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-vf", filter_complex,
        "-t", str(duration),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "medium",
        str(output_path),
    ]

    logger.debug(f"FFmpeg 命令: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120,
    )

    if result.returncode != 0:
        logger.error(f"FFmpeg 错误: {result.stderr[-500:]}")
        raise RuntimeError(f"FFmpeg 动画生成失败: {result.stderr[-200:]}")

    return output_path


def animate_all_images(storyboard_path=None, audio_dir=None, image_dir=None, output_dir=None):
    """
    主函数：为所有场景图片添加 Ken Burns 动画

    Args:
        storyboard_path: storyboard.json 路径
        audio_dir: 音频目录（用于获取时长）
        image_dir: 图片目录
        output_dir: 视频片段输出目录

    Returns:
        生成的视频片段路径列表
    """
    if storyboard_path is None:
        storyboard_path = PROJECT_ROOT / "workspace" / "storyboard.json"
    else:
        storyboard_path = Path(storyboard_path)

    if audio_dir is None:
        audio_dir = PROJECT_ROOT / "workspace" / "audio"
    else:
        audio_dir = Path(audio_dir)

    if image_dir is None:
        image_dir = PROJECT_ROOT / "workspace" / "images"
    else:
        image_dir = Path(image_dir)

    if output_dir is None:
        output_dir = PROJECT_ROOT / "workspace" / "video"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"读取分镜脚本: {storyboard_path}")
    with open(storyboard_path, "r", encoding="utf-8") as f:
        storyboard = json.load(f)

    config = load_config()
    anim_config = config["animation"]
    video_config = config["video"]

    fps = anim_config["fps"]
    default_motion = anim_config["default_motion"]
    intensity = anim_config["motion_intensity"]
    resolution = tuple(video_config["resolution"])
    motion_map = anim_config.get("motion_map", {})

    video_clips = []

    for scene in storyboard["scenes"]:
        scene_id = scene["scene_id"]
        image_path = image_dir / f"scene_{scene_id:03d}.png"
        audio_path = audio_dir / f"scene_{scene_id:03d}.wav"
        output_path = output_dir / f"scene_{scene_id:03d}.mp4"

        if not image_path.exists():
            logger.warning(f"图片不存在: {image_path}，跳过")
            continue

        # 获取时长（优先从音频获取）
        if audio_path.exists():
            duration = get_audio_duration(audio_path)
        else:
            duration = scene.get("estimated_duration", 5)

        # 确保最小时长，加 0.1s buffer 防止视频比音频短
        duration = max(duration, 1.0) + 0.1

        # 确定运动类型
        shot_type = scene["visual"].get("shot", "medium")
        motion_type = motion_map.get(shot_type, default_motion)

        logger.info(
            f"生成动画 scene_{scene_id:03d}: "
            f"motion={motion_type}, duration={duration:.1f}s"
        )

        try:
            animate_image_ffmpeg(
                image_path, output_path, duration,
                motion_type, intensity, fps, resolution,
            )
            video_clips.append(output_path)
            logger.info(f"  已生成: {output_path.name}")
        except Exception as e:
            logger.error(f"  动画生成失败: {e}")
            # 降级：直接将静态图片作为视频
            cmd = [
                FFMPEG, "-y",
                "-loop", "1", "-i", str(image_path),
                "-t", str(duration),
                "-vf", f"scale={resolution[0]}:{resolution[1]}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                str(output_path),
            ]
            subprocess.run(cmd, capture_output=True, timeout=60)
            video_clips.append(output_path)
            logger.info(f"  [静态降级] 已生成: {output_path.name}")

    logger.info(f"动画生成完成，共 {len(video_clips)} 个片段")
    return video_clips


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    animate_all_images()
