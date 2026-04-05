# CM-01 - CLAUDE.md 上下文注入系统

## 1. 概述

CLAUDE.md 上下文注入系统是 Claude Code 的核心机制之一，负责在每次对话开始时向模型注入相关的上下文信息。这是一个多层次、支持动态包含和条件规则的系统。

### 1.1 核心功能

- **多层次上下文注入**：从系统级到用户级到项目级，按优先级注入
- **@include 指令**：支持在一个记忆文件中包含其他文件
- **条件规则**：基于文件路径的 glob 匹配，动态应用规则
- **循环引用检测**：防止 @include 无限递归
- **非文本文件过滤**：阻止二进制文件被加载到上下文中

---

## 2. 文件层级与优先级

### 2.1 层级结构（从高到低）

```
优先级从高到低排列：

1. Managed（系统级）
   路径：/etc/claude-code/CLAUDE.md
   作用域：全系统所有用户
   典型用途：IT 部门强制策略、安全规范、合规要求

2. User（用户级）
   路径：~/.claude/CLAUDE.md
   作用域：单用户所有项目
   典型用途：个人编码风格偏好、常用工具配置、快捷键设置

3. Project（项目级）
   路径：CLAUDE.md, .claude/CLAUDE.md, .claude/rules/*.md
   作用域：单个项目
   典型用途：项目特定的构建命令、代码规范、架构文档
   特点：随代码库提交，团队成员共享

4. Local（本地级）
   路径：CLAUDE.local.md
   作用域：单项目本地
   典型用途：临时任务笔记、待办事项、个人调试配置
   特点：gitignored，不提交

5. AutoMem（自动记忆）
   路径：由 auto-memory 功能管理
   作用域：用户跨会话持久化
   典型用途：用户偏好、常用命令、项目切换记录

6. TeamMem（团队记忆）
   路径：团队记忆入口点
   作用域：组织内共享
   典型用途：团队规范、共享知识、最佳实践
```

### 2.2 加载顺序

文件按**反向顺序**加载（从低优先级到高优先级），即：

```
Managed → User → Project → Local → AutoMem → TeamMem
```

**原因**：后加载的文件在模型上下文中位置更靠后，根据 LLM 的注意力机制，后文的内容通常会被赋予更高的权重。

### 2.3 目录遍历算法

对于 Project 和 Local 类型文件，系统从当前工作目录向上遍历到根目录：

```typescript
let currentDir = originalCwd
const dirs: string[] = []

while (currentDir !== parse(currentDir).root) {
  dirs.push(currentDir)
  currentDir = dirname(currentDir)
}

// 从根目录向下处理（根目录的 CLAUDE.md 优先级最低）
for (const dir of dirs.reverse()) {
  // 处理 Project 文件
  join(dir, 'CLAUDE.md')
  join(dir, '.claude', 'CLAUDE.md')
  join(dir, '.claude', 'rules', '*.md')
  
  // 处理 Local 文件
  join(dir, 'CLAUDE.local.md')
}
```

**示例**：
```
假设当前目录：/home/user/projects/myapp/src/components

遍历顺序（向上）：
1. /home/user/projects/myapp/src/components
2. /home/user/projects/myapp/src
3. /home/user/projects/myapp
4. /home/user/projects
5. /home/user
6. /home
7. /

处理顺序（从根向下）：
1. /CLAUDE.md (如果存在)
2. /home/CLAUDE.md
3. ...
4. /home/user/projects/myapp/CLAUDE.md (项目根)
5. /home/user/projects/myapp/src/CLAUDE.md
6. /home/user/projects/myapp/src/components/CLAUDE.md
```

---

## 3. @include 指令系统

### 3.1 语法

```markdown
@path/to/file.md
@./relative/path.md
@~/home/path.md
@/absolute/path.md
```

- `@path`（无前缀）：相对路径，等同于 `@./path`
- `@./path`：相对于当前文件的相对路径
- `@~/path`：相对于用户家目录的路径
- `@/path`：绝对路径

### 3.2 实现细节

**提取算法**：

1. 使用 `marked` 库的 Lexer 将 markdown 转换为 tokens
2. 遍历 tokens，跳过 `code` 和 `codespan` 类型（代码块内的 @path 不解析）
3. 对 `text` 和 `html` 类型的 token，使用正则提取 @path

