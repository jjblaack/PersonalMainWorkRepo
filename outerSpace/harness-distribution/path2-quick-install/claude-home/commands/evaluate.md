---
description: 进入独立评估阶段。调用 evaluator agent 在独立 context 里按 eval-rubric 对 coding 产出打分。
---

# /evaluate · 评估阶段

你现在进入**独立评估阶段**。

## 关键前提

- 本 session 必须是**新开的、干净的 context**。如果你是从 coding session 继续的，停下来请用户开新 session。
- Evaluator 必须独立 —— 这是 Harness 设计的核心原则之一，自评会产生确认偏差。

## 做什么

1. 调用 `evaluator` agent
2. 用户应提供：
   - 被评估的代码范围（git diff / commit hash / 文件列表）
   - plan 阶段的验收标准文档
3. evaluator 会：
   - 读 `eval-rubric` skill 锚定六维度
   - 实际运行可执行的 test_steps
   - 逐维度打分
   - 必要时派生 `code-reviewer` / `security-reviewer` subagent
   - 产出标准格式的评估报告

## 判决处置

- **PASS** → 报告存档，可合并
- **PASS-WITH-NOTES** → 合并前用户确认 Minor 问题是否当场修还是记技术债
- **WARN** → 打回给用户（新开 coding session 修复）
- **BLOCK** → Critical 问题必须修，切 session 回到 coding 流程

## 报告存档位置

- 默认：项目的 `docs/plan/<同一 plan 目录>/evaluation.md`
- 多次评估时加版本后缀 `evaluation-v1.md`、`evaluation-v2.md`
