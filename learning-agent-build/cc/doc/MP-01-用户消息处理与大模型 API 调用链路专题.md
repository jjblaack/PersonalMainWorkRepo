# MP-01 - 用户消息处理与大模型 API 调用链路专题

## 1. 概述

本文档详细研究从用户发送 prompt 到最终结果呈现的完整链路，包括消息接收、消息处理、API 调用、工具调用、中间状态管理、Harness 工程等核心机制。

### 1.1 核心流程概览

```
用户输入 → handlePromptSubmit → processUserInput → query 循环 → API 调用 → 工具执行 → 结果呈现
```

### 1.2 关键组件

| 组件 | 文件路径 | 职责 |
|------|----------|------|
| **REPL** | `src/REPL.tsx` | 用户输入入口，命令解析 |
| **handlePromptSubmit** | `src/utils/handlePromptSubmit.ts` | Prompt 提交处理，粘贴内容过滤 |
| **processUserInput** | `src/utils/processUserInput/processUserInput.ts` | 用户输入核心处理，Hook 执行 |
| **query** | `src/query.ts` | 主查询循环，API 调用与工具执行编排 |
| **StreamingToolExecutor** | `src/services/tools/StreamingToolExecutor.ts` | 流式工具执行，并发控制 |
| **toolOrchestration** | `src/services/tools/toolOrchestration.ts` | 工具分区与并发/串行执行 |
| **claude.ts** | `src/services/api/claude.ts` | API 请求构建，消息标准化 |

---

## 2. 用户消息接收与处理

### 2.1 REPL 入口

**文件**: `src/REPL.tsx`

REPL 是用户交互的主要入口，负责：
- 读取用户输入（支持多行、粘贴内容）
- 解析命令（`/help`, `/compact`, `/resume` 等）
- 调用 `handlePromptSubmit` 处理 prompt 提交

```typescript
// REPL.tsx 简化流程
async function handleUserInput(rawInput: string) {
  // 1. 检查是否为 slash 命令
  if (rawInput.startsWith('/')) {
    return await handleSlashCommand(rawInput)
  }
  
  // 2. 处理 prompt 提交
  await handlePromptSubmit({
    input: rawInput,
    pastedContents: capturedPastedContents,
    // ...
  })
}
```

### 2.2 handlePromptSubmit

**文件**: `src/utils/handlePromptSubmit.ts`

职责：
- 过滤未引用的图像粘贴内容
- 构建历史条目
- 调用 `executeUserInput` 执行核心处理

```typescript
export async function handlePromptSubmit(params: HandlePromptSubmitParams) {
  // 1. 解析输入中的引用
  const referencedIds = new Set(parseReferences(input).map(r => r.id))
  
  // 2. 过滤未引用的图像（防止无用内容进入上下文）
  const pastedContents = Object.fromEntries(
    Object.entries(rawPastedContents).filter(
      ([, c]) => c.type !== 'image' || referencedIds.has(c.id)
    )
  )
  
  // 3. 执行用户输入处理
  await executeUserInput({
    input,
    pastedContents,
    // ...
  })
}
```

### 2.3 processUserInput

**文件**: `src/utils/processUserInput/processUserInput.ts`

这是用户输入处理的核心逻辑，执行以下步骤：

```typescript
export async function processUserInput({
  params,
  processUserInputContext,
  mutableMessages,
  // ...
}): Promise<ProcessUserInputBaseResult> {
  
  // ========== Phase 1: 基础处理 ==========
  const result = await processUserInputBase({
    params,
    processUserInputContext,
    mutableMessages,
  })
  
  // ========== Phase 2: 执行 UserPromptSubmit Hooks ==========
  for await (const hookResult of executeUserPromptSubmitHooks(
    params.input,
    processUserInputContext,
  )) {
    // Hook 可以：
    // 1. 抛出阻塞错误（阻止提交）
    // 2. 阻止继续（preventContinuation）
    // 3. 添加额外上下文（additionalContexts）
    
    if (hookResult.blockingError) {
      throw new Error(hookResult.blockingError)
    }
    if (hookResult.preventContinuation) {
      return { /* 提前返回 */ }
    }
    if (hookResult.additionalContexts) {
      // 注入 hook 提供的额外上下文
      result.additionalContexts.push(...hookResult.additionalContexts)
    }
  }
  
  return result
}
```

