# 图片角色外观一致性 Bugfix Design

## Overview

AutoNovel2Video 管线在生成场景图片时，每个场景独立调用 Stable Diffusion，缺乏角色外观一致性保障。同一角色在不同场景中外观随机漂移（发型、服装、体型等），严重影响视频视觉连贯性。

修复策略分两层：
1. **角色外观 prompt 注入**（核心）：在 `characters.yaml` 新增 `appearance` 字段，`build_sd_prompt()` 根据场景 speaker 自动将角色外观描述注入 prompt，锚定角色视觉特征。
2. **IP-Adapter 参考图支持**（可选增强）：在 `pipeline.yaml` 新增 IP-Adapter 配置，`generate_image_sd()` 支持通过 SD WebUI 的 IP-Adapter 扩展注入参考图，进一步增强一致性。

## Glossary

- **Bug_Condition (C)**：场景的 speaker 对应一个在 `characters.yaml` 中定义了 `appearance` 字段的角色，但 prompt 中未包含该角色的外观描述
- **Property (P)**：当 C 成立时，生成的 prompt 应包含角色的 appearance 描述，且位于 style prefix 之后、visual prompt 之前
- **Preservation**：当 speaker 为 narrator、角色无 appearance 字段、或 SD 不可用时，系统行为与修复前完全一致
- **`build_sd_prompt()`**：`scripts/03_generate_images.py` 中的函数，负责拼接 SD prompt（当前顺序：style prefix + visual prompt + shot + emotion）
- **`generate_image_sd()`**：`scripts/03_generate_images.py` 中的函数，调用 SD WebUI txt2img API 生成图片
- **`generate_all_images()`**：`scripts/03_generate_images.py` 中的主函数，遍历所有场景调用上述两个函数
- **IP-Adapter**：SD WebUI 扩展，通过参考图引导图片生成，增强角色外观一致性

## Bug Details

### Fault Condition

当场景的 speaker 对应一个有外观描述的角色时，`build_sd_prompt()` 不读取也不注入角色外观信息，导致 Stable Diffusion 每次自由发挥角色外观。此外，即使用户希望通过 IP-Adapter 参考图增强一致性，系统也不支持该功能。

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type Scene (from storyboard.json)
  OUTPUT: boolean

  characters := loadCharactersConfig("config/characters.yaml")
  speaker := input.speaker

  RETURN speaker != "narrator"
         AND speaker IN characters
         AND characters[speaker] HAS "appearance"
         AND "appearance" NOT IN buildCurrentPrompt(input)
