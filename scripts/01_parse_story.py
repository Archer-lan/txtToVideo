"""
阶段 1：小说文本 → 分镜脚本 (storyboard.json)

使用 LLM 将小说文本拆分为场景列表，每个场景包含：
- scene_id: 场景编号
- type: narration / dialogue
- speaker: 说话人（对话时）
- text: 原文
- emotion: 情绪关键词
- visual.prompt: Stable Diffusion 画面描述
- visual.shot: 镜头类型
- estimated_duration: 预估时长（秒）
"""

import json
import os
import sys
import re
import logging
import yaml
from pathlib import Path
from openai import OpenAI

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SYSTEM_PROMPT = """你是一个专业的影视分镜脚本师。你的任务是将小说文本转换为分镜脚本。

严格按照以下 JSON 格式输出，不要输出任何其他内容：

{
  "scenes": [
    {
      "scene_id": 1,
      "type": "narration 或 dialogue",
      "speaker": "角色名（type为narration时填narrator）",
      "text": "原文内容（保持原文，不要修改）",
      "emotion": "情绪关键词（压抑/紧张/温柔/愤怒/悲伤/欢快/恐惧/平静）",
      "visual": {
        "prompt": "英文画面描述，用于AI绘图，15-30个词",
        "shot": "镜头类型（wide/medium/close/extreme_close/over_shoulder/bird_eye）"
      },
      "estimated_duration": 预估朗读秒数（整数）
    }
  ]
}

规则：
1. 每个场景最多包含 1-2 句话
2. 对话和旁白要分开成不同场景
3. visual.prompt 必须是英文，描述画面内容，不要包含文字
4. visual.prompt 不要包含风格描述（如 anime, cinematic），只描述画面内容
5. estimated_duration 按中文朗读速度估算（约 3-4 字/秒）
6. 只输出 JSON，不要输出其他任何内容
"""


def load_config():
    """加载 pipeline 配置"""
    config_path = PROJECT_ROOT / "config" / "pipeline.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def create_llm_client(config):
    """创建 LLM 客户端"""
    llm_config = config["llm"]
    api_key = os.environ.get(llm_config["api_key_env"], "")
    base_url = llm_config.get("base_url") or None

    return OpenAI(api_key=api_key, base_url=base_url)


def split_text_chunks(text, max_chars=2000):
    """将长文本按段落分割为合适大小的块"""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks = []
    current_chunk = []
    current_len = 0

    for para in paragraphs:
        if current_len + len(para) > max_chars and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = [para]
            current_len = len(para)
        else:
            current_chunk.append(para)
            current_len += len(para)

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks


def extract_json_from_response(text):
    """从 LLM 响应中提取 JSON（处理 markdown code block、think 标签等情况）"""
    # 先去掉 <think>...</think> 标签（MiniMax 等模型的思考过程）
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 中的内容
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 尝试找到第一个 { 和最后一个 }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法从 LLM 响应中提取有效 JSON:\n{text[:500]}")


def validate_storyboard(data):
    """校验 storyboard 结构"""
    if "scenes" not in data:
        raise ValueError("缺少 'scenes' 字段")

    for i, scene in enumerate(data["scenes"]):
        required = ["scene_id", "type", "text", "emotion", "visual", "estimated_duration"]
        for field in required:
            if field not in scene:
                raise ValueError(f"场景 {i+1} 缺少字段: {field}")

        if "prompt" not in scene["visual"] or "shot" not in scene["visual"]:
            raise ValueError(f"场景 {i+1} 的 visual 字段不完整")

        # 补全 speaker
        if "speaker" not in scene:
            scene["speaker"] = "narrator" if scene["type"] == "narration" else "unknown"

    return data


def parse_story(input_path, output_path=None):
    """
    主函数：解析小说文本 → 生成 storyboard.json

    Args:
        input_path: 小说文本文件路径
        output_path: 输出 JSON 路径（默认 assets/storyboard.json）

    Returns:
        storyboard dict
    """
    input_path = Path(input_path)
    if output_path is None:
        output_path = PROJECT_ROOT / "assets" / "storyboard.json"
    else:
        output_path = Path(output_path)

    logger.info(f"读取小说文本: {input_path}")
    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read()

    config = load_config()
    client = create_llm_client(config)

    # 分块处理长文本
    chunks = split_text_chunks(text)
    all_scenes = []
    scene_id_counter = 1

    for i, chunk in enumerate(chunks):
        logger.info(f"处理文本块 {i+1}/{len(chunks)} ...")

        # 调用 LLM
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=config["llm"]["model"],
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"请将以下小说文本转换为分镜脚本：\n\n{chunk}"},
                    ],
                    max_tokens=config["llm"]["max_tokens"],
                    temperature=config["llm"]["temperature"],
                )

                result_text = response.choices[0].message.content
                data = extract_json_from_response(result_text)
                data = validate_storyboard(data)

                # 重新编号 scene_id
                for scene in data["scenes"]:
                    scene["scene_id"] = scene_id_counter
                    scene_id_counter += 1

                all_scenes.extend(data["scenes"])
                logger.info(f"  文本块 {i+1} 解析出 {len(data['scenes'])} 个场景")
                break

            except Exception as e:
                logger.warning(f"  第 {attempt+1} 次尝试失败: {e}")
                if attempt == max_retries - 1:
                    raise RuntimeError(f"文本块 {i+1} 解析失败，已重试 {max_retries} 次") from e

    storyboard = {"scenes": all_scenes}

    # 写入输出
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(storyboard, f, ensure_ascii=False, indent=2)

    logger.info(f"分镜脚本已生成: {output_path} (共 {len(all_scenes)} 个场景)")
    return storyboard


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    if len(sys.argv) < 2:
        print("用法: python 01_parse_story.py <input_txt>")
        sys.exit(1)

    parse_story(sys.argv[1])
