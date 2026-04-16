# 工作流使用说明（详尽版）

> 这是**给人读的**使用指南。目标是：一个懂开发但没用过这套 Harness 的同事，读完能独立上手。
> 维护：yijiang · 初版 2026-04-16
> 相关文件：协作契约 `~/.claude/CLAUDE.md`、组件清单 `~/.claude/INVENTORY.md`

---

## 目录

- Part 1：心智模型——理解这套工作流的底层设计
- Part 2：场景化实操（7 个常见场景）
- Part 3：关键决策点速查
- Part 4：Gotchas 飞轮
- Part 5：Harness 自身的演进
- Part 6：反模式与陷阱
- Part 7：快速备忘

---

# Part 1：心智模型

## 1.1 一句话定位

**这套工作流不是"让 AI 帮我写代码"，而是"让我的品味和判断力，可靠地作用到每一次 AI 产出上"。**

换一个角度：工作流不是**工具集**，是**约束系统 + 反馈闭环**。
工具集随时会过时（模型更新、新 CLI 诞生），但"我怎么和 AI 协作"这套**约束与契约**长期稳定。所以这套 Harness 的重心在 CLAUDE.md 和 agent prompt 的规则里，而不在某个具体命令的参数。

## 1.2 五个核心理念（它们决定了工作流长什么样）

### ① 绝佳实践的单一真相源 = 全局 CLAUDE.md

为什么所有 agent 都只写"承接全局 CLAUDE.md"而不自己列一遍绝佳实践？

因为 **CLAUDE.md 会被自动注入到每个 session 和每个 subagent 的 context**。如果每个 agent 都重述一遍，就有 5 份绝佳实践在系统里；改一处忘改另一处，就会漂移。

**结论：想改协作规则或绝佳实践，只改 `~/.claude/CLAUDE.md` 一处**，整套系统（planner、evaluator、code-reviewer 等）自动跟着变。

### ② 三段式的触发阈值

不是所有任务都要走三段式，那是 ceremony 过度。

| 任务类型 | 走法 |
|---------|-----|
| 单步、单文件、无架构决策的琐碎活 | 直接对话 |
| 3 步以上、新功能、涉架构、多文件协调 | **必须** `/plan` → `/code` → `/evaluate` |
| 线上排障、紧急修复 | 不走三段，修完后用 `/evaluate` 做最小验证，并记 gotcha |

### ③ Agent 挣扎 = Harness 缺口（飞轮思维）

本能反应是"这个 AI 不行"。正确反应是"我的 Harness 缺了一块"。

- 是 CLAUDE.md 没说清楚？→ 补一条铁律
- 是缺 skill？→ `/harness-retro` 时新建
- 是 hook 没拦住？→ 加 hook
- 是 agent prompt 有歧义？→ 改 agent

**每次 Agent 卡壳都是免费的 Harness bug report**，别浪费。

### ④ 独立 context 是设计，不是 bug

为什么 evaluator 必须新开 session？为什么 plan 和 code 分离？

因为 AI 在一个 session 里做完事后立刻自评，会有**确认偏差**——它投入了上下文和"努力"，会倾向于报告"完成得很好"。这不是 AI 说谎，而是它的"知情上下文"污染了判断。

**每次切 session 清空 context = 给 AI 一双干净的眼睛。**

### ⑤ 少即是多，精确优于完整

文档不是越全越好、skill 不是越多越好、hook 不是越密越好。

- 冗余文档会腐坏
- 过多 skill 会让 AI 选困难
- 过密 hook 会打断节奏
- 过长 prompt 会占 context

**凡是加东西，先问：它必要吗？它替代了什么？它多久会过时？**

## 1.3 架构全景图

