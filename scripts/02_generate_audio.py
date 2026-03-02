"""
阶段 2：分镜脚本 → 有声朗读音频

根据 storyboard.json 为每个场景生成 TTS 音频。
支持多角色语音映射 + 情绪 prosody 调节。

TTS 引擎：火山引擎 TTS
"""

import json
import os
import sys
import logging
import wave
import yaml
import time
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --- 火山引擎 TTS WebSocket 协议常量 ---
# 协议版本
PROTOCOL_VERSION = 0b0001
DEFAULT_HEADER_SIZE = 0b0001
MESSAGE_TYPE_FULL_CLIENT = 0b0001
MESSAGE_TYPE_AUDIO_ONLY_SERVER = 0b1011
MESSAGE_TYPE_FULL_SERVER = 0b1001
MESSAGE_TYPE_ERROR = 0b1111
MESSAGE_SERIAL_NONE = 0b0000
MESSAGE_SERIAL_POS = 0b0001
MESSAGE_SERIAL_NEG = 0b0010
MESSAGE_SERIAL_FINISH = 0b0011
MESSAGE_COMPRESSION_NONE = 0b0000
MESSAGE_COMPRESSION_GZIP = 0b0001


def load_config():
    config_path = PROJECT_ROOT / "config" / "pipeline.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_characters():
    char_path = PROJECT_ROOT / "config" / "characters.yaml"
    with open(char_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_voice_config(speaker, emotion, characters):
    """获取角色语音配置，包含 emotion prosody"""
    char = characters.get(speaker, characters.get("narrator"))
    voice_type = char["voice_type"]

    emotion_map = char.get("emotion_map", {})
    prosody = emotion_map.get(emotion, emotion_map.get("default", {"rate": "1.0", "pitch": "0"}))

    return voice_type, prosody


def build_tts_request(text, voice_type, prosody, config):
    """构建火山引擎 TTS 请求 payload"""
    tts_config = config["tts"]

    # 构建带 SSML prosody 的文本
    ssml_text = (
        f'<speak>'
        f'<prosody rate="{prosody["rate"]}" pitch="{prosody["pitch"]}st">'
        f'{text}'
        f'</prosody>'
        f'</speak>'
    )

    return {
        "app": {
            "appid": os.environ.get(tts_config["app_id_env"], ""),
            "token": "access_token",
            "cluster": tts_config["cluster"],
        },
        "user": {"uid": "autonovel2video"},
        "audio": {
            "voice_type": voice_type,
            "encoding": "wav",
            "sample_rate": tts_config["sample_rate"],
            "speed_ratio": float(prosody.get("rate", "1.0")),
        },
        "request": {
            "reqid": str(uuid.uuid4()),
            "text": text,
            "text_type": "plain",
            "operation": "query",
        },
    }


def generate_audio_http(text, voice_type, prosody, config, output_path):
    """使用火山引擎 HTTP API 生成音频（备用方案）"""
    import requests

    tts_config = config["tts"]
    app_id = os.environ.get(tts_config["app_id_env"], "")
    access_token = os.environ.get(tts_config["access_token_env"], "")

    url = "https://openspeech.bytedance.com/api/v1/tts"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer;{access_token}",
    }

    payload = {
        "app": {
            "appid": app_id,
            "token": access_token,
            "cluster": tts_config["cluster"],
        },
        "user": {"uid": "autonovel2video"},
        "audio": {
            "voice_type": voice_type,
            "encoding": "wav",
            "sample_rate": tts_config["sample_rate"],
            "speed_ratio": float(prosody.get("rate", "1.0")),
        },
        "request": {
            "reqid": str(uuid.uuid4()),
            "text": text,
            "text_type": "plain",
            "operation": "query",
        },
    }

    response = requests.post(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()

    result = response.json()
    if result.get("code") != 3000:
        raise RuntimeError(f"TTS API 错误: {result}")

    # 解码音频数据
    import base64

    audio_data = base64.b64decode(result["data"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(audio_data)

    return output_path


def generate_silence(duration_ms, sample_rate, output_path):
    """生成静音 WAV 文件"""
    num_samples = int(sample_rate * duration_ms / 1000)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(output_path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_samples)

    return output_path


def concat_wav_files(wav_files, output_path):
    """合并多个 WAV 文件"""
    if not wav_files:
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 读取第一个文件获取参数
    with wave.open(str(wav_files[0]), "rb") as wf:
        params = wf.getparams()

    with wave.open(str(output_path), "wb") as out_wf:
        out_wf.setparams(params)
        for wav_file in wav_files:
            with wave.open(str(wav_file), "rb") as wf:
                out_wf.writeframes(wf.readframes(wf.getnframes()))

    return output_path


def generate_audio_fallback(text, voice_type, prosody, config, output_path):
    """
    降级方案：使用 edge-tts 或生成静音占位。
    当火山引擎 API 不可用时自动切换。
    """
    try:
        import edge_tts
        import asyncio

        # edge-tts voice 映射
        voice_map = {
            "BV700_V2_streaming": "zh-CN-YunxiNeural",
            "BV123_streaming": "zh-CN-YunxiNeural",
            "BV104_streaming": "zh-CN-XiaoxiaoNeural",
        }
        voice = voice_map.get(voice_type, "zh-CN-YunxiNeural")
        rate = prosody.get("rate", "1.0")
        rate_pct = int((float(rate) - 1.0) * 100)
        rate_str = f"+{rate_pct}%" if rate_pct >= 0 else f"{rate_pct}%"

        async def _generate():
            communicate = edge_tts.Communicate(text, voice, rate=rate_str)
            await asyncio.wait_for(communicate.save(str(output_path)), timeout=30)

        asyncio.run(_generate())

        # 验证生成的文件非空
        if output_path.exists() and output_path.stat().st_size > 0:
            logger.info(f"  [edge-tts fallback] 已生成: {output_path.name}")
            return output_path
        else:
            raise RuntimeError("edge-tts 生成了空文件")

    except Exception as e:
        logger.warning(f"  edge-tts 失败: {e}，生成静音占位音频")
        # 按预估时长生成静音
        char_count = len(text)
        duration_s = max(2, char_count / 4)  # ~4字/秒
        sample_rate = config["tts"]["sample_rate"]
        generate_silence(int(duration_s * 1000), sample_rate, output_path)
        logger.info(f"  [静音占位] 已生成: {output_path.name} ({duration_s:.1f}s)")
        return output_path


def generate_all_audio(storyboard_path=None, output_dir=None):
    """
    主函数：为所有场景生成音频

    Args:
        storyboard_path: storyboard.json 路径
        output_dir: 音频输出目录

    Returns:
        生成的音频文件路径列表
    """
    if storyboard_path is None:
        storyboard_path = PROJECT_ROOT / "assets" / "storyboard.json"
    else:
        storyboard_path = Path(storyboard_path)

    if output_dir is None:
        output_dir = PROJECT_ROOT / "assets" / "audio"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"读取分镜脚本: {storyboard_path}")
    with open(storyboard_path, "r", encoding="utf-8") as f:
        storyboard = json.load(f)

    config = load_config()
    characters = load_characters()

    audio_files = []
    use_volcano = bool(
        os.environ.get(config["tts"]["app_id_env"])
        and os.environ.get(config["tts"]["access_token_env"])
    )

    if not use_volcano:
        logger.warning("火山引擎 TTS 未配置，将使用 fallback (edge-tts / 静音)")

    for scene in storyboard["scenes"]:
        scene_id = scene["scene_id"]
        speaker = scene.get("speaker", "narrator")
        text = scene["text"]
        emotion = scene.get("emotion", "default")

        output_path = output_dir / f"scene_{scene_id:03d}.wav"
        logger.info(f"生成音频 scene_{scene_id:03d}: [{speaker}] {text[:30]}...")

        voice_type, prosody = get_voice_config(speaker, emotion, characters)

        try:
            if use_volcano:
                generate_audio_http(text, voice_type, prosody, config, output_path)
                logger.info(f"  [火山引擎] 已生成: {output_path.name}")
            else:
                generate_audio_fallback(text, voice_type, prosody, config, output_path)
        except Exception as e:
            logger.warning(f"  音频生成失败: {e}，使用 fallback")
            generate_audio_fallback(text, voice_type, prosody, config, output_path)

        audio_files.append(output_path)

        # 句间停顿
        time.sleep(0.1)  # API 限流

    logger.info(f"音频生成完成，共 {len(audio_files)} 个文件")
    return audio_files


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    generate_all_audio()
