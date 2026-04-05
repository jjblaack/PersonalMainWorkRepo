# Harness 工程专题 - 03-Bash 安全检查

Bash 工具是 Claude Code 中最危险的工具，因为它可以执行任意系统命令。本节详细讲解 Bash 工具的多层安全检查机制。

## 1. 检查流程概览

```
用户命令 → AST 解析 → 语义检查 → 规则匹配 → 路径约束 → 命令注入检测 → 决策
```

**源码**: `src/tools/BashTool/bashPermissions.ts:1050-1178`

```typescript
export const bashToolCheckPermission = (
  input: z.infer<typeof BashTool.inputSchema>,
  toolPermissionContext: ToolPermissionContext,
  compoundCommandHasCd?: boolean,
  astCommand?: SimpleCommand,
): PermissionResult => {
  const command = input.command.trim()
  
  // ========== 步骤 1: 精确匹配 ==========
  const exactMatchResult = bashToolCheckExactMatchPermission(input, toolPermissionContext)
  if (exactMatchResult.behavior === 'deny' || exactMatchResult.behavior === 'ask') {
    return exactMatchResult
  }
  
  // ========== 步骤 2: 前缀/通配符规则匹配 ==========
  const { matchingDenyRules, matchingAskRules, matchingAllowRules } =
    matchingRulesForInput(input, toolPermissionContext, 'prefix', {
      skipCompoundCheck: astCommand !== undefined,
    })
  
  // 2a: deny 规则
  if (matchingDenyRules[0] !== undefined) {
    return { behavior: 'deny', decisionReason: { type: 'rule', rule: matchingDenyRules[0] } }
  }
  
  // 2b: ask 规则
  if (matchingAskRules[0] !== undefined) {
    return { behavior: 'ask', decisionReason: { type: 'rule', rule: matchingAskRules[0] } }
  }
  
  // ========== 步骤 3: 路径约束检查 ==========
  const pathResult = checkPathConstraints(
    input, getCwd(), toolPermissionContext,
    compoundCommandHasCd,
    astCommand?.redirects,
    astCommand ? [astCommand] : undefined,
  )
  if (pathResult.behavior !== 'passthrough') return pathResult
  
  // ========== 步骤 4: 精确 allow 规则 ==========
  if (exactMatchResult.behavior === 'allow') return exactMatchResult
  
  // ========== 步骤 5: 前缀/通配符 allow 规则 ==========
  if (matchingAllowRules[0] !== undefined) {
    return { behavior: 'allow', decisionReason: { type: 'rule', rule: matchingAllowRules[0] } }
  }
  
  // ========== 步骤 5b: sed 约束检查 ==========
  const sedConstraintResult = checkSedConstraints(input, toolPermissionContext)
  if (sedConstraintResult.behavior !== 'passthrough') return sedConstraintResult
  
  // ========== 步骤 6: 模式检查 ==========
  const modeResult = checkPermissionMode(input, toolPermissionContext)
  if (modeResult.behavior !== 'passthrough') return modeResult
  
  // ========== 步骤 7: 只读命令检查 ==========
  if (BashTool.isReadOnly(input)) {
    return { behavior: 'allow', decisionReason: { type: 'other', reason: 'Read-only command' } }
  }
  
  // ========== 步骤 8: 默认 ask ==========
  return {
    behavior: 'passthrough',
    suggestions: suggestionForExactCommand(command),
  }
}
```

## 2. AST 语义分析

### 2.1 为什么需要 AST 分析

传统的 shell-quote 解析存在以下问题：

1. **微分漏洞**: 不同解析器对同一命令的理解可能不同
2. **结构分析缺失**: 无法识别命令组合、控制流等复杂结构
3. **argv 提取不准确**: 引号、转义、扩展等处理复杂

**示例**: `cat "file with spaces.txt"` - shell-quote 和 bash 可能在词边界上产生分歧。

### 2.2 tree-sitter 集成

**源码**: `src/utils/bash/parser.ts`

```typescript
export async function parseCommandRaw(
  command: string,
): Promise<Node | null | typeof PARSE_ABORTED> {
  if (!command || command.length > MAX_COMMAND_LENGTH) return null
  
  if (feature('TREE_SITTER_BASH') || feature('TREE_SITTER_BASH_SHADOW')) {
    await ensureParserInitialized()
    const mod = getParserModule()
    
    if (!mod) return null
    
    try {
      const result = mod.parse(command)
      // null = timeout/node-budget 中断
      if (result === null) {
        logEvent('tengu_tree_sitter_parse_abort', {
          cmdLength: command.length,
          panic: false,
        })
        return PARSE_ABORTED
      }
      return result
    } catch {
      logEvent('tengu_tree_sitter_parse_abort', {
        cmdLength: command.length,
        panic: true,
      })
      return PARSE_ABORTED
    }
  }
  return null
}
```

