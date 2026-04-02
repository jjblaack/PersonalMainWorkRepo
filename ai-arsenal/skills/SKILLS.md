# Claude 技能清单

## 已安装技能

### gemini-to-md
- **名称**: Gemini 对话转 Markdown
- **命令**: `/gemini-to-md`
- **描述**: 指导用户将 Gemini 对话链接转换为 Markdown 格式
- **类别**: 实用工具

要使用此技能，请在任意位置输入 `/gemini-to-md`。

---

## maw 系列技能（MAW 工作流）

maw（Model-Assisted Workflow）系列技能基于文档驱动开发模式，使用 `.claude/protocol/` 目录管理项目协议文档。

### maw-prd
- **名称**: 需求文档生成器
- **命令**: `/maw-prd [目标或问题描述]`
- **描述**: 生成或修订 PRD.md，把待澄清问题显式化
- **类别**: 需求分析
- **适用场景**: 开始需求阶段、需求不清需要补齐、或 PRD 需要更新时
- **输出文件**: `.claude/protocol/PRD.md`、`.claude/protocol/STATUS.md`

### maw-spec
- **名称**: 技术规格生成器
- **命令**: `/maw-spec [目标或模块]`
- **描述**: 生成或修订 SPEC.md，把 PRD 转成可实现的技术规格与风险清单
- **类别**: 架构设计
- **适用场景**: 进入方案阶段、需要接口/数据流设计、或实现前需要冻结契约时
- **输出文件**: `.claude/protocol/SPEC.md`、`.claude/protocol/STATUS.md`

### maw-implement
- **名称**: 代码实现
- **命令**: `/maw-implement [实现范围或任务描述]`
- **描述**: 严格按 SPEC 实现代码与测试，并通过质量门禁
- **类别**: 代码实现
- **适用场景**: 进入实现阶段、补齐测试、或修复失败的测试/检查时
- **输入依赖**: `.claude/protocol/SPEC.md`
- **输出文件**: 代码文件、测试文件、`.claude/protocol/STATUS.md`

### maw-review
- **名称**: 代码评审
- **命令**: `/maw-review [评审范围，例如路径/模块/PR 描述]`
- **描述**: 按工作流标准做代码评审与风险审计，并把 Must-fix/Should-fix 结论结构化输出
- **类别**: 质量保证
- **适用场景**: 合并前评审、质量门禁前复核、或排查返工风险时
- **输出**: 结构化评审清单 + 关键证据（引用文件路径与要点）

### maw-team
- **名称**: 多智能体协作编排
- **命令**: `/maw-team <交付目标>`
- **描述**: 基于文档驱动 + teamwork(Agent Teams) 启动并编排多智能体交付
- **类别**: 项目管理
- **适用场景**: 需要并行探索、跨层改动、或复杂任务需要拆分成可并行单元时
- **推荐角色**: Analyst、Architect、Coder、Reviewer
- **输出文件**: `.claude/protocol/` 下的完整协议文档 + 任务列表