END FUNCTION
```

### Examples

- **场景 2（speaker: 苏晚）**：当前 prompt 为 `"masterpiece, best quality, anime style, cinematic lighting, detailed background, A woman gently approaching a man from behind, soft expression, standing in dim room, over the shoulder shot, warm lighting, soft glow, gentle atmosphere"`。缺少苏晚的外观描述（如 "long black hair, white dress, slender figure"），导致苏晚在不同场景中外观不一致。修复后应在 style prefix 之后注入 appearance 描述。
- **场景 3（speaker: 林舟）**：当前 prompt 不包含林舟的外观描述（如 "short dark hair, black jacket, tall young man"），导致林舟在场景 1（旁白描述他）和场景 3（他说话）中外观可能完全不同。修复后应注入 appearance。
- **场景 1（speaker: narrator）**：旁白场景，不应注入任何角色外观描述，行为不变。
- **场景 4（speaker: narrator）**：纯风景旁白场景，不应注入角色外观描述，行为不变。
- **角色无 appearance 字段**：如果 `characters.yaml` 中某角色未定义 `appearance`，prompt 拼接逻辑与当前完全一致，不报错。

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- 当 speaker 为 "narrator" 时，prompt 拼接逻辑与当前完全一致，不注入任何角色外观描述
- 当角色在 `characters.yaml` 中未定义 `appearance` 字段时，prompt 拼接逻辑与当前完全一致
- SD WebUI 不可用时，fallback 占位图生成逻辑不受影响
- `pipeline.yaml` 中未配置 IP-Adapter 时，使用纯 txt2img 方式生成，不尝试调用 IP-Adapter
- 现有 prompt 组成部分（style prefix、visual prompt、shot type、emotion）的拼接顺序和内容不变
- 鼠标点击、语音生成、动画、视频合成等其他管线阶段完全不受影响

**Scope:**
所有不涉及"角色场景 prompt 构建"和"IP-Adapter 参考图注入"的输入和流程应完全不受此修复影响。包括：
- speaker 为 narrator 的场景
- 无 appearance 字段的角色场景
- SD 不可用时的 fallback 流程
- 其他管线阶段（TTS、动画、合成、字幕）

## Hypothesized Root Cause

基于 bug 分析，根本原因如下：

1. **`characters.yaml` 缺少视觉外观字段**：当前角色配置仅包含语音相关字段（voice_type, emotion_map），没有 `appearance` 字段来存储角色的固定视觉描述。这是数据层面的缺失。

2. **`build_sd_prompt()` 不读取角色配置**：该函数签名为 `build_sd_prompt(scene, styles_config, style_name)`，只接收 scene 和 styles 配置，不接收 characters 配置，也不根据 scene.speaker 查找角色外观信息。这是逻辑层面的缺失。

3. **`generate_image_sd()` 仅支持 txt2img**：该函数只构建 txt2img payload 并调用 `/sdapi/v1/txt2img`，不支持通过 IP-Adapter 扩展注入参考图。这限制了角色一致性的增强手段。

4. **`pipeline.yaml` 无 IP-Adapter 配置**：管线配置中没有 IP-Adapter 相关的开关和参数（如 enabled、model_name、weight、reference_images 路径），无法让用户控制是否启用参考图增强。

## Correctness Properties

Property 1: Fault Condition - 角色外观 Prompt 注入

_For any_ scene where speaker is not "narrator" AND the speaker exists in characters.yaml AND the character has an "appearance" field, the fixed `build_sd_prompt()` SHALL include the character's appearance description in the positive prompt, positioned after the style prefix and before the visual prompt.

**Validates: Requirements 2.1, 2.2, 2.3**

Property 2: Preservation - 非角色场景 Prompt 不变

_For any_ scene where speaker is "narrator" OR the speaker has no "appearance" field in characters.yaml, the fixed `build_sd_prompt()` SHALL produce exactly the same positive and negative prompt as the original function, preserving all existing prompt construction behavior.

**Validates: Requirements 3.1, 3.2, 3.5**

Property 3: Preservation - SD 不可用时 Fallback 不变

_For any_ execution where SD WebUI is not available, the fixed `generate_all_images()` SHALL produce placeholder images using the same logic as the original function, regardless of character appearance or IP-Adapter configuration.

**Validates: Requirements 3.3, 3.4**

## Fix Implementation

### Changes Required

假设根因分析正确，需要以下改动：

**File**: `config/characters.yaml`

**Changes**:
1. **新增 `appearance` 字段**：为每个角色（narrator 除外）添加可选的 `appearance` 字段，包含英文外观描述（发型、服装、体型、显著特征等），直接用于 SD prompt 拼接。

示例：
```yaml
林舟:
  voice_type: "BV123_streaming"
  description: "男主角，年轻男声"
  appearance: "young man, short dark hair, black jacket, white shirt, tall and slender"
  emotion_map:
    ...

苏晚:
  voice_type: "BV104_streaming"
  description: "女主角，温柔女声"
  appearance: "young woman, long black hair, white dress, slender figure, gentle eyes"
  emotion_map:
    ...
```

---

**File**: `config/pipeline.yaml`

**Changes**:
2. **新增 `ip_adapter` 配置块**：在 `image` 配置下新增 IP-Adapter 相关配置，默认关闭。

示例：
```yaml
image:
  provider: "sd_webui"
  api_url: "http://127.0.0.1:7860"
  style: "anime_cinematic"
  batch_size: 1
  timeout: 600
  ip_adapter:
    enabled: false
    model: "ip-adapter-plus_sd15.safetensors"
    weight: 0.6
    reference_dir: "assets/reference_images"
