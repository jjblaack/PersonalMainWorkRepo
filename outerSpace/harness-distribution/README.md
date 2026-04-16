# Harness 分发包

一套为 **macOS + Claude Code** 打造的个人 AI 协同开发 harness。
两条路径随你挑，共用同一组核心理念。

---

## 两条路径

### 路径 1 · 深度适配（建议 1–2 小时，需 2–3 轮对话）

**适合**：想把 harness 贴合到你自己工作习惯的人。
**产出**：一套和你的 Soul（个人哲学）深度绑定的 `~/.claude/` 配置。

**开始方式**：
1. 翻一眼 `path1-deep-adaptation/soul-example-yijiang.md`（原作者范例，看看 Soul 长什么样）
2. 复制 `path1-deep-adaptation/soul-template.md`，按里面的提示填成你自己的 Soul
3. 在**分发包根目录下**启动 Claude Code
4. 把 `path1-deep-adaptation/BOOTSTRAP.md` 的内容整段贴给 Claude
5. 按 Claude 的引导完成对话（它会不断问你确认，这是设计特性，别嫌烦）

---

### 路径 2 · 一键快装（建议 15–30 分钟，一次对话搞定）

**适合**：先享受 harness、个人化以后慢慢补的人。
**产出**：和原作者同一套 harness 直接装到你的 `~/.claude/`。

**开始方式**：
1. 在**分发包根目录下**启动 Claude Code
2. 把 `path2-quick-install/BOOTSTRAP.md` 的内容整段贴给 Claude
3. Claude 会先问你是新用户还是老用户，然后按安装说明一步步装
4. 装完 Claude 会主动列出你需要个人化替换的字段（名字、角色等）

---

## 两条路径可以互相切换

- 装完路径 2 想深度适配？随时改 `~/.claude/CLAUDE.md` + 补 `~/.claude/my-coding-soul.md`，再跟 Claude 说"基于我的 Soul 调整 CLAUDE.md"
- 路径 1 走到一半嫌慢？直接跳到路径 2 装完，回头再补 Soul

---

## 前置要求

- **macOS**（hook 里的 `osascript` 弹窗是 macOS 原生能力，Linux/Windows 需要改 hook 换成 zenity / PowerShell dialog）
- **Claude Code CLI** 已安装并能正常使用
- `~/.claude/` 目录存在（Claude Code 首次运行会自动建）

## 核心能力概览（两条路径产出一致）

| 能力 | 实现形式 |
|---|---|
| 6 条协作铁律 | 全局 `CLAUDE.md` |
| 三段式工作流 | `/plan` → `/code` → `/evaluate` slash commands + 对应 agents |
| 硬编码 secret 硬拦 | `secret-scan.sh` hook |
| 危险命令交给你拍板 | `dangerous-command.sh` hook（osascript 弹窗） |
| 会话结束记踩坑 | `gotchas-prompt.sh` hook + `gotchas` skill |
| 月度复盘/审计 | `/harness-retro` + `/harness-audit` |

## 文件结构

```
harness-distribution/
├─ README.md                              ← 本文件
│
├─ path1-deep-adaptation/                 ← 深度适配
│  ├─ BOOTSTRAP.md                        ← 粘给 Claude Code 的入口 prompt
│  ├─ soul-template.md                    ← 空 Soul 模板，带占位符和填写提示
│  ├─ soul-example-yijiang.md             ← 原作者 Soul 完整版（参考范例）
│  ├─ harness-manual-原稿.md              ← harness 工程方法论知识源（背景读物）
│  ├─ builder-guide.md                    ← 精简版搭建指南（面向 agent）
│  └─ agent-steps.md                      ← agent 执行步骤 + 强制检查点
│
└─ path2-quick-install/                   ← 一键快装
   ├─ BOOTSTRAP.md                        ← 粘给 Claude Code 的入口 prompt
   ├─ INSTALL.md                          ← 给人看的安装说明
   ├─ agent-steps.md                      ← agent 安装步骤 + 强制检查点
   └─ claude-home/                        ← 待拷到 ~/.claude/ 的整包
      ├─ CLAUDE.md                        ← 身份段已替换为 {{占位符}}
      ├─ settings.json
      ├─ agents/        (planner / evaluator / code-reviewer / security-reviewer)
      ├─ commands/      (/plan /code /evaluate /harness-retro /harness-audit)
      ├─ hooks/         (secret-scan / dangerous-command / gotchas-prompt)
      └─ skills/        (skill-creator / doc-templates / eval-rubric / gotchas)
```

## 共同纪律（两条路径都生效）

无论走哪条，**agent 在动手前都会反复向你确认**。这是 harness 的设计原则之一：
- 改你已有文件前先列清楚动什么
- 改动前先备份 `~/.claude/` 整包快照
- 涉及删除/覆盖必须明确授权
- settings.json 永远增量合并，不整份覆盖

如果 agent 没问就开始动，你有权随时打断：「停，先说清楚」。

## 有问题怎么办

- 装完 hook 弹不出来：检查 `~/.claude/hooks/*.sh` 是否有执行权限（`chmod +x`），Claude Code 需要重启生效
- 想卸载：备份在 `~/.claude/backups/pre-install-*.tar.gz`，解压即可还原
- Claude 卡壳：把报错原样贴回去让它自己分析
