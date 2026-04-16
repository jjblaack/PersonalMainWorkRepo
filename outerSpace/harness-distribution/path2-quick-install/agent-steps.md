# Agent 执行步骤参考 · 一键快装路径

> 这份是给你（agent）看的操作手册。用户通过 `BOOTSTRAP.md` 把任务交给你。
> **带 🛑 的步骤是强制检查点，必须停下来问用户，不得跳过、不得合并。**
> 目标：把 `claude-home/` 整包复制到 `~/.claude/`，最小摩擦装完，装后提醒个人化替换。

---

## 阶段 0 · 对齐理解

1. Read：
   - `path2-quick-install/agent-steps.md`（本文件）
   - `path2-quick-install/INSTALL.md`

2. 🛑 **向用户复述任务理解**：
   - 目标：把 `path2-quick-install/claude-home/` 整套复制到 `~/.claude/`
   - 装前要先备份 + 问清老用户策略 + 增量合并 settings.json
   - 装后要主动列出需要个人化替换的占位符

   等用户说"可以"再推进。

## 阶段 1 · 识别用户身份状态

3. 运行 `ls -la ~/.claude/`，列清楚当前环境。

4. 🛑 **问用户是新用户还是老用户**：
   > "我看到你的 `~/.claude/` 里当前有 [列具体文件/目录]。你之前用过 Claude Code 吗？这些是你的自定义配置吗？哪些是不能动的？"

5. 🛑 **根据现状选策略**：

   **5a. 完全空（目录不存在或只有空壳）**
   - 直接全量拷贝，但仍要问一次："我会把 claude-home/ 下的 [列清单] 拷到 ~/.claude/，可以吗？"

   **5b. 只有 Claude Code 自动生成的运行时（projects/ history.jsonl shell-snapshots/ statsig/ 等）**
   - 全量拷贝 harness 组件（CLAUDE.md / settings.json / agents / commands / hooks / skills）
   - 不动运行时目录
   - 告诉用户"我会动哪些，不会动哪些"，等确认

   **5c. 已有 harness 组件（agents/ commands/ hooks/ skills/ CLAUDE.md 其中之一或多个）**
   必须问：
   ```
   A. 全替换：备份后整包覆盖（激进）
   B. 合并保留：保留你原有的同名文件，只补新的（保守，推荐）
   C. 纯增量：只加你完全没有的，所有同名冲突都跳过并列给你看（最保守）
   D. 暂停：我先不动，你自己想好再说
   ```

6. 🛑 **settings.json 必须增量合并**（不管选 A/B/C 都这样）：
   - 读取用户当前 `~/.claude/settings.json`
   - 读取分发包的 `claude-home/settings.json`
   - 告诉用户新 harness 需要追加：
     - `PreToolUse/Bash` 里加两个 hook：`secret-scan.sh`、`dangerous-command.sh`
     - `Stop` 里加一个 hook：`gotchas-prompt.sh`
   - **不删除**用户已有的任何 Notification / Stop 声音 / permissions / env
   - 列出合并后的预览给用户看，等确认再写入

## 阶段 2 · 备份

7. 🛑 **改动前必做完整备份**：
   ```bash
   mkdir -p ~/.claude/backups
   tar -czf ~/.claude/backups/pre-install-$(date +%Y%m%d-%H%M%S).tar.gz \
       -C ~ .claude --exclude='.claude/backups' --exclude='.claude/projects'
   ```
   告诉用户命令 + 备份路径，等确认。

## 阶段 3 · 拷贝执行

8. 按阶段 1 选的策略执行：

   **A. 全替换**
   - 先告诉用户会删除哪些（agents/ commands/ hooks/ skills/ CLAUDE.md），**不**碰 projects/ history.jsonl 等运行时
   - `cp -R path2-quick-install/claude-home/. ~/.claude/`
   - 每步简短汇报

   **B. 合并保留（默认推荐）**
   - 遍历 `claude-home/agents/*`，同名存在则跳过，列给用户看
   - `commands/ skills/` 同理
   - `hooks/`：三个 hook 文件名固定，同名存在问用户"覆盖还是保留你的"
   - `CLAUDE.md`：如存在，问"覆盖 / 改名为 CLAUDE.md.new / 跳过"
   - `settings.json`：按阶段 1 第 6 步的增量合并处理

   **C. 纯增量**
   - 只加用户完全没有的文件
   - 所有同名冲突跳过并列给用户
   - 完成后列"跳过了哪些"的清单

