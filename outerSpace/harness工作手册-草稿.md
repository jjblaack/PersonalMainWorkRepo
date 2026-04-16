# AI 协同开发 Harness 工程手册

> 版本：v1.0 · 2026年Q2  
> 维护方式：每个 sprint 结束后由 Tech Lead 审查，由 AI 协助起草更新  
> 阅读建议：新人从前言读起；有经验的开发者可直接跳到 Part 3；Tech Lead 重点关注 Part 2 和 Part 4

---

## 前言

### 0.1 认知重置：AI 协同开发不是"更好的自动补全"

如果你认为 Claude Code 只是"GitHub Copilot 的升级版"——一个更聪明的补全工具——那么这份手册对你来说会有些颠覆性。

过去一年，有两类团队在 AI 协同开发上走向了截然不同的结果：

**第一类团队**：把 AI 工具装上，发现确实能加速写一些样板代码，但总体来说提升有限，而且偶尔会引入奇怪的 bug，需要反复人工检查和修正。几个月后，大家逐渐回到了原来的工作模式，AI 工具成了偶尔用一用的辅助。

**第二类团队**：系统性地构建了围绕 AI Agent 运行的环境和机制。他们的工程师主要工作不再是写代码，而是设计 Agent 工作的上下文、约束和反馈系统。结果是：3 名工程师 + AI Agent 在 5 个月内交付了超过 100 万行代码的产品，估计仅用了传统方式 10% 的时间。

两类团队的区别不在于用的模型，也不在于 prompt 写得好不好。区别在于：**有没有构建 Harness**。

---

**什么是 Harness？**

Harness，字面意思是"马具"。野马有原始的力量和智能，但它会随意乱跑。马具把这种力量约束在正确的方向上，让它变得有用。

AI Agent 亦然。Claude、GPT 这类模型已经具备了极强的代码能力。但一个没有约束的 Agent 会：
- 一次性尝试完成整个任务，中途跑偏
- 填满上下文窗口后开始"焦虑"，匆忙宣布完成
- 复制代码库里已有的坏模式并规模化
- 对自己的输出过度自信，自我评估偏向"都很好"
- 换个会话就失忆，不知道上次做到哪里

**Harness 是你构建的，让 AI 可靠工作的整个运行环境**。它包括：上下文管理、架构约束、Hooks 自动触发、跨 session 状态管理、以及反馈闭环。

---

**核心思维转变**

| 旧思维 | Harness 思维 |
|--------|------------|
| 我来写代码，AI 帮我补全 | 我来设计 AI 工作的环境，AI 来写代码 |
| 理解每一行代码的实现 | 理解约束系统本身，理解整体架构 |
| Bug 出现了，我来修 | Agent 卡壳了，说明 Harness 有缺口，我来修 Harness |
| 文档是给人看的 | 文档首先是给 Agent 看的（版本化、可发现、精确） |
| 写好 prompt 就能得到好结果 | Prompt 只是入口，环境决定上限 |
| 模型越强，结果越好 | 模型是可替换组件，Harness 才是产品 |

这不意味着工程师不再需要技术深度。恰恰相反，**Harness Engineering 的认知要求极高**——只是把你需要深度理解的东西从"每一行代码的实现"转移到了"整个系统的约束、架构和运转机制"。

---

### 0.2 本手册的使用方式

**不同角色的阅读路径：**

- **刚接触 AI 协同开发的工程师**：按顺序从前言读到 Part 3.3，重点是建立正确认知，然后跟着 SOP 实操一个功能
- **有一定使用经验的工程师**：直接从 Part 2 开始，重点看 2.2（CLAUDE.md）、2.3（Hooks）、2.5（长任务）、3.3（日常工作流）
- **Tech Lead / 技术负责人**：重点关注 Part 2 的 Harness 架构设计、Part 3.4（持续进化）、Part 4（思维转变），这是你需要在团队层面推动的

**关于模板：**

附录 A1–A5 提供了开箱即用的配置模板。建议先理解对应章节的原理，再使用模板，否则你不知道如何根据项目实际情况调整。

**手册本身如何演进：**

这份手册本身也应该进入 Harness 的持续改进循环。建议：
- 每个 sprint 结束时，Tech Lead 花 15 分钟审查本手册是否有需要更新的地方
- 有新发现时，先在团队内部讨论，再由 AI 协助起草更新内容
- CLAUDE.md 和 Hooks 配置有变更时，同步更新附录对应模板
- 标注日期和更新原因，方便追溯

---

## Part 2：Harness 工作流搭建

### 2.1 Harness 分层模型：五层架构全景

在动手配置之前，先建立整体的架构认知。Harness 不是一个单一的配置文件，而是分层的系统，每一层有明确的职责归属。

