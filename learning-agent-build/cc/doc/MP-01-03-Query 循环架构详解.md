# MP-01-03 - Query 循环架构详解

## 1. 概述

Query 循环是 Claude Code 的核心引擎，负责编排从 API 调用到工具执行的完整流程。这是一个多阶段、支持自动恢复和降级的高级循环系统。

**核心文件**:
- `src/query.ts` (约 1700 行)
- `src/services/api/claude.ts` (API 调用)
- `src/services/tools/StreamingToolExecutor.ts` (流式工具执行)
- `src/services/tools/toolOrchestration.ts` (工具编排)

---

## 2. 架构设计

### 2.1 Query 循环的三层架构

```
┌─────────────────────────────────────────────────────────────┐
│                     query() 生成器                           │
│  (顶层包装器，处理命令生命周期通知)                          │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  queryLoop() 主循环                          │
│  (状态管理，上下文处理，自动压缩)                            │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  State (跨迭代状态)                                    │ │
│  │  - messages: Message[]                                │ │
│  │  - toolUseContext: ToolUseContext                     │ │
│  │  - autoCompactTracking: AutoCompactTrackingState      │ │
│  │  - maxOutputTokensRecoveryCount: number               │ │
│  │  - pendingToolUseSummary: Promise<...>                │ │
│  │  └───────────────────────────────────────────────────│ │
│  └───────────────────────────────────────────────────────┘ │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    流式 API 循环                              │
│  (deps.callModel, 流式处理，工具收集)                        │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  for await (const message of deps.callModel({...}))   │ │
│  │    - yield message (流式输出)                          │ │
│  │    - 收集 tool_use 块                                  │ │
│  │    - 添加到 StreamingToolExecutor                     │ │
│  └───────────────────────────────────────────────────────┘ │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  工具执行阶段                                 │
│  (StreamingToolExecutor / runTools)                         │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  - 并发安全工具 → 并行执行                             │ │
│  │  - 非并发安全工具 → 串行执行                           │ │
│  │  - 结果收集与产出                                      │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 函数签名

```typescript
// src/query.ts:181-199

export type QueryParams = {
  messages: Message[]                    // 当前消息历史
  systemPrompt: SystemPrompt             // 系统提示
  userContext: { [k: string]: string }   // 用户上下文
  systemContext: { [k: string]: string } // 系统上下文
  canUseTool: CanUseToolFn               // 工具权限检查
  toolUseContext: ToolUseContext         // 工具使用上下文
  fallbackModel?: string                 // 降级模型
  querySource: QuerySource               // 查询来源 (repl_main_thread, agent, etc.)
  maxOutputTokensOverride?: number       // 最大输出 token 覆盖
  maxTurns?: number                      // 最大轮次限制
  skipCacheWrite?: boolean               // 跳过缓存写入
  taskBudget?: { total: number }         // 任务预算
  deps?: QueryDeps                       // 依赖注入 (用于测试)
}

export async function* query(
  params: QueryParams,
): AsyncGenerator<
  | StreamEvent
  | RequestStartEvent
  | Message
  | TombstoneMessage
  | ToolUseSummaryMessage,
  Terminal