9. 🛑 **拷贝后立即校验**：
   - hook 脚本执行权限：`ls -la ~/.claude/hooks/*.sh`，任何一个缺 `x` 就 `chmod +x`
   - settings.json 合法性：`/usr/bin/python3 -c "import json; json.load(open('$HOME/.claude/settings.json'))"`
   - 关键文件齐全：`ls ~/.claude/CLAUDE.md ~/.claude/agents/planner.md ~/.claude/commands/plan.md`

## 阶段 4 · 冒烟测试

10. 🛑 **用 Write 工具创建测试 JSON 文件**（不要用 Bash 内联 echo，会误触发自己的 hook）：

    ```json
    // /tmp/test_safe.json
    {"tool_input":{"command":"echo hello"}}

    // /tmp/test_secret.json
    {"tool_input":{"command":"curl -H 'X-API-Key: sk-abcd1234efgh5678ijkl9012'"}}

    // /tmp/test_dangerous.json
    {"tool_input":{"command":"rm -rf /tmp/demo-only-not-real"},"cwd":"/tmp"}
    ```

11. 跑测试：
    - `cat /tmp/test_safe.json | ~/.claude/hooks/secret-scan.sh` → exit 0
    - `cat /tmp/test_safe.json | ~/.claude/hooks/dangerous-command.sh` → exit 0
    - `cat /tmp/test_secret.json | ~/.claude/hooks/secret-scan.sh` → exit 2
    - `cat /tmp/test_dangerous.json | ~/.claude/hooks/dangerous-command.sh` → **弹窗**
    - 🛑 **让用户在弹窗里亲自点一次"拒绝"**（验证完整交互链路，exit 2）

12. 清理测试文件（用相对路径避免触发 hook）：
    ```bash
    cd /tmp && rm -f test_safe.json test_secret.json test_dangerous.json
    ```

## 阶段 5 · 装后个人化提醒（关键！）

13. 🛑 **主动告诉用户需要做的替换**：
    ```
    装完了！现在有几处需要你自己动手（不紧急，但建议今天搞定）：

    必做：
    1. 打开 ~/.claude/CLAUDE.md，把 {{你的名字}} 替换成你的真实名字
    2. 把 "## 我是谁" 那节改成你的身份（角色、工作场景）
    3. 最后更新时间 {{装完请填日期}} 也记得改

    可选（之后慢慢补）：
    1. 写一份你自己的 Soul：参考 path1-deep-adaptation/soul-template.md 填完，
       放到 ~/.claude/my-coding-soul.md，然后跟我说"基于我的 Soul 调整 CLAUDE.md"
    2. 在 ~/.claude/skills/gotchas/SKILL.md 里提前记几条你常踩的坑
    3. 用 skill-creator 创建几个你常用的 skill
    ```

14. 告诉用户怎么验证安装成功：
    > "最简验证：打开任一个项目，输 `/plan`，看能不能触发 planner session。
    > 完整验证：让我跑一个含 `rm -rf /tmp/xxx` 的命令，看危险命令弹窗能不能弹。"

15. 🛑 **最终汇报**：
    - 总共拷贝/修改了多少文件（列 `ls` 输出）
    - 备份路径：`~/.claude/backups/pre-install-*.tar.gz`
    - 用户需做的必做步骤（名字替换）
    - 可选深度适配入口（path1 的 soul-template）

---

## 贯穿始终的纪律

- ❌ 不要批量 `cp` / `rm` 而不汇报
- ❌ 不要遇到 settings.json 冲突就整份覆盖
- ❌ 不要在没得到授权时覆盖 `~/.claude/` 下既有文件
- ❌ 不要删除 `~/.claude/backups/` / `~/.claude/projects/` / `~/.claude/history.jsonl` 等用户历史
- ✅ 每一步完成都简短汇报
- ✅ 遇到意外（陌生目录/文件/权限）立刻停下来问
- ✅ hook 里的路径用 `$HOME/.claude/hooks/...`，拷过去不需改
- ✅ 冒烟测试的危险命令弹窗**必须让用户亲自点一次**（只看代码路径不算验证过）