```
┌─────────────────────────────────────────────────────────────┐
│  L5 · Org 层（团队/组织级）                                    │
│  settings.json · 权限策略 · model 指定 · attribution 规范      │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  L4 · Repo 层（项目级）                                  │  │
│  │  CLAUDE.md · .claude/commands · hooks · skills · subagents │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │  L3 · 记忆层（任务级）                            │  │  │
│  │  │  feature_list.json · claude-progress.txt        │  │  │
│  │  │  init.sh · git history                          │  │  │
│  │  │  ┌───────────────────────────────────────────┐  │  │  │
│  │  │  │  L2 · 执行层（运行时）                      │  │  │  │
│  │  │  │  hooks 触发 · worktrees · subagents        │  │  │  │
│  │  │  │  agent teams · tmux panes                  │  │  │  │
│  │  │  │  ┌─────────────────────────────────────┐  │  │  │  │
│  │  │  │  │  L1 · 模型层                         │  │  │  │  │
│  │  │  │  │  Claude（智能本身）                   │  │  │  │  │
│  │  │  │  │  Harness 给它手、眼和工作空间          │  │  │  │  │
│  │  │  │  └─────────────────────────────────────┘  │  │  │  │
│  │  │  └───────────────────────────────────────────┘  │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**每层的职责说明：**

| 层级 | 归谁管 | 放什么 | 如何强制执行 |
|------|--------|--------|------------|
| L5 Org 层 | Tech Lead | 团队统一的权限、模型、归因规范 | `settings.json` 确定性执行，不依赖 AI 自觉 |
| L4 Repo 层 | 项目维护者 | 项目知识、开发规范、可复用能力 | CLAUDE.md + Hooks + Skills |
| L3 记忆层 | Harness 自动维护 | 任务状态、进度、已完成工作 | Agent 每个 session 必须读写 |
| L2 执行层 | 运行时动态生成 | 并行 worker、隔离环境 | worktree + tmux 隔离 |
| L1 模型层 | Anthropic | 智能本身 | 不需要管理，只需要给它正确的环境 |

**关键原则：能在高层做的约束，不要放到低层靠 AI 自觉。**

例如：禁止提交带 API key 的代码，不要写进 CLAUDE.md 说"请注意不要提交 secret"——这是废话。应该在 L2 的 pre-commit hook 里用 truffleHog 等工具扫描，硬性拦截。

---

### 2.2 CLAUDE.md 工程：团队级知识库的正确写法

CLAUDE.md 是 Agent 每次启动时最先读取的文件。它的质量直接决定 Agent 的起点状态。

#### 核心原则：精确优于完整

ETH Zürich 2026 年的研究给出了一个反直觉的结论：**AI 自动生成的 CLAUDE.md 会让任务成功率下降约 3%，而人工精心编写的 CLAUDE.md 可以提升约 4%**。差距来自于：AI 生成的内容通常通用、臃肿，给每个后续 Agent 读取时造成认知负荷。

CLAUDE.md 的每一行都应该由人类审查。

#### 60 行原则

**CLAUDE.md 控制在 60 行以内。** 它是目录，不是百科全书。

错误做法：把所有规范、知识、流程全塞进 CLAUDE.md，洋洋洒洒几百行。

正确做法：CLAUDE.md 只做三件事：
1. 告诉 Agent 这个项目是什么（3–5 行）
2. 告诉 Agent 常用命令和最重要的约定（10–15 行）
3. 指向详细文档的路径（链接到 Skills 和专项文档）

#### CLAUDE.md 的分工边界

| 应该放在 CLAUDE.md | 不应该放在 CLAUDE.md |
|-------------------|-------------------|
| 项目简介（2-3 句话） | 完整的 API 文档 |
| 启动命令、测试命令 | 所有代码规范细节 |
| 最关键的禁止行为（≤5条） | 行为约束（应该放 settings.json） |
| Skills 和文档的路径索引 | 可以用 linter 强制的规范 |
| 架构层级的一句话说明 | 超过 3 个月没更新的历史决策 |

#### 静态上下文 vs 动态 Skills

不是所有知识都应该在 Agent 启动时就加载。把知识分两类：

- **静态上下文**（放 CLAUDE.md）：每次都用得到的核心信息，例如项目结构、启动命令
- **动态 Skills**（按需加载）：只在特定任务时需要的知识，例如"如何写这个项目的 API 测试"、"前端设计规范"

Agent 遇到相关任务时会自动加载对应的 Skill，而不是在启动时就把所有知识塞满上下文。

#### CLAUDE.md 的维护规范

- **每个 sprint 结束做一次审查**：删除过时内容，过时的指令比没有指令更危险
- **有变更走 PR 流程**：CLAUDE.md 的修改需要至少一个人 review
- **禁止 AI 自动更新 CLAUDE.md**：除非有人工审查，否则 AI 生成的 CLAUDE.md 内容不得直接合并
- **标注最后更新日期**：方便判断内容是否仍然有效

#### CLAUDE.md 模板

见附录 A1。

---

### 2.3 Hooks 系统：确定性执行的神经末梢

Hooks 是 Claude Code 中最被低估的能力，也是 Harness 与"单纯靠 CLAUDE.md 约束"之间最核心的区别。

**核心理念：不要靠 AI 自觉，靠系统强制。**

当你在 CLAUDE.md 写"请确保所有代码都有类型注解"，这是在请求 AI 自觉遵守。AI 可能遵守，也可能不遵守，因为上下文已经很长了，因为这一次的任务很紧急，因为很多原因。

当你在 post-edit hook 里加一个类型检查脚本，AI 每次修改文件后都会触发检查，检查失败就是失败，没有例外。这才是可靠的约束。

#### Hook 的执行时机

| Hook 类型 | 触发时机 | 典型用途 |
|----------|---------|---------|
| `pre_tool_call` | Agent 调用工具之前 | 拦截危险命令、审查即将执行的 bash 命令 |
| `post_tool_call` | Agent 调用工具之后 | 类型检查、lint、触发测试 |
| `pre_compact` | 上下文压缩前 | 保存重要状态到文件 |
| `post_compact` | 上下文压缩后 | 重新注入关键上下文 |
| `stop` | Agent 停止时 | 更新 progress 文件、发送通知 |

#### 团队推荐的基础 Hook 配置

以下是建议所有项目都启用的最小 Hook 集合（详细配置见附录 A2）：

**安全类（硬性拦截）：**
- `pre-bash:secret-scan`：检测命令中是否包含 API Key、密码等敏感信息模式，发现即拦截
- `pre-bash:dangerous-command`：拦截 `rm -rf /`、`git push --force` 等高风险命令，要求人工确认
- `pre-bash:production-guard`：检测是否在生产环境执行写操作

**质量类（执行后检查）：**
- `post-edit:typecheck`：文件修改后触发 TypeScript 类型检查（或对应语言的静态检查）
- `post-edit:lint`：文件修改后触发 ESLint / 对应 linter
- `post-write:test-related`：检测修改的文件是否有对应测试文件，没有则提示

**状态类（跨 session 保障）：**
- `stop:progress-update`：Agent 停止时检查 `claude-progress.txt` 是否已更新
- `stop:git-commit-reminder`：如果有未提交的变更，提醒 Agent 先提交再停止

#### Hook 的错误消息工程

Hook 被触发并拦截时，给出的错误消息至关重要。错误消息应该：
1. 说清楚触发了哪条规则
2. 给出具体的修复建议
3. 如果可能，直接给出自动修复命令

这样 Agent 在看到 hook 报错后可以自行修复，而不是陷入困惑循环。

```bash
# 不好的 hook 错误消息
echo "ERROR: Type check failed"

# 好的 hook 错误消息
echo "ERROR [post-edit:typecheck]: TypeScript 类型检查失败"
echo "失败文件: src/api/user.ts"
echo "修复建议: 运行 'npx tsc --noEmit' 查看详细错误，或检查第 42 行的类型定义"
echo "如果是第三方库类型问题，可以在该行添加 // @ts-expect-error 并注明原因"
```

#### Hook 的运行时调优

Hook 不是一成不变的。随着项目推进，某些 hook 可能需要临时禁用或调整严格程度：

```bash
# 临时禁用某个 hook（例如紧急修复时）
export ECC_DISABLED_HOOKS="post-edit:typecheck"

# 调整 hook 严格程度
export ECC_HOOK_PROFILE=relaxed  # standard / strict / relaxed
```

但要注意：禁用 hook 要有记录，并在修复后重新启用。不要让"临时禁用"变成永久状态。

---

### 2.4 Skills 体系：渐进式知识披露

Skills 是 Claude Code 中的知识封装单元，类似于可按需调用的"指令模块"。正确使用 Skills 可以让 CLAUDE.md 保持精简，同时让 Agent 在需要时能够获取深度专项知识。

#### Skills 的核心价值：上下文按需加载

Agent 在任何时刻能处理的上下文是有限的。把所有知识都预先注入，等于把宝贵的上下文空间浪费在了暂时不需要的信息上。

Skills 的机制是：在 CLAUDE.md 里声明"这里有一个关于 X 的专项指南，路径是 `.claude/skills/x.md`"，Agent 在需要处理 X 相关任务时，自行读取对应的 Skill，而在其他时候不占用上下文。

#### Skill 的分类

**个人 Skills（`~/.claude/skills/`）**：  
跨项目通用的个人偏好和工作方式。例如"我喜欢的代码风格"、"我常用的调试策略"。这些只在你自己的机器上生效。

**项目 Skills（`.claude/skills/`）**：  
项目特定的专项知识，提交到 git，团队共享。例如：
- `api-testing.md`：这个项目的 API 测试规范和模板
- `database-migration.md`：数据库迁移的操作规范
- `frontend-design.md`：UI 组件的设计原则和常用模式
- `release.md`：发布流程的完整步骤

**团队 Skills（通过 plugin 共享）**：  
跨项目的团队级通用知识，可以通过 Claude Code 的 plugin 机制在团队内分发。

#### Skill 的设计原则

好的 Skill：
- **聚焦单一主题**：一个 Skill 只讲一件事，方便 Agent 判断"这次需不需要加载"
- **有明确的触发条件**：在 CLAUDE.md 里用一句话说清楚"做 X 类任务时读取此 Skill"
- **包含具体示例**：抽象规范不如一个可复制粘贴的例子
- **控制在 100 行以内**：太长的 Skill 说明设计有问题，需要拆分

#### 把重复操作变成 Slash Commands

如果某个操作你每天做超过一次，就把它变成 slash command：

```
.claude/commands/
├── techdebt.md       # /techdebt - 扫描并总结技术债
├── pr-review.md      # /pr-review - 执行标准的 PR 审查流程
├── context-dump.md   # /context-dump - 输出当前任务的状态摘要
└── implement.md      # /implement - 按团队规范实现一个功能
```

Slash command 的本质是预制的 prompt 模板，存进 git，让团队成员不需要每次重新想要怎么问 AI。

---

### 2.5 长任务 Harness：跨 Context 窗口的工程架构

这是 Harness Engineering 中最有价值、也最容易被忽略的部分。

#### 问题：Agent 的数字失忆症

你让 Claude Code 构建一个功能完整的后台系统。它工作了 40 分钟，调用了无数工具，写了很多文件，做了很多决策。然后上下文窗口满了，你开启了新的会话。

"让我先了解一下项目的当前状态……"

它从零开始了。代码还在，但 Agent 不知道什么做完了、什么没做完、为什么做了某个技术决策、下一步该做什么。你给它看了原始需求，它重新理解，可能走上和上一个 session 不一样的路。这不是工作流，这是祈祷。

**核心挑战**：Agent 工作在离散的 session 中，每个新 session 对之前发生的一切一无所知。

#### 解决方案：四件套 + 两段式 Agent

**四件套文件**（由 Initializer Agent 在项目开始时创建，并在整个开发过程中持续更新）：

```
项目根目录/
├── feature_list.json      # 完整的功能需求清单，每项带 passes: false/true 状态
├── claude-progress.txt    # 每个 session 的工作日志（做了什么、遇到了什么、下一步是什么）
├── init.sh                # 一键启动开发环境的脚本
└── .claude/
    └── CLAUDE.md          # 项目知识（不包含状态，状态在 progress.txt）