**正则表达式**：
```typescript
const includeRegex = /(?:^|\s)@((?:[^\s\\]|\\ )+)/g
```

- `(?:^|\s)`：匹配行首或空白字符（确保 @ 前面不是其他字符）
- `((?:[^\s\\]|\\ )+)`：捕获组，匹配：
  - `[^\s\\]`：非空白、非反斜杠的字符
  - `\\ `：转义的空格（支持文件名含空格）

**HTML 注释处理**：
```markdown
<!-- 这是注释 @./ignored.md --> @./included.md
```

- HTML 块级注释（`<!-- ... -->`）中的 @path 被忽略
- 注释后的残留内容（如 `<!-- note --> @./file.md`）会被检查

### 3.3 循环引用检测

```typescript
const processedPaths = new Set<string>()
const MAX_INCLUDE_DEPTH = 5

async function processMemoryFile(filePath, type, processedPaths, depth) {
  const normalizedPath = normalizePathForComparison(filePath)
  
  // 跳过已处理的路径或超过最大深度
  if (processedPaths.has(normalizedPath) || depth >= MAX_INCLUDE_DEPTH) {
    return []
  }
  
  processedPaths.add(normalizedPath)
  
  // 递归处理 @include
  for (const includePath of resolvedIncludePaths) {
    const includedFiles = await processMemoryFile(
      includePath, type, processedPaths, depth + 1, filePath
    )
    result.push(...includedFiles)
  }
}
```

**机制**：
- 使用 `Set` 记录已处理的路径（标准化后比较）
- 最大深度限制：5 层
- 路径标准化：处理 Windows 大小写差异（`C:\` vs `c:\`）

### 3.4 支持的文件类型

系统定义了白名单，只允许文本文件被 @include：

```typescript
const TEXT_FILE_EXTENSIONS = new Set([
  // 文档
  '.md', '.txt', '.text', '.rst', '.adoc', '.org', '.tex',
  // 数据
  '.json', '.yaml', '.yml', '.toml', '.xml', '.csv',
  // Web
  '.html', '.css', '.scss',
  // 编程语言（几乎所有常见语言）
  '.js', '.ts', '.tsx', '.jsx', '.py', '.go', '.rs', '.java', '.cpp',
  '.rb', '.php', '.lua', '.R', '.sh', '.sql', '.graphql',
  // 配置
  '.env', '.ini', '.cfg', '.conf', '.properties', '.lock',
  // 其他
  '.log', '.diff', '.patch', '.proto', '.vue', '.svelte',
  // ... 完整列表约 100 种扩展名
])
```

**过滤逻辑**：
```typescript
const ext = extname(filePath).toLowerCase()
if (ext && !TEXT_FILE_EXTENSIONS.has(ext)) {
  logForDebugging(`Skipping non-text file in @include: ${filePath}`)
  return { info: null, includePaths: [] }
}
```

---

## 4. 条件规则系统

### 4.1 Frontmatter 语法

条件规则使用 frontmatter 指定适用的文件路径：

```markdown
---
paths:
  - src/**/*.ts
  - tests/**/*.test.ts
---

