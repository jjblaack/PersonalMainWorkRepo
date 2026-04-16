---
description: 进入规划模式。调用 planner agent 产出实现规划+验收标准+commit 规划三份文档。
---

# /plan · 规划阶段

你现在进入**规划阶段**。本阶段**禁止写代码**。

## 铁律

本次规划严格遵循 `~/.claude/CLAUDE.md` 的协作铁律：**谋而后动、缺信息就问、少即是多**。

## 做什么

1. 调用 `planner` agent
2. 将用户本次的需求和（可选的）个人描述转给 planner
3. planner 会按流程：复述 → 等确认 → 提问 → 等确认 → 摸项目现状 → 给规划初稿 → 等确认 → 产出三份文档

## 输出位置建议

三份文档默认输出到：
- 当前项目的 `docs/plan/YYYY-MM-DD-<功能简称>/` 下
- 分为：`requirement.md`（需求交付物）、`design.md`（设计文档）、`commit-plan.md`（commit 规划）

如果当前不在项目里或用户另有要求，以用户指示为准。

## 完成后

- 提示用户：**切换一个新 session 再用 `/code` 进入编码阶段**（保持独立 context）
- 不要在 plan session 里直接开始 coding