```
┌────────────────────────────────────────────────────────┐
│ ~/.claude/CLAUDE.md  ← 协作契约 + 绝佳实践（真相源）    │
│         ↓ 自动注入所有 session / subagent                │
│ ┌────────────────────────────────────────────────────┐ │
│ │  Slash Commands（入口）                              │ │
│ │    /plan   /code   /evaluate                        │ │
│ │    /harness-retro   /harness-audit                  │ │
│ └────┬──────────┬──────────┬─────────────────────────┘ │
│      ↓          ↓          ↓                             │
│   planner     (主)      evaluator  ← Agents              │
│   agent     claude       agent                           │
│      │        │            │                             │
│      └────────┼────────────┤                             │
│              ↓             ↓                             │
│       code-reviewer · security-reviewer  ← Subagents     │
│              ↓                                           │
│   Skills：skill-creator · doc-templates · eval-rubric · gotchas │
│              ↓                                           │
│   Hooks（每次工具调用/session 结束时强制执行）           │
│    PreToolUse/Bash: secret-scan · dangerous-command      │
│    Stop:            gotchas-prompt                       │
│              ↓                                           │
│   Notification + Stop 声音（你原有的，保留）              │
└────────────────────────────────────────────────────────┘
```

---

# Part 2：场景化实操

## 场景 1：新项目从零开始（最完整的三段式范例）

### 情景
你有一个新想法——"做一个内部用的轻量 TODO 服务，带 Web UI"。从零开始。

### Step 1：打开 Claude Code，切到项目目录

```bash
mkdir ~/projects/todo-service
cd ~/projects/todo-service
claude
```

### Step 2：先定架构（**手动做，不让 AI 先跑**）

不要一上来就让 AI 生成。你先写一份 `architecture.md`（2 页内，可以粗糙），放进项目根目录：
- 技术栈（例：Node + Fastify + SQLite + htmx）
- 分层（API → Service → Repository → DB）
- 目录结构（`src/api`、`src/service`、`src/repo`）
- 关键约束（单向依赖、Repository 不返回 raw rows）

这一步是**防止 AI 在真空中发明架构**——会发明出你不想要的。

### Step 3：建项目级 CLAUDE.md

```bash
# 在项目根目录
cat > CLAUDE.md <<'EOF'
# todo-service

## 一句话
内部 TODO 服务，Node + SQLite + htmx。

## 常用
npm run dev   # 启动（3000 端口）
npm test      # 跑测试

## 分层
API → Service → Repository → DB。单向依赖。

## 禁止
- Repository 外直接写 SQL
- API 层处理业务逻辑
- 不许用 ORM（项目够简单，原生 SQL + 参数化）

<!-- 2026-04-16 初版 -->
EOF
```

**注意**：项目 CLAUDE.md 不重复全局 CLAUDE.md 的协作契约，那是全局的事；项目 CLAUDE.md 只放**项目自身**的知识。

### Step 4：走 /plan

```
你（在 Claude Code 里打）：/plan

实现 TODO 的核心 CRUD：
- GET /todos（列表）
- POST /todos（新建）
- PATCH /todos/:id（编辑标题或状态）
- DELETE /todos/:id

Web 页面用 htmx，所有操作都走 HTML 片段返回。
存储用 SQLite。

个人描述：这是我第一个 htmx 项目，不熟悉 htmx 最佳模式，规划时多给我解释一下 htmx 的约定。
```

**planner 会：**
1. 复述你的需求 → 等你确认
2. 可能提问（例：任务有没有排序需求？是否需要多用户？）→ 你回答
3. 用 Read/Grep 扫项目结构 → 给规划初稿
4. 你审查 → 提修改意见
5. 最终产出三份文档到 `docs/plan/2026-04-16-crud/`

**关键动作：审查规划时重点看什么**
- 分 Phase 是否合理（MVP 是不是最小可合并？）
- 有没有把 htmx 用错成"CRUD 完再做前端"？（Phase 拆分应该每个 Phase 内后端+前端一起）
- commit 规划每个 commit 是否原子可部署

### Step 5：切新 session，走 /code

**在终端**：退出当前 claude（`Ctrl+D`），重新进：

```bash
claude
```

新 session，打 `/code`：

```
执行 docs/plan/2026-04-16-crud/design.md 的 Phase 1（MVP）。
从 Commit 1 开始。
```

**Commit 1 完成后 claude 会停下来**：
"Commit 1 已完成：建表 + Repository.insert。测试已通过。
下一步 Commit 2：Service 层 createTodo + 对应测试。继续？"

你说"继续"再往下。