```

**两段式 Agent 架构：**

```
第一次运行（只跑一次）
    ↓
Initializer Agent
- 读取用户需求
- 展开为详细的 feature_list.json（包含所有功能项和验收标准）
- 编写 init.sh（如何启动、如何测试）
- 创建 claude-progress.txt（初始状态）
- 做初始 git commit
    ↓
每次后续运行（循环）
    ↓
Coding Agent
- 读取 feature_list.json（哪些还没完成）
- 读取 claude-progress.txt（上次做到哪里）
- 读取 git log（实际变更记录）
- 实现一个功能
- 更新 feature_list.json（标记完成）
- 更新 claude-progress.txt（记录本次工作）
- git commit
- 循环，直到所有功能完成
```

#### feature_list.json 的设计

`feature_list.json` 用 JSON 而不是 Markdown，原因是 JSON 结构性更强，Agent 不太可能在修改一项时意外破坏其他项。

```json
{
  "project": "用户管理后台",
  "created_at": "2026-04-01",
  "features": [
    {
      "id": "F001",
      "category": "认证",
      "title": "用户登录",
      "description": "支持邮箱+密码登录，登录成功返回 JWT token",
      "test_steps": [
        "POST /api/auth/login，传入正确邮箱密码，返回 200 和 token",
        "POST /api/auth/login，传入错误密码，返回 401",
        "前端登录页面可以正常提交并跳转"
      ],
      "passes": false,
      "notes": ""
    }
  ]
}
```

每次 Coding Agent 完成一项功能，它会把 `passes` 改为 `true`，并在 `notes` 里记录有什么特殊处理。

#### claude-progress.txt 的设计

```
=== Session 2026-04-02 14:30 ===
完成：F001（用户登录）、F002（用户注册）
当前状态：两个 API 均已实现并通过测试，前端表单已对接
遇到的问题：JWT secret 暂时硬编码在代码里，需要迁移到环境变量（F015）
下一步：实现 F003（忘记密码流程），需要先配置邮件服务
未提交变更：无

=== Session 2026-04-02 16:00 ===
（由下一个 Agent 在开始时追加）
...
```

**关键设计**：`claude-progress.txt` 是解释性的（为什么这么做、遇到了什么），`git log` 是实证性的（实际改了什么）。两者结合，给下一个 session 完整的画面。

#### 上下文焦虑（Context Anxiety）

这是一个在 AI 工程实践中被反复发现的现象，值得特别说明。

**什么是上下文焦虑**：随着一个 session 内的对话越来越长，上下文窗口逐渐填满，模型的行为会发生变化：
- 开始匆忙收尾任务
- 把未完成的工作标记为"完成"
- 对"还剩哪些工作"的判断变得不准确
- 代码质量可能下降

**三种应对策略**：

| 策略 | 机制 | 适用场景 |
|------|------|---------|
| Context Compaction | SDK 自动压缩旧的对话历史 | 大多数现代场景（Opus 4.6 默认支持） |
| Context Reset | 主动开启新 session，通过 progress 文件传递状态 | 任务非常长、或使用较旧的模型 |
| Chunking | 把大任务拆分为每次只做一个功能的小 session | 结合 feature_list.json 自然实现 |

在实践中，如果你在使用 Claude Opus 4.6，Compaction + Chunking（feature_list 驱动的单功能实现）已经足够应对大多数场景，不需要手动做 Context Reset。如果你在用更小的模型，Context Reset 仍然必要。

---

### 2.6 Planner → Generator → Evaluator：三段式 Harness

这是 Anthropic 工程团队目前最成熟的长任务 Harness 架构，解决了单 Agent 模式下两个根本性问题：
1. **一次性尝试**：Agent 试图在一个 session 里完成所有事，中途跑偏
2. **自我评估偏差**：Agent 评估自己的工作时，倾向于报告"质量很好"，哪怕明显有问题

**三段式架构：**

```
用户需求（一句话或一段描述）
        ↓
  ┌─────────────┐
  │   Planner   │  独立 session，独立 context
  │  规划 Agent  │  读取：用户需求 + 项目现状 + 相关 Skills
  └──────┬──────┘  产出：Sprint 级别的详细规划 + 验收标准 + 视觉设计语言
         ↓          Git commit 规划文档
  ┌─────────────┐
  │  Generator  │  独立 session，可运行多轮
  │  实现 Agent  │  读取：Planner 产出 + feature_list + progress
  └──────┬──────┘  产出：实现代码 + 测试 + 更新 progress
         ↓          每个功能完成后 git commit
  ┌─────────────┐
  │  Evaluator  │  独立 session，独立 context（这是关键！）
  │  评估 Agent  │  读取：验收标准 + 运行测试 + 检查代码
  └──────┬──────┘  产出：通过 / 不通过 + 具体问题描述
         ↓
    通过？
    ├── 是 → 标记 feature_list 项为 passes: true，继续下一个功能
    └── 否 → 把具体问题反馈给 Generator，重新实现
```

#### 为什么 Evaluator 必须独立 context？

这是三段式 Harness 最重要的设计决策。

如果你让同一个 Agent 实现完功能后立刻评估自己的实现，它几乎一定会说"实现得很好"。这不是因为模型有意说谎，而是：
- 它投入了大量上下文和"努力"来完成这个任务，有确认偏差
- 它对自己实现的决策有完整的"知情上下文"，不容易发现表面看起来合理但实际有问题的地方

把 Evaluator 放在独立的新 context 里，它没有任何"自己写的代码"的包袱，只看测试结果和验收标准，像一个不认识你的 code reviewer。

#### Evaluator 的评分标准设计

不要问 Evaluator"这个实现好不好"，而是给它具体的评分维度：

```markdown
## 评估标准

### 功能正确性（必过，不通过直接打回）
- [ ] 所有 feature_list 中标注的 test_steps 都通过
- [ ] 没有现有测试被破坏（回归测试通过）
- [ ] 边界情况有处理（空输入、超长输入、并发）

### 代码质量（加权评分）
- [ ] 没有绕过类型检查的 any 或 @ts-ignore（无充分理由）
- [ ] 没有 console.log 遗留
- [ ] 函数/变量命名在代码库中风格一致

### 安全性（必过）
- [ ] 没有硬编码的 secret 或密码
- [ ] 用户输入有校验
- [ ] SQL 查询没有字符串拼接

### 针对本项目的特定标准
- [ ] （在这里添加项目特有的检查项）
```

---

### 2.7 多 Agent 并行：Subagents、Agent Teams、Worktrees

当一个 Agent 做完一个任务需要 2 小时，并不总意味着你要等 2 小时。理解三种并行方式，选择合适的工具。

#### 三种并行方式的适用场景

**Subagents（子 Agent）** ——最常用，低开销

适用场景：一个主任务中有需要深度研究或独立执行的子任务，但不需要子任务之间互相通信。

工作机制：主 Agent 派生一个子 Agent，子 Agent 在独立的 context 里完成一项具体工作，返回压缩后的结果给主 Agent。子 Agent 相当于"上下文防火墙"——它所有的中间步骤和噪音都不会污染主 Agent 的上下文。

典型用法：
```
主 Agent（编排）
├── Subagent：研究竞品的 API 设计（只返回摘要）
├── Subagent：检查现有代码库里类似功能的实现模式（只返回关键发现）
└── 主 Agent 根据上述信息，实现新功能
```

**Git Worktrees + 多实例** ——中等开销，适合并行独立功能

适用场景：多个独立的功能或 bug fix 可以完全并行，相互之间没有依赖，不需要协调。

工作机制：
```bash
# 为每个功能创建独立的 worktree 和 branch
git worktree add ../project-feature-a feature-a
git worktree add ../project-feature-b feature-b

