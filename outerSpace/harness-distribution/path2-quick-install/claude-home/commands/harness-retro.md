---
description: Sprint 复盘 Harness 的缺口。检查 gotchas、CLAUDE.md 准确性、hook 有效性、Agent 卡壳频次，识别改进点。
---

# /harness-retro · Sprint Harness 复盘

## 什么时候跑

- 每 2 周一次（固定节奏）
- Sprint 结束前
- 觉得"最近 Agent 卡壳特别多"时

## 复盘流程

请依次回答并记录：

### 1. Gotchas 清点
- Read `~/.claude/skills/gotchas/SKILL.md`
- 列出本周期新增的 gotcha 条目
- 判断：
  - 有没有**反复出现**的？→ 应升级为全局 CLAUDE.md 的铁律 或 hook 规则
  - 有没有**过时**的（环境变了、栈变了）？→ 删除
  - 有没有**模糊/含糊**的？→ 重新表述清楚

### 2. CLAUDE.md 准确性审查
- 通读 `~/.claude/CLAUDE.md`，找出：
  - 不再准确的描述
  - 该补充但缺失的（对应近期反复卡壳的场景）
  - 过于啰嗦可以精简的

### 3. Hook 有效性评估
- 回顾：`secret-scan` / `dangerous-command` 被触发过几次？
- 有没有**误报**？→ 调整模式精度
- 有没有**漏报**（本该拦但没拦）？→ 补模式
- 有没有 hook 被频繁临时禁用？→ 检查是否真的有用

### 4. Agent 卡壳 / 产出不佳的案例
- 本周期 Agent 哪里卡壳了 / 产出不符合预期？
- **不要归咎于"模型不行"**。按飞轮思维：这是 Harness 缺口的信号。
- 对每个案例，决定补的位置：
  - 是 CLAUDE.md 没说清楚？→ 补一条铁律
  - 是某个 skill 缺？→ 新建 skill（用 `skill-creator` 辅助）
  - 是没有 hook 强制？→ 加 hook
  - 是 agent prompt 不够精确？→ 改 agent

### 5. 重复手动操作识别
- 本周期有没有超过 2 次做的相同操作？
- → 该做成 slash command 或 skill

### 6. 模型能力变化跟进
- 有没有新的 Claude 版本发布？
- 某些原来需要的 Harness 机制是否可以简化？
  - 例：context compaction 变强后，某些手动 reset 可能不再需要
  - 例：工具调用变准后，某些强制确认可放松

## 输出

一份 `harness-retro-YYYY-MM-DD.md`，放在 `~/.claude/retros/`（不存在就创建）。
明确列出：**这次要改动的 Harness 位置 + 动作**。

改动后，用 `skill-creator` 或直接 Edit 落地；更新 CLAUDE.md 时标注变更日期和原因。
