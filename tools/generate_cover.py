#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成小说封面图

用法:
    python generate_cover.py --prompt "史诗奇幻封面..." --output output/cover.png
    python generate_cover.py --config config/pipeline.yaml --style manga_comic
"""

import argparse
import base64
import json
import sys
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_config(config_path: Path = None):
    """加载配置文件"""
    if config_path is None:
        config_path = PROJECT_ROOT / "config" / "pipeline.yaml"

    try:
        import yaml
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"警告: 无法加载配置文件 {config_path}: {e}")
        return None


def generate_cover(
    api_url: str = "http://127.0.0.1:7860",
    prompt: str = None,
    negative_prompt: str = None,
    output_path: Path = None,
    width: int = 1280,
    height: int = 720,
    steps: int = 50,
    cfg_scale: float = 9.0,
    sampler: str = "DPM++ 2M Karras",
    hr_fix: bool = True,
    denoising_strength: float = 0.5,
    style_config: dict = None,
):
    """
    生成封面图

    Args:
        api_url: SD WebUI API 地址
        prompt: 正向提示词
        negative_prompt: 负向提示词
        output_path: 输出图片路径
        width: 图片宽度
        height: 图片高度
        steps: 采样步数
        cfg_scale: CFG scale
        sampler: 采样器名称
        hr_fix: 是否启用高分辨率修复
        denoising_strength: 去噪强度
        style_config: 风格配置字典 (从 styles.yaml 加载)
    """
    # 默认提示词
    if prompt is None:
        prompt = (
            "epic cinematic cover art, dramatic composition, "
            "powerful visual impact, masterpiece, best quality, "
            "vibrant colors, dynamic lighting, detailed scene"
        )

    if negative_prompt is None:
        negative_prompt = (
            "low quality, blurry, bad anatomy, extra limbs, deformed, "
            "watermark, text, signature, simple, plain, dull colors, "
            "amateur, ugly, boring composition, 3d, photorealistic"
        )

    # 合并风格配置
    if style_config:
        style_prompt = style_config.get("prompt", "")
        style_negative = style_config.get("negative_prompt", "")
        if style_prompt:
            prompt = f"{style_prompt}, {prompt}"
        if style_negative:
            negative_prompt = f"{style_negative}, {negative_prompt}"

    # 构建 payload
    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "steps": steps,
        "width": width,
        "height": height,
        "cfg_scale": cfg_scale,
        "sampler_name": sampler,
        "enable_hr": hr_fix,
        "denoising_strength": denoising_strength,
    }

    # 确定输出路径
    if output_path is None:
        output_path = PROJECT_ROOT / "output" / "cover.png"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 调用 SD WebUI API
    print(f"正在生成封面图...")
    print(f"  API: {api_url}")
    print(f"  尺寸: {width}x{height}")
    print(f"  输出: {output_path}")

    try:
        response = requests.post(f"{api_url}/sdapi/v1/txt2img", json=payload, timeout=300)
    except requests.exceptions.RequestException as e:
        print(f"错误: API 请求失败 - {e}")
        print(f"  请确保 SD WebUI 正在运行并可访问: {api_url}")
        return None

    if response.status_code == 200:
        result = response.json()
        if "images" not in result or not result["images"]:
            print("错误: API 返回结果中没有图片")
            return None

        image_data = result["images"][0]

        # 解码并保存
        with open(output_path, "wb") as f:
            f.write(base64.b64decode(image_data))

        print(f"✓ 封面图已保存: {output_path}")
        return output_path
    else:
        print(f"错误: API 返回状态码 {response.status_code}")
        print(response.text[:500])
        return None


def main():
    parser = argparse.ArgumentParser(
        description="生成小说封面图 (使用 Stable Diffusion WebUI)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本用法（使用默认提示词）
  python generate_cover.py

  # 自定义提示词
  python generate_cover.py --prompt "epic fantasy cover, dragon and knight, dramatic sky"

  # 指定输出路径和尺寸
  python generate_cover.py --output output/my_cover.png --width 1920 --height 1080

  # 使用配置文件中的风格
  python generate_cover.py --style manga_comic

  # 完整参数
  python generate_cover.py \\
      --api-url "http://127.0.0.1:7860" \\
      --prompt "epic cover..." \\
      --negative-prompt "bad quality..." \\
      --output cover.png \\
      --width 1280 --height 720 \\
      --steps 50 --cfg-scale 9 \\
      --sampler "DPM++ 2M Karras" \\
      --hr-fix --denoising-strength 0.5
        """
    )

    parser.add_argument(
        "--api-url",
        type=str,
        default="http://127.0.0.1:7860",
        help="SD WebUI API 地址 (默认: http://127.0.0.1:7860)",
    )
    parser.add_argument(
        "--prompt", "-p",
        type=str,
        default=None,
        help="正向提示词",
    )
    parser.add_argument(
        "--negative-prompt", "-n",
        type=str,
        default=None,
        help="负向提示词",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="输出图片路径 (默认: output/cover.png)",
    )
    parser.add_argument(
        "--width", "-W",
        type=int,
        default=1280,
        help="图片宽度 (默认: 1280)",
    )
    parser.add_argument(
        "--height", "-H",
        type=int,
        default=720,
        help="图片高度 (默认: 720)",
    )
    parser.add_argument(
        "--steps", "-s",
        type=int,
        default=50,
        help="采样步数 (默认: 50)",
    )
    parser.add_argument(
        "--cfg-scale", "-c",
        type=float,
        default=9.0,
        help="CFG scale (默认: 9.0)",
    )
    parser.add_argument(
        "--sampler", "-S",
        type=str,
        default="DPM++ 2M Karras",
        help="采样器名称 (默认: DPM++ 2M Karras)",
    )
    parser.add_argument(
        "--hr-fix",
        action="store_true",
        default=True,
        help="启用高分辨率修复 (默认: 开启)",
    )
    parser.add_argument(
        "--no-hr-fix",
        action="store_false",
        dest="hr_fix",
        help="禁用高分辨率修复",
    )
    parser.add_argument(
        "--denoising-strength", "-d",
        type=float,
        default=0.5,
        help="去噪强度 (默认: 0.5)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="配置文件路径 (默认: config/pipeline.yaml)",
    )
    parser.add_argument(
        "--style",
        type=str,
        default=None,
        help="使用的风格名称 (从 styles.yaml 加载)",
    )

    args = parser.parse_args()

    # 加载风格配置
    style_config = None
    if args.style:
        try:
            import yaml
            styles_path = PROJECT_ROOT / "config" / "styles.yaml"
            if styles_path.exists():
                with open(styles_path, "r", encoding="utf-8") as f:
                    styles = yaml.safe_load(f)
                    if "styles" in styles and args.style in styles["styles"]:
                        style_config = styles["styles"][args.style]
                        print(f"使用风格: {args.style}")
        except Exception as e:
            print(f"警告: 无法加载风格配置: {e}")

    # 生成封面
    result = generate_cover(
        api_url=args.api_url,
        prompt=args.prompt,
        negative_prompt=args.negative_prompt,
        output_path=args.output,
        width=args.width,
        height=args.height,
        steps=args.steps,
        cfg_scale=args.cfg_scale,
        sampler=args.sampler,
        hr_fix=args.hr_fix,
        denoising_strength=args.denoising_strength,
        style_config=style_config,
    )

    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main())
