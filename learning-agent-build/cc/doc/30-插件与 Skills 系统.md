# Claude Code 项目分析 - 插件与 Skills 系统

> 本文档深度分析 Claude Code 的插件系统和 Skills 系统，包括插件架构、技能定义、加载机制和与主系统的集成。

---

## 目录

1. [系统概述](#1-系统概述)
2. [插件系统架构](#2-插件系统架构)
3. [Skills 系统架构](#3-skills 系统架构)
4. [插件/Skill 与主系统集成](#4-插件skill 与主系统集成)
5. [用户配置和使用](#5-用户配置和使用)
6. [安全性考虑](#6-安全性考虑)

---

## 1. 系统概述

### 1.1 扩展系统组成

Claude Code 的扩展系统由两个主要部分组成：

| 组件 | 用途 | 来源 |
|------|------|------|
| **插件 (Plugins)** | 可安装的扩展功能包 | 市场、Git、NPM、本地路径 |
| **Skills** | 功能模块/自动化脚本 | 内置、项目级、用户级、插件附带 |

### 1.2 架构层次

```
┌─────────────────────────────────────────────────────────────┐
│  用户接口层                                                   │
│  /plugin 命令          /skill 命令                           │
│  设置界面              技能调用                              │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  插件管理器           技能注册表                             │
│  PluginLoader         SkillRegistry                         │
│  - 加载/卸载          - 技能发现                             │
│  - 缓存管理           - 技能调用                             │
│  - 依赖解决           - 权限检查                             │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  插件来源              技能来源                               │
│  - 市场插件            - 内置技能 (bundled)                  │
│  - Git 仓库             - 文件技能 (.claude/skills/)          │
│  - NPM 包               - MCP 技能                            │
│  - 本地路径            - 插件技能                            │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 目录结构

```
src/skills/
├── bundled/                 # 内置技能实现
│   ├── *.ts                # 各种技能定义
│   └── index.ts            # 入口文件
├── bundledSkills.ts        # 技能注册和管理
├── loadSkillsDir.ts        # 技能加载逻辑
└── mcpSkillBuilders.ts     # MCP 技能构建器

src/plugins/
├── builtinPlugins.ts        # 内置插件注册
└── bundled/
    └── index.ts             # 内置插件入口

src/utils/plugins/
├── pluginLoader.ts          # 核心加载器
├── pluginManifest.ts        # 插件清单
├── pluginCaching.ts         # 插件缓存
└── pluginError.ts           # 错误处理
```

---

## 2. 插件系统架构

### 2.1 插件来源

插件系统支持多种来源：

```typescript
// src/types/plugin.ts (简化)

export type PluginSource =
  | { type: 'marketplace'; marketplace: string; name: string }
  | { type: 'git'; url: string; subDirectory?: string }
  | { type: 'npm'; packageName: string }
  | { type: 'local'; path: string }
  | { type: 'builtin'; name: string }
```

### 2.2 插件类型定义

```typescript
// 已加载插件

export type LoadedPlugin = {
  name: string                    // 插件名称
  manifest: PluginManifest        // 插件清单
  path: string                    // 插件路径
  source: string                  // 源标识符
  repository: string              // 仓库标识符
  enabled?: boolean               // 是否启用
  isBuiltin?: boolean            // 是否为内置插件
  commandsPath?: string           // 命令路径
  agentsPath?: string             // 代理路径  
  skillsPath?: string             // 技能路径
  hooksConfig?: HooksSettings     // 钩子配置
  mcpServers?: Record<string, McpServerConfig> // MCP 服务器配置
  settings?: Record<string, unknown> // 插件设置
}

// 插件清单

export interface PluginManifest {
  name: string
  version: string
  description: string
  author?: string
  license?: string
  
  // 入口点
  commands?: string
  agents?: string
  skills?: string
  hooks?: string
  
  // 依赖
  mcpServers?: Array<{
    name: string
    command: string
    args?: string[]
  }>
  
  // 设置
  settings?: {
    required?: string[]
    properties?: Record<string, SettingSchema>
  }
}
```

### 2.3 插件目录结构

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json           # 插件清单（新格式）
├── plugin.json              # 插件清单（旧格式，向后兼容）
├── commands/                # 自定义命令
│   ├── build.md
│   └── deploy.md
├── skills/                  # 技能文件
│   └── custom-skills/
│       └── SKILL.md
├── agents/                  # AI 代理
│   └── test-runner.md
├── hooks/                   # 钩子配置
│   └── hooks.json
├── settings.json            # 插件特定设置
└── output-styles/          # 输出样式
    └── custom-style.md
```

### 2.4 插件加载流程

```typescript
// src/utils/plugins/pluginLoader.ts (简化)

export async function loadPlugin(
  source: string,
  options: LoadPluginOptions,
): Promise<LoadedPlugin> {
  // 1. 解析插件标识符
  const parsed = parsePluginIdentifier(source)
  
  // 2. 检查企业策略
  if (!isSourceAllowedByPolicy(parsed.source)) {
    throw new PluginError('Source not allowed by policy')
  }
  
  // 3. 获取市场入口（如果是市场插件）
  if (parsed.source === 'marketplace') {
    const entry = await getPluginFromMarketplace(parsed.name)
    if (!entry) {
      throw new PluginError('Plugin not found in marketplace')
    }
  }
  
  // 4. 缓存或下载
  const cachedPath = await getOrCachePlugin(parsed)
  
  // 5. 验证和组装
  const plugin = await createPluginFromPath(cachedPath, parsed)
  
  // 6. 注册插件工具
  await registerPluginTools(plugin)
  
  return plugin
}

// 解析插件标识符
export function parsePluginIdentifier(
  identifier: string,
): ParsedPluginIdentifier {
  // 格式：name@marketplace 或 name@github:user/repo 等
  
  const atIndex = identifier.lastIndexOf('@')
  
  if (atIndex === -1) {
    // 无@符号，假设是本地路径
    return {
      name: identifier,
      source: 'local',
      path: identifier,
    }
  }
  
  const name = identifier.substring(0, atIndex)
  const sourcePart = identifier.substring(atIndex + 1)
  
  // 解析来源
  if (sourcePart === 'marketplace' || sourcePart === 'anthropic-tools') {
    return { name, source: 'marketplace' }
  }
  
  if (sourcePart.includes('/')) {
    // GitHub 仓库
    return {
      name,
      source: 'git',
      url: `https://github.com/${sourcePart}`,
    }
  }
  
  // NPM 包
  return {
    name,
    source: 'npm',
    packageName: sourcePart,
  }
}
```

### 2.5 插件缓存系统

```typescript
// src/utils/plugins/pluginCaching.ts (简化)

// 缓存目录结构
// ~/.claude/plugins/cache/{marketplace}/{plugin}/{version}/

export async function cachePlugin(
  plugin: PluginManifest,
  source: PluginSource,
): Promise<string> {
  const cacheDir = getPluginCacheDir(plugin.name, plugin.version)
  
  // 检查缓存是否存在
  if (await fs.exists(cacheDir)) {
    return cacheDir
  }
  
  // 下载并缓存
  await fs.mkdir(cacheDir, { recursive: true })
  
  switch (source.type) {
    case 'marketplace':
      await downloadFromMarketplace(plugin, cacheDir)
      break
    case 'git':
      await cloneGitRepo(source.url, cacheDir)
      break
    case 'npm':
      await installNpmPackage(source.packageName, cacheDir)
      break
  }
  
  // 写入清单
  await fs.writeJson(path.join(cacheDir, 'plugin.json'), plugin)
  
  return cacheDir
}

// 清理孤立插件版本
export async function cleanupOrphanedPluginVersions(): Promise<void> {
  const cacheRoot = getPluginCacheRoot()
  const entries = await fs.readdir(cacheRoot)
  
  for (const marketplace of entries) {
    const pluginsDir = path.join(cacheRoot, marketplace)
    const plugins = await fs.readdir(pluginsDir)
    
    for (const plugin of plugins) {
      const versionsDir = path.join(pluginsDir, plugin)
      const versions = await fs.readdir(versionsDir)
      
      // 保留最新 3 个版本
      const sortedVersions = versions.sort().reverse()
      const toDelete = sortedVersions.slice(3)
      
      for (const version of toDelete) {
        await fs.remove(path.join(versionsDir, version))
      }
    }
  }
}
```

### 2.6 钩子系统

插件可以定义钩子，在特定事件发生时执行：

```typescript
// src/utils/settings/types.ts (简化)

export interface HooksSettings {
  hooks?: {
    [hookName: string]: Array<{
      matcher: string  // 正则表达式或事件名
      hooks: Array<{
        type: 'command' | 'script'
        command: string
        timeout?: number
        env?: Record<string, string>
      }>
    }>
  }
}

// 钩子类型

export type HookEvent =
  | 'PreToolUse'         // 工具使用前
  | 'PostToolUse'        // 工具使用后
  | 'OnSubagentSpawn'    // 子代理启动
  | 'OnSubagentExit'     // 子代理退出
  | 'OnUserMessage'      // 用户消息
  | 'OnAssistantMessage' // 助手消息
  | 'OnSessionStart'     // 会话开始
  | 'OnSessionEnd'       // 会话结束

// 钩子执行

export async function executeHooks(
  event: HookEvent,
  context: HookContext,
): Promise<void> {
  const hooks = getRegisteredHooks(event)
  
  for (const hook of hooks) {
    // 检查匹配器
    if (!matchesHookMatcher(hook.matcher, context)) {
      continue
    }
    
    // 执行钩子
    for (const hookCmd of hook.hooks) {
      if (hookCmd.type === 'command') {
        await executeCommand(hookCmd.command, {
          env: hookCmd.env,
          timeout: hookCmd.timeout,
        })
      }
    }
  }
}

// 示例：Prettier 格式化钩子

const prettierHookConfig: HooksSettings = {
  hooks: {
    PostToolUse: [{
      matcher: 'Write|Edit',
      hooks: [{
        type: 'command',
        command: 'prettier --write "$FILE" 2>/dev/null || true',
        env: {
          FILE: '${filePath}',  // 变量替换
        },
      }],
    }],
  },
}
```

---

## 3. Skills 系统架构

### 3.1 Skills 类型

```typescript
// src/skills/types.ts (简化)

export type SkillSource =
  | { type: 'bundled' }           // 内置技能
  | { type: 'file'; path: string } // 文件技能
  | { type: 'mcp'; serverId: string; skillName: string }
  | { type: 'plugin'; pluginName: string; skillName: string }

// 技能定义

export type SkillDefinition = {
  name: string
  description: string
  aliases?: string[]
  whenToUse?: string
  argumentHint?: string
  allowedTools?: string[]
  model?: string
  disableModelInvocation?: boolean
  userInvocable?: boolean
  isEnabled?: () => boolean
  hooks?: HooksSettings
  context?: 'inline' | 'fork'
  agent?: string
  files?: Record<string, string>  // 额外文件
  getPromptForCommand: (
    args: string,
    context: ToolUseContext,
  ) => Promise<ContentBlockParam[]>
}
```

### 3.2 内置技能

**文件**: `src/skills/bundled/index.ts`

```typescript
// 内置技能注册

import { registerBundledSkill } from './registry'

// 示例：/brief 技能

registerBundledSkill({
  name: 'brief',
  description: 'Generate a brief project overview',
  aliases: ['summary', 'overview'],
  allowedTools: ['Read', 'Glob'],
  userInvocable: true,
  
  getPromptForCommand: async (args, context) => {
    return [
      {
        type: 'text',
        text: `请生成项目的简要概述，包括：
        1. 项目目标和用途
        2. 技术栈和框架
        3. 目录结构
        4. 核心模块和组件
        
        ${args ? `额外要求：${args}` : ''}`,
      },
    ]
  },
})

// 示例：/explain 技能

registerBundledSkill({
  name: 'explain',
  description: 'Explain how code works',
  aliases: ['understand', 'analyze'],
  allowedTools: ['Read', 'Glob', 'Grep'],
  argumentHint: '[file or function]',
  userInvocable: true,
  
  getPromptForCommand: async (args, context) => {
    return [
      {
        type: 'text',
        text: `请解释以下代码的工作原理：
        
        ${args ? `目标：${args}` : '当前选中的代码'}
        
        请包括：
        1. 代码的功能和目的
        2. 关键函数和类的作用
        3. 数据流和控制流
        4. 依赖关系`,
      },
    ]
  },
})
```

### 3.3 文件技能加载

**文件**: `src/skills/loadSkillsDir.ts`

```typescript
// 从目录加载技能

export async function loadSkillsDir(
  dirPath: string,
): Promise<SkillDefinition[]> {
  const skills: SkillDefinition[] = []
  const seenFiles = new Set<string>()
  
  // 扫描目录
  const entries = await scanDirectory(dirPath, {
    ignoreGitignored: true,
  })
  
  for (const entry of entries) {
    if (!entry.isFile() || !entry.name.endsWith('SKILL.md')) {
      continue
    }
    
    // 避免重复加载
    const realPath = await fs.realpath(entry.path)
    if (seenFiles.has(realPath)) {
      continue
    }
    seenFiles.add(realPath)
    
    // 解析技能文件
    const skill = await parseSkillFile(entry.path)
    if (skill) {
      skills.push(skill)
    }
  }
  
  // 动态技能发现
  const dynamicSkills = await discoverDynamicSkills(dirPath)
  skills.push(...dynamicSkills)
  
  return skills
}

// 解析 SKILL.md 文件

export async function parseSkillFile(
  filePath: string,
): Promise<SkillDefinition | null> {
  const content = await fs.readFile(filePath, 'utf-8')
  
  // 提取前置内容
  const match = content.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/)
  if (!match) {
    return null
  }
  
  const frontmatter = parseYaml(match[1])
  const body = match[2]
  
  // 验证必需字段
  if (!frontmatter.name) {
    throw new Error('Skill must have a name')
  }
  
  return {
    name: frontmatter.name,
    description: frontmatter.description || '',
    aliases: frontmatter.aliases,
    allowedTools: frontmatter['allowed-tools'],
    context: frontmatter.context || 'inline',
    argumentHint: frontmatter['argument-hint'],
    
    getPromptForCommand: async (args, context) => {
      // 渲染技能模板
      const prompt = renderSkillTemplate(body, {
        args,
        context,
        skillDir: path.dirname(filePath),
      })
      
      return [{ type: 'text', text: prompt }]
    },
  }
}

// 渲染技能模板

function renderSkillTemplate(
  template: string,
  variables: Record<string, unknown>,
): string {
  return template.replace(/\$\{(\w+)\}/g, (match, key) => {
    const value = variables[key]
    if (value === undefined) {
      return match
    }
    return String(value)
  })
}
```

### 3.4 条件技能

支持根据文件路径模式激活的技能：

```typescript
// SKILL.md 示例

---
name: "React Component Testing"
description: "Helps write tests for React components"
allowed-tools: ["Read", "Write", "Bash(npm:*)"]
paths: ["src/**/*.tsx", "src/**/*.jsx"]
---

# React Component Testing Skill

这个技能帮助为 React 组件编写测试。

${CLAUDE_SKILL_DIR} is available for relative paths.
```

```typescript
// 动态技能发现

export async function discoverDynamicSkills(
  dirPath: string,
): Promise<SkillDefinition[]> {
  const skills: SkillDefinition[] = []
  
  // 扫描带 paths 配置的技能
  const entries = await scanDirectory(dirPath)
  
  for (const entry of entries) {
    const skill = await parseSkillFile(entry.path)
    if (!skill) continue
    
    // 检查是否有 paths 配置
    const paths = await getSkillPaths(entry.path)
    if (paths && paths.length > 0) {
      // 添加路径匹配器
      ;(skill as ConditionalSkill).paths = paths
      skills.push(skill)
    }
  }
  
  return skills
}

// 检查技能是否应该激活

export function shouldActivateSkill(
  skill: SkillDefinition & { paths?: string[] },
  filePath: string,
): boolean {
  if (!skill.paths) {
    return true  // 无路径限制，始终激活
  }
  
  return skill.paths.some(pattern => {
    const regex = patternToRegex(pattern)
    return regex.test(filePath)
  })
}
```

### 3.5 MCP 技能

```typescript
// src/skills/mcpSkillBuilders.ts (简化)

// 从 MCP 服务器构建技能

export function createMcpSkill(
  serverId: string,
  skillName: string,
  toolDefinition: ToolDefinition,
): SkillDefinition {
  return {
    name: skillName,
    description: toolDefinition.description,
    allowedTools: [`${serverId}:${toolDefinition.name}`],
    
    getPromptForCommand: async (args, context) => {
      return [
        {
          type: 'text',
          text: `调用 MCP 技能 ${skillName}，参数：${args}`,
        },
      ]
    },
  }
}
```

---

## 4. 插件/Skill 与主系统集成

### 4.1 SkillTool 集成

**文件**: `src/Tool.ts` (简化)

```typescript
// SkillTool 是主要的技能调用接口

export const SkillTool: Tool<InputSchema, Output, Progress> = buildTool({
  name: 'skill',
  
  // 输入验证
  async validateInput(
    { skill }: InputSchema,
    context: ToolUseContext,
  ): Promise<ValidationResult> {
    // 检查技能是否存在
    const skillDef = getSkillDefinition(skill)
    if (!skillDef) {
      return { valid: false, error: `Unknown skill: ${skill}` }
    }
    
    // 检查技能是否启用
    if (skillDef.isEnabled && !skillDef.isEnabled()) {
      return { valid: false, error: `Skill ${skill} is disabled` }
    }
    
    return { valid: true }
  },
  
  // 权限检查
  async checkPermissions(
    { skill, args }: { skill: string; args: string },
    context: ToolUseContext,
  ): Promise<PermissionDecision> {
    const skillDef = getSkillDefinition(skill)
    
    // 检查允许的工具
    if (skillDef?.allowedTools) {
      const decision = await checkAllowedTools(
        skillDef.allowedTools,
        context,
      )
      if (decision !== 'approved') {
        return decision
      }
    }
    
    return 'approved'
  },
  
  // 调用执行
  async call(
    { skill, args }: { skill: string; args: string },
    context: ToolUseContext,
    canUseTool: CanUseToolFn,
    parentMessage: string,
    onProgress?: OnProgressFn,
  ): Promise<Output> {
    const skillDef = getSkillDefinition(skill)
    if (!skillDef) {
      throw new Error(`Unknown skill: ${skill}`)
    }
    
    // 获取技能提示
    const prompt = await skillDef.getPromptForCommand(args, context)
    
    // 执行技能（调用 LLM）
    if (!skillDef.disableModelInvocation) {
      const result = await executeWithModel(prompt, {
        model: skillDef.model,
        allowedTools: skillDef.allowedTools,
        canUseTool,
        onProgress,
      })
      
      return {
        success: true,
        content: result.content,
      }
    }
    
    // 不调用 LLM 的技能
    return {
      success: true,
      content: 'Skill executed without model invocation',
    }
  },
  
  // 结果映射
  mapToolResultToToolResultBlockParam(
    result: Output,
    toolUseID: string,
  ): ToolResultBlockParam {
    return {
      type: 'tool_result',
      tool_use_id: toolUseID,
      content: result.success
        ? [{ type: 'text', text: result.content }]
        : [{ type: 'text', text: `Error: ${result.error}` }],
    }
  },
})
```

### 4.2 权限系统集成

```typescript
// 插件技能受权限系统约束

export async function checkPluginPermission(
  plugin: LoadedPlugin,
  toolName: string,
  context: ToolUseContext,
): Promise<PermissionDecision> {
  // 检查插件是否启用
  if (!plugin.enabled) {
    return 'denied'
  }
  
  // 检查工具权限
  const hooksConfig = plugin.hooksConfig
  if (hooksConfig?.hooks?.PreToolUse) {
    for (const hook of hooksConfig.hooks.PreToolUse) {
      if (matchesMatcher(hook.matcher, toolName)) {
        const decision = await executePermissionHook(hook.hooks, context)
        if (decision !== 'approved') {
          return decision
        }
      }
    }
  }
  
  return 'approved'
}
```

---

## 5. 用户配置和使用

### 5.1 配置插件

```json
// ~/.claude/settings.json

{
  "enabledPlugins": {
    "formatter@anthropic-tools": true,
    "linter@custom-marketplace": false
  },
  "plugins": {
    "formatter@anthropic-tools": {
      "settings": {
        "parser": "typescript",
        "printWidth": 100
      }
    }
  }
}
```

### 5.2 使用 Skills

#### 5.2.1 直接命令调用

```bash
# 在对话中
/brief
/explain src/components/App.tsx
/test --target=unit
```

#### 5.2.2 通过 SkillTool

```typescript
// 模型调用技能
skill("brief", {})
skill("explain", { file: "src/components/App.tsx" })
```

### 5.3 创建自定义 Skills

#### 5.3.1 用户级技能

```bash
# 目录：~/.claude/skills/
```

#### 5.3.2 项目级技能

```bash
# 目录：.claude/skills/
```

#### 5.3.3 技能文件格式

```markdown
---
name: "Build System"
description: "Handles project building and compilation"
allowed-tools: ["Bash(npm:*)", "Write", "Read"]
context: "fork"
argument-hint: "[target]"
---

# Build System Skill

这个技能帮助管理项目的构建过程。

可用命令：
- `npm run build` - 构建项目
- `npm run test` - 运行测试
- `npm run lint` - 代码检查

当前工作目录：${cwd}
技能目录：${CLAUDE_SKILL_DIR}
```

### 5.4 插件开发

#### 5.4.1 创建插件

```bash
my-plugin/
├── .claude-plugin/
│   └── plugin.json
├── commands/
│   └── hello.md
└── skills/
    └── my-skill/
        └── SKILL.md
```

```json
// .claude-plugin/plugin.json

{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "My custom plugin",
  "commands": "commands/",
  "skills": "skills/"
}
```

```markdown
// commands/hello.md

---
name: hello
description: Say hello
---

Hello! This is a command from a plugin.
```

---

## 6. 安全性考虑

### 6.1 路径验证

```typescript
// 防止路径遍历攻击

export function validatePluginPath(
  pluginPath: string,
  baseDir: string,
): boolean {
  const resolvedPath = path.resolve(pluginPath)
  const resolvedBase = path.resolve(baseDir)
  
  // 确保插件路径在基础目录内
  if (!resolvedPath.startsWith(resolvedBase)) {
    return false
  }
  
  // 检查符号链接
  const realPath = fs.realpathSync(pluginPath)
  if (!realPath.startsWith(resolvedBase)) {
    return false
  }
  
  return true
}
```

### 6.2 来源验证

```typescript
// 检查插件来源是否允许

export function isSourceAllowedByPolicy(
  source: PluginSource['type'],
): boolean {
  const policy = getPluginPolicy()
  
  switch (source) {
    case 'marketplace':
      return policy.allowMarketplace
    case 'git':
      return policy.allowGit
    case 'npm':
      return policy.allowNpm
    case 'local':
      return policy.allowLocal
    case 'builtin':
      return true
    default:
      return false
  }
}
```

### 6.3 钩子安全

```typescript
// 钩子执行超时和沙箱

export async function executeHook(
  hook: HookCommand,
  context: HookContext,
): Promise<HookResult> {
  const timeout = hook.timeout ?? 30000  // 默认 30 秒
  
  const controller = new AbortController()
  const timeoutId = setTimeout(() => {
    controller.abort()
  }, timeout)
  
  try {
    const result = await executeCommand(hook.command, {
      env: hook.env,
      signal: controller.signal,
      // 沙箱限制
      sandbox: {
        allowedPaths: getHookAllowedPaths(),
        allowedNetwork: false,  // 默认禁止网络
      },
    })
    
    return { success: true, output: result.output }
  } catch (error) {
    if (error.name === 'AbortError') {
      return { success: false, error: 'Hook execution timed out' }
    }
    return { success: false, error: error.message }
  } finally {
    clearTimeout(timeoutId)
  }
}
```

---

## 7. 总结

Claude Code 的插件和 Skills 系统提供了强大的功能扩展能力：

### 系统特点

| 方面 | 实现 | 收益 |
|------|------|------|
| 插件来源 | 市场/Git/NPM/本地 | 灵活分发 |
| 技能来源 | 内置/文件/MCP/插件 | 多层次扩展 |
| 缓存机制 | 版本化 ZIP 缓存 | 快速加载 |
| 钩子系统 | 事件驱动 | 自动化工作流 |
| 安全控制 | 路径验证/超时/沙箱 | 安全执行 |

### 关键设计决策

1. **插件和技能分离**: 插件是安装包，技能是功能模块
2. **前置内容配置**: 技能元数据与提示词分离
3. **动态发现**: 基于路径模式的条件技能
4. **钩子管道**: 工具使用前后的自动化处理
5. **缓存优先**: 插件缓存减少重复下载

---

*最后更新：2026-04-02*
