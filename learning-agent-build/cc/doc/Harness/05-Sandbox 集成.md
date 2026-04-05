# Harness 工程专题 - 05-Sandbox 集成

Sandbox 为 Bash 命令提供操作系统级别的隔离，是 Harness 工程的最后一道防线。

## 1. Sandbox 架构概览

### 1.1 核心文件

**源码**: `src/utils/sandbox/sandbox-adapter.ts`

```typescript
/**
 * Claude CLI sandbox manager - 封装 @anthropic-ai/sandbox-runtime
 * 
 * 功能：
 * - 文件系统隔离（允许/拒绝路径）
 * - 网络隔离（域名白名单）
 * - 依赖检查（bubblewrap, socat 等）
 * - 配置热更新
 */
export const SandboxManager: ISandboxManager = {
  initialize,
  wrapWithSandbox,
  isSandboxingEnabled,
  refreshConfig,
  // ... 其他方法
}
```

### 1.2 隔离类型

| 类型 | 实现 | 配置来源 |
|------|------|----------|
| **文件系统** | bubblewrap bind mounts | 允许/拒绝路径列表 |
| **网络** | socat 代理 + iptables | 域名白名单/黑名单 |
| **进程** | bubblewrap PID 隔离 | 自动启用 |

## 2. 配置转换

### 2.1 SandboxRuntimeConfig 结构

```typescript
type SandboxRuntimeConfig = {
  network: {
    allowedDomains: string[]
    deniedDomains: string[]
    allowUnixSockets?: boolean
    allowAllUnixSockets?: boolean
    allowLocalBinding?: boolean
    httpProxyPort?: number
    socksProxyPort?: number
  }
  filesystem: {
    allowWrite: string[]
    denyWrite: string[]
    allowRead: string[]
    denyRead: string[]
  }
  ignoreViolations?: IgnoreViolationsConfig
  enableWeakerNestedSandbox?: boolean
  enableWeakerNetworkIsolation?: boolean
  ripgrep?: {
    command: string
    args: string[]
    argv0?: string
  }
}
```

### 2.2 配置转换函数

**源码**: `src/utils/sandbox/sandbox-adapter.ts:172-381`

