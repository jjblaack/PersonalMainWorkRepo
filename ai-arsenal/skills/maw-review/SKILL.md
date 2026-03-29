---
name: maw-review
description: 按工作流标准做代码评审与风险审计，并把 Must-fix/Should-fix 结论结构化输出。用于合并前评审、质量门禁前复核、或排查返工风险时。
argument-hint: "[评审范围，例如路径/模块/PR 描述]"
disable-model-invocation: true
context: fork
agent: maw-reviewer
---

目标：用第三方视角识别高风险缺陷，并输出可执行的修复建议或风险记录。

输入：
- $ARGUMENTS

执行步骤：
1. 读取 `.claude/protocol/PRD.md`、`.claude/protocol/SPEC.md`、`.claude/protocol/STATUS.md`
2. 定位本次变更涉及的文件与测试
3. 按优先级评审：规格一致性 → 安全性 → 正确性 → 可维护性 → 可观测性 → 测试
4. 输出结构化结论（Must-fix / Should-fix / Nice-to-have），必要时把阻塞与风险写入 `STATUS.md`

输出：
- 结构化评审清单 + 关键证据（引用文件路径与要点）
