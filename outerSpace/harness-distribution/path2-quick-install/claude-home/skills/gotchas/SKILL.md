---
name: gotchas
description: 沉淀使用 Claude Code 过程中踩过的坑、总结的教训、反复出现的问题模式。Agent 遇到类似任务时应主动读取此 skill 避免重蹈覆辙。
---

# Gotchas · 踩坑沉淀

> 本文件由 `~/.claude/hooks/gotchas-prompt.sh` 在 session 结束时按需追加（用户弹窗确认）。
> 每条记录带日期，方便后续复盘和清理。
> **按月审查**：过时的坑应主动删除（过时的指令比没有指令更危险）。

## 消费方式

- Agent 在开始类似任务前应 `Read` 此文件，检查是否有相关踩坑记录
- `/harness-retro` 时通读一遍，把反复出现的 gotcha 升级为 hook 或全局 CLAUDE.md 条款
- 超过 6 个月未触发的 gotcha 可以考虑归档或删除

## 记录规范

每条记录应包含：
- 日期
- 简短的问题描述
- 教训 / 应对方式

---
<!-- 下面是自动追加区 -->