```typescript
export function convertToSandboxRuntimeConfig(
  settings: SettingsJson,
): SandboxRuntimeConfig {
  const permissions = settings.permissions || {}
  
  // ========== 网络域名 ==========
  const allowedDomains: string[] = []
  const deniedDomains: string[] = []
  
  // 从 sandbox.network.allowedDomains 获取
  for (const domain of settings.sandbox?.network?.allowedDomains || []) {
    allowedDomains.push(domain)
  }
  
  // 从 WebFetch 规则提取域名
  for (const ruleString of permissions.allow || []) {
    const rule = permissionRuleValueFromString(ruleString)
    if (rule.toolName === WEB_FETCH_TOOL_NAME && 
        rule.ruleContent?.startsWith('domain:')) {
      allowedDomains.push(rule.ruleContent.substring('domain:'.length))
    }
  }
  
  for (const ruleString of permissions.deny || []) {
    const rule = permissionRuleValueFromString(ruleString)
    if (rule.toolName === WEB_FETCH_TOOL_NAME && 
        rule.ruleContent?.startsWith('domain:')) {
      deniedDomains.push(rule.ruleContent.substring('domain:'.length))
    }
  }
  
  // ========== 文件系统路径 ==========
  // 始终包含当前目录和 Claude 临时目录
  const allowWrite: string[] = ['.', getClaudeTempDir()]
  const denyWrite: string[] = []
  const denyRead: string[] = []
  const allowRead: string[] = []
  
  // 禁止写入 settings.json（防止沙盒逃逸）
  const settingsPaths = SETTING_SOURCES.map(source =>
    getSettingsFilePathForSource(source)
  ).filter((p): p is string => p !== undefined)
  denyWrite.push(...settingsPaths)
  denyWrite.push(getManagedSettingsDropInDir())
  
  // 禁止写入 .claude/skills（与 .claude/commands 同级保护）
  denyWrite.push(resolve(originalCwd, '.claude', 'skills'))
  
  // 裸 Git 仓库 RCE 防护（检测到则 scrubBareGitRepoFiles()）
  bareGitRepoScrubPaths.length = 0
  const bareGitRepoFiles = ['HEAD', 'objects', 'refs', 'hooks', 'config']
  for (const dir of cwd === originalCwd ? [originalCwd, cwd] : [originalCwd]) {
    for (const gitFile of bareGitRepoFiles) {
      const p = resolve(dir, gitFile)
      try {
        statSync(p)
        denyWrite.push(p)  // 存在 → 只读绑定
      } catch {
        bareGitRepoScrubPaths.push(p)  // 不存在 → 命令后擦除
      }
    }
  }
  
  // 额外工作目录（--add-dir, /add-dir）
  const additionalDirs = new Set([
    ...(settings.permissions?.additionalDirectories || []),
    ...getAdditionalDirectoriesForClaudeMd(),
  ])
  allowWrite.push(...additionalDirs)
  
  // Git worktree 支持
  if (worktreeMainRepoPath && worktreeMainRepoPath !== cwd) {
    allowWrite.push(worktreeMainRepoPath)
  }
  
  // 从权限规则提取路径
  for (const source of SETTING_SOURCES) {
    const sourceSettings = getSettingsForSource(source)
    
    if (sourceSettings?.permissions) {
      for (const ruleString of sourceSettings.permissions.allow || []) {
        const rule = permissionRuleValueFromString(ruleString)
        if (rule.toolName === FILE_EDIT_TOOL_NAME && rule.ruleContent) {
          allowWrite.push(resolvePathPatternForSandbox(rule.ruleContent, source))
        }
      }
      
      for (const ruleString of sourceSettings.permissions.deny || []) {
        const rule = permissionRuleValueFromString(ruleString)
        if (rule.toolName === FILE_EDIT_TOOL_NAME && rule.ruleContent) {
          denyWrite.push(resolvePathPatternForSandbox(rule.ruleContent, source))
        }
        if (rule.toolName === FILE_READ_TOOL_NAME && rule.ruleContent) {
          denyRead.push(resolvePathPatternForSandbox(rule.ruleContent, source))
        }
      }
    }
    
    // 从 sandbox.filesystem 设置提取
    const fs = sourceSettings?.sandbox?.filesystem
    if (fs) {
      for (const p of fs.allowWrite || []) {
        allowWrite.push(resolveSandboxFilesystemPath(p, source))
      }
      for (const p of fs.denyWrite || []) {
        denyWrite.push(resolveSandboxFilesystemPath(p, source))
      }
      for (const p of fs.denyRead || []) {
        denyRead.push(resolveSandboxFilesystemPath(p, source))
      }
      if (!shouldAllowManagedReadPathsOnly() || source === 'policySettings') {
        for (const p of fs.allowRead || []) {
          allowRead.push(resolveSandboxFilesystemPath(p, source))
        }
      }
    }
  }
  
  return {
    network: {
      allowedDomains,
      deniedDomains,
      allowUnixSockets: settings.sandbox?.network?.allowUnixSockets,
      allowAllUnixSockets: settings.sandbox?.network?.allowAllUnixSockets,
      allowLocalBinding: settings.sandbox?.network?.allowLocalBinding,
      httpProxyPort: settings.sandbox?.network?.httpProxyPort,
      socksProxyPort: settings.sandbox?.network?.socksProxyPort,
    },
    filesystem: {
      denyRead,
      allowRead,
      allowWrite,
      denyWrite,
    },
    ignoreViolations: settings.sandbox?.ignoreViolations,
    enableWeakerNestedSandbox: settings.sandbox?.enableWeakerNestedSandbox,
    enableWeakerNetworkIsolation: settings.sandbox?.enableWeakerNetworkIsolation,
    ripgrep: ripgrepConfig,
  }
}
```

## 3. 路径解析语义

### 3.1 权限规则路径（Edit/Read 规则）

**源码**: `src/utils/sandbox/sandbox-adapter.ts:99-119`