**processUserInputBase** 执行的具体任务：
1. 将用户输入转换为 `UserMessage`
2. 处理粘贴内容（内联或 hash 外部存储）
3. 记录历史记录
4. 添加到消息队列

---

## 3. Query 循环 - 核心编排

**文件**: `src/query.ts`

这是整个系统的"大脑"，负责编排从 API 调用到工具执行的完整循环。

### 3.1 主循环结构

```typescript
export async function* query(params: QueryParams): AsyncGenerator<SDKMessage> {
  const {
    messages,           // 当前消息历史（包含当前用户输入）
    tools,              // 可用工具列表
    callModel,          // 模型调用函数
    // ...
  } = params
  
  // ========== 初始化阶段 ==========
  // 创建流式工具执行器（如果启用）
  const useStreamingToolExecution = config.gates.streamingToolExecution
    ? new StreamingToolExecutor({
        maxConcurrentToolRuns: getMaxConcurrentToolRuns(),
        canUseTool: params.canUseTool,
        processUserInputContext: params.processUserInputContext,
        onProgress: (progress) => emitProgress(progress),
      })
    : null
  
  // ========== 主循环 ==========
  while (true) {
    const toolUseBlocks: ToolUseBlock[] = []
    
    // --- Step 1: 调用模型 API ---
    for await (const message of callModel({
      messages,
      tools,
      // ...
    })) {
      yield message  // 流式输出给前端
      
      // 收集工具调用
      if (message.type === 'assistant') {
        const msgToolUseBlocks = extractToolUseBlocks(message)
        toolUseBlocks.push(...msgToolUseBlocks)
        
        // 如果是流式执行，将工具添加到执行器
        if (useStreamingToolExecution) {
          useStreamingToolExecution.addTool(msgToolUseBlocks[0], message)
        }
      }
    }
    
    // --- Step 2: 执行工具 ---
    if (toolUseBlocks.length === 0) {
      // 没有工具调用，循环结束
      break
    }
    
    // 获取工具执行结果
    const toolUpdates = useStreamingToolExecution
      ? useStreamingToolExecution.getRemainingResults()
      : runTools(toolUseBlocks, messages, params.canUseTool, ...)
    
    // 产出工具结果
    for await (const update of toolUpdates) {
      if (update.message) {
        messages.push(update.message)  // 添加到历史
        yield update.message
      }
      if (update.error) {
        // 处理工具错误
      }
    }
    
    // --- Step 3: 循环继续 ---
    // 如果有工具执行，继续下一轮对话
  }
}
```

### 3.2 循环设计要点

| 设计点 | 描述 |
|--------|------|
| **while(true)** | 持续循环直到模型不再调用工具 |
| **流式输出** | API 响应和工具结果都实时 yield 给前端 |
| **工具收集** | 每轮 API 响应中的工具调用被收集到 `toolUseBlocks` |
| **流式 vs 传统** | 支持两种工具执行模式，流式支持更好的并发控制 |

---

## 4. 工具编排与执行

### 4.1 StreamingToolExecutor

**文件**: `src/services/tools/StreamingToolExecutor.ts`

负责流式执行工具，支持并发控制和进度跟踪。