```

---

**File**: `scripts/03_generate_images.py`

**Function**: `build_sd_prompt()`

**Specific Changes**:
3. **新增 `characters_config` 参数**：函数签名改为 `build_sd_prompt(scene, styles_config, style_name, characters_config=None)`，保持向后兼容。

4. **注入角色外观描述**：在函数内部，当 `characters_config` 不为 None 时，根据 `scene["speaker"]` 查找角色配置，若角色存在且有 `appearance` 字段，将其插入 prompt parts 列表中 style prefix 之后、visual prompt 之前。

修改后的 prompt 拼接顺序：`style prefix + [appearance] + visual prompt + shot + emotion`

**Function**: `generate_image_sd()`

**Specific Changes**:
5. **新增 IP-Adapter 支持**：函数签名新增 `ip_adapter_config=None` 和 `reference_image_path=None` 参数。当 IP-Adapter 启用且参考图存在时，在 payload 中添加 `alwayson_scripts` 字段，通过 SD WebUI 的 ControlNet/IP-Adapter 扩展接口注入参考图。

**Function**: `generate_all_images()`

**Specific Changes**:
6. **加载角色配置**：在函数开头新增加载 `characters.yaml` 的逻辑，新增 `load_characters()` 辅助函数。

7. **传递角色配置给 `build_sd_prompt()`**：调用时传入 characters_config 参数。

8. **IP-Adapter 参考图查找与传递**：当 IP-Adapter 启用时，根据 scene.speaker 在 `reference_dir` 中查找对应角色的参考图（如 `assets/reference_images/林舟.png`），传递给 `generate_image_sd()`。

## Testing Strategy

### Validation Approach

测试策略分两阶段：首先在未修复代码上运行探索性测试，确认 bug 存在并验证根因假设；然后在修复后验证 fix 正确性和行为保持。

### Exploratory Fault Condition Checking

**Goal**: 在未修复代码上复现 bug，确认根因分析。如果探索性测试未能复现预期的 bug 模式，需要重新假设根因。

**Test Plan**: 构造包含角色 speaker 的场景，调用 `build_sd_prompt()`，断言返回的 prompt 中不包含任何角色外观描述。在未修复代码上运行，预期测试通过（因为 bug 确实存在——prompt 中确实没有外观描述）。

**Test Cases**:
1. **角色场景 Prompt 缺失外观**：构造 speaker 为 "林舟" 的场景，调用 `build_sd_prompt()`，验证返回的 prompt 中不包含任何外观关键词（在未修复代码上应通过，确认 bug 存在）
2. **多角色场景外观漂移**：构造多个 speaker 为同一角色的场景，验证各场景 prompt 之间没有共同的角色外观锚点（在未修复代码上应通过）
3. **IP-Adapter 不支持**：验证 `generate_image_sd()` 的 payload 中不包含 `alwayson_scripts` 字段（在未修复代码上应通过）

**Expected Counterexamples**:
- `build_sd_prompt()` 返回的 prompt 中完全没有角色外观描述
- 函数签名中不接受 characters_config 参数
- `generate_image_sd()` 的 payload 中无 IP-Adapter 相关字段

### Fix Checking

**Goal**: 验证对所有满足 bug condition 的输入，修复后的函数产生正确行为。

**Pseudocode:**
```
FOR ALL scene WHERE isBugCondition(scene) DO
  positive, negative := build_sd_prompt_fixed(scene, styles, style_name, characters)
  character := characters[scene.speaker]
  ASSERT character["appearance"] IN positive
  ASSERT positive.index(style_prefix) < positive.index(character["appearance"]) < positive.index(visual_prompt)
END FOR
```

### Preservation Checking

**Goal**: 验证对所有不满足 bug condition 的输入，修复后的函数与原函数产生完全相同的结果。

**Pseudocode:**
```
FOR ALL scene WHERE NOT isBugCondition(scene) DO
  ASSERT build_sd_prompt_original(scene, styles, style_name) == build_sd_prompt_fixed(scene, styles, style_name, characters)
END FOR
```

**Testing Approach**: 推荐使用 Property-Based Testing 进行 preservation checking，因为：
- 可自动生成大量测试用例覆盖输入域
- 能捕获手动单元测试可能遗漏的边界情况
- 对非 bug 输入的行为不变性提供强保证

**Test Plan**: 先在未修复代码上观察 narrator 场景和无 appearance 角色场景的 prompt 输出，然后编写 property-based test 验证修复后这些场景的输出不变。

**Test Cases**:
1. **Narrator 场景 Prompt 保持**：验证 speaker 为 "narrator" 的场景，修复前后 `build_sd_prompt()` 输出完全一致
2. **无 Appearance 角色 Prompt 保持**：验证角色无 `appearance` 字段时，修复前后 prompt 输出完全一致
3. **SD 不可用 Fallback 保持**：验证 SD 不可用时，修复前后 `generate_all_images()` 均生成占位图，行为一致
4. **无 IP-Adapter 配置时行为保持**：验证 `pipeline.yaml` 中无 `ip_adapter` 配置时，`generate_image_sd()` 仅使用 txt2img，payload 与修复前一致

### Unit Tests

- 测试 `build_sd_prompt()` 在有 appearance 角色场景下正确注入外观描述
- 测试 `build_sd_prompt()` 在 narrator 场景下不注入外观描述
- 测试 `build_sd_prompt()` 在角色无 appearance 字段时不注入外观描述
- 测试 appearance 描述在 prompt 中的位置（style prefix 之后、visual prompt 之前）
- 测试 `generate_image_sd()` 在 IP-Adapter 启用时 payload 包含正确的 alwayson_scripts
- 测试 `generate_image_sd()` 在 IP-Adapter 未启用时 payload 与原始一致
- 测试 `load_characters()` 正确加载角色配置

### Property-Based Tests

- 随机生成场景配置（不同 speaker、有无 appearance），验证 prompt 注入逻辑的正确性
- 随机生成非 bug condition 场景，验证修复前后 prompt 输出完全一致（preservation）
- 随机生成 IP-Adapter 配置组合（enabled/disabled、有无参考图），验证 payload 构建的正确性

### Integration Tests

- 端到端测试：加载真实的 storyboard.json 和 characters.yaml，验证所有场景的 prompt 生成正确
- 测试 IP-Adapter 参考图查找逻辑（参考图存在/不存在）
- 测试完整的 `generate_all_images()` 流程（使用 mock SD API），验证角色场景和旁白场景的处理正确
