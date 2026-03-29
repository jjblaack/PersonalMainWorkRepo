# 多智能体工作流说明文档（面向 Claude Code + Teamwork/Agent Teams）

## 1. 背景与目标

在 AI 辅助开发中，多智能体协作的价值不在“更多对话”，而在“并行探索 + 可追溯交付”。Claude Code 早期的多智能体实践往往依赖手工切换角色与文件传递，稳定但协调成本高。

随着 Claude Code 支持 teamwork（Agent Teams）模式（详见本仓库的 [agent-team.md](file:///Users/jett/Documents/sub_projects/auto_coding_test1/agent-team.md)），我们可以在不牺牲“文档可审计性”的前提下，引入：

- 共享任务列表（任务依赖、认领、完成态）
- 智能体之间直接消息（点对点/广播）
- Team lead 统一编排（拆任务、汇总、质量门禁）

本文档在原有“文档驱动协作”的基础上，升级为“文档作为系统记录 + Teamwork 作为协作总线”的混合架构。

## 2. 架构设计

### 2.1 核心理念：Artifact-First + Teamwork-Orchestrated

本工作流将协作分为两类信息流：

- **系统记录（Artifacts）**：决策、规格、验收标准、风险与结论，必须落在项目文件里，便于追踪与复用。
- **协作总线（Teamwork）**：任务拆分、状态推进、即时沟通、争议收敛，由 Agent Teams 的任务列表与消息系统承载。

原则：消息用于“推进协作”，文档用于“固化结果”。任何影响实现/验收的结论必须回写到文档。

### 2.2 组件与职责边界

在 Teamwork 模式下，一个团队由以下组件构成：

- **Team lead（主会话）**：创建团队、拆分任务、分配/认领策略、汇总结论、执行最终集成与验收。
- **Teammates（独立会话）**：各自维护独立上下文窗口，围绕任务产出明确交付物。
- **Shared task list（共享任务列表）**：统一状态机（pending / in progress / completed）与任务依赖。
- **Mailbox（消息系统）**：直接沟通、辩论式收敛、阻塞上报与验收通知。

### 2.3 推荐角色划分（与交付物绑定）

角色划分的关键不是“头衔”，而是“文件所有权 + 交付边界”。推荐按交付物拆分：

#### 2.3.1 需求分析（Analyst）
- 交付物：`PRD.md`
- 目标：需求闭环、范围边界、验收口径一致

#### 2.3.2 技术方案（Architect）
- 交付物：`SPEC.md`
- 目标：设计可实现、风险可控、依赖明确；将不确定性显式化

#### 2.3.3 实现与测试（Coder）
- 交付物：代码 + 自动化测试 + 必要的配置变更
- 目标：严格对齐 SPEC；优先通过测试与类型检查/静态检查

#### 2.3.4 评审与质量（Reviewer）
- 交付物：评审结论（可写入 `STATUS.md` 或直接在 PR/任务中结构化输出）
- 目标：安全性、可维护性、可观测性、测试覆盖的质量把关

#### 2.3.5 可选：对抗式审查（Devil’s Advocate）
- 交付物：风险清单/反例/边界条件
- 目标：主动“找茬”，避免团队过早收敛到错误假设

## 3. Claude Code 环境下的实施策略（含 Teamwork）

### 3.1 协议文件系统（项目内的“系统记录”）

建议在项目根目录使用统一协议目录存放协作文档：

- 推荐：`.claude/protocol/`
- 兼容旧命名：`.claudecode/protocol/`

文档集合建议最小化为：

- `PRD.md`：需求文档（范围、用户故事、验收标准、非功能指标）
- `SPEC.md`：技术规格（架构、数据流、接口、异常策略、迁移策略）
- `TEST_PLAN.md`：测试计划（测试维度、关键用例、回归范围）
- `STATUS.md`：状态跟踪（当前阶段、风险、待澄清问题、已决策事项）

### 3.2 Teamwork 启用与显示模式（最小必要信息）

Agent Teams 为实验功能，需显式开启（配置细节见 [agent-team.md](file:///Users/jett/Documents/sub_projects/auto_coding_test1/agent-team.md)）。

启用方式（示例）：

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

显示模式建议：

- **in-process**：无需额外依赖，适合快速开始
- **split panes**：适合长时间并行与频繁交互（依赖 tmux 或 iTerm2）

如需强制指定显示模式，可在设置中配置：

```json
{
  "teammateMode": "in-process"
}
```

### 3.3 团队启动与任务拆分模板

Team lead 的启动提示词建议包含三块：范围、角色、交付物路径。示例：

```text
创建一个 agent team 来完成 {目标}。
角色：
- Analyst：只负责补全/修订 .claude/protocol/PRD.md
- Architect：只负责补全/修订 .claude/protocol/SPEC.md
- Coder：只负责实现代码与测试，不修改 PRD/SPEC
- Reviewer：只做评审与风险清单，结论回写 STATUS.md
约束：
- 不在同一文件上并行写入，避免冲突
- 任何影响实现的结论必须回写到协议文档
```

任务拆分建议遵循：

- 任务粒度：一个任务产出一个明确交付物或一个可验收的增量
- 依赖显式化：SPEC 未完成时，阻塞实现类任务
- 并行最大化：先让 Analyst/Architect/Reviewer 并行探索，Coder 等 SPEC 基线稳定后进入实现

### 3.4 冲突与一致性策略（避免“并行写坏”）

并行协作最常见失败模式是“同文件覆盖”。推荐规则：

- 以“文件所有权”分工：PRD/SPEC/TEST_PLAN/STATUS 分别由固定角色写入
- 以“目录所有权”分工：实现阶段按模块/目录切分给不同实现者
- 以“合并点”收敛：只允许 Team lead 进行最终集成与跨文件一致性调整

### 3.5 质量门禁（可选：用 hooks 自动拦截）

当任务完成被标记为 completed 前，建议统一通过质量门禁：

- 必要门禁：测试通过、lint/类型检查通过
- 结构门禁：SPEC 与实现一致；新增接口有对应测试
- 风险门禁：Reviewer 的高风险项必须显式处置或记录为已接受风险

若使用 Claude Code hooks，可考虑：

- `TeammateIdle`：队友即将 idle 时触发，发现遗漏则退回继续
- `TaskCompleted`：任务即将完成时触发，门禁不通过则阻止完成态

### 3.6 并行协作最佳实践（降低协调成本）

- 控制队友规模：一般 3–5 个更稳，更多会带来通信与 token 成本爆炸
- 拆任务而不是拆角色：当某一角色被阻塞时，新增“可并行任务”比新增队友更有效
- 少用广播：广播成本随人数线性增长；优先点对点同步，并附“文档位置”
- 等队友产出再推进：lead 不要过早接管实现，避免并行探索浪费
- 避免同文件并行写：即使任务列表有锁，编辑冲突依然会造成覆盖与回滚成本

### 3.7 Teamwork 运行时落盘位置（便于排障与审计）

Agent Teams 的团队与任务会存储在本机本地目录（具体路径与格式见 [agent-team.md](file:///Users/jett/Documents/sub_projects/auto_coding_test1/agent-team.md)）：

- Team config：`~/.claude/teams/{team-name}/config.json`
- Task list：`~/.claude/tasks/{team-name}/`

## 4. 人机协作与验收机制

### 4.1 人的介入点（从“手工盯着”转为“门禁验收”）

- **PRD 验收**：范围与验收标准确认（避免做错方向）
- **SPEC 验收**：关键设计决策确认（避免做对方向但不可落地）
- **实现验收**：测试/质量门禁通过后再进行代码验收

### 4.2 风险任务的“先计划后实现”

对高风险变更（架构调整、迁移、鉴权、数据模型变化），建议要求队友先提交计划并由 lead 审批后再改代码（Agent Teams 支持“Require plan approval”模式，细节见 [agent-team.md](file:///Users/jett/Documents/sub_projects/auto_coding_test1/agent-team.md)）。

### 4.3 反馈与回滚策略

反馈必须落点到可行动项：

- 需求误解：修订 PRD，并在 STATUS 记录“变更原因”
- 设计不合理：修订 SPEC，并补充替代方案与取舍
- 实现偏离：修订代码与测试，并在 PR/任务中关联到 SPEC 章节

## 5. 上下文管理（面向 Teamwork 的现实约束）

Teamwork 的关键约束是：队友不会继承 lead 的对话历史，只会加载项目上下文与 spawn prompt。因此，需要把“可复用上下文”外置到文件。

### 5.1 分层存储（摘要 + 证据）

- `context_index.md`：目标、阶段、关键决策、未决问题索引
- `context_detail.md`：关键原文、重要日志、证据与推导过程

### 5.2 启动协议（适用于 lead 与所有 teammates）

```text
Initialization Protocol:
1. 读取 .claude/protocol/STATUS.md 了解当前阶段与阻塞项
2. 读取 PRD/SPEC/TEST_PLAN 中与本任务相关的章节（只读优先）
3. 仅在需要时读取 context_detail.md 的末尾内容恢复语境
4. 产出结论必须回写到对应协议文档；仅在消息里同步“变更摘要 + 指向文档位置”
```

### 5.3 滑动窗口策略

- 默认只读：`context_index.md` 全量 + `context_detail.md` 末尾片段
- 按需检索：当摘要指向某历史决策时，再精确查找旧段落

## 6. 示例：用 Teamwork 执行一个典型功能交付

### 6.1 启动一个并行团队（需求/方案/评审先行）

```text
创建一个 agent team 来交付“新增 Web API：/v1/orders 查询接口”。
分 4 个队友：
- Analyst：补全 PRD.md 的接口需求与验收标准
- Architect：补全 SPEC.md 的接口定义、鉴权、错误码、性能指标
- Reviewer：从安全与回归风险角度审查，并更新 STATUS.md 风险项
- Coder：等待 SPEC 基线稳定后再实现（先只准备测试策略）
```

### 6.2 需求不明确时的“向前追问”闭环

当 Architect 发现需求缺口：

1. 在 `PRD.md` 加入 `[TODO: 需要澄清：并发量级/分页上限/一致性要求]`
2. 在 `STATUS.md` 标记 `Current_Step: Requirements_Refinement` 与阻塞原因
3. 通过消息通知 Analyst（点对点，而非广播），并附上文档位置

## 7. 总结：升级带来的收益与新风险

### 7.1 收益

- **并行探索更有效**：任务列表 + 直接消息降低协调摩擦
- **系统记录更稳定**：文档固化结论，避免上下文漂移
- **质量门禁更可靠**：可在任务完成态引入自动化校验与拦截

### 7.2 新风险与局限（需要显式管理）

- **Token 成本线性增长**：队友越多成本越高，应按任务独立性扩缩
- **会话恢复限制**：部分模式下 `/resume` 不能恢复队友（细节见 [agent-team.md](file:///Users/jett/Documents/sub_projects/auto_coding_test1/agent-team.md)）
- **并行写入冲突**：必须坚持文件/目录所有权与 lead 最终集成策略
- **状态滞后与卡住**：任务状态可能延迟更新，必要时需要人工核对并纠正
- **关闭与清理成本**：队友可能要完成当前动作才能退出；清理团队应由 lead 统一执行
- **团队形态限制**：一个会话只能管理一个团队，且不支持嵌套团队
