# Harness 清单与搭建实录

> 本文档记录**这套全局 Harness 搭了哪些东西、为什么这样搭、每个组件对应 Soul 的哪一条**。
> 维护人：yijiang
> 初始搭建时间：2026-04-16
> 搭建依据：
> - 主：`~/Desktop/AI+/outerSpace/我的coding-soul.md`
> - 辅：`~/Desktop/AI+/outerSpace/harness工作手册-草稿.md`
> - 素材库：`~/Desktop/AI+/outerSpace/source/`

---

## 一、搭建的顶层设计思想

### 1.1 为什么有这套 Harness？

Soul 开篇已定调：**"AI 时代，品味是最重要的，做已经不是问题，理解深度是关键。"**
这套 Harness 的目的不是"让 AI 会写代码"（它本来就会），而是**让我 yijiang 的品味和判断力，能可靠地作用到每一次 AI 协同产出上**。

Harness 是"马具"——给野马装上正确的方向控制。组件本身不重要，**组件承载的约束与意图**才是价值。

### 1.2 三条设计铁律（贯穿所有组件）

**铁律 1：Soul 是唯一真相源。**
Harness 手册和 source 里各种开源实践只是素材库。凡是与 Soul 冲突的，一律以 Soul 为准。Soul 的每一条都必须在组件里有落实点（见 §2 的映射表）。

**铁律 2：少即是多，精确优于完整。**
- source 里有 40+ skills、20+ agents，**没有一个全盘拉进来**
- 全局只放**跨项目通用**的东西；项目特定的留给项目级 CLAUDE.md
- 每个 agent prompt 都精简到不含冗余；删除了与全局 CLAUDE.md 重复的表述
- 语言/栈特定内容（React/Django/Spring…）**全部排除**（不在全局层面有意义）

**铁律 3：绝佳实践的单一真相源 = 全局 CLAUDE.md。**
这是搭建过程中**最关键的架构决策**。
- 所有 agent / command 的 prompt 都**不重复**写绝佳实践，只写"承接全局 CLAUDE.md"
- 原因：CLAUDE.md 会被自动注入到任何 session 和 subagent 的 context，重复写 = 双份信息源 = 必然漂移
- 想改协作规则、想添绝佳实践，**只改 CLAUDE.md 一处**，整套系统同步生效
- 这与 Soul 第 5 条"飞轮"直接对应：改一处就转动整台机器

### 1.3 我与 AI 的分工边界

| 我（yijiang）负责 | AI 负责 |
|---|---|
| Soul 的定义与演进 | 按 Soul 执行 |
| CLAUDE.md 的最终确认 | 按 CLAUDE.md 行事 |
| 架构决策、取舍判断 | 规划、实现、评估、执行 |
| 每个关键节点的"可以"/"不可以" | 阐述、提问、提议、等待 |
| gotchas 沉淀内容 | Stop hook 触发，AI 协助记录 |
| Harness 自身的演进方向 | 在 `/harness-retro` 时提出候选改动 |

---

## 二、Soul 每一条 → 组件映射表（完整逐条对照）