### 2.3 parseForSecurityFromAst

**源码**: `src/utils/bash/ast.ts`

```typescript
export type ParseForSecurityResult =
  | { kind: 'simple'; commands: SimpleCommand[] }
  | { kind: 'too-complex'; reason: string; nodeType?: string }
  | { kind: 'parse-unavailable' }

export type SimpleCommand = {
  argv: string[]           // argv[0] 是命令名，后续是参数
  envVars: { name: string; value: string }[]  // VAR=val 赋值
  redirects: Redirect[]    // 重定向
  text: string             // 原始文本 span
}
```

**核心函数**:

```typescript
export function parseForSecurityFromAst(
  command: string,
  astRoot: Node,
): ParseForSecurityResult {
  // ========== 预检查 ==========
  // 控制字符检测（NBSP, CR 等）
  if (CONTROL_CHAR_RE.test(command)) {
    return {
      kind: 'too-complex',
      reason: 'Command contains control characters',
      nodeType: 'control_char',
    }
  }
  
  // 不可见 Unicode 空白
  if (UNICODE_WHITESPACE_RE.test(command)) {
    return {
      kind: 'too-complex',
      reason: 'Command contains invisible Unicode characters',
      nodeType: 'unicode_whitespace',
    }
  }
  
  // 反斜杠 + 空白（词边界分歧）
  if (BACKSLASH_WHITESPACE_RE.test(command)) {
    return {
      kind: 'too-complex',
      reason: 'Command contains backslash-escaped whitespace',
      nodeType: 'backslash_whitespace',
    }
  }
  
  // zsh 特性（动态目录、EQUALS 扩展）
  if (ZSH_TILDE_BRACKET_RE.test(command) || ZSH_EQUALS_EXPANSION_RE.test(command)) {
    return {
      kind: 'too-complex',
      reason: 'Command contains zsh-specific expansions',
      nodeType: 'zsh_expansion',
    }
  }
  
  // 括号 + 引号组合（复杂解析边界）
  if (BRACE_QUOTE_COMBOS_RE.test(command)) {
    return {
      kind: 'too-complex',
      reason: 'Command contains complex brace/quote combinations',
      nodeType: 'brace_quote_combo',
    }
  }
  
  // ========== AST 遍历 ==========
  const commands: SimpleCommand[] = []
  const result = walkProgram(astRoot)
  
  if (result.kind === 'error') {
    return { kind: 'too-complex', reason: result.reason, nodeType: result.nodeType }
  }
  
  return { kind: 'simple', commands: result.commands }
}
```

### 2.4 危险节点类型

```typescript
const DANGEROUS_TYPES = new Set([
  'command_substitution',   // $(...)
  'process_substitution',   // <(...) >(...)
  'expansion',              // ${...}, $((...))
  'simple_expansion',       // $VAR（未加引号）
  'brace_expression',       // {a,b}
  'subshell',               // (...)
  'compound_statement',     // { ...; }
  'for_statement',          // for x in ...; do ...; done
  'while_statement',        // while ...; do ...; done
  'until_statement',        // until ...; do ...; done
  'if_statement',           // if ...; then ...; fi
  'case_statement',         // case ... in ... esac
  'function_definition',    // foo() { ... }
  'test_command',           // [ ... ]
  'ansi_c_string',          // $'...'
  'translated_string',      // $"..."
  'herestring_redirect',    // <<<
  'heredoc_redirect',       // <<
])
```

### 2.5 语义检查