```typescript
export function resolvePathPatternForSandbox(
  pattern: string,
  source: SettingSource,
): string {
  // // 前缀：绝对路径（CC 特定约定）
  if (pattern.startsWith('//')) {
    return pattern.slice(1)  // "//.aws/**" → "/.aws/**"
  }
  
  // / 前缀：相对于 settings 文件目录
  if (pattern.startsWith('/') && !pattern.startsWith('//')) {
    const root = getSettingsRootPathForSource(source)
    return resolve(root, pattern.slice(1))
  }
  
  // ~/ 和相对路径：交给 sandbox-runtime 处理
  return pattern
}
```

### 3.2 sandbox.filesystem 路径

```typescript
export function resolveSandboxFilesystemPath(
  pattern: string,
  source: SettingSource,
): string {
  // // 前缀：绝对路径（兼容旧语法）
  if (pattern.startsWith('//')) return pattern.slice(1)
  
  // 其他路径：expandPath 处理 ~/ 和相对路径
  return expandPath(pattern, getSettingsRootPathForSource(source))
}
```

**差异说明**:
- 权限规则：`/path` 相对于 settings 目录
- sandbox.filesystem: `/path` 是绝对路径

## 4. 包装器剥离

### 4.1 Argv 级剥离

**源码**: `src/utils/sandbox/sandbox-adapter.ts:678-701`

```typescript
export function stripWrappersFromArgv(argv: string[]): string[] {
  let a = argv
  for (;;) {
    if (a[0] === 'time' || a[0] === 'nohup') {
      a = a.slice(a[1] === '--' ? 2 : 1)
    } else if (a[0] === 'timeout') {
      const i = skipTimeoutFlags(a)
      if (i < 0 || !a[i] || !/^\d+(?:\.\d+)?[smhd]?$/.test(a[i]!)) return a
      a = a.slice(i + 1)
    } else if (
      a[0] === 'nice' &&
      a[1] === '-n' &&
      a[2] &&
      /^-?\d+$/.test(a[2])
    ) {
      a = a.slice(a[3] === '--' ? 4 : 3)
    } else {
      return a
    }
  }
}
```

## 5. 初始化流程

### 5.1 异步初始化

**源码**: `src/utils/sandbox/sandbox-adapter.ts:730-792`

```typescript
async function initialize(
  sandboxAskCallback?: SandboxAskCallback,
): Promise<void> {
  if (!isSandboxingEnabled()) return
  
  const wrappedCallback: SandboxAskCallback | undefined = sandboxAskCallback
    ? async (hostPattern: NetworkHostPattern) => {
        // enforce allowManagedDomainsOnly 策略
        if (shouldAllowManagedSandboxDomainsOnly()) {
          logForDebugging(
            `[sandbox] Blocked network request to ${hostPattern.host} (allowManagedDomainsOnly)`
          )
          return false
        }
        return sandboxAskCallback(hostPattern)
      }
    : undefined
  
  initializationPromise = (async () => {
    try {
      // 解析 worktree 主仓库路径
      if (worktreeMainRepoPath === undefined) {
        worktreeMainRepoPath = await detectWorktreeMainRepoPath(getCwdState())
      }
      
      const settings = getSettings_DEPRECATED()
      const runtimeConfig = convertToSandboxRuntimeConfig(settings)
      
      // 初始化基础沙盒管理器（带日志监控）
      await BaseSandboxManager.initialize(runtimeConfig, wrappedCallback)
      
      // 订阅设置变化
      settingsSubscriptionCleanup = settingsChangeDetector.subscribe(() => {
        const settings = getSettings_DEPRECATED()
        const newConfig = convertToSandboxRuntimeConfig(settings)
        BaseSandboxManager.updateConfig(newConfig)
        logForDebugging('Sandbox configuration updated from settings change')
      })
    } catch (error) {
      initializationPromise = undefined
      logForDebugging(`Failed to initialize sandbox: ${errorMessage(error)}`)
    }
  })()
  
  return initializationPromise
}
```

### 5.2 配置热更新

```typescript
function refreshConfig(): void {
  if (!isSandboxingEnabled()) return
  const settings = getSettings_DEPRECATED()
  const newConfig = convertToSandboxRuntimeConfig(settings)
  BaseSandboxManager.updateConfig(newConfig)
}
```

## 6. 平台检查

### 6.1 支持的平台

```typescript
const isSupportedPlatform = memoize((): boolean => {
  return BaseSandboxManager.isSupportedPlatform()
})

// 支持：macOS, Linux, WSL2+
// 不支持：WSL1, Windows 原生
```