| Soul 条目 | 落实组件 | 备注 |
|---|---|---|
| §1 CLAUDE.md 是核心 | **全局 CLAUDE.md** | 全局只写"协作契约+绝佳实践"，不放项目知识 |
| §1 只记需求交付物、设计文档、架构文档 | **`doc-templates` skill** | 提供三种模板 |
| §2.1 plan/coding/evaluator 都应是独立 session | **3 个 slash command**（`/plan`、`/code`、`/evaluate`）分别拉起新 session | 每个 command 的模板里都会提示用户下一阶段切 session |
| §2.2 Plan 输入=产品需求+项目现状+相关skill+个人描述（+默认绝佳实践） | `planner` agent + 承接全局 CLAUDE.md（绝佳实践单一源） | 显式输入只剩：需求+个人描述（可选）；项目现状由 agent 自己摸；skill 按需加载；绝佳实践自动继承 |
| §2.2 Plan 输出=详细实现规划+验收标准+commit 规划 | `planner` agent 的三份产出格式（在 prompt 里强制） | 用 `doc-templates` 设计文档模板承载 |
| §2.3 Coding 拆步骤+调 subagent | `/code` command 的拆步骤规则+主动提议 subagent 指令 | 每完成一个 commit 单元就停下来确认 |
| §2.3 Coding 输出=代码+测试+说明+commit | `/code` command 的产出要求 | |
| §2.4 Evaluator 输入=代码+验收标准+评分维度+相关skill+个人描述+绝佳实践 | `evaluator` agent + `eval-rubric` skill | 评分维度单独沉淀成 skill，evaluator 必须引用 |
| §2.4 Evaluator 输出=评估报告+commit 评估 | `evaluator` agent 的输出格式要求 | |
| §3 一套装备 agent+skill+hook | 三类都搭了 | agent 4个 / skill 4个 / hook 3个 |
| §3.1 Hook 硬性条件：密码/rm/git push --force 等 | `secret-scan.sh` + `dangerous-command.sh` | 匹配 PreToolUse/Bash |
| §3.2 Skill 区分个人/项目/团队 | 全局只放跨项目通用 skill | 项目/团队 skill 放项目里，不进全局 |
| §3.3 Agent 上下文隔离 | `evaluator` 在独立 context / `code-reviewer` / `security-reviewer` 作为 subagent | |
| §4.1 TDD 要先调好运行环境 | `planner` agent prompt 强制：TDD 第 0 步规划测试环境验证 | 也在 `/code` 的 TDD 流程里重复 |
| §4.2 谋而后动：阐述→确认→方案→再确认→才动 | **全局 CLAUDE.md 铁律 1** | 所有 agent 自动继承 |
| §4.3 缺信息就问 | **全局 CLAUDE.md 铁律 2** | 所有 agent 自动继承 |
| §4.4 主动提议 subagent | **全局 CLAUDE.md 铁律 3** + `planner` / `/code` 的 prompt 再次强调 | |
| §4.5 最佳实践随代码和模型演进（飞轮） | `/harness-retro` command | 双周复盘，显式识别改进点 |
| §4.6.1 人 + agent 的 review | `code-reviewer` + `security-reviewer` subagent | |
| §4.6.2 多阶段 review（plan 方向 + coding 每块 + evaluator 整体） | 三段式本身 + `/code` 中每 2-3 commit 提议派 code-reviewer | |
| §4.6.3 agent review 多角度 | `eval-rubric` 的六维度 | |
| §4.7 月度 harness 安全扫描 | `/harness-audit` command | 定义扫描 checklist |
| §4.8 常见坑专区 + session 结束自动总结 | `gotchas` skill + `gotchas-prompt.sh` Stop hook（osascript 交互式弹窗） | 用户留空=skip，输入=追加 |
| §5 人的使用实践思想 | **`workflow-guide.md`** | 场景化操作手册 |
| §5.1 理解为什么有这些最佳实践 | 本文档 INVENTORY.md + workflow-guide.md 的"设计思想"章节 | |
| §5.2 何时 subagent / 何时切 session | workflow-guide.md 的 Part 3 决策点速查 | |

---

## 三、完整资产清单

### 3.1 文件树