```typescript
export class StreamingToolExecutor {
  private tools: QueuedTool[] = []
  private readonly maxConcurrentToolRuns: number
  private readonly canUseTool: CanUseToolFn
  private readonly onProgress: (progress: ToolProgress) => void
  
  // 添加工具到执行队列
  addTool(block: ToolUseBlock, assistantMessage: AssistantMessage): void {
    const isConcurrencySafe = checkConcurrencySafety(block)
    
    this.tools.push({
      id: block.id,
      block,
      status: 'queued',
      isConcurrencySafe,
      assistantMessage,
    })
    
    // 触发队列处理
    void this.processQueue()
  }
  
  // 处理执行队列
  private async processQueue(): Promise<void> {
    const queuedTools = this.tools.filter(t => t.status === 'queued')
    
    for (const tool of queuedTools) {
      // 检查是否可以执行（并发控制）
      if (!this.canExecuteTool(tool.isConcurrencySafe)) {
        continue
      }
      
      tool.status = 'executing'
      
      // 异步执行工具（不阻塞队列）
      this.executeTool(tool)
        .catch(error => tool.error = error)
        .finally(() => tool.status = 'completed')
    }
  }
  
  // 检查工具是否可以执行
  private canExecuteTool(isConcurrencySafe: boolean): boolean {
    const executingTools = this.tools.filter(t => t.status === 'executing')
    
    if (executingTools.length === 0) {
      return true  // 没有正在执行的工具
    }
    
    if (isConcurrencySafe) {
      // 当前工具是并发安全的，检查所有正在执行的工具是否也安全
      return executingTools.every(t => t.isConcurrencySafe)
    }
    
    return false  // 非并发安全工具必须串行执行
  }
  
  // 获取剩余结果（未完成的工具结果）
  getRemainingResults(): AsyncGenerator<ToolUpdate> {
    // 返回尚未产出的工具结果
  }
}
```

### 4.2 并发安全判断

```typescript
function checkConcurrencySafety(block: ToolUseBlock): boolean {
  // 只读工具可以并发执行
  const concurrencySafeTools = new Set([
    FILE_READ_TOOL_NAME,      // 文件读取
    FILE_SEARCH_TOOL_NAME,    // 文件搜索
    GrepToolName,             // Grep 搜索
    GlobToolName,             // Glob 匹配
    // ... 其他只读工具
  ])
  
  return concurrencySafeTools.has(block.name)
}
```

### 4.3 toolOrchestration

**文件**: `src/services/tools/toolOrchestration.ts`

当不使用流式执行时，使用传统的工具编排方式。

```typescript
export async function* runTools(
  toolUseBlocks: ToolUseBlock[],
  messages: Message[],
  canUseTool: CanUseToolFn,
  processUserInputContext: ProcessUserInputContext,
): AsyncGenerator<ToolUpdate> {
  
  // 分区：将工具按并发安全性分组
  for (const { isConcurrencySafe, blocks } of partitionToolCalls(toolUseBlocks)) {
    if (isConcurrencySafe) {
      // 并发执行只读工具
      for await (const update of runToolsConcurrently(
        blocks, canUseTool, processUserInputContext
      )) {
        yield update
      }
    } else {
      // 串行执行非并发安全工具（如 Bash、FileEdit）
      for await (const update of runToolsSerially(
        blocks, canUseTool, processUserInputContext
      )) {
        yield update
      }
    }
  }
}

// 分区逻辑
function partitionToolCalls(toolCalls: ToolUseBlock[]): Array<{
  isConcurrencySafe: boolean
  blocks: ToolUseBlock[]
}> {
  const partitions: Array<{ isConcurrencySafe: boolean; blocks: ToolUseBlock[] }> = []
  
  for (const block of toolCalls) {
    const isSafe = checkConcurrencySafety(block)
    const lastPartition = partitions[partitions.length - 1]
    
    // 如果当前工具的并发安全性与上一个分区相同，合并
    if (lastPartition?.isConcurrencySafe === isSafe) {
      lastPartition.blocks.push(block)
    } else {
      // 否则创建新分区
      partitions.push({ isConcurrencySafe: isSafe, blocks: [block] })
    }
  }
  
  return partitions
}
```