### 6.2 依赖检查

```typescript
const checkDependencies = memoize((): SandboxDependencyCheck => {
  const { rgPath, rgArgs } = ripgrepCommand()
  return BaseSandboxManager.checkDependencies({
    command: rgPath,
    args: rgArgs,
  })
})
```

### 6.3 enabledPlatforms 设置

```typescript
function isPlatformInEnabledList(): boolean {
  try {
    const settings = getInitialSettings()
    const enabledPlatforms = settings?.sandbox?.enabledPlatforms
    if (enabledPlatforms === undefined) return true
    if (enabledPlatforms.length === 0) return false
    
    const currentPlatform = getPlatform()
    return enabledPlatforms.includes(currentPlatform)
  } catch (error) {
    return true
  }
}
```

### 6.4 Sandbox 不可用原因

```typescript
function getSandboxUnavailableReason(): string | undefined {
  if (!getSandboxEnabledSetting()) return undefined
  
  if (!isSupportedPlatform()) {
    const platform = getPlatform()
    if (platform === 'wsl') {
      return 'sandbox.enabled is set but WSL1 is not supported (requires WSL2)'
    }
    return `sandbox.enabled is set but ${platform} is not supported`
  }
  
  if (!isPlatformInEnabledList()) {
    return `sandbox.enabled is set but ${getPlatform()} is not in sandbox.enabledPlatforms`
  }
  
  const deps = checkDependencies()
  if (deps.errors.length > 0) {
    const platform = getPlatform()
    const hint = platform === 'macos'
      ? 'run /sandbox or /doctor for details'
      : 'install missing tools (e.g. apt install bubblewrap socat)'
    return `sandbox.enabled is set but dependencies are missing: ${deps.errors.join(', ')}`
  }
  
  return undefined
}
```

## 7. Sandbox 自动允许

### 7.1 自动允许逻辑

**源码**: `src/tools/BashTool/bashPermissions.ts:1270-1360`

```typescript
function checkSandboxAutoAllow(
  input: z.infer<typeof BashTool.inputSchema>,
  toolPermissionContext: ToolPermissionContext,
): PermissionResult {
  const command = input.command.trim()
  
  // 检查显式 deny 规则
  const { matchingDenyRules } = matchingRulesForInput(
    input, toolPermissionContext, 'prefix',
  )
  
  if (matchingDenyRules[0] !== undefined) {
    return { behavior: 'deny', decisionReason: { type: 'rule', rule: matchingDenyRules[0] } }
  }
  
  // 复合命令：逐个子命令检查
  // 防止 "echo hello && rm -rf /" 绕过 Bash(rm:*) deny 规则
  const subcommands = splitCommand(command)
  for (const subcmd of subcommands) {
    const subResult = checkSubcommandAgainstRules(subcmd, toolPermissionContext)
    if (subResult.behavior === 'deny' || subResult.behavior === 'ask') {
      return subResult
    }
  }
  
  // 没有显式阻止 → 自动允许
  return {
    behavior: 'allow',
    decisionReason: {
      type: 'sandbox',
      reason: 'Command will run in sandbox with restricted filesystem/network access',
    },
  }
}
```

### 7.2 排除命令

```typescript
export function getExcludedCommands(): string[] {
  const settings = getSettings_DEPRECATED()
  return settings?.sandbox?.excludedCommands ?? []
}
```

排除的命令即使在沙盒中运行也需要用户审批。

### 7.3 环境变量绕过防护

```typescript
// BINARY_HIJACK_VARS 检测（防止 LD_PRELOAD 等劫持）
export const BINARY_HIJACK_VARS = /^(LD_|DYLD_|PATH$)/

// excludedCommands 匹配时剥离环境变量
export function stripAllLeadingEnvVars(
  command: string,
  blocklist?: RegExp,  // BINARY_HIJACK_VARS
): string {
  // ... 剥离逻辑
}
```

## 8. 安全加固

### 8.1 Settings 文件保护

```typescript
// 禁止写入 settings.json（防止沙盒逃逸）
const settingsPaths = SETTING_SOURCES.map(source =>
  getSettingsFilePathForSource(source)
).filter((p): p is string => p !== undefined)
denyWrite.push(...settingsPaths)
denyWrite.push(getManagedSettingsDropInDir())
```