>
```

---

## 3. Query 循环详细流程

### 3.1 顶层包装器

**文件**: `src/query.ts:219-239`

```typescript
export async function* query(
  params: QueryParams,
): AsyncGenerator<..., Terminal> {
  const consumedCommandUuids: string[] = []
  
  // 调用主循环
  const terminal = yield* queryLoop(params, consumedCommandUuids)
  
  // 仅当 queryLoop 正常返回时执行
  // 跳过 throw (错误传播) 和 .return() (Return completion)
  // 这与 print.ts 的 drainCommandQueue 信号相同
  for (const uuid of consumedCommandUuids) {
    notifyCommandLifecycle(uuid, 'completed')
  }
  
  return terminal
}
```

**设计思想**：
- 分离关注点：`query` 处理命令生命周期，`queryLoop` 处理核心逻辑
- 命令 UUID 追踪：记录本 turn 消耗的命令，完成后通知
- 异常安全：错误时跳过通知，避免错误标记为完成

---

### 3.2 状态初始化

**文件**: `src/query.ts:268-280`

```typescript
// 跨迭代可变状态
let state: State = {
  messages: params.messages,
  toolUseContext: params.toolUseContext,
  maxOutputTokensOverride: params.maxOutputTokensOverride,
  autoCompactTracking: undefined,         // 自动压缩追踪
  stopHookActive: undefined,              // Stop Hook 激活标记
  maxOutputTokensRecoveryCount: 0,        // 最大输出 token 恢复计数
  hasAttemptedReactiveCompact: false,     // 是否尝试过响应式压缩
  turnCount: 1,                           // 轮次计数
  pendingToolUseSummary: undefined,       // 待处理的工具使用摘要
  transition: undefined,                  // 上一轮继续的原因
}

// Token 预算追踪器 (可选)
const budgetTracker = feature('TOKEN_BUDGET') 
  ? createBudgetTracker() 
  : null
```

---

### 3.3 主循环结构

**文件**: `src/query.ts:307-322`

```typescript
// eslint-disable-next-line no-constant-condition
while (true) {
  // 每轮迭代开始时解构状态
  // toolUseContext 会在迭代中重新赋值，其他为只读
  let { toolUseContext } = state
  const {
    messages,
    autoCompactTracking,
    maxOutputTokensRecoveryCount,
    hasAttemptedReactiveCompact,
    maxOutputTokensOverride,
    pendingToolUseSummary,
    stopHookActive,
    turnCount,
  } = state
  
  // ========== 技能发现预取 ==========
  // 每轮执行（使用 findWritePivot guard 在非写迭代提前返回）
  const pendingSkillPrefetch = skillPrefetch?.startSkillDiscoveryPrefetch(
    null, messages, toolUseContext,
  )
  
  yield { type: 'stream_request_start' }
  
  queryCheckpoint('query_fn_entry')
  
  // ...
}
```

**为什么使用 `while(true)`**：
- 工具调用可能触发更多工具调用
- 循环持续直到模型不再调用工具
- 通过 `return { reason: '...' }` 退出

---

### 3.4 查询追踪与链 ID

**文件**: `src/query.ts:346-363`

```typescript
// ========== 初始化或递增查询链追踪 ==========
const queryTracking = toolUseContext.queryTracking
  ? {
      chainId: toolUseContext.queryTracking.chainId,
      depth: toolUseContext.queryTracking.depth + 1,  // 深度 +1
    }
  : {
      chainId: deps.uuid(),  // 新链生成 UUID
      depth: 0,
    }

const queryChainIdForAnalytics = queryTracking.chainId

toolUseContext = {
  ...toolUseContext,
  queryTracking,
}
```

**用途**：
- `chainId`: 标识同一个用户请求触发的所有查询
- `depth`: 追踪嵌套深度（主查询=0，子 agent=1，etc.）
- 用于遥测和调试

---

### 3.5 上下文预处理流水线

这是 Query 循环最复杂的部分，按顺序执行多种上下文优化：

```typescript
let messagesForQuery = [...getMessagesAfterCompactBoundary(messages)]

// ========== Step 1: Tool Result 预算限制 ==========
// 在 microcompact 之前执行 — 缓存的 MC 按 tool_use_id 操作
messagesForQuery = await applyToolResultBudget(
  messagesForQuery,
  toolUseContext.contentReplacementState,
  persistReplacements ? records => 
    recordContentReplacement(records, toolUseContext.agentId) 
  : undefined,
  new Set(
    toolUseContext.options.tools
      .filter(t => !Number.isFinite(t.maxResultSizeChars))
      .map(t => t.name)
  ),
)