**关键动作**：
- 如果你想派 subagent 做"调研 htmx 最佳响应模式"，主 claude 应该主动提议——没提议，你可以手动要求："这块你先派 subagent 研究一下 htmx 的最佳片段返回模式再开始"
- 中途任何卡壳，**不要硬催 AI 想办法**，停下来问：是 plan 漏了？是信息不够？记 gotcha。

### Step 6：切新 session，走 /evaluate

Phase 1 所有 commit 完成后，再退出 claude，重新进：

```
/evaluate

评估最近 5 个 commit（git log --oneline -5）。
验收标准见 docs/plan/2026-04-16-crud/design.md#验收标准。
```

**evaluator 会**：
1. 读 `eval-rubric` 锚定六维度
2. 读验收标准
3. 实际跑 test_steps（包括 `npm test`、`curl` 打接口）
4. 逐维度打分，产出报告

**判决处理**：
- **PASS** → 合并、标记 feature 完成、进入 Phase 2
- **WARN/BLOCK** → 新开 coding session 修，然后再 `/evaluate` 一次

### Step 7：session 结束时

关闭 claude 前会弹 **gotchas 对话框**。
- 这次你踩到的坑是什么？
- 示例输入：`htmx 的 HX-Trigger header 在 response 里大小写敏感，之前试 hx-trigger 失效浪费 20 分钟`

下次类似场景，AI 会读到这条 gotcha 避开。

### 关键注意点
- ✅ 每个阶段切 session
- ✅ 每个 commit 单元停下确认
- ✅ 绝不让 AI 同时开两个功能
- ✅ Phase 完成都要 /evaluate 一次，不要积压到项目尾声

---

## 场景 2：旧项目接手后加新功能（代码考古 + 渐进）

### 情景
你接手一个两年前同事写的后端服务，要新加"订单批量导出"功能。代码量 ~5 万行，你没通读过。

### 核心策略：**先让 AI 建立对项目的理解，再走三段式**

### Step 1：让 AI 做一次代码考古

```
你：请探索当前代码库，产出一份 architecture.md 放到项目根目录。
内容包含：
1. 项目是做什么的（2-3 句话）
2. 技术栈
3. 目录结构及职责
4. 主要数据流（请求进来经过哪些层）
5. 你发现的主要模式和约定（即使是非正式的）
6. 你发现的技术债 / 不一致之处（如实描述，不要美化）

完成前先阐述你的探索策略，我确认后再开始。
```

**关键动作**：
- **这不是 /plan，这是一次性的考古任务**。探索完了产出 `architecture.md`，**人工审查并修正**
- 你会发现 AI 找到了你都不知道的问题——这本身是收益
- **不要相信任何一个字，逐点核对**。错的直接改正。

### Step 2：更新项目 CLAUDE.md

基于 architecture.md + 你的了解，更新项目 CLAUDE.md，**明确告诉 AI 有哪些"地雷"**：

```markdown
## 禁止踩的地雷
- legacy/ 目录是 2022 年以前的旧逻辑，不要改，不要模仿
- utils/fmt.ts 里的函数很多已废弃但未删，新代码用 src/format/ 下的
- 订单相关只有 order.service.ts 可信，orderV2 是已废弃的旧尝试
```

### Step 3：走 /plan（但在 prompt 里强调"渐进"）

```
/plan

在现有订单服务基础上，新增"批量导出"：
- POST /orders/export，接收筛选条件，返回 CSV 下载链接
- 需要支持至少 10 万条数据
- 异步任务，用 bull 队列（当前项目已有）

个人描述：
- 这是旧项目接手，我对订单模块的细节还不够熟
- 规划时请先摸清 order.service.ts 里已有哪些可复用的查询逻辑，不要重新发明
- 如果发现现有架构不支持某个需求，先告诉我，不要擅自"顺便重构"
```

**planner 会**：
- 摸代码、查既有 query 构造器
- 明确标出"复用 XXX 函数" vs "需要新增"
- 如果发现"legacy 里有个相似实现但不能用"会在规划里注明

### Step 4-6：/code 和 /evaluate 同场景 1

**特别提醒**：旧项目最容易中招的是 **AI 复制了 legacy 里的坏模式**。
- Evaluator 阶段特别看一下：有没有从 legacy/ 里 import？有没有用废弃的 utils/fmt？
- 在项目 CLAUDE.md 的"地雷"清单里明确列出来之后，AI 一般不会踩；但要抽查

