# Agent 执行步骤参考 · 深度适配路径

> 这份是给你（agent）看的操作手册。用户通过 `BOOTSTRAP.md` 把任务交给你。
> **带 🛑 的步骤是强制检查点，必须停下来问用户，不得跳过、不得合并。**
> 目标：基于用户的 Soul 搭一套贴合他工作习惯的 `~/.claude/` 全局 harness。

---

## 阶段 0 · 对齐理解

1. Read 以下文件（顺序不重要，可并行）：
   - `path1-deep-adaptation/agent-steps.md`（本文件）
   - `path1-deep-adaptation/builder-guide.md`
   - `path1-deep-adaptation/soul-template.md`
   - `path1-deep-adaptation/soul-example-yijiang.md`

2. 🛑 **向用户复述本次任务的理解**，至少覆盖：
   - 目标：为他搭一套贴合他 Soul 的全局 `~/.claude/` harness
   - 推进方式：多阶段对话，每阶段检查点都会问他
   - 需要他先做什么（可能需要填 Soul）

   等用户明确说"可以"再推进。

## 阶段 1 · 识别用户身份状态

3. 运行 `ls -la ~/.claude/`，把当前目录内容列给用户。

4. 🛑 **问用户是新用户还是老用户**：
   > "你之前用过 Claude Code 吗？`~/.claude/` 下这些文件/目录都是你的吗？有没有我不能动的？"

5. 🛑 **如果检测到已有 `agents/` `commands/` `hooks/` `skills/` 或 `CLAUDE.md`**，问处理策略：
   ```
   A. 全替换：备份老的后整包覆盖（激进但干净）
   B. 合并保留：保留你原有的同名文件，只补新的（保守，推荐）
   C. 纯增量：只加你完全没有的，所有同名冲突都跳过并列给你看（最保守）
   D. 暂停：我先不动，你自己想好再说
   ```

6. 🛑 **settings.json 必须增量合并**：
   - 读取用户现有 `~/.claude/settings.json`
   - 告诉用户新 harness 需要追加哪些 hook（逐条列）
   - **不删除**任何用户已有配置（Notification 声音、Stop 声音、permissions、env 等）
   - 列出合并后的预览给用户看，等确认再写入

## 阶段 2 · Soul 准备

7. 在**当前工作目录**找用户的 Soul 文件（可能的文件名：`my-coding-soul.md` / `coding-soul.md` / `soul.md` / 其他）。

8. 🛑 **如果找不到 Soul**：
   > "我没看到你的 Soul 文件。建议你先参考 `path1-deep-adaptation/soul-example-yijiang.md` 看 Soul 长什么样，然后复制 `path1-deep-adaptation/soul-template.md` 填成你自己的版本。填完告诉我路径，我在这里等你。"

   ⚠️ 不要自作主张帮用户"脑补"一份 Soul。Soul 必须由用户自己写。

9. 🛑 **Soul 拿到后**，Read 一遍，向用户复述你理解到的关键信息：
   - 姓名/角色/场景
   - 协作铁律
   - 绝佳实践
   - 工作流阈值
   - 评审维度

   如有任何一项不确定，问用户澄清。

## 阶段 3 · 备份

10. 🛑 **改动前必做完整备份**：
    ```bash
    mkdir -p ~/.claude/backups
    tar -czf ~/.claude/backups/pre-install-$(date +%Y%m%d-%H%M%S).tar.gz \
        -C ~ .claude --exclude='.claude/backups' --exclude='.claude/projects'
    ```
    执行前告诉用户命令内容和备份路径，等用户确认。

## 阶段 4 · 组件生成（一块一块来）

按 `builder-guide.md` 的组件清单推进。**每块完成后必须停下来汇报：**
- 生成了哪些文件（列路径）
- 核心内容是什么（2–3 句话概括）
- 让用户确认再进下一块

推荐顺序：