// ========== Step 2: Snip (历史剪除) ==========
let snipTokensFreed = 0
if (feature('HISTORY_SNIP')) {
  queryCheckpoint('query_snip_start')
  const snipResult = snipModule!.snipCompactIfNeeded(messagesForQuery)
  messagesForQuery = snipResult.messages
  snipTokensFreed = snipTokensFreed
  if (snipResult.boundaryMessage) {
    yield snipResult.boundaryMessage
  }
  queryCheckpoint('query_snip_end')
}

// ========== Step 3: Microcompact (微压缩) ==========
queryCheckpoint('query_microcompact_start')
const microcompactResult = await deps.microcompact(
  messagesForQuery,
  toolUseContext,
  querySource,
)
messagesForQuery = microcompactResult.messages
const pendingCacheEdits = feature('CACHED_MICROCOMPACT')
  ? microcompactResult.compactionInfo?.pendingCacheEdits
  : undefined
queryCheckpoint('query_microcompact_end')

// ========== Step 4: Context Collapse (上下文折叠) ==========
if (feature('CONTEXT_COLLAPSE') && contextCollapse) {
  const collapseResult = await contextCollapse.applyCollapsesIfNeeded(
    messagesForQuery,
    toolUseContext,
    querySource,
  )
  messagesForQuery = collapseResult.messages
}

// ========== Step 5: Auto Compact (自动压缩) ==========
queryCheckpoint('query_autocompact_start')
const { compactionResult, consecutiveFailures } = await deps.autocompact(
  messagesForQuery,
  toolUseContext,
  {
    systemPrompt, userContext, systemContext, toolUseContext,
    forkContextMessages: messagesForQuery,
  },
  querySource,
  tracking,
  snipTokensFreed,
)
queryCheckpoint('query_autocompact_end')
```

### 3.6 预处理顺序 rationale

```
顺序：ToolResult Budget → Snip → Microcompact → Collapse → AutoCompact

为什么这个顺序？

1. ToolResult Budget (最先)
   - 减少 tool_result 内容大小
   - 为后续压缩腾出空间
   - 不影响压缩算法 (按 tool_use_id 操作)

2. Snip (第二)
   - 移除旧的消息对
   - 快速释放 token
   - snipTokensFreed 传递给 autocompact 用于阈值计算

3. Microcompact (第三)
   - 基于缓存编辑的快速压缩
   - 删除已修改的文件内容
   - 在 autocompact 之前执行，可能避免完整压缩

4. Context Collapse (第四)
   - 如果 Collapse 能让上下文低于 autocompact 阈值
   - 则 autocompact 变成 no-op
   - 保留细粒度上下文而非单一摘要

5. AutoCompact (最后)
   - 完整的对话摘要
   - 在其他优化都无效时执行
   - 最昂贵但最有效