# 在各自的 worktree 里启动独立的 Claude Code 实例
cd ../project-feature-a && claude
cd ../project-feature-b && claude  # 另一个终端
```

每个实例在完全隔离的代码副本里工作，互不干扰，最终通过 git merge 整合。

**Agent Teams（实验性功能）** ——高开销，适合需要协作的复杂重构

适用场景：多个 Agent 需要互相通信、共享发现、协调决策。例如大规模重构时，需要 API 层 Agent 和 DB 层 Agent 实时协调接口变更。

注意：Agent Teams 大约消耗 7 倍于单 session 的 token，且当前（Opus 4.6）要求所有 Agent 使用同等级别的模型。如果子任务之间不需要实时通信，用 Worktrees 多实例会更经济。

#### 决策树：选哪种并行方式？

```
需要并行吗？
├── 否 → 单 Agent + feature_list 驱动即可
└── 是 → 子任务之间需要互相通信吗？
    ├── 否 → 子任务完全独立吗？
    │   ├── 是 → Git Worktrees + 多实例
    │   └── 否（需要汇总结果）→ Subagents（主 Agent 编排）
    └── 是 → Agent Teams（考虑 token 成本）
```

#### Subagent 的设计规范

Subagent 的返回值应该高度压缩，只包含主 Agent 需要的信息，不包含过程：

```markdown
---
name: codebase-explorer
description: 探索代码库，回答关于现有实现的具体问题
tools: ["Read", "Grep", "Glob", "Bash"]
model: sonnet  # 探索类任务用 Sonnet，成本更低
---

你是一个代码库探索专家。你的任务是回答关于代码库的具体问题。

返回格式要求：
1. 直接回答问题（2-3句话）
2. 列出关键发现（bullet points，每条不超过1行）
3. 如果有重要代码示例，附上文件路径和行号（不要复制完整代码）
4. 总长度不超过 300 字

不要：解释你的探索过程、列出你查看过的所有文件、返回大段代码
```

---

### 2.8 架构约束的强制执行

AI Agent 是一台极其高效的模式复制机。它会忠实地复制代码库中已有的模式——无论那些模式好还是坏。

这意味着：**你喂给 Agent 什么样的代码库，它就会放大什么样的模式**。

如果你的代码库层级混乱、依赖方向随意，Agent 会生成更多层级混乱、依赖随意的代码。如果你的代码库有清晰的分层和约束，Agent 会生成更多符合约束的代码，而且还会给你找出既有的违规。

#### 定义分层架构并强制执行

以后端服务为例，定义清晰的分层规则：

```
Types（类型定义）
  ↓ 只能单向依赖
Config（配置）
  ↓
Repository（数据访问层）
  ↓
Service（业务逻辑层）
  ↓
Controller/Route（接口层）
  ↓
UI（如果有）
```

规则：上层可以依赖下层，下层不能依赖上层。横切关注点（auth、logging、metrics）通过统一的 Providers 接口注入，不允许直接导入。

这个规则写进 CLAUDE.md 是不够的。需要用自定义 linter 在代码层面强制执行。

#### 自定义 Linter 的设计

```typescript
// 架构约束 linter 示例（以 TypeScript 项目为例）
// .claude/linters/architecture.ts

const LAYER_ORDER = ['types', 'config', 'repository', 'service', 'controller', 'ui'];

export function checkLayerViolation(importPath: string, currentFile: string): string | null {
  const currentLayer = getLayer(currentFile);
  const importedLayer = getLayer(importPath);
  
  if (LAYER_ORDER.indexOf(importedLayer) > LAYER_ORDER.indexOf(currentLayer)) {
    return `架构违规：${currentLayer} 层不应该依赖 ${importedLayer} 层\n` +
           `当前文件：${currentFile}\n` +
           `被导入：${importPath}\n` +
           `修复建议：考虑通过 Service 层暴露接口，或通过 Provider 注入依赖`;
  }
  return null;
}
```

Linter 的错误消息包含修复建议，Agent 看到报错后能够自行修复，而不是反复问"这是什么意思"。

#### 让 Agent 参与维护约束

约束规则本身也可以用 Agent 来生成和维护——但这一步需要人工审查。

一个好的工作流：
1. Tech Lead 定义架构规则（自然语言）
2. 请 Agent 基于规则编写 linter 代码
3. Tech Lead review linter 代码（不超过 30 分钟）
4. 把 linter 加入 CI，从此自动执行
5. 如果发现 linter 有误报或漏报，把反馈提供给 Agent，迭代改进

---

*（Part 2 完，共 8 节）*

---

## Part 3：最佳工作实践

### 3.1 新项目启动 SOP

新项目是建立 Harness 最好的时机。从一开始就正确，比后来修正代价低得多。

**第一周节奏**：

```
Day 1：建立 Harness 骨架
Day 2-3：实现第一批功能，验证 Harness 有效性
Day 4-5：根据实践反馈，调整 Harness
```

#### 完整步骤

**Step 1：建立 Org 级配置（30 分钟，一次性）**

如果团队还没有统一的 `settings.json`，先建立。见附录 A2 的 settings.json 模板。关键配置项：
- 指定默认 model
- 配置 attribution（git commit 如何标注 AI 协作）
- 配置基础权限策略（哪些操作需要人工确认）

**Step 2：初始化项目结构（不要让 AI 随意生成，先规划）**

在让 AI 写任何代码之前，先明确：
- 技术选型（语言、框架、主要依赖）
- 分层架构（参考 2.8 节，定义你的层级规则）
- 目录结构（主要目录和它们的职责）

把这些写成一个 `architecture.md` 文件（2 页以内），放在项目根目录。这是给 AI 看的，也是给团队看的。

**Step 3：创建项目级 CLAUDE.md（参考 2.2 节和附录 A1）**

遵循 60 行原则，只写核心内容。

**Step 4：配置 Hooks（参考 2.3 节和附录 A2）**

先配置安全类的硬性拦截 hook，再配置质量类 hook。先从最简单的开始，随项目推进逐步添加。

**Step 5：触发 Initializer Agent**

有了以上骨架之后，用 Initializer Agent 展开详细需求：

```
Prompt（给 Initializer Agent）：

你是项目初始化 Agent。请基于以下信息，为这个项目建立 Harness 基础设施：

项目描述：[2-3句话描述项目是什么]
技术栈：[已确定的技术选型]
架构文档：[附上 architecture.md 的内容]

请完成以下任务：
1. 读取 architecture.md，理解项目结构
2. 创建 feature_list.json，把项目目标展开为具体的、可测试的功能列表
   - 每项功能包含：id、category、title、description、test_steps（至少3条）、passes: false
   - 从最核心的功能开始，至少覆盖 MVP 范围
3. 创建 init.sh，包含：安装依赖、启动开发服务器、运行测试的命令
4. 创建 claude-progress.txt，写入初始状态说明
5. 做一个 git commit，提交以上所有文件

完成后，输出 feature_list.json 的摘要（功能数量、主要类别）。
```

**Step 6：验证 Harness 有效性**

Initializer 完成后，用 Coding Agent 实现 feature_list 里的第一个功能，观察：
- Hook 有没有正确触发？
- 错误消息是否足够清晰让 Agent 自修？
- progress 文件有没有被正确更新？
- 是否需要调整 CLAUDE.md 里的某些描述？

根据观察，调整 Harness 配置，然后继续。

#### 强制约束的最小可行集

不要一开始就配置几十条规则。从最小可行集开始：

| 优先级 | 规则 | 原因 |
|--------|------|------|
| P0（必须） | secret 扫描 hook | 安全底线，不可妥协 |
| P0（必须） | 危险命令拦截 | 防止不可逆操作 |
| P1（第一周内） | 类型检查 hook | 早期就开始约束，比后期补代价低 |
| P1（第一周内） | lint hook | 代码风格统一 |
| P2（功能稳定后） | 架构约束 linter | 等架构稳定了再固化 |
| P2（功能稳定后） | 自定义业务规则 | 根据项目特点逐步添加 |

---

### 3.2 存量项目接入 SOP

为已有项目建立 Harness 比新项目难，因为你面对的是已经存在的代码库，可能有几年的历史、各种风格、不一致的模式。

**关键原则：不是重写，是渐进式注入**

不要试图先把代码库"整理好"再开始使用 AI。代价太高，而且在整理过程中会积累更多变更。正确的方式是：接受现状，渐进式建立 Harness，用 Harness 驱动代码库逐步改善。

#### 第一阶段：建立上下文可见性（1-2天）

让 AI 能够"看懂"这个代码库，是一切的前提。

**Step 1：让 AI 做一次代码库探索**

```
请探索这个代码库，生成一份 architecture.md，包含：
1. 这个项目是做什么的（2-3句话）
2. 技术栈（语言、框架、主要依赖）
3. 目录结构及各目录的职责
4. 主要的数据流（请求进来后经过哪些层次）
5. 你发现的主要模式和约定（即使是非正式的）
6. 你发现的主要问题或不一致之处

