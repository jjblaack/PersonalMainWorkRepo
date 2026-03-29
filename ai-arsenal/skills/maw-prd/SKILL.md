---
name: maw-prd
description: 生成或修订 PRD.md，并把待澄清问题显式化。用于开始需求阶段、需求不清需要补齐、或 PRD 需要更新时。
argument-hint: "[目标或问题描述]"
disable-model-invocation: true
context: fork
agent: maw-analyst
---

目标：把当前需求固化为可执行、可验收的 PRD，并让阻塞项可见。

输入：
- $ARGUMENTS（可为空；为空时以当前对话与仓库现状为准）

执行步骤：
1. 优先对齐路径：使用 `.claude/protocol/` 作为协议目录；若目录或文件不存在，创建最小骨架
2. 读取并更新 `.claude/protocol/PRD.md`，至少包含：范围、用户故事、验收标准、非功能指标、边界条件
3. 将所有不确定性写成 `[TODO: 需要澄清：… | 负责人：… | 截止：…]`
4. 同步更新 `.claude/protocol/STATUS.md`，写明 `Current_Step`、`Blockers`、`Decisions`、`Risks`

输出：
- 修改完成后输出简短摘要：PRD 更新点、TODO 变化、STATUS 更新点