```

---

### 3.7 压缩后处理

**文件**: `src/query.ts:470-543`

```typescript
if (compactionResult) {
  const {
    preCompactTokenCount,
    postCompactTokenCount,
    truePostCompactTokenCount,
    compactionUsage,
  } = compactionResult

  // ========== 遥测记录 ==========
  logEvent('tengu_auto_compact_succeeded', {
    originalMessageCount: messages.length,
    compactedMessageCount: compactionResult.summaryMessages.length + 
                           compactionResult.attachments.length + 
                           compactionResult.hookResults.length,
    preCompactTokenCount,
    postCompactTokenCount,
    truePostCompactTokenCount,
    compactionInputTokens: compactionUsage?.input_tokens,
    compactionOutputTokens: compactionUsage?.output_tokens,
    compactionCacheReadTokens: compactionUsage?.cache_read_input_tokens ?? 0,
    compactionCacheCreationTokens: compactionUsage?.cache_creation_input_tokens ?? 0,
    compactionTotalTokens: ...,
    queryChainId: queryChainIdForAnalytics,
    queryDepth: queryTracking.depth,
  })

  // ========== Task Budget 追踪 ==========
  if (params.taskBudget) {
    const preCompactContext = finalContextTokensFromLastResponse(messagesForQuery)
    taskBudgetRemaining = Math.max(
      0,
      (taskBudgetRemaining ?? params.taskBudget.total) - preCompactContext,
    )
  }

  // ========== 重置压缩追踪 ==========
  tracking = {
    compacted: true,
    turnId: deps.uuid(),
    turnCounter: 0,
    consecutiveFailures: 0,
  }

  // ========== 构建并产出压缩后消息 ==========
  const postCompactMessages = buildPostCompactMessages(compactionResult)
  for (const message of postCompactMessages) {
    yield message
  }

  // 继续当前查询，使用压缩后的消息
  messagesForQuery = postCompactMessages
} else if (consecutiveFailures !== undefined) {
  // 自动压缩失败，传播失败计数用于熔断器
  tracking = {
    ...(tracking ?? { compacted: false, turnId: '', turnCounter: 0 }),
    consecutiveFailures,
  }
}
```

---

## 4. API 调用循环

### 4.1 设置阶段

**文件**: `src/query.ts:560-590`

```typescript
queryCheckpoint('query_setup_start')

// ========== 创建流式工具执行器 ==========
const useStreamingToolExecution = config.gates.streamingToolExecution
let streamingToolExecutor = useStreamingToolExecution
  ? new StreamingToolExecutor(
      toolUseContext.options.tools,
      canUseTool,
      toolUseContext,
    )
  : null

// ========== 获取当前模型 ==========
const appState = toolUseContext.getAppState()
const permissionMode = appState.toolPermissionContext.mode
let currentModel = getRuntimeMainLoopModel({
  permissionMode,
  mainLoopModel: toolUseContext.options.mainLoopModel,
  exceeds200kTokens:
    permissionMode === 'plan' &&
    doesMostRecentAssistantMessageExceed200k(messagesForQuery),
})

queryCheckpoint('query_setup_end')

// ========== 创建 Dump Prompts 包装器 ==========
// 每个查询会话只创建一次，避免内存泄漏
// 每次调用 createDumpPromptsFetch 会创建闭包捕获请求体 (~700KB)
// 只创建一次意味着只保留最新请求体 (~500MB → ~700KB)
const dumpPromptsFetch = config.gates.isAnt
  ? createDumpPromptsFetch(toolUseContext.agentId ?? config.sessionId)
  : undefined
```

---

### 4.2 Token 预算阻塞检查

**文件**: `src/query.ts:592-648`

```typescript
// ========== 阻塞限制检查 ==========
// 当自动压缩关闭时生效
// 为 /compact 手动压缩保留空间

// 跳过检查的情况：
// 1. 刚执行完压缩 (结果已验证低于阈值)
// 2. querySource 是 compact/session_memory (forked agent，会死锁)
// 3. Reactive compact 启用且允许自动压缩 (抢占在 API 前返回)
// 4. Context Collapse 启用 (它自己会处理恢复)

let collapseOwnsIt = false
if (feature('CONTEXT_COLLAPSE')) {
  collapseOwnsIt =
    (contextCollapse?.isContextCollapseEnabled() ?? false) &&
    isAutoCompactEnabled()
}

const mediaRecoveryEnabled = reactiveCompact?.isReactiveCompactEnabled() ?? false

if (
  !compactionResult &&
  querySource !== 'compact' &&
  querySource !== 'session_memory' &&
  !(reactiveCompact?.isReactiveCompactEnabled() && isAutoCompactEnabled()) &&
  !collapseOwnsIt
) {
  const { isAtBlockingLimit } = calculateTokenWarningState(
    tokenCountWithEstimation(messagesForQuery) - snipTokensFreed,
    toolUseContext.options.mainLoopModel,
  )
  
  if (isAtBlockingLimit) {
    yield createAssistantAPIErrorMessage({
      content: PROMPT_TOO_LONG_ERROR_MESSAGE,
      error: 'invalid_request',
    })
    return { reason: 'blocking_limit' }
  }
}
```

**阻塞阈值**：
```typescript
// src/services/compact/autoCompact.ts:65

