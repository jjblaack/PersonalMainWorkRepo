# 深度适配路径 · Bootstrap Prompt

> 使用方式：在**分发包根目录下**启动 Claude Code，然后把下面 `---` 之间的整段内容复制粘贴给 Claude。

---

你好 Claude。我拿到了一份 harness 分发包，想走"深度适配"路径，为我自己搭一套贴合我工作习惯的 `~/.claude/` 配置。

## 我把材料都放在你当前工作目录下了

- `path1-deep-adaptation/soul-template.md` —— 空的 Soul 模板（我可能填完了，也可能还没填）
- `path1-deep-adaptation/soul-example-yijiang.md` —— 原作者 yijiang 的 Soul 完整版，作为参考范例
- `path1-deep-adaptation/harness-manual-原稿.md` —— harness 工程方法论的知识源（信息量大但杂，背景读物，别全搬进 CLAUDE.md）
- `path1-deep-adaptation/builder-guide.md` —— 精简版搭建指南（你主要照这个做）
- `path1-deep-adaptation/agent-steps.md` —— **你的执行步骤参考，里面列了所有你必须问我确认的检查点，不得跳过**

## 我希望你遵守的纪律

1. 严格按 `agent-steps.md` 的流程走，所有带 🛑 的检查点必须停下来问我
2. **协作铁律**（这是最核心的，比任何工具选择都重要）：
   - **谋而后动**：接到需求先复述你的理解 → 等我确认 → 给出方案 → 等我确认 → 才动手
   - **缺信息就问**：任何不清楚的点主动问我，不要脑补/假设/编造
   - **少即是多**：只做被明确要求的事，不顺手"优化"、不重构未被要求的代码
3. 任何会动到我 `~/.claude/` 下已有文件的操作，先列清楚要动什么、影响什么，**等我明确说"可以"**
4. **先备份后改动**：改动前先把整个 `~/.claude/` 打包快照

## 请执行的第一步

Read 下面这 4 个文件：
1. `path1-deep-adaptation/agent-steps.md`
2. `path1-deep-adaptation/builder-guide.md`
3. `path1-deep-adaptation/soul-template.md`
4. `path1-deep-adaptation/soul-example-yijiang.md`

读完后回复我：
- 你理解的本次任务目标是什么
- 你准备分哪几个阶段推进、每个阶段会问我什么
- 你需要我先做哪些前置准备（比如填 Soul 模板）

**不要直接开始装任何东西。** 我看到你的理解和计划之后，会告诉你能不能开始。