```
~/.claude/
├── CLAUDE.md                         # 全局协作契约（~60 行，单一真相源）
├── INVENTORY.md                      # 本文档
├── workflow-guide.md                 # 详尽使用指南
├── settings.json                     # 增量更新（保留原 Notification + Stop 声音 + 新增 3 hook）
├── hooks/
│   ├── secret-scan.sh                # PreToolUse/Bash：拦 secret
│   ├── dangerous-command.sh          # PreToolUse/Bash：拦高危命令
│   └── gotchas-prompt.sh             # Stop：osascript 弹窗沉淀 gotcha
├── agents/
│   ├── planner.md                    # 规划 agent（原创，按 Soul 2.2）
│   ├── evaluator.md                  # 评估 agent（原创，按 Soul 2.4）
│   ├── code-reviewer.md              # 代码 review（砍栈特定，保通用框架）
│   └── security-reviewer.md          # 安全 review（原件保留）
├── skills/
│   ├── skill-creator/                # Anthropic 官方，原封复制
│   ├── doc-templates/                # 原创，三类文档模板
│   ├── eval-rubric/                  # 原创，六维度评分
│   └── gotchas/                      # 初始空壳，由 Stop hook 追加
├── commands/
│   ├── plan.md                       # /plan
│   ├── code.md                       # /code
│   ├── evaluate.md                   # /evaluate
│   ├── harness-retro.md              # /harness-retro
│   └── harness-audit.md              # /harness-audit
└── backups/
    └── pre-harness-YYYYMMDD-HHMMSS.tar.gz   # 搭建前全量备份
```

### 3.2 每个组件的简述

#### 3.2.1 顶层

| 文件 | 行数 | 类型 | 作用 |
|------|------|------|------|
| `CLAUDE.md` | ~60 | 原创 | 协作契约+绝佳实践的**单一真相源** |
| `settings.json` | - | 增量 | 保留原 Notification/Stop 声音，新增 3 个 hook 引用 |
| `INVENTORY.md` | 本 | 原创 | 清单+设计思想 |
| `workflow-guide.md` | ~800 | 原创 | 场景化使用指南 |

#### 3.2.2 Hooks