```typescript
export function checkSemantics(
  commands: SimpleCommand[],
): { ok: true } | { ok: false; reason: string } {
  for (const cmd of commands) {
    const baseCmd = cmd.argv[0]
    if (!baseCmd) continue
    
    // ========== 评估类内置命令 ==========
    const bashKeyword = baseCmd in SHELL_KEYWORDS
    if (bashKeyword) {
      const keyword = SHELL_KEYWORDS[baseCmd as keyof typeof SHELL_KEYWORDS]!
      if (keyword.type === 'eval-like') {
        return {
          ok: false,
          reason: `${baseCmd} can execute arbitrary code`,
        }
      }
      if (keyword.type === 'control-flow') {
        return {
          ok: false,
          reason: `${baseCmd} is a control flow keyword`,
        }
      }
      if (keyword.type === 'source') {
        return {
          ok: false,
          reason: `${baseCmd} can source external scripts`,
        }
      }
    }
    
    // ========== 包装器剥离检查 ==========
    // nice, stdbuf, timeout 等包装器需要剥离后检查内层命令
    const stripped = stripWrappersFromArgv(cmd.argv)
    if (stripped.length < cmd.argv.length) {
      // 剥离后重新检查
      const innerCheck = checkSemantics([{ ...cmd, argv: stripped }])
      if (!innerCheck.ok) return innerCheck
    }
  }
  
  return { ok: true }
}
```

## 3. 路径约束检查

### 3.1 允许的工作目录

**源码**: `src/tools/BashTool/pathValidation.ts`

```typescript
export function checkPathConstraints(
  input: z.infer<typeof BashTool.inputSchema>,
  cwd: string,
  toolPermissionContext: ToolPermissionContext,
  compoundCommandHasCd?: boolean,
  redirects?: Redirect[],
  astCommands?: readonly SimpleCommand[],
): PermissionResult {
  const command = input.command.trim()
  
  // ========== 提取文件参数 ==========
  // 从 argv 中提取可能是文件路径的参数
  const filePaths = astCommands
    ? astCommands.flatMap(cmd => extractFilePathsFromArgv(cmd.argv))
    : extractFilePathsFromCommand(command)
  
  // ========== 检查每个文件路径 ==========
  for (const filePath of filePaths) {
    const resolvedPath = resolve(filePath, cwd)
    
    // 检查是否在允许的工作目录内
    const isInAllowedPath = isPathInAllowedDirectories(resolvedPath, toolPermissionContext)
    if (!isInAllowedPath) {
      return {
        behavior: 'ask',
        decisionReason: {
          type: 'workingDir',
          reason: `Command accesses path outside allowed directories: ${resolvedPath}`,
        },
        blockedPath: resolvedPath,
      }
    }
    
    // 检查敏感路径（.git, .claude, .vscode 等）
    if (isPathInProtectedNamespace(resolvedPath)) {
      return {
        behavior: 'ask',
        decisionReason: {
          type: 'safetyCheck',
          classifierApprovable: true,  // auto 模式下可交给分类器
        },
      }
    }
  }
  
  // ========== 检查输出重定向 ==========
  if (redirects) {
    for (const redirect of redirects) {
      if (['>', '>>', '>|'].includes(redirect.op)) {
        const targetPath = resolve(redirect.target, cwd)
        
        // 禁止写入敏感路径
        if (isPathInProtectedNamespace(targetPath)) {
          return {
            behavior: 'ask',
            decisionReason: {
              type: 'safetyCheck',
              reason: `Writing to protected path: ${targetPath}`,
            },
          }
        }
      }
    }
  }
  
  return { behavior: 'passthrough' }
}
```

### 3.2 敏感路径保护

```typescript
const PROTECTED_NAMESPACES = [
  '.git',      // Git 仓库
  '.claude',   // Claude 配置
  '.vscode',   // VSCode 配置
  '.idea',     // IDEA 配置
  '.env',      // 环境变量文件
  'node_modules',
  '__pycache__',
  // ...
]

export function isPathInProtectedNamespace(path: string): boolean {
  const normalized = path.replace(/\\/g, '/')
  return PROTECTED_NAMESPACES.some(ns => 
    normalized.includes(`/${ns}/`) || normalized.endsWith(`/${ns}`)
  )
}
```

## 4. 命令注入检测

### 4.1 安全异步检查

**源码**: `src/tools/BashTool/bashSecurity.ts`

```typescript
export async function bashCommandIsSafeAsync_DEPRECATED(
  command: string,
): Promise<{ behavior: 'passthrough' | 'ask'; message?: string }> {
  // 检测命令注入模式
  // - 命令替换 $(...)
  // - 进程替换 <(...) >(...)
  // - 管道内的危险命令
  // - shell 操作符 && || ; | &
  
  if (hasCommandInjection(command)) {
    return {
      behavior: 'ask',
      message: 'Command contains possible injection patterns',
    }
  }
  
  return { behavior: 'passthrough' }
}
```

### 4.2 AST 优先原则