不要美化，如实描述你看到的情况。
```

让 AI 生成 architecture.md，然后**人工审查并修正**。这一步是了解代码库真实状态的好机会——很多团队发现 AI 找出了他们自己都忘记了的问题。

**Step 2：建立 CLAUDE.md**

基于 architecture.md 和你的了解，写 CLAUDE.md。重点是：
- 告诉 AI 这个项目有哪些"地雷"（例如：不要修改 legacy/ 下的文件，那是旧系统，不要动）
- 告诉 AI 哪些是主要的技术债，暂时不需要修复
- 告诉 AI 现有代码的风格约定（即使不完美，也要告诉它"现有代码是这个风格，新代码也保持一致"）

**Step 3：配置最小 Hook 集合**

先只配置安全类 hook，质量类 hook 等稳定后再加。对于存量代码库，一开始就打开所有 lint hook 会产生大量噪音。

#### 第二阶段：建立 Harness 驱动的工作模式（第一个 sprint）

在第一个正式 sprint 里，不是让 AI 直接"修复所有问题"，而是：

1. **选择一个新功能作为切入点**：用这个新功能的开发来验证 Harness，而不是去动已有代码
2. **为这个功能建立 feature_list**：哪怕项目已经运行多年，这个新功能的开发可以完全用 Harness 驱动
3. **观察 Agent 如何处理存量代码**：它会尝试复制哪些模式？这些模式是好的吗？根据观察调整 CLAUDE.md

#### 第三阶段：逐步提升代码库的 AI 可读性（持续进行）

**技术债的 AI 化处理策略**：

不要让 AI 一次性重构所有技术债（风险极高）。正确方式：

```
/techdebt（自定义 slash command）
```

定期运行这个 command，让 AI 扫描代码库，输出：
- 影响 AI 可读性最严重的 N 个问题
- 每个问题的修复优先级和预估改动范围
- 建议的修复顺序

然后把影响最严重的问题纳入 sprint 计划，像普通功能一样用 Harness 来修复。

**逐步添加架构约束**：

不要一开始就把存量代码所有违规都找出来——那是几百条错误，没法处理。策略是：

1. 先在新文件上执行约束（linter 只对 `src/new/` 目录下的文件生效）
2. 当团队熟悉约束后，把范围扩展到修改过的旧文件
3. 最终覆盖整个代码库

---

### 3.3 日常开发工作流（Inner Loop）

这是工程师每天都会经历的工作循环。掌握这个工作流，是日常提效的核心。

#### 一个功能从需求到 PR 的完整流程

```
1. 意图表达（5分钟）
   └─ 进入 Plan Mode，描述要做什么

2. 计划确认（5-10分钟）
   └─ 审查 AI 给出的计划，修正误解，确认方向

3. 上下文清空 + 执行（自动）
   └─ 计划被接受后，开启新 session 执行（保持干净的起点）

4. 执行过程监控（异步）
   └─ Agent 工作时，你做其他事情；有权限请求时及时响应

5. 结果审查（10-20分钟）
   └─ 不是逐行 review，而是验证关键行为

6. Challenge 环节（可选，重要功能必做）
   └─ "反驳这个实现"、"这个方案的最大风险是什么"

7. PR 提交
```

#### Plan Mode 的正确使用

**任何非平凡任务（3步以上或涉及架构决策）都要先进 Plan Mode。**

Plan Mode 的价值不只是让 AI 更好地理解任务，更重要的是：**你在 plan 阶段发现误解比在执行阶段发现要便宜得多**。

```
进入 Plan Mode 的触发词：
"在你开始任何代码修改之前，先给我一个计划..."
"进入计划模式。不要执行任何代码变更，先解释你的实现思路..."
```

好的 plan 应该包含：
- 会修改哪些文件（或新建哪些文件）
- 为什么这样组织（关键的架构决策）
- 有哪些已知的风险或不确定性
- 完成后如何验证

如果 plan 里有你不认同的地方，在这里纠正，而不是等执行完再改。

#### Context 清空的时机

以下情况适合开启新的 session（清空 context）：
- 一个完整的功能已经完成并提交
- Plan 已经确认，开始执行阶段（plan 和 execute 分离）
- 遇到奇怪的行为，怀疑是 context 污染导致的
- 距离上次 context 清空已经过去很长时间且有多个不相关任务

不适合中途清空 context：
- 当前任务只完成了一半，有很多未提交的上下文状态

#### Challenge 模式：提升质量的关键习惯

对于重要功能，不要在 Agent 完成后就直接提 PR。先用 Challenge 模式做一轮压力测试：

```
"你刚完成了 [功能描述]。现在请以一个严格的 code reviewer 身份，
找出这个实现最大的 3 个问题或风险。如果没有重大问题，说明为什么。
不要只说好话，要主动找问题。"
```

或者：

```
"假设这个代码在生产环境上线了，什么情况会导致它出问题？
列出最可能出现的 3 个故障场景。"
```

Challenge 模式不是让 AI 推翻自己的实现，而是让它换个视角，主动找出你自己可能忽略的问题。

#### Slash Commands 的内循环优化

把以下操作变成 slash command（见 `.claude/commands/` 目录），消除重复输入：

| Command | 作用 |
|---------|------|
| `/plan` | 进入标准 Plan Mode，包含你希望 plan 覆盖的所有维度 |
| `/implement` | 按团队规范实现一个功能（自动加载相关 Skills） |
| `/pr-review` | 执行标准的 PR review 流程（检查清单 + 潜在问题） |
| `/techdebt` | 扫描并总结当前代码库的技术债状况 |
| `/context-dump` | 输出当前任务的状态摘要，方便切换 session |
| `/challenge` | 对当前实现做压力测试 |

---

### 3.4 持续进化：让 AI 越用越好的飞轮机制

这是最重要也最容易被忽视的部分。很多团队在配置好 Harness 之后，就把它当成一个固定的系统来使用。但 Harness 是活的——它需要和代码库一起演进，也需要跟随模型能力的提升而简化。

#### 飞轮的核心逻辑

```
Agent 卡壳 or 产出不好
    ↓
这是信号：Harness 有缺口
    ↓
识别缺口：缺少工具？缺少上下文？约束不够？评估不准？
    ↓
修复 Harness（更新 CLAUDE.md / 添加 Hook / 完善 Skill）
    ↓
下次同类任务，Agent 自主完成
    ↓
（循环，Harness 越来越好，AI 能自主完成的范围越来越广）
```

**核心心态转变：Agent 失败 ≠ 模型不够好。Agent 失败 = Harness 需要改进的信号。**

#### Sprint Retro 中的 Harness 审查（每两周15分钟）

在每个 sprint 结束的 retro 里，加入一个固定的 Harness 审查环节：

```
Harness 审查 checklist：

[ ] 这个 sprint 里，Agent 哪些地方卡壳了或产出不符合预期？
    → 对应的 CLAUDE.md / Skills / Hooks 需要补充什么？

[ ] 有没有手动重复做了超过一次的操作？
    → 应该做成 slash command 或 skill

[ ] CLAUDE.md 里有没有不再准确的描述？
    → 删除或更新，stale 内容比没有内容更危险

[ ] 这个 sprint 有没有新的架构决策？
    → 是否需要固化为 linter 规则或 Hook？

[ ] 模型能力有变化吗？（新版本发布）
    → 某些之前需要的 Harness 机制是否可以简化？
