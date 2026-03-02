"""
Preservation Property Tests: 非角色场景及 Fallback 行为不变

These tests verify baseline behavior on UNFIXED code.
They establish the preservation properties that must hold after the fix:
- Narrator scenes produce expected prompt (style_prefix + visual_prompt + shot + emotion)
- Characters without appearance field produce same prompt as current behavior
- Placeholder image generation works when SD is unavailable
- generate_image_sd payload has no alwayson_scripts field
- Existing prompt parts maintain original order and content

EXPECTED: All tests PASS on unfixed code (confirms baseline behavior to preserve).

Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5
"""

import sys
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import module with numeric prefix
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "generate_images", PROJECT_ROOT / "scripts" / "03_generate_images.py"
)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

build_sd_prompt = _module.build_sd_prompt
generate_image_sd = _module.generate_image_sd
generate_placeholder_image = _module.generate_placeholder_image


# --- Test Data ---

STYLES_CONFIG = {
    "styles": {
        "anime_cinematic": {
            "positive_prefix": "masterpiece, best quality, anime style, cinematic lighting, detailed background",
            "negative_prompt": "lowres, bad anatomy, bad hands, text, error",
            "width": 512,
            "height": 288,
            "steps": 15,
            "cfg_scale": 7,
            "sampler": "DPM++ 2M",
        }
    },
    "shot_map": {
        "wide": "wide angle shot, establishing shot",
        "medium": "medium shot, waist up",
        "close": "close-up shot, detailed face",
    },
    "emotion_map": {
        "平静": "serene atmosphere, natural lighting, peaceful",
        "温柔": "warm lighting, soft glow, gentle atmosphere",
        "紧张": "dramatic lighting, high contrast, tense atmosphere",
    },
}

STYLE_NAME = "anime_cinematic"
STYLE_PREFIX = STYLES_CONFIG["styles"][STYLE_NAME]["positive_prefix"]
NEGATIVE_PROMPT = STYLES_CONFIG["styles"][STYLE_NAME]["negative_prompt"]


# --- Hypothesis Strategies ---

shot_types = st.sampled_from(["wide", "medium", "close"])
emotions = st.sampled_from(["平静", "温柔", "紧张"])
visual_prompts = st.sampled_from([
    "A man standing in a dark alley, looking tense",
    "A woman gently approaching from behind, soft expression",
    "Two people talking in a dimly lit room",
    "A figure walking through rain-soaked streets at night",
    "A peaceful landscape with mountains and a lake",
])


def make_scene(speaker, visual_prompt, shot, emotion):
    """Construct a test scene dict."""
    return {
        "scene_id": 1,
        "speaker": speaker,
        "text": "测试台词",
        "emotion": emotion,
        "visual": {
            "prompt": visual_prompt,
            "shot": shot,
        },
    }


# --- Property-Based Tests ---