```typescript
// bashPermissions.ts:1217-1239
if (!astParseSucceeded && !isEnvTruthy(process.env.CLAUDE_CODE_DISABLE_COMMAND_INJECTION_CHECK)) {
  const safetyResult = await bashCommandIsSafeAsync(input.command)
  
  if (safetyResult.behavior !== 'passthrough') {
    return {
      behavior: 'ask',
      decisionReason: {
        type: 'other',
        reason: safetyResult.message ?? 'Command contains patterns that could pose security risks',
      },
      suggestions: [],  // 不建议保存危险命令
    }
  }
}
```

**设计思想**: AST 解析成功时，跳过传统的正则检测，因为：
1. AST 已经验证了结构安全性
2. 传统检测容易产生误报
3. 避免重复检查

## 5. Sandbox 自动允许

### 5.1 Sandbox 自动允许逻辑

**源码**: `src/tools/BashTool/bashPermissions.ts:1270-1360`

```typescript
function checkSandboxAutoAllow(
  input: z.infer<typeof BashTool.inputSchema>,
  toolPermissionContext: ToolPermissionContext,
): PermissionResult {
  const command = input.command.trim()
  
  // 检查显式 deny/ask 规则
  const { matchingDenyRules, matchingAskRules } = matchingRulesForInput(
    input, toolPermissionContext, 'prefix',
  )
  
  // deny 规则优先
  if (matchingDenyRules[0] !== undefined) {
    return { behavior: 'deny', decisionReason: { type: 'rule', rule: matchingDenyRules[0] } }
  }
  
  // 复合命令：逐个子命令检查 deny/ask 规则
  if (matchingAskRules[0] !== undefined) {
    // 复合命令需要逐个子命令检查
    const subcommands = splitCommand(command)
    for (const subcmd of subcommands) {
      const subResult = checkSubcommandAgainstRules(subcmd, toolPermissionContext)
      if (subResult.behavior === 'deny' || subResult.behavior === 'ask') {
        return subResult
      }
    }
    return { behavior: 'ask', decisionReason: { type: 'rule', rule: matchingAskRules[0] } }
  }
  
  // 没有显式阻止 → 自动允许（沙盒保护）
  return {
    behavior: 'allow',
    decisionReason: {
      type: 'sandbox',
      reason: 'Command will run in sandbox with restricted filesystem/network access',
    },
  }
}
```

### 5.2 排除命令

```typescript
export function getExcludedCommands(): string[] {
  const settings = getSettings_DEPRECATED()
  return settings?.sandbox?.excludedCommands ?? []
}
```

排除的命令即使在沙盒中运行也需要用户审批。

## 6. sed 约束检查

**源码**: `src/tools/BashTool/sedValidation.ts`

```typescript
export function checkSedConstraints(
  input: z.infer<typeof BashTool.inputSchema>,
  toolPermissionContext: ToolPermissionContext,
): PermissionResult {
  const command = input.command.trim()
  
  // 检测 sed 原地编辑操作
  const sedInPlaceEdit = /sed\s+(-i|--in-place)/.exec(command)
  if (sedInPlaceEdit) {
    return {
      behavior: 'ask',
      decisionReason: {
        type: 'safetyCheck',
        reason: 'sed in-place editing can modify files destructively',
      },
    }
  }
  
  return { behavior: 'passthrough' }
}
```

## 7. 完整检查流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                        Bash 命令输入                              │
└─────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤 1: AST 解析 (tree-sitter)                                   │
│ - 解析为 AST                                                     │
│ - 预检查（控制字符、Unicode 空白、反斜杠空白）                      │
│ - 提取 SimpleCommand[] (argv, envVars, redirects)                │
│ - parseForSecurityFromAst                                        │
│   → simple / too-complex / parse-unavailable                     │
└─────────────────────────────────────────────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │ parse 成功                   │ parse 失败/太复杂
                    ▼                              ▼
┌───────────────────────────────────┐   ┌───────────────────────────────────┐
│ 步骤 2: 语义检查                   │   │ 步骤 2: 回退到传统检查            │
│ - checkSemantics()                │   │ - shell-quote 解析                │
│ - eval-like builtins (eval, etc.) │   │ - 正则命令注入检测                │
│ - 控制流命令 (for, while, if)     │   │ - 回退到 ask                       │
│ - 包装器剥离检查                   │   │                                   │
└───────────────────────────────────┘   └───────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤 3: 规则匹配                                                 │
│ - 精确匹配：bashToolCheckExactMatchPermission                   │
│ - 前缀/通配符匹配：matchingRulesForInput                        │
│   - stripSafeWrappers（包装器剥离）                              │
│   - stripAllLeadingEnvVars（deny/ask 规则）                       │
│   - 复合命令检测（前缀/通配符不匹配）                              │
└─────────────────────────────────────────────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │ 匹配 deny/ask               │ 无匹配
                    ▼                              ▼