11. **CLAUDE.md**（最先做，其他组件都会引用它）
    - 结构：我是谁 / 协作铁律 / 绝佳实践 / 三段式阈值 / 组件索引
    - 严格 ≤ 60 行
    - 基于 Soul 的内容填，不要加 Soul 没提到的条款（如需加，问用户）

12. **hooks 三件套**
    - `secret-scan.sh`：硬拦（macOS BSD grep 注意用 `/usr/bin/grep -qE -e "$pat"`，-e 显式声明防止以 `-` 开头的 pattern 被当 option）
    - `dangerous-command.sh`：osascript 弹窗，默认按钮"拒绝"，超时/关闭也走拒绝分支
    - `gotchas-prompt.sh`：Stop 时弹 osascript 输入框，空输入跳过，非空追加到 `skills/gotchas/SKILL.md`
    - 所有 `.sh` 文件 `chmod +x`

13. **settings.json 增量合并**
    - 预览合并结果给用户
    - 用户确认后写入

14. **agents 四件套**
    - planner / evaluator / code-reviewer / security-reviewer
    - 每个 agent ≤ 120 行
    - **不要**在 agents 里重复复制 CLAUDE.md 的绝佳实践（agent 启动会继承 context）
    - evaluator 必须强调"独立 context，不得读取 coding agent 的对话历史"

15. **skills 四件套**
    - `skill-creator`：直接从 Anthropic 仓库拷过来（或用户有就复用）
    - `doc-templates`：三种模板（需求/设计/架构）
    - `eval-rubric`：基于 Soul 的评审维度生成
    - `gotchas`：空壳 + 可选地把用户 Soul 里"常踩的坑"迁移进来作初始内容

16. **commands 五个**
    - `/plan` `/code` `/evaluate` `/harness-retro` `/harness-audit`
    - 每个 ≤ 50 行

## 阶段 5 · 冒烟测试

17. 🛑 **用 Write 工具创建测试 JSON 文件，送 hook 验证**（不要用 Bash 内联 echo，会误触发自己）：
    - 安全命令（如 `echo hello`）→ 两个 hook 都 exit 0
    - secret 模式（如包含 `sk-abcdefghijklmnopqrstu`）→ secret-scan exit 2
    - 危险命令（如 `rm -rf /tmp/demo`）→ dangerous-command 弹窗 → **让用户亲自点一次"拒绝"验证交互链路**

18. 验证 settings.json 合法：
    ```bash
    /usr/bin/python3 -c "import json; json.load(open('$HOME/.claude/settings.json'))"
    ```

## 阶段 6 · 文档与交付

19. 生成 `~/.claude/INVENTORY.md`：记录
    - 搭建清单（每个组件的用途和来源）
    - 设计决策（为什么这么选、舍弃了什么、为什么）
    - Soul → 组件映射表（每条 Soul 条款对应哪个组件）
    - 备份位置

20. 生成 `~/.claude/workflow-guide.md`：场景化使用指南
    - 新项目启动怎么用
    - 老项目接入怎么用
    - 紧急修复怎么用
    - 大型重构怎么用
    - 琐碎修改怎么用
    - 探索性研究怎么用
    - Gotchas 飞轮机制怎么用

21. 🛑 **最终汇报**：
    - 生成/修改了哪些文件（给完整列表）
    - 备份路径是什么
    - 还需要用户手动做什么（比如填 gotchas 初始内容）
    - 建议的下一步（比如跑一次 `/plan` 做真实功能验证）

---

## 贯穿始终的纪律

- ❌ 不要批量写多个文件而不汇报
- ❌ 不要遇到 settings.json 冲突就整份覆盖
- ❌ 不要在没得到授权时动 `~/.claude/` 下的既有文件
- ❌ 不要脑补 Soul 里没写的东西
- ❌ 不要自作主张删除 `~/.claude/backups/` / `~/.claude/projects/` 等用户历史
- ✅ 每一步完成都简短汇报
- ✅ 遇到意外文件/配置/权限，停下来问
- ✅ 任何 `rm` / 覆盖操作，必须先问
- ✅ 每个 hook 的错误信息都要写清楚匹配到哪条规则 + 修复建议
