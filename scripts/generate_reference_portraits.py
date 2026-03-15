"""
角色定妆照生成器

为 characters.yaml 中定义了 appearance 的角色生成参考肖像图，
保存到 assets/reference_images/ 下，供 IP-Adapter 使用以保持角色一致性。

用法: python -m scripts.generate_reference_portraits
"""

import base64
import logging
import os
import yaml
import requests
from pathlib import Path

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
API_URL = "http://127.0.0.1:7860"


def generate_portrait(character_name, appearance, output_path, style_config):
    """为单个角色生成定妆照"""
    # 肖像专用 prompt：半身像、正面、干净背景、突出角色特征
    positive = (
        f"masterpiece, best quality, ultra-detailed, manga style, "
        f"character portrait, upper body, front view, looking at viewer, "
        f"simple clean background, solo, 1person, "
        f"detailed face, symmetric face, beautiful detailed eyes, "
        f"{appearance}"
    )
    negative = (
        "lowres, bad anatomy, bad hands, text, logo, watermark, blurry, "
        "deformed, disfigured, distorted face, asymmetric face, cross-eyed, "
        "ugly face, extra limbs, fused fingers, too many fingers, "
        "multiple people, crowd, busy background, "
        "bad face, mangled face, extra faces, cloned face"
    )

    payload = {
        "prompt": positive,
        "negative_prompt": negative,
        "width": 512,
        "height": 768,  # 竖版肖像
        "steps": style_config.get("steps", 28),
        "cfg_scale": style_config.get("cfg_scale", 7.5),
        "sampler_name": style_config.get("sampler", "DPM++ 2M Karras"),
        "batch_size": 1,
        "n_iter": 1,
        "restore_faces": False,
        "alwayson_scripts": {
            "ADetailer": {
                "args": [
                    True, False,
                    {
                        "ad_model": "face_yolov8s.pt",
                        "ad_prompt": f"(detailed face, symmetric face, beautiful eyes), {appearance}",
                        "ad_negative_prompt": "(deformed face, asymmetric face, bad eyes, cross-eyed)",
                        "ad_confidence": 0.3,
                        "ad_denoising_strength": 0.4,
                        "ad_inpaint_only_masked": True,
                        "ad_inpaint_only_masked_padding": 64,
                        "ad_mask_blur": 8,
                        "ad_inpaint_width": 512,
                        "ad_inpaint_height": 512,
                        "ad_use_inpaint_width_height": True,
                    },
                ]
            }
        },
    }

    resp = requests.post(f"{API_URL}/sdapi/v1/txt2img", json=payload, timeout=300)
    resp.raise_for_status()
    img_data = base64.b64decode(resp.json()["images"][0])

    with open(output_path, "wb") as f:
        f.write(img_data)

    return len(img_data)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    # 加载配置
    with open(PROJECT_ROOT / "config" / "characters.yaml", "r", encoding="utf-8") as f:
        characters = yaml.safe_load(f)
    with open(PROJECT_ROOT / "config" / "styles.yaml", "r", encoding="utf-8") as f:
        styles = yaml.safe_load(f)
    with open(PROJECT_ROOT / "config" / "pipeline.yaml", "r", encoding="utf-8") as f:
        pipeline = yaml.safe_load(f)

    style_name = pipeline["image"]["style"]
    style_config = styles["styles"][style_name]

    output_dir = PROJECT_ROOT / "assets" / "reference_images"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 检查 SD 可用性
    try:
        r = requests.get(f"{API_URL}/sdapi/v1/sd-models", timeout=5)
        r.raise_for_status()
        logger.info("SD WebUI 已连接")
    except Exception as e:
        logger.error(f"SD WebUI 不可用: {e}")
        return

    # 为每个有 appearance 的角色生成定妆照
    generated = 0
    for name, config in characters.items():
        if name == "narrator" or "appearance" not in config:
            continue

        output_path = output_dir / f"{name}.png"
        if output_path.exists():
            logger.info(f"跳过 {name}（已存在）")
            continue

        logger.info(f"生成定妆照: {name} - {config['appearance'][:50]}...")
        try:
            size = generate_portrait(name, config["appearance"], output_path, style_config)
            logger.info(f"  ✓ 已保存: {output_path.name} ({size/1024:.0f}KB)")
            generated += 1
        except Exception as e:
            logger.error(f"  ✗ 失败: {e}")

    logger.info(f"定妆照生成完成，新生成 {generated} 张")


if __name__ == "__main__":
    main()
