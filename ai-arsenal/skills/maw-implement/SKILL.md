---
name: maw-implement
description: 严格按 SPEC 实现代码与测试，并通过质量门禁。用于进入实现阶段、补齐测试、或修复失败的测试/检查时。
argument-hint: "[实现范围或任务描述]"
disable-model-invocation: true
context: fork
agent: maw-coder
---

目标：把 `.claude/protocol/SPEC.md` 落地为可运行交付物（代码 + 测试），并保持与 SPEC 一致。

输入：
- $ARGUMENTS（可为空）

执行步骤：
1. 读取 `.claude/protocol/SPEC.md` 与 `.claude/protocol/STATUS.md`
2. 若 SPEC 缺少关键契约信息，停止实现并在 `STATUS.md` 写明阻塞
3. 实现代码与测试，优先保证正确性与可验证性
4. 运行项目已有的测试与质量检查命令（如果仓库提供）
5. 将通过/失败结果与残留风险写入 `STATUS.md`

输出：
- 完成摘要：实现了哪些 SPEC 点、测试变化、门禁结果、STATUS 更新点