---

## 5. API 调用层

### 5.1 claude.ts - API 请求构建

**文件**: `src/services/api/claude.ts`

负责构建并发送 API 请求到 Anthropic。

```typescript
async function* queryModel({
  messages,
  tools,
  options,
  // ...
}): AsyncGenerator<AssistantMessage> {
  
  // ========== Step 1: 构建工具 Schema ==========
  const toolSchemas = await Promise.all(
    filteredTools.map(tool => toolToAPISchema(tool, {
      model: options.mainLoopModel,
      // ...
    }))
  )
  
  // ========== Step 2: 标准化消息 ==========
  // 将内部消息格式转换为 API 兼容格式
  let messagesForAPI = normalizeMessagesForAPI(messages, filteredTools)
  
  // ========== Step 3: 构建系统 Prompt ==========
  const systemPrompt = buildSystemPrompt({
    tools: filteredTools,
    options,
    // ...
  })
  
  // ========== Step 4: 调用 API ==========
  const client = createAnthropicClient(options)
  
  const stream = client.beta.messages.stream({
    model: options.mainLoopModel,
    max_tokens: getMaxOutputTokensForModel(options.mainLoopModel),
    messages: messagesForAPI,
    system: systemPrompt,
    tools: toolSchemas,
    betas: getRequiredBetas(filteredTools),
  }, {
    // Beta headers for caching, etc.
  })
  
  // ========== Step 5: 流式处理响应 ==========
  for await (const event of stream) {
    if (event.type === 'content_block_delta') {
      // 处理文本/思考块增量
      yieldTextDelta(event.delta.text)
    } else if (event.type === 'content_block_start') {
      // 处理新内容块开始
      if (event.content_block.type === 'tool_use') {
        yieldToolUseStart(event.content_block)
      }
    } else if (event.type === 'content_block_stop') {
      // 处理内容块结束
    } else if (event.type === 'message_delta') {
      // 处理消息 delta（停止原因等）
    }
  }
}
```

### 5.2 消息标准化

```typescript
// src/utils/messages.ts
export function normalizeMessagesForAPI(
  messages: Message[],
  filteredTools: Tool[],
): MessageParam[] {
  // 1. 过滤掉附件消息（attachments 在系统 prompt 中注入）
  // 2. 合并连续的 assistant 消息
  // 3. 确保 user/assistant 交替
  // 4. 处理工具结果引用
  
  const apiMessages: MessageParam[] = []
  
  for (const message of messages) {
    if (message.type === 'attachment') {
      // 跳过附件消息（单独处理）
      continue
    }
    
    // 转换为 API 格式
    const apiMessage = convertToAPIFormat(message)
    apiMessages.push(apiMessage)
  }
  
  return apiMessages
}
```

### 5.3 Beta Headers 与功能开关

```typescript
function getRequiredBetas(tools: Tool[]): string[] {
  const betas: string[] = []
  
  // Prompt caching
  if (feature('PROMPT_CACHING')) {
    betas.push('prompt-caching-2024-07-31')
  }
  
  // Tool-specific betas
  for (const tool of tools) {
    if (tool.requiresBeta) {
      betas.push(tool.requiresBeta)
    }
  }
  
  return betas
}
```

---

## 6. Harness 工程 - AI 控制机制

Harness（约束与编排）工程指的是对 AI 行为进行控制和引导的所有机制。

### 6.1 System Prompt 构建

System Prompt 是控制 AI 行为的第一道防线。

```typescript
function buildSystemPrompt({
  tools,
  options,
  memoryFiles,
  // ...
}): string {
  const parts: string[] = []
  
  // 1. 基础系统指令
  parts.push(BASE_SYSTEM_INSTRUCTION)
  
  // 2. 工具描述
  parts.push(buildToolsSection(tools))
  
  // 3. 记忆文件注入（CLAUDE.md 等）
  parts.push(buildMemorySection(memoryFiles))
  
  // 4. 项目特定指令
  if (options.projectInstructions) {
    parts.push(options.projectInstructions)
  }
  
  // 5. 安全限制
  parts.push(buildSafetySection())
  
  return parts.join('\n\n')
}
```