export const MANUAL_COMPACT_BUFFER_TOKENS = 3_000

// 阻塞限制 = 有效上下文窗口 - 3000 tokens
// 为用户手动执行 /compact 保留空间
```

---

### 4.3 流式 API 调用

**文件**: `src/query.ts:654-863`

```typescript
let attemptWithFallback = true

try {
  while (attemptWithFallback) {
    attemptWithFallback = false
    
    try {
      let streamingFallbackOccured = false
      
      queryCheckpoint('query_api_streaming_start')
      
      // ========== 调用模型 API ==========
      for await (const message of deps.callModel({
        messages: prependUserContext(messagesForQuery, userContext),
        systemPrompt: fullSystemPrompt,
        thinkingConfig: toolUseContext.options.thinkingConfig,
        tools: toolUseContext.options.tools,
        signal: toolUseContext.abortController.signal,
        options: {
          async getToolPermissionContext() {
            const appState = toolUseContext.getAppState()
            return appState.toolPermissionContext
          },
          model: currentModel,
          ...(config.gates.fastModeEnabled && {
            fastMode: appState.fastMode,
          }),
          toolChoice: undefined,
          isNonInteractiveSession: toolUseContext.options.isNonInteractiveSession,
          fallbackModel,
          onStreamingFallback: () => {
            streamingFallbackOccured = true
          },
          querySource,
          agents: toolUseContext.options.agentDefinitions.activeAgents,
          allowedAgentTypes: toolUseContext.options.agentDefinitions.allowedAgentTypes,
          hasAppendSystemPrompt: !!toolUseContext.options.appendSystemPrompt,
          maxOutputTokensOverride,
          fetchOverride: dumpPromptsFetch,
          mcpTools: appState.mcp.tools,
          hasPendingMcpServers: appState.mcp.clients.some(c => c.type === 'pending'),
          queryTracking,
          effortValue: appState.effortValue,
          advisorModel: appState.advisorModel,
          skipCacheWrite,
          agentId: toolUseContext.agentId,
          addNotification: toolUseContext.addNotification,
          ...(params.taskBudget && {
            taskBudget: {
              total: params.taskBudget.total,
              ...(taskBudgetRemaining !== undefined && {
                remaining: taskBudgetRemaining,
              }),
            },
          }),
        },
      })) {
        
        // ========== 处理流式降级 ==========
        if (streamingFallbackOccured) {
          // 产出 tombstone 移除孤立消息
          for (const msg of assistantMessages) {
            yield { type: 'tombstone' as const, message: msg }
          }
          logEvent('tengu_orphaned_messages_tombstoned', {
            orphanedMessageCount: assistantMessages.length,
            queryChainId: queryChainIdForAnalytics,
            queryDepth: queryTracking.depth,
          })

          // 清空收集器
          assistantMessages.length = 0
          toolResults.length = 0
          toolUseBlocks.length = 0
          needsFollowUp = false

          // 丢弃失败的流式尝试结果，创建新的执行器
          if (streamingToolExecutor) {
            streamingToolExecutor.discard()
            streamingToolExecutor = new StreamingToolExecutor(
              toolUseContext.options.tools,
              canUseTool,
              toolUseContext,
            )
          }
        }
        
        // ========== 回填工具输入 (Observable Input) ==========
        // 在产出前将 observable 输入字段回填到克隆消息
        // 原始消息保持不变 (用于 prompt caching)
        let yieldMessage: typeof message = message
        if (message.type === 'assistant') {
          let clonedContent: typeof message.message.content | undefined
          for (let i = 0; i < message.message.content.length; i++) {
            const block = message.message.content[i]!
            if (
              block.type === 'tool_use' &&
              typeof block.input === 'object' &&
              block.input !== null
            ) {
              const tool = findToolByName(toolUseContext.options.tools, block.name)
              if (tool?.backfillObservableInput) {
                const originalInput = block.input as Record<string, unknown>
                const inputCopy = { ...originalInput }
                tool.backfillObservableInput(inputCopy)
                
                // 只有在添加（而非覆盖）字段时才克隆
                const addedFields = Object.keys(inputCopy).some(k => !(k in originalInput))
                if (addedFields) {
                  clonedContent ??= [...message.message.content]
                  clonedContent[i] = { ...block, input: inputCopy }
                }
              }
            }
          }
          if (clonedContent) {
            yieldMessage = {
              ...message,
              message: { ...message.message, content: clonedContent },
            }
          }
        }
        
        // ========== 扣留可恢复错误 ==========
        // (prompt-too-long, max-output-tokens)
        // 直到知道恢复是否能成功
        let withheld = false
        if (feature('CONTEXT_COLLAPSE')) {
          if (contextCollapse?.isWithheldPromptTooLong(message, isPromptTooLongMessage, querySource)) {
            withheld = true
          }
        }
        if (reactiveCompact?.isWithheldPromptTooLong(message)) {
          withheld = true
        }
        if (mediaRecoveryEnabled && reactiveCompact?.isWithheldMediaSizeError(message)) {
          withheld = true
        }
        if (isWithheldMaxOutputTokens(message)) {
          withheld = true
        }
        if (!withheld) {
          yield yieldMessage
        }
        
        // ========== 收集 Assistant 消息和工具调用 ==========
        if (message.type === 'assistant') {
          assistantMessages.push(message)

          const msgToolUseBlocks = message.message.content.filter(
            content => content.type === 'tool_use',
          ) as ToolUseBlock[]
          
          if (msgToolUseBlocks.length > 0) {
            toolUseBlocks.push(...msgToolUseBlocks)
            needsFollowUp = true  // 需要执行工具
          }

          // 添加到流式执行器
          if (streamingToolExecutor && !toolUseContext.abortController.signal.aborted) {
            for (const toolBlock of msgToolUseBlocks) {
              streamingToolExecutor.addTool(toolBlock, message)
            }
          }
        }

        // ========== 产出已完成的工具结果 ==========
        if (streamingToolExecutor && !toolUseContext.abortController.signal.aborted) {
          for (const result of streamingToolExecutor.getCompletedResults()) {
            if (result.message) {
              yield result.message
              toolResults.push(
                ...normalizeMessagesForAPI([result.message], toolUseContext.options.tools)
                  .filter(_ => _.type === 'user'),
              )
            }
          }
        }
      }
      
      queryCheckpoint('query_api_streaming_end')
      
      // ========== 产出 Microcompact 边界消息 ==========
      if (feature('CACHED_MICROCOMPACT') && pendingCacheEdits) {
        const lastAssistant = assistantMessages.at(-1)
        const usage = lastAssistant?.message.usage
        const cumulativeDeleted = usage
          ? ((usage as unknown as Record<string, number>).cache_deleted_input_tokens ?? 0)
          : 0
        const deletedTokens = Math.max(0, cumulativeDeleted - pendingCacheEdits.baselineCacheDeletedTokens)
        if (deletedTokens > 0) {
          yield createMicrocompactBoundaryMessage(
            pendingCacheEdits.trigger,
            0,
            deletedTokens,
            pendingCacheEdits.deletedToolIds,
            [],
          )
        }
      }
      
    } catch (innerError) {
      // ========== 模型降级处理 ==========
      if (innerError instanceof FallbackTriggeredError && fallbackModel) {
        currentModel = fallbackModel
        attemptWithFallback = true

        // 清空消息，产出缺失的工具结果
        yield* yieldMissingToolResultBlocks(assistantMessages, 'Model fallback triggered')
        assistantMessages.length = 0
        toolResults.length = 0
        toolUseBlocks.length = 0
        needsFollowUp = false

        // 丢弃失败尝试的结果
        if (streamingToolExecutor) {
          streamingToolExecutor.discard()
          streamingToolExecutor = new StreamingToolExecutor(
            toolUseContext.options.tools,
            canUseTool,
            toolUseContext,
          )
        }

        toolUseContext.options.mainLoopModel = fallbackModel

        // 降级前剥离签名块 (thinking 签名与模型绑定)
        if (process.env.USER_TYPE === 'ant') {
          messagesForQuery = stripSignatureBlocks(messagesForQuery)
        }

        logEvent('tengu_model_fallback_triggered', {
          original_model: innerError.originalModel,
          fallback_model: fallbackModel,
          entrypoint: 'cli',
          queryChainId: queryChainIdForAnalytics,
          queryDepth: queryTracking.depth,
        })

        yield createSystemMessage(
          `Switched to ${renderModelName(innerError.fallbackModel)} due to high demand for ${renderModelName(innerError.originalModel)}`,
          'warning',
        )

        continue
      }
      throw innerError
    }
  }
} catch (error) {
  // ========== 错误处理 ==========
  logError(error)
  
  const errorMessage = error instanceof Error ? error.message : String(error)
  logEvent('tengu_query_error', {
    assistantMessages: assistantMessages.length,
    toolUses: assistantMessages.flatMap(_ =>
      _.message.content.filter(content => content.type === 'tool_use'),
    ).length,
    queryChainId: queryChainIdForAnalytics,
    queryDepth: queryTracking.depth,
  })

  // 图像大小/调整错误：用户友好消息
  if (error instanceof ImageSizeError || error instanceof ImageResizeError) {
    yield createAssistantAPIErrorMessage({ content: error.message })
    return { reason: 'image_error' }
  }

  // 产出缺失的工具结果
  yield* yieldMissingToolResultBlocks(assistantMessages, errorMessage)

  // 产出实际错误消息
  yield createAssistantAPIErrorMessage({ content: errorMessage })

  logAntError('Query error', error)
  return { reason: 'model_error', error }
}
```

---

## 5. 流式执行与工具执行

### 5.1 StreamingToolExecutor 集成

```typescript
// 创建执行器
const streamingToolExecutor = useStreamingToolExecution
  ? new StreamingToolExecutor(toolDefinitions, canUseTool, toolUseContext)
  : null

