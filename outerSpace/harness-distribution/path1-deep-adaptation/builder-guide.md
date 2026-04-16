# Harness 搭建者指南（面向 agent）

> 本文档是给帮用户搭 harness 的 agent 看的精简提纲。
> 需要更深入的背景（五层架构的来龙去脉、Anthropic 团队的实践总结、各项研究引用），读 `harness-manual-原稿.md`。
> **原则：原稿是背景读物，别整段搬进 CLAUDE.md。CLAUDE.md 必须 ≤ 60 行。**

---

## 什么是 Harness

Harness = 让 AI 可靠工作的整个运行环境。不是单个配置文件，是**分层系统**，由以下几类组件组成：

- 上下文约束（`CLAUDE.md`，协作契约+绝佳实践）
- 确定性执行（`hooks`，硬护栏，不靠 AI 自觉）
- 可复用技能（`skills`，按需加载的知识模块）
- 专项子智能体（`agents`，上下文隔离的专家）
- 工作流入口（`commands`，slash 命令）
- 运行时配置（`settings.json`，注册 hook + 权限 + env）

## 五层架构（全局 harness 主要在 L2–L4）

```
L5 Org   settings.json · 权限策略 · model · attribution 规范
L4 Repo  CLAUDE.md · commands · hooks · skills · subagents
L3 记忆  feature_list · progress · git history（项目级，此次不搭）
L2 执行  hook 触发 · worktree · subagent
L1 模型  Claude 本体（不管）
```

**核心原则**：能在高层做的约束，不要下放到低层靠 AI 自觉。
**反例**：「禁止提交 secret」写在 CLAUDE.md 请求 AI 自律 = 废话；写成 pre-tool hook 硬拦 = 可靠。

## 本次要搭的全局组件清单

### 1. CLAUDE.md（全局协作契约，≤ 60 行）

结构固定：
- `## 我是谁`：一句话身份（来自 Soul）
- `## 协作铁律`：6 条左右，来自 Soul 的"和 AI 协作原则"
- `## 绝佳实践`：5–7 条，来自 Soul 的"工作习惯"
- `## 三段式工作流的触发阈值`：基于 Soul 的"工作流节奏"填
- `## 组件索引`：表格，指向 commands / agents / skills

**禁区**：全局 CLAUDE.md 只写"我和 AI 怎么协作"的元规则，不写项目知识（项目知识写在项目自己的 CLAUDE.md）。

### 2. hooks（确定性硬护栏）

- **`secret-scan.sh`** · PreToolUse/Bash
  检测 API key (sk-*, AKIA*, ghp_*)、私钥 blob、硬编码密码 → 硬拦 `exit 2`。硬编码 secret 没有"我就是要这样"的合理场景，zero-tolerance。

- **`dangerous-command.sh`** · PreToolUse/Bash
  检测 `rm -rf`、`git push --force`、`DROP TABLE` 等 → **不硬拦，用 osascript 弹窗把决策权交给用户**：
  - 用户点"允许" → `exit 0` 放行 + stderr 留痕
  - 用户点"拒绝"/超时/关闭 → `exit 2` 拦截
  - 默认按钮"拒绝"（safer default）

- **`gotchas-prompt.sh`** · Stop
  每次 session 结束用 osascript 弹输入框，用户输一句话追加到 `skills/gotchas/SKILL.md`（空输入=跳过）。

### 3. agents（子智能体，独立 context）

- **planner** · 接需求 + 个人描述，产出 `实现规划.md` + `验收标准.md` + `commit规划.md`
- **evaluator** · **必须独立 context**，按 `eval-rubric` skill 打分，输出 PASS / PASS-WITH-NOTES / WARN / BLOCK
- **code-reviewer** · 通用代码审查，多维度（安全/正确/可靠/可维护）
- **security-reviewer** · 专门扫 OWASP Top 10 + secret 泄露 + 权限缺失

### 4. skills（按需加载知识）

- **skill-creator** · Anthropic 原版（直接复制），创建新 skill 用
- **doc-templates** · 需求交付物 / 设计文档 / 架构文档三种模板。来自 Soul 的"文档只记源头"理念
- **eval-rubric** · evaluator 的评分维度准则，来自 Soul 的"评审维度"
- **gotchas** · 初始可以是空壳或从 Soul 的"常踩的坑"部分迁移进来，会被 hook 持续追加

### 5. commands（slash 入口）

- `/plan` → 调 planner agent
- `/code` → 进入编码阶段，强制拆步骤、适当派 subagent、每块让用户确认
- `/evaluate` → 调 evaluator agent（独立 context）
- `/harness-retro` → sprint 复盘，检查 gotchas + CLAUDE.md 准确性 + hook 有效性
- `/harness-audit` → 月度安全扫描

### 6. settings.json（严格增量合并，绝不整替）

需要追加：
- `PreToolUse` 里 `Bash` 匹配器的 hooks 数组，追加 `secret-scan.sh` 和 `dangerous-command.sh`
- `Stop` 的 hooks 数组，追加 `gotchas-prompt.sh`

**保留用户原有的**：Notification / Stop 声音 / 任何其他已存在的 permissions / env / model 配置。

## 三段式工作流（基于 Soul 的阈值定制）

```
用户需求
   ↓
/plan → planner agent（独立 session）→ 实现规划 + 验收标准 + commit 规划
   ↓
/code → 主 agent（按 commit 规划拆步骤，派 subagent，每块让用户确认）
   ↓
/evaluate → evaluator agent（独立 session！）→ 评估报告
```

用户的 Soul 决定阈值（什么规模触发三段、什么规模直接做、紧急修复怎么办）。搭建时请把阈值明确写进 CLAUDE.md 的"三段式工作流的触发阈值"章节。

## 搭建时的自检准则

1. **Soul 是唯一真理源**：任何配置都要能追溯到 Soul 的某条原则。如果 Soul 没提到但你想加，先问用户。
2. **少即是多**：CLAUDE.md ≤ 60 行 / 每个 skill ≤ 100 行 / 每个 agent.md ≤ 120 行。冗余是负债。
3. **CLAUDE.md 是唯一事实源**：绝佳实践写一次。agent 启动时继承 CLAUDE.md 的 context，**不要**在每个 `agents/*.md` 里重复复制绝佳实践。
4. **hook 是决定论**：能 hook 的约束不要写进 CLAUDE.md 请求 AI 自律。
5. **先备份，后改动**：改用户任何 `~/.claude/` 下文件前，先 `tar -czf` 整包快照。
6. **该问就问**：涉及删除/覆盖用户已有文件，**必须先列清楚 + 等明确授权**。
7. **文档精度优先**：INVENTORY 记"为什么这么建"，workflow-guide 记"什么场景怎么用"。别互相重复。
