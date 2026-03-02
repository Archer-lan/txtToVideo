"""
Bug Condition Exploration Test: 角色外观 Prompt 注入缺失

This test verifies that the bug exists in the UNFIXED code.
It calls build_sd_prompt() with a characters_config parameter containing
character appearance data, and asserts the appearance is included in the prompt.

EXPECTED: This test FAILS on unfixed code, confirming the bug exists.
- Current build_sd_prompt() does NOT accept characters_config parameter (TypeError)
- Even if it did, it does not inject appearance into the prompt

Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.3
"""

import sys
import os
from pathlib import Path
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

# Add project root to path so we can import the module
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Module has numeric prefix (03_generate_images.py), use importlib
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "generate_images", PROJECT_ROOT / "scripts" / "03_generate_images.py"
)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
build_sd_prompt = _module.build_sd_prompt


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

CHARACTERS_CONFIG = {
    "林舟": {
        "voice_type": "BV123_streaming",
        "description": "男主角，年轻男声",
        "appearance": "young man, short dark hair, black jacket, white shirt, tall and slender",
        "emotion_map": {"default": {"rate": "1.0", "pitch": "0"}},
    },
    "苏晚": {
        "voice_type": "BV104_streaming",
        "description": "女主角，温柔女声",
        "appearance": "young woman, long black hair, white dress, slender figure, gentle eyes",
        "emotion_map": {"default": {"rate": "1.0", "pitch": "0"}},
    },
    "narrator": {
        "voice_type": "BV700_V2_streaming",
        "description": "旁白，沉稳男声",
        "emotion_map": {"default": {"rate": "1.0", "pitch": "0"}},
    },
}


# --- Hypothesis Strategies ---

character_names = st.sampled_from(["林舟", "苏晚"])

appearance_strings = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Z"), whitelist_characters=", "),
    min_size=3,
    max_size=80,
).filter(lambda s: s.strip() and any(c.isalpha() for c in s))

shot_types = st.sampled_from(["wide", "medium", "close"])
emotions = st.sampled_from(["平静", "温柔", "紧张"])
visual_prompts = st.sampled_from([
    "A man standing in a dark alley, looking tense",
    "A woman gently approaching from behind, soft expression",
    "Two people talking in a dimly lit room",
    "A figure walking through rain-soaked streets at night",
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


# --- Property-Based Test ---


@given(
    character=character_names,
    appearance=appearance_strings,
    visual_prompt=visual_prompts,
    shot=shot_types,
    emotion=emotions,
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_character_appearance_injected_into_prompt(
    character, appearance, visual_prompt, shot, emotion
):
    """
    **Validates: Requirements 1.2, 2.1, 2.2, 2.3**

    Property 1: Fault Condition - 角色外观 Prompt 注入缺失

    For any scene where speaker is a character with an appearance field,
    build_sd_prompt() should include the appearance in the positive prompt,
    positioned after style prefix and before visual prompt.

    On UNFIXED code, this test FAILS because:
    - build_sd_prompt() does not accept characters_config parameter (TypeError)
    """
    # Build characters config with the generated appearance
    chars_config = dict(CHARACTERS_CONFIG)
    chars_config[character] = dict(chars_config[character])
    chars_config[character]["appearance"] = appearance

    scene = make_scene(character, visual_prompt, shot, emotion)

    # Call build_sd_prompt with characters_config (new expected signature)
    # Current code: build_sd_prompt(scene, styles_config, style_name) - no characters_config
    # Expected:     build_sd_prompt(scene, styles_config, style_name, characters_config)
    positive, negative = build_sd_prompt(
        scene, STYLES_CONFIG, STYLE_NAME, characters_config=chars_config
    )

    # Assert appearance is present in the positive prompt
    assert appearance in positive, (
        f"Character '{character}' appearance '{appearance}' not found in prompt: {positive}"
    )

    # Assert ordering: style_prefix < appearance < visual_prompt
    style_prefix = STYLES_CONFIG["styles"][STYLE_NAME]["positive_prefix"]
    prefix_idx = positive.index(style_prefix)
    appearance_idx = positive.index(appearance)
    visual_idx = positive.index(visual_prompt)

    assert prefix_idx < appearance_idx < visual_idx, (
        f"Appearance not positioned correctly. "
        f"prefix@{prefix_idx}, appearance@{appearance_idx}, visual@{visual_idx}"
    )