// 在流式处理中添加工具
if (message.type === 'assistant') {
  const msgToolUseBlocks = message.message.content.filter(
    content => content.type === 'tool_use',
  ) as ToolUseBlock[]
  
  if (streamingToolExecutor) {
    for (const toolBlock of msgToolUseBlocks) {
      streamingToolExecutor.addTool(toolBlock, message)
    }
  }
}

// 产出已完成的工具结果
if (streamingToolExecutor) {
  for (const result of streamingToolExecutor.getCompletedResults()) {
    if (result.message) {
      yield result.message
    }
  }
}
```

### 5.2 传统 runTools 路径

当 `streamingToolExecution` 禁用时使用：

```typescript
// src/query.ts (工具执行阶段)

const toolUpdates = streamingToolExecutor
  ? streamingToolExecutor.getRemainingResults()
  : runTools(toolUseBlocks, messages, canUseTool, processUserInputContext)

for await (const update of toolUpdates) {
  if (update.message) {
    messages.push(update.message)
    yield update.message
  }
  if (update.error) {
    // 处理工具错误
  }
}
```

---

## 6. 循环继续条件

Query 循环在以下情况继续：

| 条件 | 描述 |
|------|------|
| `needsFollowUp = true` | 有工具调用需要执行 |
| 工具执行后模型可能再次响应 | 工具结果可能触发新的工具调用 |

循环在以下情况终止：

| 终止原因 | 返回值 |
|----------|--------|
| 无工具调用 | `{ reason: 'complete' }` |
| 阻塞限制 | `{ reason: 'blocking_limit' }` |
| 图像错误 | `{ reason: 'image_error' }` |
| 模型错误 | `{ reason: 'model_error', error }` |
| 用户中断 | `{ reason: 'user_interrupted' }` |
| Stop Hook 激活 | `{ reason: 'stop_hook' }` |

---

## 7. 设计思想总结

### 7.1 生成器架构优势

```typescript
export async function* query(...) {
  // 使用 yield* 委托给 queryLoop
  const terminal = yield* queryLoop(params, consumedCommandUuids)
  // 正常返回时处理命令完成通知
  for (const uuid of consumedCommandUuids) {
    notifyCommandLifecycle(uuid, 'completed')
  }
  return terminal
}
```

**优势**：
- 流式输出：实时向客户端推送消息
- 异常传播：错误通过 `throw` 向上传播
- 早期返回：`return` 立即终止循环
- 状态保持：生成器天然保持跨迭代状态

### 7.2 上下文优化层次

```
Token Result Budget → Snip → Microcompact → Collapse → AutoCompact

