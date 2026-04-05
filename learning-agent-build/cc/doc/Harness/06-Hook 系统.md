# Harness 工程专题 - 06-Hook 系统

Hook 系统允许开发者在权限决策的关键节点注入自定义逻辑，实现自动化决策、审计、通知等功能。

## 1. Hook 类型

系统定义了以下 Hook 类型：

| Hook 类型 | 触发时机 | 用途 |
|----------|----------|------|
| SessionStart | 会话启动 | 注入环境变量、初始化检查 |
| UserPromptSubmit | 用户提交 prompt | 验证/修改输入、添加上下文 |
| PermissionRequest | 权限请求 | 自动化权限决策 |
| PreCompact | 压缩前 | 保存状态、自定义指令 |
| PostCompact | 压缩后 | 恢复状态、清理 |
| Stop | 用户停止 | 清理资源、保存状态 |

## 2. PermissionRequest Hook

### 2.1 Hook 执行入口

**源码**: `src/utils/permissions/permissions.ts:400-471`

```typescript
async function runPermissionRequestHooksForHeadlessAgent(
  tool: Tool,
  input: { [key: string]: unknown },
  toolUseID: string,
  context: ToolUseContext,
  permissionMode: string | undefined,
  suggestions: PermissionUpdate[] | undefined,
): Promise<PermissionDecision | null> {
  try {
    for await (const hookResult of executePermissionRequestHooks(
      tool.name,
      toolUseID,
      input,
      context,
      permissionMode,
      suggestions,
      context.abortController.signal,
    )) {
      if (!hookResult.permissionRequestResult) {
        continue
      }
      
      const decision = hookResult.permissionRequestResult
      
      if (decision.behavior === 'allow') {
        const finalInput = decision.updatedInput ?? input
        
        // 持久化权限更新
        if (decision.updatedPermissions?.length) {
          persistPermissionUpdates(decision.updatedPermissions)
          context.setAppState(prev => ({
            ...prev,
            toolPermissionContext: applyPermissionUpdates(
              prev.toolPermissionContext,
              decision.updatedPermissions!,
            ),
          }))
        }
        
        return {
          behavior: 'allow',
          updatedInput: finalInput,
          decisionReason: {
            type: 'hook',
            hookName: 'PermissionRequest',
          },
        }
      }
      
      if (decision.behavior === 'deny') {
        if (decision.interrupt) {
          logForDebugging(
            `Hook interrupt: tool=${tool.name} hookMessage=${decision.message}`
          )
          context.abortController.abort()
        }
        
        return {
          behavior: 'deny',
          message: decision.message || 'Permission denied by hook',
          decisionReason: {
            type: 'hook',
            hookName: 'PermissionRequest',
            reason: decision.message,
          },
        }
      }
    }
  } catch (error) {
    logError(
      new Error('PermissionRequest hook failed for headless agent', {
        cause: toError(error),
      })
    )
  }
  
  return null  // 无 Hook 决策 → 自动拒绝
}
```

### 2.2 Hook 执行器

**源码**: `src/utils/hooks.ts`

```typescript
export async function* executePermissionRequestHooks(
  toolName: string,
  toolUseID: string,
  input: Record<string, unknown>,
  context: ToolUseContext,
  permissionMode: string | undefined,
  suggestions: PermissionUpdate[] | undefined,
  signal: AbortSignal,
): AsyncGenerator<HookResult> {
  // 加载并执行所有注册的 PermissionRequest hooks
  const hooks = getRegisteredHooks('PermissionRequest')
  
  for (const hook of hooks) {
    if (signal.aborted) break
    
    try {
      const result = await hook.execute({
        toolName,
        toolUseID,
        input,
        permissionMode,
        suggestions,
        signal,
      })
      
      if (result) {
        yield result
      }
    } catch (error) {
      logError(new Error(`Hook ${hook.name} failed: ${errorMessage(error)}`))
    }
  }
}
```

## 3. UI 交互集成

### 3.1 interactiveHandler

**源码**: `src/hooks/toolPermission/handlers/interactiveHandler.ts`