这是只适用于 TypeScript 源文件和测试文件的规则。
```

### 4.2 处理流程

**Phase 1: 解析 frontmatter**

```typescript
function parseFrontmatterPaths(rawContent: string) {
  const { frontmatter, content } = parseFrontmatter(rawContent)
  
  if (!frontmatter.paths) {
    return { content } // 无条件规则
  }
  
  const patterns = splitPathInFrontmatter(frontmatter.paths)
    .map(pattern => {
      // 移除 /** 后缀（ignore 库自动处理）
      return pattern.endsWith('/**') ? pattern.slice(0, -3) : pattern
    })
    .filter(p => p.length > 0)
  
  // 如果所有模式都是 ** (match-all)，视为无条件
  if (patterns.length === 0 || patterns.every(p => p === '**')) {
    return { content }
  }
  
  return { content, paths: patterns }
}
```

**Phase 2: 路径匹配**

```typescript
export async function processConditionedMdRules(
  targetPath, rulesDir, type, processedPaths, includeExternal
) {
  // 1. 加载所有条件规则文件
  const conditionedRuleMdFiles = await processMdRules({
    rulesDir, type, processedPaths,
    conditionalRule: true, // 只加载带 frontmatter paths 的文件
  })
  
  // 2. 过滤出匹配 targetPath 的规则
  return conditionedRuleMdFiles.filter(file => {
    if (!file.globs || file.globs.length === 0) return false
    
    // 计算相对路径
    const baseDir = type === 'Project' 
      ? dirname(dirname(rulesDir)) // .claude 的父目录
      : getOriginalCwd() // Managed/User 规则相对于项目根
    
    const relativePath = isAbsolute(targetPath)
      ? relative(baseDir, targetPath)
      : targetPath
    
    // 检查路径有效性
    if (!relativePath || relativePath.startsWith('..') || isAbsolute(relativePath)) {
      return false
    }
    
    // 使用 ignore 库进行 glob 匹配
    return ignore().add(file.globs).ignores(relativePath)
  })
}
```

### 4.3 匹配示例

```yaml
# .claude/rules/frontend.md
---
paths:
  - src/components/**
  - src/pages/**
---
前端组件规范...

# .claude/rules/backend.md
---
paths:
  - src/api/**
  - src/services/**
---
后端 API 规范...

# .claude/rules/all.md
---
paths:
  - "**"
---
全项目通用规范...
```

**匹配逻辑**：
- `src/components/Button.tsx` → 匹配 `frontend.md` 和 `all.md`
- `src/api/users.ts` → 匹配 `backend.md` 和 `all.md`
- `README.md` → 只匹配 `all.md`

### 4.4 应用场景

1. **语言特定规则**：针对不同编程语言配置不同的 Lint 规则、测试命令
2. **模块特定规则**：前端、后端、数据管道等不同模块有不同的开发流程
3. **测试 vs 生产**：测试文件和生产代码有不同的规范

---

## 5. 文件内容处理

### 5.1 Frontmatter 移除

```typescript
const { frontmatter, content } = parseFrontmatter(rawContent)
// content 已移除 frontmatter
```

### 5.2 HTML 注释移除

```typescript
export function stripHtmlComments(content: string): {
  content: string
  stripped: boolean
} {
  if (!content.includes('<!--')) {
    return { content, stripped: false }
  }
  
  const tokens = new Lexer({ gfm: false }).lex(content)
  return stripHtmlCommentsFromTokens(tokens)
}

function stripHtmlCommentsFromTokens(tokens) {
  let result = ''
  const commentSpan = /<!--[\s\S]*?-->/g
  
  for (const token of tokens) {
    if (token.type === 'html') {
      const trimmed = token.raw.trimStart()
      if (trimmed.startsWith('<!--') && trimmed.includes('-->')) {
        // 只移除完整的注释块
        const residue = token.raw.replace(commentSpan, '')
        if (residue.trim().length > 0) {
          result += residue // 保留注释后的残留内容
        }
        continue
      }
    }
    result += token.raw
  }
  
  return { content: result, stripped: true }
}
```

**注意**：
- 只移除**块级**HTML 注释，代码块内的注释保留
- 未闭合的注释（`<!--` 无 `-->`）保留，防止拼写错误吞掉文件剩余内容

### 5.3 AutoMem/TeamMem 截断

```typescript
if (type === 'AutoMem' || type === 'TeamMem') {
  finalContent = truncateEntrypointContent(strippedContent).content
}
```

截断到最大字符数限制（默认 40000 字符）。

---

## 6. 内容差异化检测

### 6.1 设计目的

当文件内容经过处理（移除 frontmatter、移除注释、截断）后，与磁盘上的原始内容不同，系统需要记录这种差异，以便：

1. 缓存去重：相同内容不重复处理
2. 变更检测：磁盘文件变化时能感知
3. Edit/Write 操作：需要显式 Read 后才能修改

### 6.2 实现

```typescript
type MemoryFileInfo = {
  path: string
  type: MemoryType
  content: string          // 处理后的内容（注入上下文）
  parent?: string          // 包含此文件的父文件路径
  globs?: string[]         // 条件规则的路径模式
  contentDiffersFromDisk?: boolean  // 内容是否与磁盘不同
  rawContent?: string      // 磁盘原始内容（当不同时）
}

// 在 parseMemoryFileContent 中
const contentDiffersFromDisk = finalContent !== rawContent
return {
  info: {
    ...,
    contentDiffersFromDisk,
    rawContent: contentDiffersFromDisk ? rawContent : undefined,
  },
}
```

**覆盖场景**：
- Frontmatter 移除
- HTML 注释移除
- MEMORY.md 入口点截断

---

## 7. 排除机制

### 7.1 claudeMdExcludes 配置

用户可以通过配置排除特定的 CLAUDE.md 文件：

```typescript
function isClaudeMdExcluded(filePath: string, type: MemoryType): boolean {
  // 只适用于 User、Project、Local 类型
  if (type !== 'User' && type !== 'Project' && type !== 'Local') {
    return false
  }
  
  const patterns = getInitialSettings().claudeMdExcludes
  
  // 构建扩展模式列表（包含 realpath 解析）
  const expandedPatterns = resolveExcludePatterns(patterns)
  
  return picomatch.isMatch(normalizedPath, expandedPatterns, { dot: true })
}
```

### 7.2 符号链接处理

在 macOS 等系统上，`/tmp` 可能是 `/private/tmp` 的符号链接。排除模式需要同时匹配原始路径和解析后的路径：

```typescript
function resolveExcludePatterns(patterns: string[]) {
  const expanded: string[] = patterns.map(p => p.replaceAll('\\', '/'))
  
  for (const normalized of expanded) {
    if (!normalized.startsWith('/')) continue
    
    // 找到静态前缀（glob 字符之前的部分）
    const globStart = normalized.search(/[*?{[]/)
    const staticPrefix = globStart === -1 ? normalized : normalized.slice(0, globStart)
    const dirToResolve = dirname(staticPrefix)
    
    try {
      const resolvedDir = fs.realpathSync(dirToResolve).replaceAll('\\', '/')
      if (resolvedDir !== dirToResolve) {
        const resolvedPattern = resolvedDir + normalized.slice(dirToResolve.length)
        expanded.push(resolvedPattern)
      }
    } catch {
      // 目录不存在，跳过
    }
  }
  
  return expanded
}
```

---

## 8. Hooks 系统

### 8.1 InstructionsLoaded Hook

当指令文件加载完成时触发：

```typescript
// 在 getMemoryFiles 返回前
if (!forceIncludeExternal) {
  const eagerLoadReason = consumeNextEagerLoadReason()
  if (eagerLoadReason !== undefined && hasInstructionsLoadedHook()) {
    for (const file of result) {
      if (!isInstructionsMemoryType(file.type)) continue
      const loadReason = file.parent ? 'include' : eagerLoadReason
      void executeInstructionsLoadedHooks(
        file.path, file.type, loadReason,
        { globs: file.globs, parentFilePath: file.parent },
      )
    }
  }
}
```

**触发条件**：
- `forceIncludeExternal = false`（正常加载，非外部包含检查）
- 存在注册的 InstructionsLoaded hook
- 文件类型是指令类型（Managed/User/Project/Local）

**加载原因**：
- `'session_start'`：会话启动时
- `'compact'`：压缩后重新加载
- `'include'`：通过 @include 加载

---

## 9. 外部包含检查

### 9.1 问题背景

用户可能在 CLAUDE.md 中使用 `@include` 指向当前工作目录之外的文件。这可能导致：

- 意外泄露敏感信息
- 加载不相关的配置

### 9.2 检测机制

```typescript
export function getExternalClaudeMdIncludes(
  files: MemoryFileInfo[]
): ExternalClaudeMdInclude[] {
  const externals: ExternalClaudeMdInclude[] = []
  for (const file of files) {
    // User 类型 + 有父文件 + 不在原始 CWD 内 = 外部包含
    if (file.type !== 'User' && file.parent && !pathInOriginalCwd(file.path)) {
      externals.push({ path: file.path, parent: file.parent })
    }
  }
  return externals
}
```

### 9.3 用户批准流程

```typescript
const config = getCurrentProjectConfig()
const includeExternal =
  forceIncludeExternal ||
  config.hasClaudeMdExternalIncludesApproved ||
  false
```

- 首次发现外部包含时显示警告
- 用户批准后会设置 `hasClaudeMdExternalIncludesApproved`
- 警告只显示一次（`hasClaudeMdExternalIncludesWarningShown` 标记）

---

## 10. 性能优化

### 10.1 Memoization

```typescript
export const getMemoryFiles = memoize(async (forceIncludeExternal = false) => {
  // ...
})
```

使用 `lodash-es/memoize` 缓存结果，避免重复加载。

### 10.2 缓存失效

```typescript
export function clearMemoryFileCaches(): void {
  getMemoryFiles.cache?.clear?.()
}

export function resetGetMemoryFilesCache(reason: InstructionsLoadReason = 'session_start'): void {
  nextEagerLoadReason = reason
  shouldFireHook = true
  clearMemoryFileCaches()
}
```

**何时失效**：
- 会话压缩后（`reason = 'compact'`）
- 工作树切换
- 设置同步
- 内存对话框操作

### 10.3 延迟加载

条件规则文件采用延迟加载策略：

1. **Eager Load**：无条件规则在启动时加载
2. **Lazy Load**：条件规则只在访问匹配文件时加载

```typescript
// getManagedAndUserConditionalRules 在访问文件前调用
export async function getManagedAndUserConditionalRules(
  targetPath, processedPaths
) {
  // 只加载匹配 targetPath 的 Managed 和 User 条件规则
}
```

---

## 11. 错误处理

### 11.1 文件读取错误

```typescript
function handleMemoryFileReadError(error: unknown, filePath: string): void {
  const code = getErrnoCode(error)
  
  // ENOENT = 文件不存在，EISDIR = 是目录 - 两者都是预期情况，静默跳过
  if (code === 'ENOENT' || code === 'EISDIR') {
    return
  }
  
  // EACCES = 权限不足，记录事件
  if (code === 'EACCES') {
    logEvent('tengu_claude_md_permission_error', {
      is_access_error: 1,
      has_home_dir: filePath.includes(getClaudeConfigHomeDir()) ? 1 : 0,
    })
  }
}
```

### 11.2 规则目录错误

```typescript
try {
  entries = await fs.readdir(resolvedRulesDir)
} catch (e: unknown) {
  const code = getErrnoCode(e)
  if (code === 'ENOENT' || code === 'EACCES' || code === 'ENOTDIR') {
    return [] // 目录不存在/无权限/不是目录，返回空数组
  }
  throw e // 其他错误向上传播
}
```

---

## 12. Git Worktree 支持

### 12.1 问题

当在 git worktree 中运行时，向上遍历目录树会同时经过 worktree 根和主 repo 根。两者都包含 `CLAUDE.md` 等文件，导致重复加载。

### 12.2 解决方案

```typescript
const gitRoot = findGitRoot(originalCwd)
const canonicalRoot = findCanonicalGitRoot(originalCwd)
const isNestedWorktree =
  gitRoot !== null &&
  canonicalRoot !== null &&
  normalizePathForComparison(gitRoot) !== normalizePathForComparison(canonicalRoot) &&
  pathInWorkingPath(gitRoot, canonicalRoot)

for (const dir of dirs) {
  const skipProject =
    isNestedWorktree &&
    pathInWorkingPath(dir, canonicalRoot) &&
    !pathInWorkingPath(dir, gitRoot)
  
  // 跳过主 repo 中的检查-in 文件（CLAUDE.md 等）
  if (isSettingSourceEnabled('projectSettings') && !skipProject) {
    // 加载 Project 文件
  }
  
  // CLAUDE.local.md 仍然加载（gitignored，只存在于主 repo）
  if (isSettingSourceEnabled('localSettings')) {
    // 加载 Local 文件
  }
}
```

**逻辑**：
- Project 类型（检查-in）文件：跳过主 repo 中、worktree 外的目录
- Local 类型（gitignored）文件：仍然加载，只存在于主 repo

---

## 13. 总结

CLAUDE.md 上下文注入系统是一个复杂而灵活的系统，核心特点：

| 特性 | 描述 |
|------|------|
| 多层次 | 6 层优先级，从系统到用户到项目 |
| 动态包含 | @include 指令支持文件组合 |
| 条件规则 | 基于路径 glob 的动态应用 |
| 安全防护 | 非文本过滤、外部包含检查、排除配置 |
| 性能优化 | Memoization、延迟加载、缓存失效 |
| 错误处理 | 优雅降级，权限错误上报 |
| 特殊情况 | Git worktree、符号链接、循环引用 |

这个系统确保了模型在每次对话开始时都能获得最相关、最全面的上下文信息，同时保持灵活性和安全性。
