# 一键快装 · 安装说明（给人看的）

> 这份是给你（使用者）看的。agent 装的时候会自动走 `agent-steps.md`。

---

## 装完你会得到什么

一套开箱即用的全局 `~/.claude/` harness，包含：

| 能力 | 实现 |
|---|---|
| 6 条协作铁律 | `CLAUDE.md` |
| 三段式工作流 | `/plan` → `/code` → `/evaluate` + 对应 agents |
| 硬编码 secret 硬拦 | `hooks/secret-scan.sh` |
| 危险命令（rm -rf / git push --force 等）交给你拍板 | `hooks/dangerous-command.sh`（osascript 弹窗） |
| 会话结束记踩坑 | `hooks/gotchas-prompt.sh` + `skills/gotchas/` |
| 月度复盘/审计 | `/harness-retro` + `/harness-audit` |
| 4 个专项 agent | planner / evaluator / code-reviewer / security-reviewer |
| 4 个核心 skill | skill-creator / doc-templates / eval-rubric / gotchas |

## 目录结构预览（装到 `~/.claude/` 后长这样）

```
~/.claude/
├─ CLAUDE.md               ← 全局协作契约（有占位符需要你改）
├─ settings.json           ← 增量合并后的配置（保留你原有的）
├─ agents/
│  ├─ planner.md
│  ├─ evaluator.md
│  ├─ code-reviewer.md
│  └─ security-reviewer.md
├─ commands/
│  ├─ plan.md
│  ├─ code.md
│  ├─ evaluate.md
│  ├─ harness-retro.md
│  └─ harness-audit.md
├─ hooks/
│  ├─ secret-scan.sh       ← chmod +x
│  ├─ dangerous-command.sh ← chmod +x
│  └─ gotchas-prompt.sh    ← chmod +x
└─ skills/
   ├─ skill-creator/
   ├─ doc-templates/
   ├─ eval-rubric/
   └─ gotchas/
```

## 前置要求

- **macOS**（hook 用 osascript 弹窗，Linux/Windows 需要改 hook 换成 zenity / PowerShell dialog）
- **Claude Code CLI** 已装且能用
- 建议 `~/.claude/` 已存在（Claude Code 首次运行会自动建）

## 怎么启动安装

1. 在**分发包根目录下**打开 Claude Code
2. 把 `BOOTSTRAP.md` 里那段 prompt 整段粘给 Claude
3. Claude 会先 Read 文档，然后问你：
   - 你是新用户还是老用户？
   - `~/.claude/` 当前有什么？
   - 处理策略（A/B/C/D）
4. 你回答后，Claude 会做备份 → 合并 settings → 拷贝文件 → 冒烟测试
5. 装完 Claude 会列出你需要手动改的占位符

## 装完要做什么

### 必做（第一次使用前）

1. 打开 `~/.claude/CLAUDE.md`，把里面 `{{你的名字}}` 替换成你的名字
2. 把 `## 我是谁` 那节改成你的身份描述（角色 + 工作场景）
3. 试跑一次验证：
   - 在任意项目下输 `/plan`，看 planner session 能不能正常触发
   - 发一个含 `rm -rf /tmp/demo` 的命令，看危险命令弹窗能不能弹出来

### 可选（随时可以补）

1. **完善 Soul**：参考分发包里的 `path1-deep-adaptation/soul-template.md` 填一份你自己的 Soul，放到 `~/.claude/my-coding-soul.md`。然后跟 Claude 说"基于我的 Soul 调整 CLAUDE.md"，它会按你的 Soul 更新协作铁律、绝佳实践、工作流阈值、评审维度。
2. **补 gotchas**：每次 session 结束 hook 会弹输入框，你写一句踩坑就自动追加到 `~/.claude/skills/gotchas/SKILL.md`。累积几周就是你的个人知识库。
3. **加新 skill**：用 `skill-creator` skill 创建你常用的 skill（比如某个框架、某种代码风格）。

## 常见问题

**Q: 装完 hook 弹不出来？**
A: 三步排查：
1. `ls -la ~/.claude/hooks/*.sh` 看是否有执行权限，没有就 `chmod +x ~/.claude/hooks/*.sh`
2. Claude Code 需要重启才能加载新 hook
3. 检查 `~/.claude/settings.json` 里有没有正确注册（PreToolUse + Stop）

**Q: secret-scan 误报了？**
A: 如果你的命令确实需要包含示例 secret（比如写文档），临时在环境变量里做，或者跟 Claude 说"这是文档示例，请求豁免"，Claude 会换一种方式帮你做。

**Q: 我想卸载？**
A: 备份在 `~/.claude/backups/pre-install-<timestamp>.tar.gz`，解压覆盖就能还原到装之前的状态：
```bash
tar -xzf ~/.claude/backups/pre-install-<timestamp>.tar.gz -C ~
```

**Q: 我想同时享受一键快装 + 深度适配？**
A: 顺序：
1. 先走一键快装，装完能用
2. 参考 `path1-deep-adaptation/soul-template.md` 填你的 Soul
3. 跟 Claude 说"帮我基于我的 Soul 调整 CLAUDE.md 和各个 skill/agent"

**Q: 已经在用一套自己的 ~/.claude/，会被覆盖吗？**
A: 不会。Claude 在装之前会先问你策略：
- A. 全替换（激进）
- B. 合并保留你原有的（推荐）
- C. 纯增量（最保守）
- D. 暂停让你想好

而且改动前会先 `tar -czf` 整包备份，随时能还原。