```typescript
function handleInteractivePermission(
  params: InteractivePermissionParams,
  resolve: (decision: PermissionDecision) => void,
): void {
  const { ctx, description, result, awaitAutomatedChecksBeforeDialog } = params
  
  const { resolve: resolveOnce, isResolved, claim } = createResolveOnce(resolve)
  let userInteracted = false
  
  ctx.pushToQueue({
    assistantMessage: ctx.assistantMessage,
    tool: ctx.tool,
    description,
    input: displayInput,
    toolUseContext: ctx.toolUseContext,
    toolUseID: ctx.toolUseID,
    permissionResult: result,
    
    // 用户开始交互时取消分类器
    onUserInteraction() {
      const GRACE_PERIOD_MS = 200
      if (Date.now() - permissionPromptStartTimeMs < GRACE_PERIOD_MS) {
        return  // 宽限期内忽略交互
      }
      userInteracted = true
      clearClassifierChecking(ctx.toolUseID)
    },
    
    // 允许
    async onAllow(
      updatedInput,
      permissionUpdates: PermissionUpdate[],
      feedback?: string,
      contentBlocks?: ContentBlockParam[],
    ) {
      if (!claim()) return
      
      // 桥接响应（CCR）
      if (bridgeCallbacks && bridgeRequestId) {
        bridgeCallbacks.sendResponse(bridgeRequestId, {
          behavior: 'allow',
          updatedInput,
          updatedPermissions: permissionUpdates,
        })
        bridgeCallbacks.cancelRequest(bridgeRequestId)
      }
      
      resolveOnce(
        await ctx.handleUserAllow(
          updatedInput,
          permissionUpdates,
          feedback,
          permissionPromptStartTimeMs,
          contentBlocks,
          result.decisionReason,
        ),
      )
    },
    
    // 拒绝
    onReject(feedback?: string, contentBlocks?: ContentBlockParam[]) {
      if (!claim()) return
      
      if (bridgeCallbacks && bridgeRequestId) {
        bridgeCallbacks.sendResponse(bridgeRequestId, {
          behavior: 'deny',
          message: feedback ?? 'User denied permission',
        })
        bridgeCallbacks.cancelRequest(bridgeRequestId)
      }
      
      ctx.logDecision(
        {
          decision: 'reject',
          source: { type: 'user_reject', hasFeedback: !!feedback },
        },
        { permissionPromptStartTimeMs },
      )
      resolveOnce(ctx.cancelAndAbort(feedback, undefined, contentBlocks))
    },
    
    // 重新检查权限（用于 CCR 模式切换）
    async recheckPermission() {
      if (isResolved()) return
      
      const freshResult = await hasPermissionsToUseTool(
        ctx.tool,
        ctx.input,
        ctx.toolUseContext,
        ctx.assistantMessage,
        ctx.toolUseID,
      )
      
      if (freshResult.behavior === 'allow') {
        if (!claim()) return
        if (bridgeCallbacks && bridgeRequestId) {
          bridgeCallbacks.cancelRequest(bridgeRequestId)
        }
        ctx.removeFromQueue()
        ctx.logDecision({ decision: 'accept', source: 'config' })
        resolveOnce(ctx.buildAllow(freshResult.updatedInput ?? ctx.input))
      }
    },
  })
  
  // ========== 异步执行 Hook ==========
  if (!awaitAutomatedChecksBeforeDialog) {
    void (async () => {
      if (isResolved()) return
      
      const currentAppState = ctx.toolUseContext.getAppState()
      const hookDecision = await ctx.runHooks(
        currentAppState.toolPermissionContext.mode,
        result.suggestions,
        result.updatedInput,
        permissionPromptStartTimeMs,
      )
      
      if (!hookDecision || !claim()) return
      
      if (bridgeCallbacks && bridgeRequestId) {
        bridgeCallbacks.cancelRequest(bridgeRequestId)
      }
      channelUnsubscribe?.()
      ctx.removeFromQueue()
      resolveOnce(hookDecision)
    })()
  }
  
  // ========== 异步执行 Bash 分类器 ==========
  if (
    feature('BASH_CLASSIFIER') &&
    result.pendingClassifierCheck &&
    ctx.tool.name === BASH_TOOL_NAME &&
    !awaitAutomatedChecksBeforeDialog
  ) {
    setClassifierChecking(ctx.toolUseID)
    void executeAsyncClassifierCheck(...)
  }
}
```

### 3.2 竞争机制

多个决策源并行运行，先到先得：

```
用户交互 ─┐
          │
Hook ─────┼──→ claim() 原子检查 ──→ resolve(决策)
          │
分类器 ───┘
```

```typescript
const { resolve: resolveOnce, isResolved, claim } = createResolveOnce(resolve)

// claim() 是原子检查 - 只有第一个调用者成功
function claim(): boolean {
  if (resolved) return false
  resolved = true
  return true
}
```

## 4. Coordinator 模式

### 4.1 coordinatorHandler

**源码**: `src/hooks/toolPermission/handlers/coordinatorHandler.ts`

```typescript
async function handleCoordinatorPermission(
  params: CoordinatorPermissionParams,
): Promise<PermissionDecision | null> {
  const { ctx, updatedInput, suggestions, permissionMode } = params
  
  try {
    // 1. Hook 优先（快速、本地）
    const hookResult = await ctx.runHooks(
      permissionMode,
      suggestions,
      updatedInput,
    )
    if (hookResult) return hookResult
    
    // 2. 分类器（慢、推理 - 仅 Bash）
    const classifierResult = feature('BASH_CLASSIFIER')
      ? await ctx.tryClassifier?.(params.pendingClassifierCheck, updatedInput)
      : null
    if (classifierResult) return classifierResult
    
  } catch (error) {
    if (error instanceof Error) {
      logError(error)
    } else {
      logError(new Error(`Automated permissions check failed: ${String(error)}`))
    }
  }
  
  // 3. 都没有决策 → 回退到对话框
  return null
}
```