@given(
    visual_prompt=visual_prompts,
    shot=shot_types,
    emotion=emotions,
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_narrator_scene_prompt_structure(visual_prompt, shot, emotion):
    """
    **Validates: Requirements 3.2, 3.5**

    Property 2 (partial): For narrator scenes, build_sd_prompt() output
    follows the expected structure: style_prefix + visual_prompt + shot + emotion.

    On UNFIXED code this PASSES, establishing the baseline to preserve.
    """
    scene = make_scene("narrator", visual_prompt, shot, emotion)
    positive, negative = build_sd_prompt(scene, STYLES_CONFIG, STYLE_NAME)

    # Positive prompt must contain all expected parts
    assert STYLE_PREFIX in positive, f"Style prefix missing from prompt: {positive}"
    assert visual_prompt in positive, f"Visual prompt missing from prompt: {positive}"

    shot_text = STYLES_CONFIG["shot_map"].get(shot, "")
    if shot_text:
        assert shot_text in positive, f"Shot type '{shot_text}' missing from prompt: {positive}"

    emotion_text = STYLES_CONFIG["emotion_map"].get(emotion, "")
    if emotion_text:
        assert emotion_text in positive, f"Emotion '{emotion_text}' missing from prompt: {positive}"

    # Negative prompt must match style's negative prompt
    assert negative == NEGATIVE_PROMPT, f"Negative prompt mismatch: {negative}"

    # Verify ordering: style_prefix comes before visual_prompt
    prefix_idx = positive.index(STYLE_PREFIX)
    visual_idx = positive.index(visual_prompt)
    assert prefix_idx < visual_idx, (
        f"Style prefix should come before visual prompt. "
        f"prefix@{prefix_idx}, visual@{visual_idx}"
    )


@given(
    visual_prompt=visual_prompts,
    shot=shot_types,
    emotion=emotions,
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_character_without_appearance_prompt_unchanged(visual_prompt, shot, emotion):
    """
    **Validates: Requirements 3.1, 3.5**

    Property 2 (partial): For characters without appearance field in characters config,
    build_sd_prompt() output is identical to the current behavior (no appearance injection).

    Current characters.yaml has no appearance field, so calling build_sd_prompt()
    with any character speaker produces the same structure as narrator scenes.
    On UNFIXED code this PASSES.
    """
    # Use a character name that exists in characters.yaml but has no appearance
    scene = make_scene("林舟", visual_prompt, shot, emotion)
    positive, negative = build_sd_prompt(scene, STYLES_CONFIG, STYLE_NAME)

    # Should produce the same structure as any other scene
    assert STYLE_PREFIX in positive
    assert visual_prompt in positive
    assert negative == NEGATIVE_PROMPT

    # Verify ordering is preserved
    prefix_idx = positive.index(STYLE_PREFIX)
    visual_idx = positive.index(visual_prompt)
    assert prefix_idx < visual_idx


@given(
    visual_prompt=visual_prompts,
    shot=shot_types,
    emotion=emotions,
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_prompt_parts_maintain_order(visual_prompt, shot, emotion):
    """
    **Validates: Requirements 3.5**

    Property 2 (partial): Existing prompt parts (style prefix, visual prompt,
    shot type, emotion) maintain their original order and content.

    The expected order is: style_prefix, visual_prompt, shot, emotion.
    On UNFIXED code this PASSES.
    """
    scene = make_scene("narrator", visual_prompt, shot, emotion)
    positive, _ = build_sd_prompt(scene, STYLES_CONFIG, STYLE_NAME)

    # Split the positive prompt by ", " to check part ordering
    shot_text = STYLES_CONFIG["shot_map"].get(shot, "")
    emotion_text = STYLES_CONFIG["emotion_map"].get(emotion, "")

    # All parts should be present
    parts_present = []
    if STYLE_PREFIX in positive:
        parts_present.append(("style_prefix", positive.index(STYLE_PREFIX)))
    if visual_prompt in positive:
        parts_present.append(("visual_prompt", positive.index(visual_prompt)))
    if shot_text and shot_text in positive:
        parts_present.append(("shot", positive.index(shot_text)))
    if emotion_text and emotion_text in positive:
        parts_present.append(("emotion", positive.index(emotion_text)))

    # Verify order: style_prefix < visual_prompt < shot < emotion
    expected_order = ["style_prefix", "visual_prompt", "shot", "emotion"]
    actual_order = [name for name, _ in sorted(parts_present, key=lambda x: x[1])]

    assert actual_order == expected_order, (
        f"Prompt parts out of order. Expected {expected_order}, got {actual_order}. "
        f"Prompt: {positive}"
    )


def test_placeholder_image_generation():
    """
    **Validates: Requirements 3.3**

    Property 3: generate_placeholder_image() works correctly when SD is unavailable.
    It should return valid image bytes.

    On UNFIXED code this PASSES.
    """
    width, height = 512, 288
    scene_id = 1
    text = "测试场景描述"

    image_data = generate_placeholder_image(width, height, scene_id, text)

    # Should return bytes
    assert isinstance(image_data, bytes), f"Expected bytes, got {type(image_data)}"
    # Should be non-empty
    assert len(image_data) > 0, "Placeholder image should not be empty"
    # Should start with PNG magic bytes
    assert image_data[:4] == b"\x89PNG", "Placeholder image should be a valid PNG"


def test_placeholder_image_without_text():
    """
    **Validates: Requirements 3.3**

    Property 3 (edge case): generate_placeholder_image() works with empty text.

    On UNFIXED code this PASSES.
    """
    width, height = 512, 288
    scene_id = 5

    image_data = generate_placeholder_image(width, height, scene_id, text="")

    assert isinstance(image_data, bytes)
    assert len(image_data) > 0
    assert image_data[:4] == b"\x89PNG"


def test_generate_image_sd_payload_no_alwayson_scripts():
    """
    **Validates: Requirements 3.4**

    Property 2 (partial): generate_image_sd() payload has no alwayson_scripts field.
    When pipeline.yaml has no ip_adapter config, the payload sent to SD WebUI
    should be a pure txt2img request without any extension scripts.

    On UNFIXED code this PASSES.
    """
    positive = "masterpiece, best quality, a test scene"
    negative = "lowres, bad anatomy"
    style_config = {
        "width": 512,
        "height": 288,
        "steps": 15,
        "cfg_scale": 7,
        "sampler": "DPM++ 2M",
    }
    api_url = "http://127.0.0.1:7860"

    # Mock requests.post to capture the payload
    captured_payload = {}

    def mock_post(url, json=None, timeout=None):
        captured_payload.update(json)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "images": ["iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="]
        }
        return mock_response

    with patch("requests.post", side_effect=mock_post):
        generate_image_sd(positive, negative, style_config, api_url)

    # Payload should NOT contain alwayson_scripts
    assert "alwayson_scripts" not in captured_payload, (
        f"Payload should not contain alwayson_scripts, but found: {captured_payload.get('alwayson_scripts')}"
    )

    # Payload should contain expected txt2img fields
    assert captured_payload["prompt"] == positive
    assert captured_payload["negative_prompt"] == negative
    assert captured_payload["width"] == 512
    assert captured_payload["height"] == 288
    assert captured_payload["steps"] == 15
    assert captured_payload["cfg_scale"] == 7
    assert captured_payload["sampler_name"] == "DPM++ 2M"