| 文件 | 触发 | 行为 | 理由 |
|------|------|------|------|
| `secret-scan.sh` | PreToolUse/Bash | 匹配 sk-/AKIA/ghp_/私钥/硬编码密码 模式 → exit 2 拦截 | Soul 3.1 安全硬约束 |
| `dangerous-command.sh` | PreToolUse/Bash | 匹配 rm -rf /*/ git push --force / DROP TABLE / fork bomb 等 → exit 2 拦截 | Soul 3.1 + Harness 手册 2.3 |
| `gotchas-prompt.sh` | Stop | osascript 对话框（30s 超时）询问是否沉淀；输入=追加到 gotchas/SKILL.md，留空=skip | Soul 4.8 session 结束自总结 |

#### 3.2.3 Agents

| 文件 | 出处 | 策略 | 关键改动 |
|------|------|------|---------|
| `planner.md` | 原创（参考 source/everything-claude-code/agents/planner.md 的结构） | **重写** | 按 Soul 2.2 的 I/O 规范；强调复述→确认→提问→确认→摸→给→确认循环；"绝佳实践"不重述，继承 CLAUDE.md |
| `evaluator.md` | 原创（源件无） | **原创** | 按 Soul 2.4；强调独立 context；强制引用 eval-rubric skill；"找问题优先" |
| `code-reviewer.md` | source/everything-claude-code/agents/code-reviewer.md | **精简** | 砍掉 React/Next.js 栈特定（~30 行）+ Node.js/Backend 栈特定（~27 行）+ Stripe 示例；保留通用审查框架+置信度过滤+AI 代码审查附录 |
| `security-reviewer.md` | 同上 | **原件保留** | 108 行信息密度已经极高，OWASP Top 10 + 代码模式表 + 误报规则全是精华，不动 |

#### 3.2.4 Skills

| 目录 | 出处 | 策略 | 用途 |
|------|------|------|------|
| `skill-creator/` | source/Anthropic的skills/skills/skill-creator | **原封复制** | 官方权威，用于后续生成新 skill |
| `doc-templates/` | 原创 | **原创** | 三类模板：需求/设计/架构 |
| `eval-rubric/` | 原创 | **原创** | Evaluator 的六维度评分表 |
| `gotchas/` | 原创 | **原创空壳** | 由 Stop hook 按需追加 |

#### 3.2.5 Slash Commands

| 文件 | 关键行为 |
|------|---------|
| `plan.md` | 调 `planner` agent，完成后提示切 session 到 `/code` |
| `code.md` | 拆步骤、每 commit 单元停下确认、主动提议 subagent、TDD 先验环境、被 hook 拦截时不绕过 |
| `evaluate.md` | 调 `evaluator` agent，要求新开 session；判决 PASS/BLOCK 的处置路径 |
| `harness-retro.md` | 双周复盘：gotchas / CLAUDE.md / hooks / 卡壳案例 / 重复操作 / 模型变化 |
| `harness-audit.md` | 月度扫描：settings / hooks / CLAUDE.md / skill/agent 里的敏感信息 / gotchas 泄密 / 备份 |

---

## 四、刻意**没做**的事（取舍记录）

这些是在构建中明确决定不做的，避免未来重复踩坑。

| 没做的事 | 理由 |
|---------|------|
| 没拉 source 里 30+ 语言特定的 reviewer / build / test skills | 全局无意义，属于项目级 |
| 没全量拉 everything-claude-code 的 40+ skills | 80% 用不上；少即是多 |
| 没在全局配 typecheck / lint hook | 栈绑定的东西必须项目级 |
| 没在全局生成 feature_list.json / claude-progress.txt / init.sh 模板 | 不是每个任务都需要；`/plan` 按需生成 |
| 没单独建 "coder" agent | coding 阶段本来就是主 claude，有 `/code` command 框住行为即可 |
| 没把绝佳实践在每个 agent prompt 里重写一遍 | 单一真相源 = 全局 CLAUDE.md，重写 = 漂移 |
| 没用源件的 planner 照搬 | I/O 规范与 Soul 2.2 不匹配，重写更省 |
| 没把 `security-reviewer` 砍到 40 行 | 安全是高代价领域，108 行原件信息密度足够精炼，砍了丢太多 |

---

## 五、未来演进规则

### 5.1 什么时候改 CLAUDE.md
- 发现反复踩的坑（见 `/harness-retro`）
- 模型能力变化导致旧约束过紧或过松
- 工作方式演化（例如新加入长任务场景）
- **改动必走自检**：标注变更日期和原因（文件末尾注释）

### 5.2 什么时候新增 Skill
- 发现某类任务**反复出现**且跨项目通用
- 用 `skill-creator` 辅助生成，但最终人工审查
- 项目特定的 skill 放项目里，别进全局

### 5.3 什么时候新增 Agent
- 有一类任务**需要独立 context + 明确产出格式**
- 现有 agent 的 prompt 已经过长且混入多种职责 → 拆分
- 一次性任务不要建 agent，写进 command 或直接对话就好

### 5.4 什么时候新增 Hook
- 有反复出现的危险行为需要硬拦（不能只靠提醒）
- 有团队/个人的确定性规则需要每次执行
- **警惕过度 hook 化**：太多 hook 会拖慢交互、产生噪声

### 5.5 什么时候改 Agent prompt
- 发现 agent 的产出长期偏离预期 → 先看 CLAUDE.md 是否缺条款
- 在 CLAUDE.md 改不动的情况下，才改 agent prompt
- 改 agent prompt 的前提：明确比 CLAUDE.md 多了什么信息量

---

## 六、自检清单（每次修改 Harness 后跑一遍）

- [ ] `~/.claude/settings.json` 是合法 JSON（`python3 -c "import json; json.load(open('...'))"`）
- [ ] `~/.claude/hooks/*.sh` 都有执行权限（`ls -la`）
- [ ] 所有 agent 文件都有合法的 frontmatter（name / description / tools / model）
- [ ] 所有 skill 目录都有 `SKILL.md`，frontmatter 含 name + description
- [ ] 所有 command 文件都有 description frontmatter
- [ ] 新建 session，`/` 能看到所有命令，skill 列表能看到所有 skill
- [ ] CLAUDE.md 不超过 100 行（参考 Harness 手册 60 行原则，略有放宽）
- [ ] 没有任何文件里包含真实 secret / 内部 URL / 真实用户数据

---

<!-- 最后更新：2026-04-16 · 原因：初始搭建 -->