### 4.2 顺序执行

Coordinator 模式下，Hook 和分类器顺序执行：

```
Hook → 有决策？返回 : 分类器 → 有决策？返回 : 对话框
```

## 5. 决策原因记录

### 5.1 Hook 决策原因

```typescript
decisionReason: {
  type: 'hook',
  hookName: 'PermissionRequest',
  reason?: string,  // Hook 提供的拒绝原因
}
```

### 5.2 日志记录

```typescript
ctx.logDecision(
  { decision: 'accept', source: { type: 'hook' } },
  { permissionPromptStartTimeMs },
)
```

## 6. Hook 结果类型

```typescript
type HookResult = {
  // 阻塞性错误（终止执行）
  blockingError?: string
  
  // 阻止继续
  preventContinuation?: boolean
  stopReason?: string
  
  // 权限决策
  permissionRequestResult?: PermissionDecision
  
  // 额外上下文
  additionalContexts?: HookAdditionalContext[]
  
  // 修改输入
  modifiedInput?: Record<string, unknown>
}
```

## 7. 设计思想

### 7.1 非阻塞设计

Hook 异步执行，不阻塞 UI 显示：

```typescript
void (async () => {
  const hookDecision = await ctx.runHooks(...)
  if (!hookDecision || !claim()) return
  resolveOnce(hookDecision)
})()
```

### 7.2 原子竞争

`claim()` 确保只有一个决策源获胜：

```typescript
function claim(): boolean {
  if (resolved) return false
  resolved = true
  return true
}
```

### 7.3 错误隔离

单个 Hook 失败不影响其他 Hook：

```typescript
for (const hook of hooks) {
  try {
    const result = await hook.execute(...)
    if (result) yield result
  } catch (error) {
    logError(new Error(`Hook ${hook.name} failed: ${errorMessage(error)}`))
  }
}
```

### 7.4 取消传播

用户交互时取消后台任务：

```typescript
onUserInteraction() {
  const GRACE_PERIOD_MS = 200
  if (Date.now() - permissionPromptStartTimeMs < GRACE_PERIOD_MS) return
  userInteracted = true
  clearClassifierChecking(ctx.toolUseID)  // 取消分类器
}
```

### 7.5 Grace Period

宽限期防止意外取消：

```typescript
const GRACE_PERIOD_MS = 200
if (Date.now() - permissionPromptStartTimeMs < GRACE_PERIOD_MS) {
  return  // 忽略早期交互
}
```

## 8. Bridge 集成

### 8.1 CCR 桥接

```typescript
// 发送请求到 CCR
bridgeCallbacks.sendRequest(
  bridgeRequestId,
  ctx.tool.name,
  displayInput,
  ctx.toolUseID,
  description,
  result.suggestions,
  result.blockedPath,
)

// 订阅响应
const unsubscribe = bridgeCallbacks.onResponse(
  bridgeRequestId,
  response => {
    if (!claim()) return  // 本地已决策
    signal.removeEventListener('abort', unsubscribe)
    ctx.removeFromQueue()
    
    if (response.behavior === 'allow') {
      resolveOnce(ctx.buildAllow(response.updatedInput ?? displayInput))
    } else {
      resolveOnce(ctx.cancelAndAbort(response.message))
    }
  },
)

signal.addEventListener('abort', unsubscribe, { once: true })
```

### 8.2 Channel 权限中继

```typescript
// 发送到多个 channel（Telegram, iMessage 等）
for (const client of channelClients) {
  void client.client.notification({
    method: CHANNEL_PERMISSION_REQUEST_METHOD,
    params: {
      request_id: channelRequestId,
      tool_name: ctx.tool.name,
      description,
      input_preview: truncateForPreview(displayInput),
    },
  })
}

// 订阅响应
const mapUnsub = channelCallbacks.onResponse(
  channelRequestId,
  response => {
    if (!claim()) return
    channelUnsubscribe?.()
    
    if (response.behavior === 'allow') {
      resolveOnce(ctx.buildAllow(displayInput))
    } else {
      resolveOnce(ctx.cancelAndAbort(`Denied via channel ${response.fromServer}`))
    }
  },
)
```

## 9. 总结

Hook 系统的特点：

1. **灵活扩展**: 在关键节点注入自定义逻辑
2. **非阻塞设计**: 异步执行，不阻塞 UI
3. **原子竞争**: 多个决策源并行，先到先得
4. **错误隔离**: 单个 Hook 失败不影响整体
5. **取消传播**: 用户交互时取消后台任务
6. **Bridge 集成**: 支持 CCR 和 Channel 远程决策
7. **Grace Period**: 防止意外取消分类器