```

#### CLAUDE.md 的版本管理

CLAUDE.md 应该有版本历史，记录每次重大变更的原因：

```markdown
<!-- CLAUDE.md 变更日志 -->
<!-- 2026-04-10：添加了数据库迁移规范（retro 发现 Agent 经常搞错迁移顺序） -->
<!-- 2026-03-25：移除了旧的 API 版本说明（v1 已下线） -->
<!-- 2026-03-10：初始版本 -->
```

#### Harness 的货架期管理

Harness 不是一劳永逸的。以下情况需要主动重新评估 Harness 设计：

| 触发事件 | 可能需要的调整 |
|---------|-------------|
| 模型升级（例如升级到更新的 Claude 版本） | 某些 context reset 机制可能不再需要；某些约束可以放松 |
| 项目阶段切换（从快速验证到生产就绪） | 质量类 hook 需要收紧；架构约束需要更严格 |
| 团队规模扩大 | 需要更多团队协作类配置；Subagent 定义需要标准化 |
| 技术栈更新 | 相关的 linter 和 Skills 需要同步更新 |
| 代码库规模扩大 | 可能需要引入 Subagent 来做上下文分割 |

**Boris Cherny（Claude Code 核心开发者）的观察**：Claude Code 的 Harness 本身也在持续被重写，任何给定的代码行的货架期大约只有两个月。你自己的 Harness 也应该保持这种意识——它不是永久架构，而是当前最佳实践的体现。

---

### 3.5 代码质量与安全的 AI 时代保障

AI 协同开发带来的最危险的错觉是：代码生成得更快，所以质量也更好。数据恰恰相反。

**AI 速度悖论**：根据对 900 名工程师的调查，63% 的组织代码交付速度加快了，但 45% 的 AI 生成代码相关部署会产生问题。代码生成快了，但下游的测试、安全、部署环节还没有同步跟上，结果是把未经验证的代码更快地推入生产。

#### 测试策略的变化

AI 时代，测试策略应该倒置：**E2E 测试优先，单元测试补充**。

原因：AI 生成的代码很容易让单元测试通过（它可以直接对着测试反向生成实现），但 E2E 测试模拟的是真实用户行为，更难作弊。

```
测试优先级：
1. E2E 测试（Puppeteer/Playwright）：验证真实用户场景
2. 集成测试：验证组件之间的接口契约
3. 单元测试：验证独立逻辑，补充覆盖率
```

把 Puppeteer/Playwright 测试集成到 Evaluator Agent 的检查流程中，让 Agent 的 "完成" 声明必须通过浏览器测试验证，而不只是代码编译通过。

#### AI 生成代码的 Review 策略

不建议逐行 review AI 生成的代码（效率太低，而且容易陷入细节遗漏全局）。建议的 review 策略：

**关注点层次化**：

| Review 层次 | 关注什么 | 如何高效做 |
|------------|---------|----------|
| 架构层 | 有没有违反分层规则？有没有奇怪的依赖？ | Linter 自动检查，人工 review diff 中的新依赖 |
| 接口层 | 对外暴露的 API 是否符合设计？ | 重点 review interface/type 定义 |
| 安全层 | 有没有安全漏洞？ | 运行 agentshield 扫描 + 人工检查输入验证 |
| 逻辑层 | 核心业务逻辑是否正确？ | 重点 review 复杂逻辑和边界处理 |
| 风格层 | 代码风格是否一致？ | 基本上由 linter 保证，不需要人工花太多时间 |

**用 AI 做 AI 的 code review**：

对于规模较大的 PR，可以开一个独立 context 的 Review Subagent：

```
用一个新的 session，完全独立的 context。

你是一名资深 code reviewer。请审查以下变更（git diff 输出）：
[粘贴 diff]

请重点关注：
1. 安全问题（输入验证、SQL 注入、权限检查）
2. 错误处理（边界情况、异常处理）
3. 与现有代码库风格的一致性
4. 性能隐患

输出格式：按严重程度（Critical / Major / Minor）分类的问题列表。
如果没有问题，请明确说明并解释为什么你认为这个变更是安全的。
```

#### Harness 安全扫描

定期（至少每月一次）对 Harness 自身做安全扫描：

```bash
# 使用 agentshield 扫描 Harness 配置
npx ecc-agentshield scan

# 检查项目：
# - CLAUDE.md 中是否有不应该出现的信息
# - MCP 服务器配置是否有安全风险
# - Hooks 中是否有被注入的风险
# - settings.json 权限配置是否过于宽松
```

---

### 3.6 团队协作模式

当整个团队都使用 AI 协同开发时，需要建立协调机制，避免每个人的 Harness 各自为政。

#### CLAUDE.md 的 PR 流程

CLAUDE.md 是团队共同的"对 AI 的约定"，它的变更影响所有人。建立明确的修改流程：

- **任何人都可以提出**：通过 PR 的方式提议修改 CLAUDE.md
- **必须说明原因**：PR 描述里需要解释为什么需要这个变更（是因为 Agent 产生了什么问题？还是有什么新发现？）
- **Tech Lead review**：CLAUDE.md 的变更需要 Tech Lead 或指定的 AI 协作负责人 review
- **生效前通知团队**：合并前在团队群里告知变更内容，让大家知道 Agent 的行为会有哪些变化
- **不允许 AI 直接提交 CLAUDE.md**：AI 可以草拟，但最终内容必须经过人工确认

#### 跨成员的 Harness 知识共享

建立团队的 Harness 知识积累机制：

```
.claude/
├── CLAUDE.md              # 核心配置（严格管控）
├── skills/                # 项目 Skills（走 PR，任何人可贡献）
│   ├── README.md          # Skills 索引和使用指南
│   └── *.md
├── commands/              # Slash Commands（走 PR）
├── subagents/             # Subagent 定义（走 PR）
└── hooks/                 # Hooks 配置（Tech Lead 管控）
```

Skills 和 Commands 的贡献门槛低（任何人发现一个有用的 skill 都可以 PR），但质量要经过 review。

#### AI 协同时代的 Code Review 角色变化

当大量代码由 AI 生成时，传统的逐行 code review 不再适用（也没必要）。Code review 的重心应该转移：

| 传统 Code Review | AI 时代的 Code Review |
|----------------|---------------------|
| 检查代码写法是否正确 | Linter 和类型检查自动做 |
| 检查逻辑是否正确 | 重点检查核心业务逻辑和边界 |
| 检查风格是否一致 | Lint Hook 自动保证 |
| 理解每一行代码 | 理解整体设计意图和架构决策 |
| Reviewer 是"质检员" | Reviewer 是"设计审查员" |

Code review 应该更多地问：
- "这个设计方向对吗？"
- "这里的 API 设计合理吗，后续扩展会不会很麻烦？"
- "这个功能的边界情况有没有被覆盖到？"

而不是：
- "这个变量名能不能改一下？"（Lint 处理）
- "这里的缩进不对"（格式化工具处理）

---

*（Part 3 完，共 6 节）*

---

## Part 4：工作方式与思维转变

### 4.1 工程师角色的重新定义

这个问题值得直接面对：**AI 会不会取代工程师？**

短期答案：不会。但它会重新定义工程师做什么。

更准确的描述是：AI 正在自动化"代码生产"这件事，就像工业革命自动化了"体力劳动"一样。工人没有消失，但工人做的事情完全变了。

**在 AI 协同开发的范式里，工程师的核心价值在于：**

- **架构判断力**：能够判断什么是好的系统设计，能够识别 AI 生成的架构方案中的问题
- **Harness 设计能力**：构建让 AI 可靠工作的约束系统和反馈机制
- **意图表达能力**：能够精确表达"想要什么"，把模糊需求转化为 Agent 可执行的规范
- **边界识别能力**：知道什么工作适合托付给 AI，什么工作必须人类做
- **质量判断力**：在 AI 产出面前能做出准确的好/坏判断

**什么工作必须由人类做：**

| 必须人类做 | 可以完全托付 AI |
|----------|-------------|
| 架构决策（选哪个方向） | 按照已确定的设计实现代码 |
| 产品判断（这个功能值不值得做） | 重构、格式化、套用现有模式 |
| CLAUDE.md 的审查和确认 | 根据规范写单元测试 |
| 安全边界的划定 | 文档草稿生成 |
| 团队协作和沟通 | 样板代码和 CRUD 操作 |
| 最终的技术决策 | 代码库探索和信息检索 |

**"Agent 挣扎 = 信号"的工作心态**

这是一个需要刻意培养的思维习惯。当 Agent 卡壳、循环、或者产出质量差，本能反应是"模型不够好"或者"这个任务 AI 做不了"。

但大多数时候，真正的原因是 Harness 有缺口：
- 缺少某个工具
- 缺少某段上下文
- 某个约束描述得不够精确
- 某个边界情况没有被明确说明

把"Agent 挣扎"当成 Harness 的 bug report，而不是 Agent 的能力限制，这个思维转变会显著提升你改进 Harness 的动力和效率。

---

### 4.2 意图表达的工程化

"会用 AI"的人和"善用 AI"的人，最大的区别不在于工具的选择，而在于**意图表达的质量**。

#### Spec-First 开发

传统开发：想到一个点子 → 开始写代码 → 写完了再理解到底做了什么

Spec-First 开发：想到一个点子 → 写清楚 spec → Agent 按 spec 实现 → 人工验证 spec 被正确实现

Spec 不需要完美，但需要包含：
- **目标**：这个功能为什么存在，它要解决什么问题
- **行为描述**：在正常情况下、边界情况下、错误情况下，系统应该怎么表现
- **验收标准**：什么情况下算"完成了"

```markdown
## Spec：用户邮件验证功能

