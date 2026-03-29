---
name: maw-spec
description: 生成或修订 SPEC.md，把 PRD 转成可实现的技术规格与风险清单。用于进入方案阶段、需要接口/数据流设计、或实现前需要冻结契约时。
argument-hint: "[目标或模块]"
disable-model-invocation: true
context: fork
agent: maw-architect
---

目标：把 PRD 转成可实现、可验证、可评审的 SPEC，并把技术风险与依赖显式化。

输入：
- $ARGUMENTS（可为空）

执行步骤：
1. 确保协议目录是 `.claude/protocol/`；不存在则创建最小骨架文件
2. 读取 `.claude/protocol/PRD.md` 与 `.claude/protocol/STATUS.md`
3. 更新 `.claude/protocol/SPEC.md`，至少包含：架构/数据流、接口契约、错误策略、鉴权、幂等、可观测性、迁移策略
4. 将所有不确定性变成 TODO，并在 `STATUS.md` 里标记阻塞与风险

输出：
- 修改完成后输出简短摘要：SPEC 变更点、风险与缓解、STATUS 更新点