设计原则：
1. 先快后慢：快速优化 (Snip, MC) 在前，慢速优化 (AC) 在后
2. 先轻后重：轻量操作可能避免重量操作
3. 互相补充：每种优化针对不同场景
```

### 7.3 错误恢复策略

| 错误类型 | 恢复策略 |
|----------|----------|
| Prompt Too Long | Context Collapse / Reactive Compact / AutoCompact |
| Max Output Tokens | 减少输出 token 重试 |
| Model Unavailable | 降级到 fallback 模型 |
| Image Size Error | 用户友好错误消息 |
| User Interrupt |  synthetic 错误 + 清理 |

### 7.4 并发控制

```typescript
// queryGuard 确保同一时间只有一个 query 在执行
queryGuard.reserve()
try {
  await executeUserInput({...})
} finally {
  queryGuard.cancelReservation()
}
```

### 7.5 可观测性

```typescript
// 遥测打点
queryCheckpoint('query_fn_entry')
queryCheckpoint('query_snip_start')
queryCheckpoint('query_microcompact_start')
queryCheckpoint('query_autocompact_start')
queryCheckpoint('query_api_streaming_start')
queryCheckpoint('query_api_streaming_end')

// 事件记录
logEvent('tengu_auto_compact_succeeded', {...})
logEvent('tengu_model_fallback_triggered', {...})
logEvent('tengu_query_error', {...})
```

---

## 8. 与其他模块的交互

```
┌─────────────────────────────────────────────────────────────┐
│                         Query 循环                           │
└───────────────────────────┬─────────────────────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
         ▼                  ▼                  ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  AutoCompact    │ │  Context        │ │  StreamingTool  │
│  - 对话摘要     │ │  Collapse       │ │  Executor       │
│  - 文件恢复     │ │  - 折叠视图     │ │  - 并发控制     │
│  - Skill 恢复   │ │  - Commit 日志  │ │  - 进度追踪     │
└─────────────────┘ └─────────────────┘ └─────────────────┘
         │                  │                  │
         └──────────────────┼──────────────────┘
                            │
                            ▼
                  ┌─────────────────┐
                  │  deps.callModel │
                  │  (API 调用)      │
                  └─────────────────┘
```

---

## 9. 总结

Query 循环是 Claude Code 的核心编排引擎，具有以下特点：

1. **生成器架构**：流式输出，异常安全
2. **多层上下文优化**：5 层递进式优化策略
3. **流式工具执行**：实时产出，并发控制
4. **错误恢复**：多种恢复路径 (降级、压缩、截断)
5. **可观测性**：详细打点和遥测
6. **依赖注入**：便于测试和 Mock

这套设计支撑了从简单对话到复杂多轮工具调用的全场景需求。