**目标**：用户注册后需要验证邮箱，确保邮箱真实有效

**行为**：
- 用户注册成功后，系统立刻发送验证邮件（包含 24 小时有效的链接）
- 用户点击链接后，账户状态从 "pending" 变为 "active"
- 24 小时内未验证，用户可以请求重新发送（每小时限一次）
- 超过 72 小时未验证，账户自动删除

**验收标准**：
- 注册后 30 秒内收到邮件
- 验证链接在 24 小时内有效，之后返回明确的错误提示
- 用户状态在数据库中正确更新
- 重发限制被正确执行（测试：1 小时内连续请求返回 429）
```

#### 让 AI 先 Interview 你，再执行

对于复杂功能，不要直接告诉 AI "做 X"。先让它向你提问：

```
我想实现一个用户权限管理系统。在你开始规划之前，
请先向我提问，把你认为实现这个功能之前必须明确的问题都问清楚。
等我回答完所有问题，再给我一个实现计划。
```

这个方法的价值是：AI 会问出你自己都没想到的边界情况。它的提问往往比你预期的要深——这些问题如果在实现之后才发现，代价会高很多。

#### Phase-wise 分阶段计划

对于中等以上规模的任务，要求 Agent 给出分阶段的计划，而不是一次性的实现方案：

```
"请给出一个分阶段的实现计划：
- Phase 1（MVP，1-2天）：最核心的功能，可以上线但功能有限
- Phase 2（完整版，3-5天）：完整的功能集
- Phase 3（优化）：性能优化和边缘情况处理

每个 Phase 列出：包含什么功能、不包含什么功能、完成标准"
```

分阶段计划有几个好处：
1. 迫使 Agent 思考优先级
2. 让你可以在 Phase 1 完成后检查方向是否正确
3. 每个 phase 规模可控，不容易出现长时间跑偏

---

### 4.3 Vibe Coding 的陷阱与 Harness Engineering 的边界

"Vibe Coding"（氛围编程）这个词由 Andrej Karpathy 在 2025 年初提出，描述一种完全依赖 AI、接受所有变更、不去深入理解代码的开发方式。

它有吸引力，因为短期内确实"感觉很快"。但它是有代价的。

#### Vibe Coding 的实际代价

**代价 1：质量债务快速积累**

Agent 接受了你的每一个修改，包括错误的、不一致的、短视的修改。几个 sprint 之后，代码库变成了一个没人能完全理解的混乱状态。

**代价 2：失去理解力等于失去控制力**

如果你对代码库的某个部分完全没有理解，你就没有能力判断 AI 的建议是否合理。你的所有决策都变成了"听起来不错，就用它"——这是极其危险的，尤其在涉及安全、性能、数据一致性这类领域。

**代价 3：对 AI 产生错误的依赖**

当代码库的理解完全外包给 AI 之后，你失去了独立判断的能力。AI 给出自信但错误的答案时，你没有能力识别。

#### Harness Engineering 不等于放弃理解

Harness Engineering 并不要求你理解每一行代码。但它要求你理解：

- **系统的整体架构和分层结构**：我知道这个系统由哪些层组成，每层的职责是什么
- **核心业务逻辑的关键决策**：我知道最重要的业务规则是什么，为什么这样设计
- **约束系统本身**：我知道 linter 在检查什么、hooks 在拦截什么、评分标准是怎么定义的

简单来说：你放弃理解"每一行代码怎么写的"，但不放弃理解"这个系统为什么是这样设计的"。

#### 什么时候 AI 的速度是净正收益

下列情况，AI 速度提升是真实的、低风险的：
- 样板代码和重复性实现（CRUD、数据转换）
- 按照已有模式新增类似功能
- 文档和注释的生成
- 测试用例的编写（在有明确规范的情况下）
- 代码格式化和风格统一

下列情况，AI 速度提升需要谨慎对待：
- 新的架构设计（可能引入不合适的模式）
- 安全相关的实现（必须有专门的安全检查）
- 性能关键路径（需要测量，不能相信 AI 的估计）
- 复杂的并发和状态管理（错误很难发现）

---

### 4.4 度量与反思：如何知道我们变好了

Harness Engineering 如果没有度量，就会变成"感觉在用，不知道有没有效"。建立简单可行的度量指标，让改进有据可依。

#### 建议度量的指标

**效率类（月度跟踪）：**

| 指标 | 如何度量 | 健康方向 |
|------|---------|---------|
| PR throughput | 每人每周合并的 PR 数量 | 随 Harness 成熟持续提升 |
| AI 自主完成率 | "不需要人工干预就完成的任务"的比例 | 随 Harness 成熟而提升 |
| 返工率 | PR 因 review 意见被打回重做的比例 | 应该稳定或下降 |
| context 重启频率 | 每个任务平均重启几次 session | 应该随 Harness 改善而降低 |

**质量类（sprint 周期跟踪）：**

| 指标 | 如何度量 | 健康方向 |
|------|---------|---------|
| 生产 bug 率 | 与 AI 生成代码相关的生产 bug 数量 | 不应该随速度提升而上升 |
| E2E 测试覆盖率 | 关键用户场景被 E2E 测试覆盖的比例 | 应该稳步提升 |
| 安全扫描通过率 | agentshield 扫描发现的问题数量 | 随 Harness 成熟而减少 |

**Harness 健康度（sprint retro 时评估）：**

```
Harness 健康度评估（1-5分）：

1. CLAUDE.md 准确性：它现在描述的项目状态还准确吗？
2. Hook 有效性：Hook 有没有被频繁绕过？有没有误报？
3. Agent 自主率：最近 sprint 里，Agent 卡壳几次？每次的原因是什么？
4. 代码库 AI 可读性：新加入的 Agent 能快速理解代码库吗？
5. Skills 使用率：现有的 Skills 有没有被 Agent 使用？有没有遗漏的场景？
```

#### 警惕"AI 速度悖论"

最重要的度量原则：**不要只看速度，要同时看质量**。

如果你发现代码生成速度提升了 50%，但生产 bug 也增加了 50%，你实际上没有提升——你只是把问题推到了后面，让它在生产环境爆发，代价更高。

真正的提效是：**速度提升 AND 质量稳定或提升**。如果两者出现了反向，说明 Harness 的某个环节出了问题，需要排查。

---

*（Part 4 完，共 4 节）*

---

## 附录

### A1：CLAUDE.md 团队模板

```markdown
# [项目名称]

## 项目简介
[2-3句话：这个项目是什么、主要用户是谁、核心价值是什么]

## 技术栈
- 语言：[例：TypeScript 5.x]
- 框架：[例：Next.js 14 + FastAPI]
- 数据库：[例：PostgreSQL 15 + Redis]
- 测试：[例：Jest + Playwright]

## 快速上手
```bash
./init.sh          # 初始化开发环境
npm run dev        # 启动开发服务器（端口 3000）
npm test           # 运行测试
npm run typecheck  # 类型检查
```