### 关键注意点
- ✅ 考古第一，规划第二
- ✅ 项目 CLAUDE.md 明确列"地雷"（禁区、废弃代码、陷阱）
- ✅ 规划时强调"复用 > 新增"，避免 AI 重新发明
- ✅ 评估时特别检查是否污染了 legacy 模式
- ❌ 不要上来就让 AI "整理一下代码库"——代价太高，没完没了

---

## 场景 3：线上排障 / 紧急修复

### 情景
凌晨 3 点告警，生产服务 500。你需要快速定位和修复。

### 核心策略：**不走三段式，但纪律不能松**

### Step 1：先别让 AI 动手，让它先搞清楚发生了什么

```
你：生产环境 users service 在过去 30 分钟内 500 率 15%。
日志里看到大量 "database connection timeout"。

不要修任何代码。先做：
1. 梳理最近 48 小时的 commit，列出可能相关的
2. 读 DB 连接池配置
3. 给我最可能的 3 个猜测，按概率排序
```

**关键动作**：
- 不 `/plan` 也不 `/code`，直接对话
- 但你依然强制 "谋而后动"——"先分析，别动手"
- 让 AI 给**多个假设**，不要让它一条路走到黑

### Step 2：确认假设后再让它修

```
你：对，是 Commit abc123 引入的。那个 commit 里加了个 for 循环里单条查询，变成了 N+1。

请改成批量 IN 查询。只改这一处，不要顺手优化别的。
```

**关键**：告诉它**只改这一处**。线上排障最怕 AI "顺手优化"引入新 bug。

### Step 3：修完跑 /evaluate（极简版）

即使紧急，也不要跳过 evaluate。但可以告诉 evaluator "只看这一处修改，跑回归测试"：

```
/evaluate

只评估 commit abc456（N+1 修复）。
不跑全套 rubric，重点：
- 功能正确性（原场景修复 + 回归）
- 有没有引入新的 N+1 或锁
```

### Step 4：事后记 gotcha

session 结束弹窗时，一定要记。示例：

```
N+1 查询在单元测试里看不出来（测试数据太少），只有生产数据规模才会暴露。
教训：PR review 时对"循环里调 DB"零容忍，哪怕只有 1 处。
```

### 关键注意点
- ✅ 先分析，后动手
- ✅ 明确只改这一处
- ✅ 事后的 gotcha 必须记
- ❌ 不要因为紧急就跳过 evaluate（可以精简，不能跳过）
- ❌ 不要让 AI 在紧急状态下"顺手改"相关代码

---

## 场景 4：大型重构（分 Phase + worktree 并行）

### 情景
要把单体后端拆成 3 个微服务。持续 2 个 sprint。

### 核心策略：**分 Phase + 每 Phase 完整三段 + 独立 worktree 并行**

### Step 1：先用 /plan 做顶层 Phase 切分

```
/plan

把 monolith 拆成 auth / order / inventory 三个服务。
约束：
- 保持 API 契约不变（前端不改）
- 通过 RPC 调用，用当前已有的 gRPC 基建
- 数据库暂时共用，下个 Phase 再拆

个人描述：
- 这次规划请做"顶层 Phase 切分"，不做每个 Phase 的细节
- 每个 Phase 完成后我会单独再开 /plan 做细化
```

产出：Phase 0（准备工作）→ Phase 1（抽 auth）→ Phase 2（抽 order）→ Phase 3（抽 inventory）→ Phase 4（清理 monolith）

### Step 2：每个 Phase 再单独 /plan + /code + /evaluate

不要一次性规划 4 个 Phase 的细节——context 太长，且前一个 Phase 会改变后一个 Phase 的前提。

### Step 3：Phase 2 和 Phase 3 可以并行（用 git worktree）

```bash
# 主 worktree 做 Phase 2
cd ~/projects/monolith
git worktree add ../monolith-phase3 feature/extract-inventory

# 开两个终端
# 终端 1：Phase 2
cd ~/projects/monolith && claude

# 终端 2：Phase 3
cd ~/projects/monolith-phase3 && claude
```

两个 Phase **完全隔离**，各自走三段式，最后 merge 合并。