### 6.2 canUseTool - 工具调用权限控制

```typescript
// hooks/useCanUseTool.ts
export type CanUseToolFn = (
  toolName: string,
  toolInput: unknown,
  context: CanUseToolContext,
) => Promise<CanUseToolResult>

export type CanUseToolResult = {
  behavior: 'allow' | 'deny' | 'ask'
  updatedInput?: unknown  // 可以修改输入
  reason?: string
}

// 实现
export function createCanUseTool(
  mode: PermissionMode,
  approvedTools: Set<string>,
  // ...
): CanUseToolFn {
  return async (toolName, toolInput, context) => {
    // 1. 检查模式（Ask vs Always Allow）
    if (mode === 'alwaysAllow') {
      return { behavior: 'allow' }
    }
    
    // 2. 检查是否是已批准的工具
    if (approvedTools.has(toolName)) {
      return { behavior: 'allow' }
    }
    
    // 3. 检查危险操作
    if (isDangerousTool(toolName, toolInput)) {
      return { behavior: 'ask' }
    }
    
    // 4. 默认允许
    return { behavior: 'allow' }
  }
}
```

### 6.3 工具 Schema 设计

工具 Schema 的设计本身就是一种控制：

```typescript
// 文件读取工具 Schema
const FILE_READ_TOOL_SCHEMA = {
  name: 'Read',
  description: '读取文件内容。使用此工具查看现有文件的内容。',
  input_schema: {
    type: 'object',
    properties: {
      file_path: {
        type: 'string',
        description: '要读取的文件路径（相对或绝对）',
      },
      offset: {
        type: 'integer',
        description: '起始行号（可选，用于大文件的部分读取）',
      },
      limit: {
        type: 'integer',
        description: '最多读取的行数（可选）',
      },
    },
    required: ['file_path'],
  },
}

// 设计要点：
// 1. 明确的参数要求（required）
// 2. 参数约束（offset/limit 用于防止大文件）
// 3. 清晰的描述引导正确使用
```

### 6.4 超时与取消控制

```typescript
// query.ts 中的取消控制
const controller = new AbortController()

// 用户按下 Ctrl+C 时
process.on('SIGINT', () => {
  controller.abort()
  // 清理进行中的工具执行
  streamingToolExecutor.cancelAll()
})

// 工具执行超时
async function executeToolWithTimeout(
  tool: QueuedTool,
  timeoutMs: number = 300_000,  // 5 分钟
): Promise<void> {
  const timeout = setTimeout(() => {
    tool.status = 'timed_out'
    tool.error = new Error('Tool execution timed out')
  }, timeoutMs)
  
  try {
    await executeTool(tool)
  } finally {
    clearTimeout(timeout)
  }
}
```

---

## 7. 中间状态管理

### 7.1 消息状态流转

```
用户输入 → UserMessage → [API 处理] → AssistantMessage → [工具调用] → UserMessage(tool_result) → ...
```

### 7.2 文件状态缓存

**文件**: `src/utils/fileStateCache.ts`

