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
import chardet
from pathlib import Path
from openai import OpenAI

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def detect_file_encoding(file_path):
    """自动检测文件编码"""
    with open(file_path, 'rb') as f:
        raw_data = f.read(100000)  # 读取前100KB用于检测
        result = chardet.detect(raw_data)
        encoding = result.get('encoding', 'utf-8')
        confidence = result.get('confidence', 0)
        logger.info(f"检测到文件编码: {encoding} (置信度: {confidence:.2%})")
        # 如果置信度较低，默认为utf-8
        if confidence < 0.7:
            return 'utf-8'
        return encoding

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
        "prompt": "英文画面描述，用于AI绘图，20-40个词",
        "shot": "镜头类型（wide/medium/close/extreme_close/over_shoulder/bird_eye）"
      },
      "estimated_duration": 预估朗读秒数（整数）
    }
  ]
}

规则：
1. 每句话就是一个独立场景（一句话一张图）
2. 对话和旁白要分开成不同场景
3. visual.prompt 必须是英文，描述画面内容，不要包含文字
4. visual.prompt 不要包含风格描述（如 anime, cinematic），只描述画面内容
5. estimated_duration 按中文朗读速度估算（约 6-7 字/秒，因为语速是2倍）
6. 只输出 JSON，不要输出其他任何内容

【画面描述的关键要求 - 保持叙事连贯性】：
- 每个场景的 visual.prompt 必须与前后场景在空间、人物、动作上保持连贯
- 必须明确描述：当前场景的地点环境 + 出现的人物（外貌/服装）+ 正在发生的动作/状态
- 同一地点的连续场景，背景环境描述要保持一致（如"convenience store interior"要贯穿始终）
- 人物在连续场景中的位置关系、服装、状态要保持一致，不能突然改变
- 镜头切换要符合电影逻辑：先用 wide 建立场景，再用 medium/close 聚焦细节
- 对话场景要体现说话人的表情、姿态，以及对话发生的空间背景
- 动作场景要体现动作的连续性（如"人物A正在做X"→"X的结果/反应"）
- 避免生成与情节无关的通用画面（如单纯的"dark room"、"man standing"等）
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


def split_text_chunks(text, max_chars=1200):
    """将长文本按段落分割为合适大小的块（缩小块大小以适配带全局摘要的 prompt）"""
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


SUMMARY_PROMPT = """你是一个专业的影视分镜脚本师。请分析以下小说章节，生成一份简洁的"章节视觉摘要"，用于指导后续每个场景的画面生成。

请严格按以下 JSON 格式输出，不要输出其他内容：

{
  "locations": [
    {"id": "loc_1", "name": "地点名", "description": "英文环境描述，30词以内，包含光线、氛围、关键物件"}
  ],
  "characters_in_chapter": [
    {"name": "角色名", "appearance": "英文外貌描述，20词以内，包含服装、发型、体型"}
  ],
  "plot_phases": [
    {"phase": 1, "summary": "英文剧情阶段摘要，15词以内", "location_id": "loc_1", "characters": ["角色名"], "mood": "情绪基调"}
  ]
}

要求：
- locations: 本章出现的所有地点，description 用英文描述视觉特征
- characters_in_chapter: 本章出现的所有角色及其外貌（英文）
- plot_phases: 将本章剧情分为3-6个阶段，标注每个阶段的地点、人物、情绪
- 所有视觉描述必须是英文
"""


def generate_chapter_summary(text, client, config):
    """
    调用 LLM 生成章节全局视觉摘要。
    返回摘要 dict，失败时返回 None。
    """
    logger.info("生成章节视觉摘要...")
    # 取前 3000 字（足够覆盖整章核心内容）
    summary_text = text[:3000] if len(text) > 3000 else text

    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=config["llm"]["model"],
                messages=[
                    {"role": "system", "content": SUMMARY_PROMPT},
                    {"role": "user", "content": f"请分析以下章节并生成视觉摘要：\n\n{summary_text}"},
                ],
                max_tokens=config["llm"]["max_tokens"],
                temperature=0.2,
            )
            result_text = response.choices[0].message.content
            summary = extract_json_from_response(result_text)
            logger.info(f"  章节摘要生成完成: {len(summary.get('locations', []))} 个地点, "
                        f"{len(summary.get('characters_in_chapter', []))} 个角色, "
                        f"{len(summary.get('plot_phases', []))} 个剧情阶段")
            return summary
        except Exception as e:
            logger.warning(f"  章节摘要生成失败 (第 {attempt+1} 次): {e}")
    logger.warning("章节摘要生成失败，将不使用全局摘要")
    return None


def build_summary_context(summary):
    """将章节摘要转为可注入 SYSTEM_PROMPT 的文本"""
    if summary is None:
        return ""

    lines = ["\n\n【本章全局视觉参考（所有场景的画面描述必须基于此信息）】"]

    locations = summary.get("locations", [])
    if locations:
        lines.append("地点环境：")
        for loc in locations:
            lines.append(f"  - {loc['name']} ({loc['id']}): {loc['description']}")

    characters = summary.get("characters_in_chapter", [])
    if characters:
        lines.append("出场角色：")
        for ch in characters:
            lines.append(f"  - {ch['name']}: {ch['appearance']}")

    phases = summary.get("plot_phases", [])
    if phases:
        lines.append("剧情阶段：")
        for ph in phases:
            chars = ", ".join(ph.get("characters", []))
            lines.append(f"  - 阶段{ph['phase']}: {ph['summary']} | 地点: {ph['location_id']} | 人物: {chars} | 情绪: {ph['mood']}")

    lines.append("\n请在生成每个场景的 visual.prompt 时，严格引用上述地点描述和角色外貌，确保画面与剧情阶段匹配。")
    return "\n".join(lines)


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
    # 自动检测文件编码
    file_encoding = detect_file_encoding(input_path)
    with open(input_path, "r", encoding=file_encoding) as f:
        text = f.read()

    config = load_config()
    client = create_llm_client(config)

    # ===== 方案 2: 先生成章节全局视觉摘要 =====
    chapter_summary = generate_chapter_summary(text, client, config)
    summary_context = build_summary_context(chapter_summary)
    system_prompt_with_summary = SYSTEM_PROMPT + summary_context

    # 分块处理长文本
    chunks = split_text_chunks(text)
    all_scenes = []
    scene_id_counter = 1
    # 用于跨块传递上下文：记录上一块最后几个场景的摘要
    prev_context_summary = ""

    for i, chunk in enumerate(chunks):
        logger.info(f"处理文本块 {i+1}/{len(chunks)} ...")

        # 构建用户消息，携带前序上下文
        if prev_context_summary:
            user_content = (
                f"【前序场景上下文（用于保持画面连贯性，不要重复生成这些场景）】\n"
                f"{prev_context_summary}\n\n"
                f"【请将以下新文本转换为分镜脚本，画面描述需与上述上下文保持连贯】\n\n{chunk}"
            )
        else:
            user_content = f"请将以下小说文本转换为分镜脚本：\n\n{chunk}"

        # 调用 LLM（使用带全局摘要的 system prompt）
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=config["llm"]["model"],
                    messages=[
                        {"role": "system", "content": system_prompt_with_summary},
                        {"role": "user", "content": user_content},
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

                # 更新跨块上下文：取本块最后3个场景的关键信息
                tail_scenes = data["scenes"][-3:]
                prev_context_summary = "\n".join(
                    f"- 场景{s['scene_id']}: {s['text'][:40]}... | 画面: {s['visual']['prompt'][:60]} | 地点/状态延续至下一块"
                    for s in tail_scenes
                )
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