### Step 4：大重构特别警惕：Evaluator 必须跑 E2E

每个 Phase 的 /evaluate，除了单元测试，**必须跑端到端**：
- 前端完整走一遍主流程
- 能 curl 就 curl 全链路

原因：单元测试很容易在重构中保持 pass（AI 会调整 mock），但 E2E 很难作弊。

### 关键注意点
- ✅ 顶层切 Phase → 逐 Phase 三段式
- ✅ 独立 worktree 并行，不要在一个分支上同时搞多 Phase
- ✅ E2E 验证是重构的救命稻草
- ❌ 不要一次规划全部细节
- ❌ 不要让 AI 同时在 3 个服务里跳来跳去

---

## 场景 5：小修小补（不开 ceremony）

### 情景
改个按钮文案、加一行日志、调一个阈值常量。

### 核心策略：**直接对话，不开三段式**

```
你：把 src/pages/dashboard.tsx 里 "登出" 按钮的文案改成 "退出"，其他不动。
```

主 claude 会**依然遵守 CLAUDE.md 铁律**：复述 → 确认 → 动手。不需要 /plan。

### 关键注意点
- ✅ 琐碎任务不开 ceremony
- ✅ 但铁律不变：AI 依然会复述+等确认
- ❌ 不要自己判断"这任务琐碎就跳过复述"——那是 AI 该做的判断，你让它跳它才跳

---

## 场景 6：文档补完

### 情景
项目架构文档缺失 / 过时，需要补一份。

### Step 1：让 AI 做考古（同场景 2 的 Step 1）

### Step 2：套用 `doc-templates` skill 的架构文档模板

```
你：基于你刚才的考古，按 doc-templates skill 的架构文档模板，起草一份 architecture.md。
输出后我审查，然后我会自己手动修订。

注意：你的产出只是草稿，不要自认为是最终版。
```

### Step 3：你逐段审查、修正、发布

**关键**：架构文档**不允许 AI 直接提交**。AI 起草，人工确认。这是 CLAUDE.md 的铁律之一。

---

## 场景 7：探索性调研 / 技术选型

### 情景
要引入一个消息队列，不确定选 RabbitMQ / Kafka / NATS。

### 核心策略：**用 subagent 做独立调研，主 claude 汇总**

```
你：我要给项目加消息队列，候选 RabbitMQ / Kafka / NATS。
当前项目规模：[XXX]
需求特点：[XXX]
非功能要求：[XXX]

请你：
1. 派 3 个 subagent 分别深入调研这三个候选
2. 每个 subagent 返回：核心特点、与当前项目的契合度、陷阱、迁移成本
3. 主 agent 汇总，给出推荐和理由

不要直接回答我的问题——先按这个流程执行。
```

**为什么用 subagent**：每个候选的调研会占大量 context（文档、示例、对比），汇集到主 agent 会爆。subagent 各自独立 context，返回**压缩结果**给主 agent。

### 关键注意点
- ✅ 调研类任务天然适合 subagent 并行
- ✅ 明确要求返回格式（压缩结果），不要让 subagent 返回全文
- ✅ 主 agent 的职责是汇总和推荐，不是自己做全部调研
- ❌ 不要让主 claude 一个人调研 3 个候选——context 会被撑爆、后面没法细聊

---

# Part 3：关键决策点速查

## 3.1 何时切 session（清空 context）

| 场景 | 切 | 不切 |
|------|---|-----|
| plan 阶段刚结束，要进入 coding | ✅ 切 | |
| coding 阶段刚结束，要进入 evaluate | ✅ 切（**强制**） | |
| 一个完整功能已合并 | ✅ 切 | |
| 从 A 功能转去做 B 功能（无关） | ✅ 切 | |
| 觉得 AI 行为奇怪、疑似 context 污染 | ✅ 切 | |
| 距离上次切已经 2+ 小时且话题很多 | ✅ 切 | |
| 当前 commit 只完成了一半 | | ❌ 不切 |
| 还在调试同一个问题的不同假设 | | ❌ 不切 |
| 刚做完复述确认，还没开始执行 | | ❌ 不切 |

