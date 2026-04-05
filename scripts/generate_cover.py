#!/usr/bin/env python3
"""
封面图片生成 - 通过 Stable Diffusion WebUI API 生成封面

用法:
    python scripts/generate_cover.py -o output/cover.png
    python scripts/generate_cover.py -o output/cover.png --sd-url http://127.0.0.1:7860
    python scripts/generate_cover.py -o output/cover.png --prompt "epic fantasy scene"
"""

import argparse
import base64
import sys
from pathlib import Path

import requests


DEFAULT_PROMPT = (
    "explosive dynamic composition, ten people in intense dramatic poses "
    "around a glowing magical circle, powerful magic energy swirling, "
    "a colossal terrifying goat-headed deity looming above with burning red eyes, "
    "thunder and lightning striking, epic cinematic lighting, vibrant saturated colors, "
    "hyper-detailed, masterpiece, stunning spectacle, dramatic action scene, "
    "dynamic angle, powerful perspective, breathtaking, incredible details, "
    "award-winning illustration"
)

DEFAULT_NEGATIVE = (
    "low quality, blurry, bad anatomy, extra limbs, deformed, watermark, "
    "text, simple, plain, dull colors, amateur, ugly, boring composition"
)


def generate_cover(output_path, sd_url="http://127.0.0.1:7860", prompt=None, negative_prompt=None):
    """生成封面图片并保存到指定路径"""
    payload = {
        "prompt": prompt or DEFAULT_PROMPT,
        "negative_prompt": negative_prompt or DEFAULT_NEGATIVE,
        "steps": 50,
        "width": 1280,
        "height": 720,
        "cfg_scale": 9,
        "sampler_name": "DPM++ 2M Karras",
        "hr_fix": True,
        "denoising_strength": 0.5,
    }

    print(f"正在生成封面图片...")
    response = requests.post(f"{sd_url}/sdapi/v1/txt2img", json=payload)

    if response.status_code == 200:
        result = response.json()
        image_data = result["images"][0]

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(base64.b64decode(image_data))

        print(f"封面已保存: {output}")
    else:
        print(f"错误: {response.status_code}")
        print(response.text)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="生成封面图片")
    parser.add_argument("-o", "--output", required=True, help="输出文件路径")
    parser.add_argument("--sd-url", default="http://127.0.0.1:7860", help="SD WebUI 地址")
    parser.add_argument("--prompt", default=None, help="自定义正向提示词")
    parser.add_argument("--negative-prompt", default=None, help="自定义负向提示词")
    args = parser.parse_args()

    generate_cover(args.output, args.sd_url, args.prompt, args.negative_prompt)


if __name__ == "__main__":
    main()
