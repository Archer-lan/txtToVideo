"""
阶段 3：分镜脚本 → 关键画面（Stable Diffusion）

为每个场景生成关键帧图片。
支持 Stable Diffusion WebUI API 和 fallback 占位图。
"""

import json
import os
import sys
import logging
import base64
import yaml
import time
import requests
from pathlib import Path
from io import BytesIO
from scripts.platform_utils import get_default_font_path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_config():
    config_path = PROJECT_ROOT / "config" / "pipeline.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_styles():
    style_path = PROJECT_ROOT / "config" / "styles.yaml"
    with open(style_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_characters():
    char_path = PROJECT_ROOT / "config" / "characters.yaml"
    with open(char_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)




def build_sd_prompt(scene, styles_config, style_name, characters_config=None):
    """构建完整的 Stable Diffusion prompt"""
    style = styles_config["styles"][style_name]
    shot_map = styles_config.get("shot_map", {})
    emotion_map = styles_config.get("emotion_map", {})

    # 基础 prompt
    visual_prompt = scene["visual"]["prompt"]
    shot_type = scene["visual"].get("shot", "medium")
    emotion = scene.get("emotion", "平静")

    # 角色外观注入
    appearance = ""
    if characters_config is not None and scene.get("speaker") != "narrator":
        speaker = scene.get("speaker", "")
        character = characters_config.get(speaker)
        if character and "appearance" in character:
            appearance = character["appearance"]

    # 组合 prompt: style_prefix + [appearance] + visual_prompt + shot + emotion
    parts = [
        style["positive_prefix"],
        appearance,
        visual_prompt,
        shot_map.get(shot_type, ""),
        emotion_map.get(emotion, ""),
    ]

    positive = ", ".join(p for p in parts if p)
    negative = style["negative_prompt"]

    return positive, negative






def generate_image_sd(positive, negative, style_config, api_url, timeout=120, ip_adapter_config=None, reference_image_path=None):
    """调用 Stable Diffusion WebUI API 生成图片"""
    payload = {
        "prompt": positive,
        "negative_prompt": negative,
        "width": style_config["width"],
        "height": style_config["height"],
        "steps": style_config["steps"],
        "cfg_scale": style_config["cfg_scale"],
        "sampler_name": style_config["sampler"],
        "batch_size": 1,
        "n_iter": 1,
        "restore_faces": True,
    }

    # ADetailer: 自动检测并高清重绘人脸和手部
    adetailer_args = {
        "args": [
            True,   # ad_enable
            False,  # skip_img2img
            {
                "ad_model": "face_yolov8n.pt",
                "ad_prompt": positive,
                "ad_negative_prompt": negative,
                "ad_confidence": 0.3,
                "ad_denoising_strength": 0.4,
                "ad_inpaint_only_masked": True,
                "ad_inpaint_only_masked_padding": 32,
            },
            {
                "ad_model": "hand_yolov8n.pt",
                "ad_prompt": positive,
                "ad_negative_prompt": negative,
                "ad_confidence": 0.3,
                "ad_denoising_strength": 0.4,
                "ad_inpaint_only_masked": True,
                "ad_inpaint_only_masked_padding": 32,
            },
        ]
    }

    # 构建 alwayson_scripts
    alwayson = {"ADetailer": adetailer_args}

    # IP-Adapter reference image injection
    if (
        ip_adapter_config is not None
        and ip_adapter_config.get("enabled") is True
        and reference_image_path is not None
        and os.path.exists(reference_image_path)
    ):
        with open(reference_image_path, "rb") as img_file:
            ref_image_b64 = base64.b64encode(img_file.read()).decode("utf-8")
        alwayson["controlnet"] = {
            "args": [{
                "enabled": True,
                "module": "ip-adapter_clip_sd15",
                "model": ip_adapter_config["model"],
                "weight": ip_adapter_config["weight"],
                "image": ref_image_b64,
                "resize_mode": "Crop and Resize",
            }]
        }

    payload["alwayson_scripts"] = alwayson

    response = requests.post(
        f"{api_url}/sdapi/v1/txt2img",
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()

    result = response.json()
    image_data = base64.b64decode(result["images"][0])
    return image_data





def check_sd_available(api_url):
    """检查 Stable Diffusion WebUI 是否可用"""
    try:
        resp = requests.get(f"{api_url}/sdapi/v1/sd-models", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def generate_placeholder_image(width, height, scene_id, text=""):
    """生成占位图片（当 SD 不可用时）"""
    try:
        from PIL import Image, ImageDraw, ImageFont

        img = Image.new("RGB", (width, height), color=(30, 30, 50))
        draw = ImageDraw.Draw(img)

        # 绘制网格
        for x in range(0, width, 50):
            draw.line([(x, 0), (x, height)], fill=(50, 50, 70), width=1)
        for y in range(0, height, 50):
            draw.line([(0, y), (width, y)], fill=(50, 50, 70), width=1)

        # 中央文字
        label = f"Scene {scene_id}"
        try:
            font_path = get_default_font_path()
            font = ImageFont.truetype(font_path, 48)
            small_font = ImageFont.truetype(font_path, 20)
        except Exception:
            font = ImageFont.load_default()
            small_font = font

        bbox = draw.textbbox((0, 0), label, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        draw.text(
            ((width - text_w) / 2, (height - text_h) / 2),
            label,
            fill=(200, 200, 220),
            font=font,
        )

        # 场景描述
        if text:
            short_text = text[:40] + ("..." if len(text) > 40 else "")
            bbox2 = draw.textbbox((0, 0), short_text, font=small_font)
            tw2 = bbox2[2] - bbox2[0]
            draw.text(
                ((width - tw2) / 2, (height + text_h) / 2 + 20),
                short_text,
                fill=(150, 150, 170),
                font=small_font,
            )

        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    except ImportError:
        # 如果连 PIL 都没有，生成最小的 1x1 PNG 然后用 ffmpeg 缩放
        logger.warning("PIL 不可用，生成纯色占位图")
        import struct
        import zlib

        # 创建简单 PNG
        def create_minimal_png(w, h, r, g, b):
            raw_data = b""
            for _ in range(h):
                raw_data += b"\x00"  # filter byte
                raw_data += bytes([r, g, b]) * w
            compressed = zlib.compress(raw_data)

            png = b"\x89PNG\r\n\x1a\n"
            # IHDR
            ihdr_data = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
            ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
            png += struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
            # IDAT
            idat_crc = zlib.crc32(b"IDAT" + compressed) & 0xFFFFFFFF
            png += struct.pack(">I", len(compressed)) + b"IDAT" + compressed + struct.pack(">I", idat_crc)
            # IEND
            iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
            png += struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)
            return png

        return create_minimal_png(width, height, 30, 30, 50)


def generate_all_images(storyboard_path=None, output_dir=None):
    """
    主函数：为所有场景生成画面

    Args:
        storyboard_path: storyboard.json 路径
        output_dir: 图片输出目录

    Returns:
        生成的图片文件路径列表
    """
    if storyboard_path is None:
        storyboard_path = PROJECT_ROOT / "assets" / "storyboard.json"
    else:
        storyboard_path = Path(storyboard_path)

    if output_dir is None:
        output_dir = PROJECT_ROOT / "assets" / "images"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"读取分镜脚本: {storyboard_path}")
    with open(storyboard_path, "r", encoding="utf-8") as f:
        storyboard = json.load(f)

    config = load_config()
    styles_config = load_styles()
    characters_config = load_characters()

    image_config = config["image"]
    style_name = image_config["style"]
    style = styles_config["styles"][style_name]
    api_url = image_config["api_url"]
    timeout = image_config.get("timeout", 120)

    # Load IP-Adapter config
    ip_adapter_config = image_config.get("ip_adapter")

    sd_available = check_sd_available(api_url)
    if sd_available:
        logger.info(f"Stable Diffusion WebUI 已连接: {api_url}")
    else:
        logger.warning(f"Stable Diffusion WebUI 不可用 ({api_url})，将生成占位图片")

    image_files = []

    for scene in storyboard["scenes"]:
        scene_id = scene["scene_id"]
        output_path = output_dir / f"scene_{scene_id:03d}.png"

        positive, negative = build_sd_prompt(scene, styles_config, style_name, characters_config=characters_config)
        logger.info(f"生成图片 scene_{scene_id:03d}: {positive[:60]}...")

        try:
            if sd_available:
                # Look up reference image for IP-Adapter
                ref_image_path = None
                if (
                    ip_adapter_config is not None
                    and ip_adapter_config.get("enabled") is True
                ):
                    speaker = scene.get("speaker", "")
                    reference_dir = ip_adapter_config.get("reference_dir", "assets/reference_images")
                    candidate = PROJECT_ROOT / reference_dir / f"{speaker}.png"
                    if candidate.exists():
                        ref_image_path = str(candidate)

                image_data = generate_image_sd(positive, negative, style, api_url, timeout, ip_adapter_config=ip_adapter_config, reference_image_path=ref_image_path)
                logger.info(f"  [SD WebUI] 已生成: {output_path.name}")
            else:
                image_data = generate_placeholder_image(
                    style["width"], style["height"], scene_id, scene["text"]
                )
                logger.info(f"  [占位图] 已生成: {output_path.name}")

            with open(output_path, "wb") as f:
                f.write(image_data)

            image_files.append(output_path)

        except Exception as e:
            logger.error(f"  图片生成失败: {e}，使用占位图")
            image_data = generate_placeholder_image(
                style["width"], style["height"], scene_id, scene["text"]
            )
            with open(output_path, "wb") as f:
                f.write(image_data)
            image_files.append(output_path)

        # SD API 限流
        if sd_available:
            time.sleep(0.5)

    logger.info(f"图片生成完成，共 {len(image_files)} 个文件")
    return image_files


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    generate_all_images()
