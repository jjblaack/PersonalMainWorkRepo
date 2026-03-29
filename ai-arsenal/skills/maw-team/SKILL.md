---
name: maw-team
description: 基于文档驱动 + teamwork(Agent Teams) 启动并编排多智能体交付。用于需要并行探索、跨层改动、或复杂任务需要拆分成可并行单元时。
argument-hint: "<交付目标>"
disable-model-invocation: true
context: fork
agent: maw-lead
---

目标：用 Team lead 的方式启动/编排 teamwork，把协作消息收敛为协议文档与可验收交付物。

输入：
- 交付目标：$0

执行步骤：
1. 确保协议目录 `.claude/protocol/` 存在；若不存在则创建最小骨架文件：`PRD.md`、`SPEC.md`、`TEST_PLAN.md`、`STATUS.md`
2. 读取并对齐协议现状，明确当前阶段（Requirements / Spec / Implementation / Review / Done）
3. 如果 Agent Teams 可用：
   - 创建一个 agent team，角色建议：Analyst、Architect、Coder、Reviewer
   - 为每个角色分配“文件所有权”与“只写哪些文件”的硬约束
   - 在共享任务列表里拆出可并行任务，并设置依赖关系（例如：SPEC 完成前阻塞实现任务）
4. 如果 Agent Teams 不可用：
   - 用项目内 subagents（`.claude/agents/`）按阶段串行推进：maw-analyst → maw-architect → maw-coder → maw-reviewer
5. 明确冲突控制与收敛点：
   - 避免同文件并行写
   - 只允许 lead 做最终集成与跨文档一致性校对
6. 在 `STATUS.md` 写清：Current_Step、Blockers、Decisions、Risks、Done，并在每个阶段完成后更新

输出：
- 给出一个可直接复制执行的“团队启动提示词”（用于创建 team）
- 给出一个初始任务列表（5–20 条，含依赖）
- 给出本次迭代的验收门禁清单
