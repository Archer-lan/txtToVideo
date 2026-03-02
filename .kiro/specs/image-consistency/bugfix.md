# Bugfix Requirements Document

## Introduction

AutoNovel2Video 项目在生成小说视频时，每个场景的图片由 Stable Diffusion 独立生成，缺乏角色外观一致性保障机制。当前 `characters.yaml` 仅包含语音映射（voice_type, emotion_map），没有视觉外观描述字段；`build_sd_prompt()` 函数在拼接 prompt 时只使用 style prefix + visual prompt + shot + emotion，不包含任何角色外观信息。这导致同一角色在不同场景中的发型、服装、体型等外观特征随机变化，画风也会在场景间漂移，严重影响视频的视觉连贯性。

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN 同一角色（如"林舟"）出现在多个场景中 THEN 系统为每个场景独立生成图片，角色的发型、服装、体型等外观特征在不同场景间随机变化，无法保持一致

1.2 WHEN `build_sd_prompt()` 为包含角色的场景构建 prompt THEN 系统仅拼接 style prefix、visual prompt、shot type 和 emotion，不注入任何角色固定外观描述，导致 Stable Diffusion 每次自由发挥角色外观

1.3 WHEN `characters.yaml` 中定义角色配置 THEN 系统仅存储语音相关字段（voice_type, emotion_map），不包含任何视觉外观描述字段（如发型、服装、体型等），无法为图片生成提供角色外观锚点

1.4 WHEN 用户希望通过 IP-Adapter 参考图进一步增强角色一致性 THEN 系统不支持 IP-Adapter 参考图注入，`pipeline.yaml` 中无相关配置项，图片生成流程无法将参考图传递给 SD WebUI

### Expected Behavior (Correct)

2.1 WHEN 同一角色出现在多个场景中 THEN 系统 SHALL 自动将该角色的固定外观描述（发型、服装、体型等）注入到每个相关场景的 prompt 中，确保角色外观在不同场景间保持一致

2.2 WHEN `build_sd_prompt()` 为包含角色的场景构建 prompt THEN 系统 SHALL 从 `characters.yaml` 中读取该场景 speaker 对应角色的外观描述，并将其拼接到 prompt 中（位于 style prefix 之后、visual prompt 之前）

2.3 WHEN `characters.yaml` 中定义角色配置 THEN 系统 SHALL 支持 `appearance` 字段，包含角色的固定视觉外观描述（如发型、服装、体型、显著特征等），该字段为可选项，缺失时不影响现有流程

2.4 WHEN 用户在 `pipeline.yaml` 中启用 IP-Adapter 且提供了角色参考图路径 THEN 系统 SHALL 在调用 SD WebUI API 时通过 IP-Adapter 扩展将参考图注入生成过程，作为角色一致性的可选增强手段

### Unchanged Behavior (Regression Prevention)

3.1 WHEN `characters.yaml` 中的角色没有定义 `appearance` 字段 THEN 系统 SHALL CONTINUE TO 正常生成图片，prompt 拼接逻辑与当前行为一致，不报错不中断

3.2 WHEN 场景的 speaker 为 "narrator"（旁白）THEN 系统 SHALL CONTINUE TO 按现有逻辑生成图片，不注入任何角色外观描述

3.3 WHEN Stable Diffusion WebUI 不可用 THEN 系统 SHALL CONTINUE TO 生成占位图片作为 fallback，不因新增的角色外观逻辑而中断

3.4 WHEN `pipeline.yaml` 中未配置 IP-Adapter 相关选项 THEN 系统 SHALL CONTINUE TO 使用纯 txt2img 方式生成图片，不尝试调用 IP-Adapter 扩展

3.5 WHEN 现有的 style prefix、shot type、emotion 等 prompt 组成部分 THEN 系统 SHALL CONTINUE TO 按原有顺序和逻辑拼接，新增的角色外观描述不覆盖或破坏已有 prompt 结构