```typescript
// 缓存最近读取的文件内容
type FileStateCache = Map<
  string,  // 文件路径
  {
    content: string
    timestamp: number
    isPartialView?: boolean
  }
>

// 从消息历史中提取读取的文件
export function extractReadFilesFromMessages(
  messages: Message[],
  cwd: string,
): FileStateCache {
  const cache = createFileStateCacheWithSizeLimit(10)
  
  // 第一遍：找到所有 FileReadTool 的调用
  const fileReadToolUseIds = new Map<string, string>()
  
  for (const message of messages) {
    if (message.type === 'assistant') {
      for (const block of message.message.content) {
        if (block.type === 'tool_use' && block.name === FILE_READ_TOOL_NAME) {
          fileReadToolUseIds.set(block.id, block.input.file_path)
        }
      }
    }
  }
  
  // 第二遍：找到对应的工具结果并缓存
  for (const message of messages) {
    if (message.type === 'user') {
      for (const block of message.message.content) {
        if (block.type === 'tool_result') {
          const filePath = fileReadToolUseIds.get(block.tool_use_id)
          if (filePath) {
            cache.set(filePath, {
              content: extractContentFromToolResult(block),
              timestamp: message.timestamp ? new Date(message.timestamp).getTime() : Date.now(),
            })
          }
        }
      }
    }
  }
  
  return cache
}
```

### 7.3 会话持久化

**文件**: `src/utils/sessionStorage.ts`

使用 JSONL 格式存储会话历史：

```typescript
export async function recordTranscript(messages: Message[]): Promise<void> {
  const sessionPath = getSessionFilePath()
  
  // 每条消息作为一行 JSON
  const line = JSON.stringify({
    type: message.type,
    uuid: message.uuid,
    message: message.message,
    parentUuid: message.parentUuid,
    timestamp: message.timestamp,
  })
  
  await appendFile(sessionPath, line + '\n')
}
```

---

## 8. 自动压缩机制

### 8.1 触发条件

**文件**: `src/services/compact/autoCompact.ts`

```typescript
// 阈值计算
const AUTOCOMPACT_BUFFER_TOKENS = 13_000

export function getAutoCompactThreshold(model: string): number {
  const effectiveContextWindow = getEffectiveContextWindowSize(model)
  return effectiveContextWindow - AUTOCOMPACT_BUFFER_TOKENS
}

// 检查是否需要压缩
export async function shouldAutoCompact(
  messages: Message[],
  model: string,
): Promise<boolean> {
  if (!isAutoCompactEnabled()) return false
  
  const tokenCount = tokenCountWithEstimation(messages)
  const threshold = getAutoCompactThreshold(model)
  
  return tokenCount >= threshold
}
```

### 8.2 压缩流程

```typescript
export async function autoCompactIfNeeded(
  messages: Message[],
  toolUseContext: ToolUseContext,
): Promise<{ wasCompacted: boolean }> {
  
  // 1. 检查是否需要压缩
  const shouldCompact = await shouldAutoCompact(messages, model)
  if (!shouldCompact) return { wasCompacted: false }
  
  // 2. 尝试会话记忆压缩（优先）
  const sessionMemoryResult = await trySessionMemoryCompaction(...)
  if (sessionMemoryResult) {
    return { wasCompacted: true, compactionResult: sessionMemoryResult }
  }
  
  // 3. 传统对话压缩
  const compactionResult = await compactConversation(
    messages,
    toolUseContext,
    cacheSafeParams,
  )
  
  return { wasCompacted: true, compactionResult }
}
```

---

## 9. Hook 系统

Hook 系统允许在关键时刻插入自定义逻辑。

### 9.1 Hook 类型

| Hook | 触发时机 | 用途 |
|------|----------|------|
| **SessionStart** | 会话启动 | 注入环境变量、初始化检查 |
| **UserPromptSubmit** | 用户提交 prompt | 验证、修改输入、添加上下文 |
| **PreCompact** | 压缩前 | 保存状态、自定义指令 |
| **PostCompact** | 压缩后 | 恢复状态、清理 |
| **Stop** | 用户停止 | 清理资源、保存状态 |

### 9.2 UserPromptSubmit Hook