┌───────────────────────────────────┐   ┌───────────────────────────────────┐
│ 返回 deny/ask                     │   │ 步骤 4: 路径约束检查                │
└───────────────────────────────────┘   │ - checkPathConstraints()          │
                                        │ - 文件路径提取                      │
                                        │ - 工作目录检查                      │
                                        │ - 敏感路径检查 (.git, .claude)     │
                                        │ - 重定向目标检查                    │
                                        └───────────────────────────────────┘
                                                           │
                                        ┌──────────────────┴──────────────────┐
                                        │ 阻止                                │ 通过
                                        ▼                                     ▼
                              ┌───────────────────┐   ┌───────────────────────────────────┐
                              │ 返回 ask          │   │ 步骤 5: sed 约束检查                │
                              └───────────────────┘   │ - checkSedConstraints()           │
                                                      │ - sed -i 原地编辑检测             │
                                                      └───────────────────────────────────┘
                                                                         │
                                                      ┌──────────────────┴──────────────────┐
                                                      │ 阻止                                │ 通过
                                                      ▼                                     ▼
                                            ┌───────────────────┐   ┌───────────────────────────────────┐
                                            │ 返回 ask          │   │ 步骤 6: 模式检查                    │
                                            └───────────────────┘   │ - checkPermissionMode()           │
                                                                    │ - acceptEdits 模式                 │
                                                                    └───────────────────────────────────┘
                                                                                       │
                                                                    ┌──────────────────┴──────────────────┐
                                                                    │ 阻止                                │ 通过
                                                                    ▼                                     ▼
                                                          ┌───────────────────┐   ┌───────────────────────────────────┐
                                                          │ 返回 ask/deny     │   │ 步骤 7: 只读命令检查                │
                                                          └───────────────────┘   │ - BashTool.isReadOnly()           │
                                                                                  │ - ls, cat, head, tail, grep, etc. │
                                                                                  └───────────────────────────────────┘
                                                                                                     │
                                                                                  ┌──────────────────┴──────────────────┐
                                                                                  │ 只读                                │ 非只读
                                                                                  ▼                                     ▼
                                                                        ┌───────────────────┐   ┌───────────────────────────────────┐
                                                                        │ 返回 allow        │   │ 步骤 8: 默认 ask（带建议）           │
                                                                        └───────────────────┘   │ - suggestionForExactCommand()     │
                                                                                                └───────────────────────────────────┘
```

## 8. 关键设计原则

### 8.1 防御深度

```
规则匹配 → AST 语义 → 路径约束 → 命令注入 → Sandbox
```

多层检查确保单层绕过不会导致安全问题。

### 8.2 失败关闭

```typescript
// AST 解析失败 → too-complex → ask
if (result.kind === 'too-complex') {
  return { kind: 'too-complex', reason: '...' }
}

// 规则匹配不确定 → ask
if (noRulesMatch) {
  return { behavior: 'ask' }
}
```

### 8.3 AST 优先

AST 解析成功时，回退到传统检查：

```typescript
if (!astParseSucceeded) {
  // 传统正则检测
  const safetyResult = await bashCommandIsSafeAsync(command)
}
```

### 8.4 保守剥离

包装器和环境变量剥离采用保守策略：

```typescript
// SAFE_ENV_VARS 白名单
const SAFE_ENV_VARS = new Set([
  'NODE_ENV', 'GOOS', 'GOARCH',  // 仅安全配置
  // 不包含 PATH, LD_PRELOAD, PYTHONPATH 等危险变量
])
```

### 8.5 复合命令免疫

前缀/通配符规则不匹配复合命令：

```typescript
// 防止 cd /path && python3 evil.py 绕过
if (isCompoundCommand.get(cmdToMatch)) {
  return false  // 前缀/通配符规则不匹配
}
```

## 9. 总结

Bash 安全检查机制具有以下特点：

1. **AST 优先**: tree-sitter 提供准确的结构分析
2. **多层防御**: 规则 → 语义 → 路径 → 注入 → Sandbox
3. **失败关闭**: 不确定时要求用户审批
4. **复合命令免疫**: 前缀/通配符规则不匹配复合命令
5. **保守剥离**: 仅剥离已知安全的包装器和环境变量
6. **敏感路径保护**: .git, .claude, .vscode 等自动保护