**判断原则**：切 session 的成本 = 重新摸一遍项目上下文。如果当前 session 的 context 里有大量"正在进行的状态"，切了就要重新建立。所以**切在"自然断点"而不是"随便一个时刻"**。

## 3.2 何时用 subagent

| 场景 | 用 subagent |
|------|-------------|
| 需要深度研究一个主题（代码考古、第三方库调研） | ✅ |
| 需要同时探索多个方案 | ✅（多 subagent 并行） |
| 要做代码 review 但主 context 已经有了"实现思路" | ✅（code-reviewer 独立 context） |
| 要做安全 review | ✅（security-reviewer） |
| 要做独立评估 | ✅（evaluator，走 /evaluate） |
| 简单的文件改动 | ❌ 别用 |
| 主任务本来就简单 | ❌ 别用 |
| 不需要独立 context 的信息查询 | ❌ 直接 Grep |

**何时主动提议 vs 被动等用户要求**：
- AI 应该主动提议（CLAUDE.md 铁律 3），由用户拍板
- 用户也可以直接指令："这块你先派 subagent 研究一下"

## 3.3 何时升级到三段式

| 触发条件 | 走法 |
|---------|-----|
| ≥3 步且涉及新文件 | 三段式 |
| 涉及架构决策（新增层、换存储、换模式） | 三段式 |
| 涉及 3+ 文件协调修改 | 三段式 |
| 涉及安全敏感（鉴权、支付、用户数据） | 三段式（且 evaluate 必派 security-reviewer） |
| 跨 session 要做 30 分钟+ | 三段式 |
| 单步改一个常量 | 直接对话 |
| 纯文档修订 | 直接对话 |
| 添加一个小工具函数 | 直接对话 |

**边缘情况**：任务起初看着像琐碎，做的过程中发现涉及架构 → **立刻停下，切 session 走 /plan**。不要"半路升级"继续在当前 session 里摸。

## 3.4 何时让 AI "强制放慢"

有些时刻 AI 会急着推进，但你应该强制它放慢：

| 时刻 | 怎么说 |
|------|-------|
| 它跳过复述直接给方案 | "停。先复述你的理解再说。" |
| 它没问就假设了关键点 | "你假设了 X，但这个我没确认。先问我，不要自己填。" |
| 它连续跑 5 个工具调用没停 | "暂停。汇报一下你做到哪了、接下来要做什么。" |
| 它准备删/覆盖文件 | "先说清楚你要删什么、为什么，等我说可以。" |
| 它说"已经完成了" | "别急。run evaluator 或自己做一遍 Challenge：这实现最大的 3 个风险是什么？" |

---

# Part 4：Gotchas 飞轮

## 4.1 机制

```
session 运行中
    ↓
session 结束（主动 Ctrl+D 或 AI stop）
    ↓
Stop hook 触发 → osascript 弹窗
    ↓
你有 30 秒决定：
  - 输入内容 → 追加到 ~/.claude/skills/gotchas/SKILL.md
  - 留空 + OK → skip
  - Cancel 或超时 → skip
    ↓
（如果写了）下次 session，AI 可按需 Read gotchas skill
```

## 4.2 什么值得记

| 值得记 | 不值得记 |
|--------|---------|
| 浪费了 15+ 分钟才搞清楚的小陷阱 | 一看就懂的常识 |
| 被同一个问题绊倒过 2+ 次 | 一次性的环境问题 |
| 非显而易见的工具/API 行为 | 标准用法 |
| 踩了 AI 的"过度自信"坑 | AI 的一次性失误（可能下次不会） |

**示例（值得记的 gotcha）**：
- "htmx 的 HX-Trigger header 区分大小写，hx-trigger 小写版本失效"
- "在 macOS 上用 osascript 弹 dialog，text returned 字段解析要小心换行符"
- "PostgreSQL 的 json 字段比较用 -> 取值再 = 比较，不能直接 = 整个 json"
- "Claude Code 的 Stop hook 不能用交互式 stdin，得用 osascript"

## 4.3 如何消费 gotchas

1. **被动消费**：Agent 在开始新任务前会主动 `Read` gotchas skill（如果 description 描述与任务相关）
2. **主动消费**：你在 /plan 的 prompt 里可以说"开始前先读 gotchas skill 看有无相关踩坑"
3. **定期审查**：`/harness-retro` 时通读一遍，升级共性 gotcha 为 CLAUDE.md 铁律或 hook 规则