```typescript
// src/utils/hooks/userPromptSubmitHook.ts
export async function* executeUserPromptSubmitHooks(
  input: string,
  context: ProcessUserInputContext,
): AsyncGenerator<UserPromptSubmitHookResult> {
  
  const hooks = getUserPromptSubmitHooks()
  
  for (const hook of hooks) {
    try {
      const result = await hook({ input, context })
      yield result
    } catch (error) {
      yield { blockingError: error.message }
      break
    }
  }
}

// Hook 返回结果类型
type UserPromptSubmitHookResult = {
  blockingError?: string      // 阻塞错误
  preventContinuation?: boolean // 阻止继续
  additionalContexts?: string[] // 额外上下文
}
```

---

## 10. 完整流程时序图

```
┌─────────┐    ┌──────────────┐    ┌────────────────┐    ┌───────────┐    ┌──────────┐
│  User   │    │    REPL      │    │ handlePrompt   │    │  process │    │   query  │
│         │    │              │    │ Submit         │    │  UserInput │    │  Loop    │
└────┬────┘    └──────┬───────┘    └───────┬────────┘    └─────┬─────┘    └────┬─────┘
     │                │                     │                   │              │
     │ 1.输入 prompt   │                     │                   │              │
     │───────────────>│                     │                   │              │
     │                │                     │                   │              │
     │                │ 2.调用 handlePrompt │                   │              │
     │                │────────────────────>│                   │              │
     │                │                     │                   │              │
     │                │                     │ 3.过滤粘贴内容    │              │
     │                │                     │ 4.执行 Hooks      │              │
     │                │                     │                   │              │
     │                │                     │ 5.调用 executeUserInput           │
     │                │                     │──────────────────>│              │
     │                │                     │                   │              │
     │                │                     │                   │ 6.创建消息   │
     │                │                     │                   │─────────────>│
     │                │                     │                   │              │
     │                │                     │                   │ 7.调用 API   │
     │                │                     │                   │ (streaming)  │
     │                │                     │                   │              │
     │                │                     │                   │<────────────>│ Anthropic API
     │                │                     │                   │              │
     │                │                     │                   │ 8.流式响应   │
     │                │                     │                   │              │
     │                │                     │                   │ 9.收集工具   │
     │                │                     │                   │              │
     │                │                     │                   │ 10.执行工具  │
     │                │                     │                   │─────────────>│
     │                │                     │                   │              │
     │                │                     │                   │<────────────>│ Tool Execute
     │                │                     │                   │              │
     │                │                     │                   │ 11.工具结果  │
     │                │                     │                   │              │
     │                │                     │                   │ 12.循环判断  │
     │                │                     │                   │ (继续 or 结束)│
     │                │                     │                   │              │
     │                │                     │                   │ 13.产出结果  │
     │                │<──────────────────────────────────────────────────────│
     │                │                     │                   │              │
     │<──────────────────────────────────────────────────────────────────────│
     │ 14.显示响应                                                                    
     │
```

---

## 11. 总结

Claude Code 的消息处理与 API 调用链路是一个多阶段、多层次的复杂系统：

| 阶段 | 核心组件 | 关键职责 |
|------|----------|----------|
| **输入处理** | REPL, handlePromptSubmit | 接收用户输入，过滤粘贴内容 |
| **预处理** | processUserInput | 执行 Hooks，构建消息 |
| **编排** | query 循环 | 协调 API 调用与工具执行 |
| **API** | claude.ts | 构建请求，调用 API |
| **工具执行** | StreamingToolExecutor, toolOrchestration | 并发控制，结果收集 |
| **状态管理** | fileStateCache, sessionStorage | 缓存、持久化 |
| **Harness** | System Prompt, canUseTool | AI 行为控制 |

整个系统的设计原则：
1. **流式处理**：实时输出，降低延迟感
2. **并发安全**：区分只读/写入工具，安全并发
3. **模块化**：各组件职责清晰，易于测试和扩展
4. **容错性**：错误处理、超时控制、取消机制
5. **可观测性**：Hook 系统、进度跟踪、遥测记录

这套架构支撑了 Claude Code 从简单对话到复杂多轮工具调用的全场景需求。