## 架构分层
[一句话说明分层规则，例：Repository → Service → Controller，单向依赖，不允许跨层]
详细规则：.claude/skills/architecture.md

## 关键约定
1. [最重要的约定1，例：所有 API 返回值必须通过 zod schema 验证]
2. [最重要的约定2，例：数据库操作只能在 Repository 层进行]
3. [最重要的约定3，例：不允许在 commit 中包含 TODO，改用 issue tracker]
4. [最重要的约定4]
5. [最重要的约定5，最多5条]

## 注意事项（避坑）
- [已知的技术债或遗留问题，例：legacy/ 目录是旧系统代码，不要修改]
- [环境特殊性，例：本地开发需要 VPN]

## Skills 索引
- 需要写 API 测试 → .claude/skills/api-testing.md
- 需要做数据库迁移 → .claude/skills/database-migration.md
- 需要修改前端组件 → .claude/skills/frontend-design.md
- 需要发布流程 → .claude/skills/release.md

## 进度追踪
- 当前任务状态：claude-progress.txt
- 功能清单：feature_list.json

<!-- 最后更新：[日期] · 原因：[更新原因] -->
```

---

### A2：Hooks 配置模板

```json
{
  "hooks": {
    "pre_tool_call": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/pre-bash-secret-scan.sh",
            "description": "扫描 bash 命令中的 secret 模式"
          },
          {
            "type": "command", 
            "command": ".claude/hooks/pre-bash-dangerous-command.sh",
            "description": "拦截高风险命令"
          }
        ]
      }
    ],
    "post_tool_call": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/post-edit-typecheck.sh",
            "description": "文件修改后触发类型检查"
          },
          {
            "type": "command",
            "command": ".claude/hooks/post-edit-lint.sh", 
            "description": "文件修改后触发 lint"
          }
        ]
      }
    ],
    "stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/stop-progress-update.sh",
            "description": "检查 progress 文件是否已更新"
          }
        ]
      }
    ]
  }
}
```

**pre-bash-dangerous-command.sh 示例：**

```bash
#!/bin/bash
# 检测高风险命令
COMMAND="$1"

DANGEROUS_PATTERNS=(
  "rm -rf /"
  "git push --force"
  "git push -f"
  "DROP TABLE"
  "DELETE FROM .* WHERE"
  "truncate"
)

for pattern in "${DANGEROUS_PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qi "$pattern"; then
    echo "ERROR [pre-bash:dangerous-command]: 检测到高风险命令模式：'$pattern'"
    echo "命令内容：$COMMAND"
    echo "如果这是预期的操作，请在命令前加上 '# CONFIRMED_DANGEROUS:' 注释并说明原因"
    exit 1
  fi
done
```

---

### A3：feature_list.json + claude-progress.txt 模板

**feature_list.json：**

```json
{
  "project": "项目名称",
  "created_at": "YYYY-MM-DD",
  "last_updated": "YYYY-MM-DD",
  "summary": {
    "total": 0,
    "completed": 0,
    "in_progress": 0
  },
  "features": [
    {
      "id": "F001",
      "category": "认证",
      "priority": "P0",
      "title": "功能标题",
      "description": "功能的详细描述，包括输入、处理逻辑、输出",
      "test_steps": [
        "具体的、可执行的测试步骤1",
        "具体的、可执行的测试步骤2",
        "边界情况测试"
      ],
      "passes": false,
      "completed_at": null,
      "notes": ""
    }
  ]
}
```

**claude-progress.txt：**

```
=== 项目：[项目名称] ===
初始化时间：YYYY-MM-DD
当前阶段：[例：MVP 开发阶段]

=== Session YYYY-MM-DD HH:MM ===
本次完成：
- [功能 ID] [功能名称]：[完成情况说明]

当前状态：
[对项目当前状态的简短描述]

遇到的问题：
- [问题1]（已解决/待处理）

下一步：
- [下一个要实现的功能 ID 和名称]
- [需要注意的事项]

未提交变更：[有/无]
测试状态：[全部通过/部分通过/有失败]
```

---

### A4：Subagent 定义模板库

**planner.md：**

```markdown
---
name: planner
description: 将用户需求展开为详细的实现计划和功能清单
tools: ["Read", "Grep", "Glob"]
model: opus
---

你是一名资深技术规划师。你的任务是将用户的需求转化为清晰、可执行的实现计划。

工作流程：
1. 读取 architecture.md 了解项目结构
2. 读取现有的 feature_list.json（如果存在）了解已有功能
3. 分析用户需求，识别所有需要实现的功能点
4. 为每个功能点编写详细的描述和可测试的验收标准

输出格式：
- 整体实现计划（分 Phase 描述）
- 更新后的 feature_list.json（新功能项追加到已有列表）
- 依赖关系说明（哪些功能必须先于哪些功能实现）
```

**code-reviewer.md：**

```markdown
---
name: code-reviewer
description: 对代码变更进行独立、批判性的审查
tools: ["Read", "Grep", "Glob", "Bash"]
model: opus
---

你是一名严格的代码审查员。你与实现这些代码的 Agent 完全独立，没有任何"自己写的代码"的包袱。

审查维度（按严重程度排序）：
1. 安全性（Critical）：输入验证、权限检查、SQL 注入、secret 泄露
2. 正确性（Critical）：逻辑是否正确、边界情况是否处理
3. 可靠性（Major）：错误处理、事务完整性、并发安全
4. 可维护性（Minor）：命名清晰度、代码重复、注释质量

输出格式：
- Critical 问题（必须修复才能合并）
- Major 问题（建议修复）
- Minor 问题（可选改进）
- 通过的方面（简短说明为什么这个变更是安全的）

如果没有发现任何问题，请明确说明并给出你的判断依据。不要只说"代码看起来不错"。
```

**security-reviewer.md：**

```markdown
---
name: security-reviewer
description: 专门针对安全漏洞的代码审查
tools: ["Read", "Grep", "Glob", "Bash"]
model: opus
---

你是一名专注于安全的代码审查员。你的任务是发现代码中的安全漏洞。

重点检查：
1. 注入漏洞（SQL 注入、命令注入、XSS）
2. 认证和授权问题（权限检查缺失、越权访问）
3. 敏感数据处理（密码、token、PII 的存储和传输）
4. 输入验证（未经验证的用户输入直接使用）
5. 依赖安全（引入的第三方库是否有已知漏洞）

对于每个发现的问题：
- 说明问题类型和 CVE 参考（如果适用）
- 给出一个最简单的攻击场景说明
- 提供修复建议（包括代码示例）
```

---

### A5：参考资料与延伸阅读

**原始资料：**

- [Harness Engineering: Leveraging Codex in an Agent-First World](https://openai.com/index/harness-engineering/) — OpenAI 原始实验报告
- [Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) — Anthropic 长任务 Harness 研究
- [Harness Design for Long-Running Application Development](https://www.anthropic.com/engineering/harness-design-long-running-apps) — Anthropic 三段式 Harness 实战
- [Skill Issue: Harness Engineering for Coding Agents](https://www.humanlayer.dev/blog/skill-issue-harness-engineering-for-coding-agents) — HumanLayer 团队实战总结
- [Harness Engineering（ThoughtWorks 分析）](https://martinfowler.com/articles/exploring-gen-ai/harness-engineering.html) — Birgitta Böckeler 对 Harness 三要素的分析

**社区资源（持续更新）：**

- [awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) — Claude Code 工具、Hooks、Skills 的精选列表
- [everything-claude-code](https://github.com/affaan-m/everything-claude-code) — 36 个专业化 Subagent + 13 条 Guardrail 规则的完整框架
- [claude-code-best-practice](https://github.com/shanraisshan/claude-code-best-practice) — Boris Cherny 团队的最佳实践总结
- [claude-code-ultimate-guide](https://github.com/FlorianBruniaux/claude-code-ultimate-guide) — 从入门到专家的完整指南

**模型演进追踪：**

Harness 的某些假设会随模型能力提升而失效（例如 Context Reset 在 Opus 4.6 上已经很少需要）。建议订阅 Anthropic 的 [Engineering Blog](https://www.anthropic.com/engineering) 来追踪最新变化。

---

*手册版本：v1.0 · 最后更新：2026年Q2*  
*下次审查：下一个 sprint 结束时*  
*维护人：[yijiang]*
```