## 4.4 清理纪律

- **每月至少审查一次**（`/harness-audit` 顺手做）
- **超过 6 个月未触发**的 gotcha → 归档或删除
- **被升级为 CLAUDE.md / hook 的** → 从 gotchas 删除（避免双份）

---

# Part 5：Harness 自身的演进

## 5.1 演进的触发事件

| 事件 | 要做什么 |
|------|---------|
| 某个 Agent 行为反复不符合预期 | `/harness-retro` 里识别根因，改对应组件 |
| 新 Claude 版本发布 | 评估哪些 Harness 机制可以放松（例：context 管理） |
| 团队规模变化 | 可能需要增加协作约定 |
| 新技术栈加入 | 可能需要新的项目级 skill |
| 连续 3 次踩同一个坑 | 从 gotchas 升级为 CLAUDE.md 铁律或 hook |

## 5.2 演进的位置选择

**决策树**：

```
发现一个 Harness 改进点
    ↓
这是"硬性强制"吗？（必须每次都执行、不能靠 AI 自觉）
    ├── 是 → Hook
    └── 否 ↓
这是"跨项目通用知识"吗？
    ├── 是 ↓
    │   这是"每次都要读"的吗？
    │     ├── 是 → 加到全局 CLAUDE.md
    │     └── 否 → 做成全局 Skill
    └── 否（项目特定） ↓
        这是"特定场景的深度知识"吗？
          ├── 是 → 项目级 Skill
          └── 否 → 项目 CLAUDE.md
```

## 5.3 演进节奏

| 频率 | 动作 |
|------|------|
| 每天 | session 结束时按需记 gotcha |
| 每 2 周 | `/harness-retro`（15 分钟） |
| 每月 | `/harness-audit`（30 分钟） |
| 每季度 | 通读全局 CLAUDE.md + agent prompt，看有无过时内容 |
| 模型大版本更新 | 重新评估哪些约束可以放松 |

## 5.4 演进的纪律

1. **不要 AI 自主改 CLAUDE.md 或 agent prompt**。AI 可以草拟，人工必审。
2. **改动标注日期和原因**（在文件末尾注释）。方便追溯。
3. **改动后跑自检**（见 INVENTORY.md §6）。
4. **大幅改动前先备份**（`~/.claude/backups/`）。

---

# Part 6：反模式与陷阱

## 6.1 Vibe Coding（氛围编程）——最大的陷阱

**症状**：
- AI 给啥接啥，不逐点审查
- 不理解代码库，完全靠 AI 的建议做判断
- 每次 PR review 就是"看起来不错，合并"

**代价**：
- 质量债务快速积累
- 失去对系统的理解 = 失去控制力
- AI 给出自信但错误的答案时，你没能力识别

**对策**：
- **理解每一行代码不必要，但理解架构、关键决策、约束系统必须**
- 每个 plan 阶段亲自审查分 Phase 合理性
- 每个 evaluate 阶段看总评之外，抽查一两个 Critical / Major 的具体位置

## 6.2 AI 速度悖论

**症状**：
- 代码生成速度 +50%
- 生产 bug 也 +50%
- 实际效率未提升，只是把成本推到了下游

**对策**：
- 跟踪两个指标同时变化（代码产出速度 vs 生产 bug 率）
- E2E 测试优先，单元测试补充
- Evaluator 必须实际跑测试，不能只看代码"应该 work"

## 6.3 三段式仪式化

**症状**：
- 改个文案也走 /plan → /code → /evaluate
- 搞了一堆 ceremony 结果没有实际价值
- 所有任务都装模作样走流程，反而真正需要的任务走不认真

**对策**：
- 严格按触发阈值判断（见 Part 3.3）
- 琐碎任务直接对话，铁律（复述+确认）依然生效
- 把 ceremony 留给真正值得的任务

## 6.4 过度信任 Evaluator 自评

**症状**：
- Evaluator 说 PASS，你就直接合并
- 不抽查 Critical 问题的具体位置
- 不实际跑一下主流程