### 8.2 .claude/skills 保护

```typescript
// 与 .claude/commands 同级保护
denyWrite.push(resolve(originalCwd, '.claude', 'skills'))
if (cwd !== originalCwd) {
  denyWrite.push(resolve(cwd, '.claude', 'skills'))
}
```

### 8.3 裸 Git 仓库 RCE 防护

```typescript
// 检测并禁止写入裸 Git 仓库文件
const bareGitRepoFiles = ['HEAD', 'objects', 'refs', 'hooks', 'config']
for (const dir of [originalCwd, cwd]) {
  for (const gitFile of bareGitRepoFiles) {
    const p = resolve(dir, gitFile)
    try {
      statSync(p)
      denyWrite.push(p)  // 存在 → 只读绑定
    } catch {
      bareGitRepoScrubPaths.push(p)  // 不存在 → 命令后擦除
    }
  }
}

// 命令后擦除
function scrubBareGitRepoFiles(): void {
  for (const p of bareGitRepoScrubPaths) {
    try {
      rmSync(p, { recursive: true })
      logForDebugging(`[Sandbox] scrubbed planted bare-repo file: ${p}`)
    } catch {
      // ENOENT 是预期情况
    }
  }
}
```

### 8.4 Linux Glob 模式警告

```typescript
function getLinuxGlobPatternWarnings(): string[] {
  const platform = getPlatform()
  if (platform !== 'linux' && platform !== 'wsl') return []
  
  const settings = getSettings_DEPRECATED()
  if (!settings?.sandbox?.enabled) return []
  
  const warnings: string[] = []
  const hasGlobs = (path: string): boolean => {
    const stripped = path.replace(/\/\*\*$/, '')
    return /[*?[\]]/.test(stripped)
  }
  
  for (const ruleString of [
    ...(settings?.permissions?.allow || []),
    ...(settings?.permissions?.deny || []),
  ]) {
    const rule = permissionRuleValueFromString(ruleString)
    if (
      (rule.toolName === FILE_EDIT_TOOL_NAME ||
       rule.toolName === FILE_READ_TOOL_NAME) &&
      rule.ruleContent &&
      hasGlobs(rule.ruleContent)
    ) {
      warnings.push(ruleString)
    }
  }
  
  return warnings
}
```

bubblewrap 不支持 glob 模式，仅匹配精确路径。

## 9. 设计思想

### 9.1 防御深度

```
权限规则 → Sandbox 文件系统 → Sandbox 网络 → 操作系统
```

多层隔离确保单层绕过不会导致安全问题。

### 9.2 配置一致性

权限规则和 sandbox.filesystem 配置自动同步，避免配置分裂。

### 9.3 热更新支持

设置变化时自动刷新沙盒配置，无需重启。

### 9.4 保守默认

- 默认禁用沙盒（用户显式启用）
- 依赖缺失时给出明确错误
- 不支持的平台静默返回 false

### 9.5 Git 工作树支持

自动检测工作树并允许主仓库写入：

```typescript
async function detectWorktreeMainRepoPath(cwd: string): Promise<string | null> {
  const gitPath = join(cwd, '.git')
  try {
    const gitContent = await readFile(gitPath, { encoding: 'utf8' })
    const gitdirMatch = gitContent.match(/^gitdir:\s*(.+)$/m)
    if (!gitdirMatch?.[1]) return null
    
    const gitdir = resolve(cwd, gitdirMatch[1].trim())
    const marker = `${sep}.git${sep}worktrees${sep}`
    const markerIndex = gitdir.lastIndexOf(marker)
    if (markerIndex > 0) {
      return gitdir.substring(0, markerIndex)
    }
    return null
  } catch {
    return null
  }
}
```

## 10. 总结

Sandbox 集成的特点：

1. **OS 级隔离**: bubblewrap 提供文件系统/网络/进程隔离
2. **配置转换**: 权限规则自动转换为沙盒配置
3. **热更新**: 设置变化实时生效
4. **平台兼容**: macOS/Linux/WSL2 支持
5. **Git 友好**: 工作树、裸仓库特殊处理
6. **防御深度**: 多层保护，保守默认
