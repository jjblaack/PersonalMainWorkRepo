---
name: "project-navigator"
description: "长期记忆索引：通过根目录 MAP.md 导航项目背景/设计思想/模块关系与文档位置。遇到项目理解、架构、思想或跨模块任务时，先读 MAP.md，再按映射直达目标，不进行盲搜。"
allowed_tools:
  - Read
  - Bash
---

# Project Navigator

本 Skill 作为项目的“长期记忆索引层”。用一份根目录的 MAP.md 作为唯一入口，给予 Agent 对项目的上帝视角；在涉及项目理解与跨模块协作时，先读地图再行动。

## 设计哲学
- 极简原则：不做复杂逻辑判断，只维护一份根目录 MAP.md 作为索引入口。
- 舞台模式：通过 MAP.md 传达项目背景、设计哲学与文件路径映射，让 Agent 自行判断需读取的具体文件。
- 结构规范：
  - 所有项目文档统一维护在单一目录下（默认 ./docs，可通过脚本参数修改）。
  - MAP.md 采用条目式映射：[标题](相对路径) - 语义描述。
  - 文档文件夹中的每份 .md 顶部需有简要意图说明：首行标题或 YAML frontmatter 中的 description 字段。

## 智能检索（Retrieval）规范
- 当用户提及项目逻辑、架构、哲学或任何跨模块任务时：
  1) 必须第一步读取根目录的 MAP.md。
  2) 根据 MAP.md 的标题与 Summary 判断目标文档，直接读取对应文件。
  3) 严禁在未查看 MAP.md 前进行盲目搜索。
- 当 MAP.md 显示多个候选，优先选择最贴近用户意图的条目；若仍不确定，再最小化使用搜索工具以验证假设。
- 当 ./MAP.md 不存在或明显过期时：
  1) 先运行维护脚本刷新/生成 MAP.md
  2) 再回到“先读 MAP.md → 按映射直达目标文件”的流程

## MAP.md 约定
- 放置位置：项目根目录 ./MAP.md
- 内容结构：
  - 顶部包含生成元信息：生成时间、docs 目录、更新命令、摘要规则、忽略规则等。
  - 按语义分区：Philosophy / Architecture / Conventions / Playbooks / Reference / Misc。
  - 可选按语言分栏：中文 / English（脚本参数控制）。
- 条目格式：
  - - [标题](相对路径) - Summary
  - 可附加 tags： (tags: a, b)
  - 当出现同名标题时，脚本会在标题后追加文件名以消歧（保持映射可读且稳定）。

## 维护脚本（Maintenance）
- 位于本 Skill 下的 scripts/maintain_map.py
- 职责：
  - 遍历文档目录（默认 ./docs），抽取每个 .md 的标题与摘要：
    - 标题：优先首个 Markdown 标题行（# ...），否则使用首个非空行或文件名
    - 摘要：优先 frontmatter: description（默认截断为 80 字）
    - 标签：可选解析 frontmatter: tags（用于分类与检索提示）
  - 生成/更新根目录 MAP.md，包含分区、语言分栏（可选）、生成元信息
  - 默认忽略噪声目录/文件（node_modules、.git、dist、drafts、archived、.trae 等），也支持自定义 ignore
- 使用方式（示例）：
  - 读取地图：Read file_path:"./MAP.md" limit:500
  - 生成/更新地图（默认 docs 目录与 MAP.md 路径）：
    - Bash command: "python3 ./.trae/skills/project-navigator/scripts/maintain_map.py"
  - 指定目录与输出：
    - Bash command: "python3 ./.trae/skills/project-navigator/scripts/maintain_map.py --docs-dir ./docs --map-file ./MAP.md"
  - 自定义忽略规则（可重复传参）：
    - Bash command: "python3 ./.trae/skills/project-navigator/scripts/maintain_map.py --ignore '**/drafts/**' --ignore '**/archived/**'"
  - 按语言分栏：
    - Bash command: "python3 ./.trae/skills/project-navigator/scripts/maintain_map.py --lang-sections"
  - 控制地图密度（每个分区最多收录 N 条，0 为不限制）：
    - Bash command: "python3 ./.trae/skills/project-navigator/scripts/maintain_map.py --max-per-category 200"
  - 仅预览（不落盘）：
    - Bash command: "python3 ./.trae/skills/project-navigator/scripts/maintain_map.py --dry-run"

## 文档模板（推荐）
在 docs 目录新建文档时，建议使用以下最小模板以保证索引质量：

```markdown
---
description: 一句话说明本文用途与适用场景（建议 ≤ 80 字）
tags:
  - philosophy
  - architecture
---

# 文档标题
```

## 团队协作建议（可选）
- 建议在 CI 或 pre-commit 中运行维护脚本，确保 MAP.md 与 docs 同步更新：
  - python3 ./.trae/skills/project-navigator/scripts/maintain_map.py
- 当你新增/移动/重命名 docs 下的文件后，优先刷新 MAP.md 再发起跨模块讨论。

## 使用流程（对话内建议）
1) 读取 ./MAP.md 获取全局视图。
2) 按用户意图匹配最相关条目，直接 Read 目标文档。
3) 如地图缺漏或新增文档未收录，调用维护脚本刷新地图，然后重试步骤 1-2。

## Evals（验证用例）
- 场景 A：用户问“我们要增加一个新模块，请根据项目哲学告诉我应该参考哪个现有文档？”
  - 期望行为：先 Read ./MAP.md → 找到含“哲学/设计原则/架构风格”等条目 → Read 该文档 → 基于文档内容给出参考建议与进一步阅读路径。
- 场景 B：用户说“我刚写完了一份关于新特性的哲学文档，请同步到地图中。”
  - 期望行为：调用 Bash 运行维护脚本刷新地图 → 再 Read ./MAP.md 验证新条目出现 → 回答已同步并提供该条目的直达路径。

## 触发条件总结
- 当需要理解项目背景、设计哲学、模块关系或定位某类知识的存放位置时，调用本 Skill。
- 对跨模块任务的理解与规划，必须以阅读 MAP.md 开场，并严格按映射跳转目标文档。