**对策**：
- Evaluator 是助手，不是法官
- 重要功能（支付、鉴权、数据迁移）合并前你必须**自己走一遍主场景**
- 如果 evaluator 长期 PASS 但生产有 bug → 升级 eval-rubric

## 6.5 忘了切 session

**症状**：
- Plan 完了在同一个 session 里继续 /code
- Coding 完了在同一个 session 里继续 /evaluate
- AI 的判断被前面的 context 污染

**对策**：
- 养成 `Ctrl+D` → `claude` 的肌肉记忆
- 如果忘了切，发现时立刻切，不要想"算了这次就这样"

## 6.6 Harness 固化症

**症状**：
- 搭建完 Harness 之后几个月不改
- 模型升级了还用老 Harness
- gotchas 攒了一堆但从没升级过

**对策**：
- 严格执行每双周 `/harness-retro`
- 把 retro 当作真正的工作，不是形式

## 6.7 全局污染症

**症状**：
- 把项目特定的 skill/hook 写进全局
- 全局 CLAUDE.md 里有项目细节
- 一份全局配置跨不了项目用

**对策**：
- 每次想加东西进全局，先问："这在其他项目也用得上吗？"
- 不确定 → 放项目级
- 全局 CLAUDE.md 只写"协作契约+通用绝佳实践"，**不写任何具体项目名**

---

# Part 7：快速备忘

## 7.1 命令速查

| 命令 | 什么时候用 |
|------|-----------|
| `/plan` | 中等+任务开始 |
| `/code` | plan 完成后，新 session |
| `/evaluate` | code 完成后，新 session |
| `/harness-retro` | 每 2 周 |
| `/harness-audit` | 每月 |

## 7.2 Agent 速查

| Agent | 作用 | 触发方式 |
|-------|-----|---------|
| `planner` | 规划三份文档 | `/plan` |
| `evaluator` | 独立评估 | `/evaluate` |
| `code-reviewer` | 代码 review subagent | 主 claude 主动派 / 你要求 |
| `security-reviewer` | 安全 review subagent | 主 claude 主动派 / 涉敏感时 |

## 7.3 Skill 速查

| Skill | 什么时候被加载 |
|-------|--------------|
| `skill-creator` | 你要新建 skill 时 |
| `doc-templates` | Agent 写需求/设计/架构文档时 |
| `eval-rubric` | Evaluator 打分前 |
| `gotchas` | Agent 开新任务前按相关性检查 |

## 7.4 Hook 速查

| Hook | 触发 | 你会感知到 |
|------|------|-----------|
| `secret-scan` | AI 要跑含 secret 的 bash | 命令被拒，AI 会看到错误提示 |
| `dangerous-command` | AI 要跑 rm -rf / git push --force 等 | 同上 |
| `gotchas-prompt` | session 结束 | 看到 osascript 弹窗 |
| Notification 声音 | AI 等你授权时 | 听到 Ping |
| Stop 声音 | 任务完成时 | 听到 Glass |

## 7.5 常用文件路径

- 全局协作契约：`~/.claude/CLAUDE.md`
- 组件清单：`~/.claude/INVENTORY.md`
- 本指南：`~/.claude/workflow-guide.md`
- Gotchas：`~/.claude/skills/gotchas/SKILL.md`
- 备份：`~/.claude/backups/`
- retro 记录：`~/.claude/retros/`（`/harness-retro` 自动创建）
- audit 记录：`~/.claude/audits/`（`/harness-audit` 自动创建）

## 7.6 应急回滚

如果 Harness 改坏了：

```bash
# 查看备份
ls -la ~/.claude/backups/

# 恢复到最近备份（示例）
cd ~
tar -xzf ~/.claude/backups/pre-harness-YYYYMMDD-HHMMSS.tar.gz
```

---

## 结语

这套 Harness 不是终点，是**起点**。

它承载的每一条规则、每一个组件，都应该在实际使用中被验证、被改进、被简化或被废弃。

**你是方向盘，AI 是引擎。Harness 是让这两者稳定连接的传动轴。**

如果某一天你发现 Harness 变得碍事、变得过时、变得不再反映你对协作的理解——那不是 Harness 的问题，是到了该改它的时候。

Happy shipping.

<!-- 2026-04-16 初版 · 维护人 yijiang -->
