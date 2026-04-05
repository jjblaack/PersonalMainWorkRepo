# MP-01-04 - StreamingToolExecutor 并发控制详解

## 1. 概述

`StreamingToolExecutor` 是 Claude Code 用于流式执行工具的核心组件，支持并发控制和进度追踪。它允许并发安全工具并行执行，同时确保非并发安全工具串行执行。

**核心文件**:
- `src/services/tools/StreamingToolExecutor.ts` (约 450 行)

---

## 2. 架构设计

### 2.1 工具分类

工具根据并发安全性分为两类：

| 类型 | 特征 | 示例 | 执行方式 |
|------|------|------|----------|
| **并发安全** | 只读操作，无副作用 | Read, Glob, Grep, WebFetch | 并行执行 |
| **非并发安全** | 写入操作，有副作用 | Bash, FileEdit, FileWrite | 串行执行 |

### 2.2 执行策略

```
工具调用序列：[Read(A), Read(B), Bash(cmd), Read(C), Edit(file)]

分区结果：
┌─────────────────┬───────────────┬───────────────┐
│ 并发安全批次     │ 非并发安全    │ 并发安全批次   │
│ [Read(A), Read(B)] │ [Bash(cmd)]   │ [Read(C)]      │
│ 并行执行        │ 串行执行      │ 并行执行       │
└─────────────────┴───────────────┴───────────────┘
                  │
                  ▼
         ┌───────────────┐
         │ [Edit(file)]  │
         │ 串行执行      │
         └───────────────┘
```

### 2.3 核心类型定义

**文件**: `src/services/tools/StreamingToolExecutor.ts:14-32`

```typescript
type MessageUpdate = {
  message?: Message
  newContext: ToolUseContext
}

type ToolStatus = 'queued' | 'executing' | 'completed' | 'yielded'

type TrackedTool = {
  id: string
  block: ToolUseBlock
  assistantMessage: AssistantMessage
  status: ToolStatus
  isConcurrencySafe: boolean
  promise?: Promise<void>
  results?: Message[]
  // 进度消息单独存储，立即产出
  pendingProgress: Message[]
  contextModifiers?: Array<(context: ToolUseContext) => ToolUseContext>
}
```

---

## 3. StreamingToolExecutor 类详解

### 3.1 类结构与构造函数

**文件**: `src/services/tools/StreamingToolExecutor.ts:40-62`

```typescript
export class StreamingToolExecutor {
  private tools: TrackedTool[] = []
  private toolUseContext: ToolUseContext
  private hasErrored = false
  private erroredToolDescription = ''
  
  // 兄弟 AbortController
  // 是 toolUseContext.abortController 的子控制器
  // Bash 工具错误时触发，立即杀死兄弟 subprocess
  private siblingAbortController: AbortController
  
  private discarded = false
  // 唤醒 getRemainingResults 的信号
  private progressAvailableResolve?: () => void

  constructor(
    private readonly toolDefinitions: Tools,
    private readonly canUseTool: CanUseToolFn,
    toolUseContext: ToolUseContext,
  ) {
    this.toolUseContext = toolUseContext
    this.siblingAbortController = createChildAbortController(
      toolUseContext.abortController,
    )
  }
}
```

**字段说明**：

| 字段 | 用途 |
|------|------|
| `tools` | 追踪的所有工具 |
| `hasErrored` | 是否有工具出错 |
| `erroredToolDescription` | 出错工具的描述 (用于错误消息) |
| `siblingAbortController` | 级联取消控制器 |
| `discarded` | 是否被丢弃 (流式降级时使用) |

---

### 3.2 addTool - 添加工具到执行队列

**文件**: `src/services/tools/StreamingToolExecutor.ts:76-124`

```typescript
addTool(block: ToolUseBlock, assistantMessage: AssistantMessage): void {
  // ========== 查找工具定义 ==========
  const toolDefinition = findToolByName(this.toolDefinitions, block.name)
  
  if (!toolDefinition) {
    // 工具不存在：立即返回错误结果
    this.tools.push({
      id: block.id,
      block,
      assistantMessage,
      status: 'completed',
      isConcurrencySafe: true,
      pendingProgress: [],
      results: [
        createUserMessage({
          content: [{
            type: 'tool_result',
            content: `<tool_use_error>Error: No such tool available: ${block.name}</tool_use_error>`,
            is_error: true,
            tool_use_id: block.id,
          }],
          toolUseResult: `Error: No such tool available: ${block.name}`,
          sourceToolAssistantUUID: assistantMessage.uuid,
        }),
      ],
    })
    return
  }

  // ========== 并发安全性检查 ==========
  const parsedInput = toolDefinition.inputSchema.safeParse(block.input)
  const isConcurrencySafe = parsedInput?.success
    ? (() => {
        try {
          return Boolean(toolDefinition.isConcurrencySafe(parsedInput.data))
        } catch {
          // isConcurrencySafe 抛出异常 (如 shell-quote 解析失败)
          // 保守处理：视为不并发安全
          return false
        }
      })()
    : false

  // ========== 添加到队列 ==========
  this.tools.push({
    id: block.id,
    block,
    assistantMessage,
    status: 'queued',
    isConcurrencySafe,
    pendingProgress: [],
  })

  // 触发队列处理
  void this.processQueue()
}
```

**并发安全性判断逻辑**：

```typescript
// 工具定义中的 isConcurrencySafe
const toolDefinition = {
  name: 'Read',
  inputSchema: z.object({ file_path: z.string() }),
  isConcurrencySafe: (input) => {
    // 只读工具返回 true
    return true
  },
}

// Bash 工具的并发安全判断
const bashToolDefinition = {
  name: 'Bash',
  inputSchema: z.object({ command: z.string() }),
  isConcurrencySafe: (input) => {
    // 分析命令是否为只读
    const readOnlyCommands = ['ls', 'cat', 'head', 'tail', 'grep', 'find', ...]
    const command = input.command.split(/\s+/)[0]
    return readOnlyCommands.includes(command)
  },
}
```

---

### 3.3 canExecuteTool - 并发控制核心

**文件**: `src/services/tools/StreamingToolExecutor.ts:129-135`

```typescript
private canExecuteTool(isConcurrencySafe: boolean): boolean {
  const executingTools = this.tools.filter(t => t.status === 'executing')
  
  return (
    executingTools.length === 0 ||
    (isConcurrencySafe && executingTools.every(t => t.isConcurrencySafe))
  )
}
```

**判断逻辑**：

```
情况 1: 没有正在执行的工具
→ 可以执行

情况 2: 当前工具是并发安全的
        且所有正在执行的工具也是并发安全的
→ 可以执行

情况 3: 当前工具不是并发安全的
→ 不能执行 (必须等待所有工具完成)

情况 4: 当前工具是并发安全的
        但有非并发安全工具正在执行
→ 不能执行 (必须等待)
```

---

### 3.4 processQueue - 队列处理

**文件**: `src/services/tools/StreamingToolExecutor.ts:140-151`

```typescript
private async processQueue(): Promise<void> {
  for (const tool of this.tools) {
    if (tool.status !== 'queued') continue

    if (this.canExecuteTool(tool.isConcurrencySafe)) {
      // 可以执行：启动工具
      await this.executeTool(tool)
    } else {
      // 不能执行：如果是非并发安全工具，停止处理
      // (必须保持顺序，等待前面的工具完成)
      if (!tool.isConcurrencySafe) break
    }
  }
}
```

**执行流程示例**：

```
队列状态：[Read(A):queued, Read(B):queued, Bash(cmd):queued, Read(C):queued]

Iteration 1:
- Read(A): canExecuteTool(true) → 执行
- Read(B): canExecuteTool(true) → 执行 (Read(A) 是并发安全)
- Bash(cmd): canExecuteTool(false) → 跳过，break

Iteration 2 (Read(A), Read(B) 完成后):
- Bash(cmd): canExecuteTool(false) → 执行 (无正在执行工具)

Iteration 3 (Bash 完成后):
- Read(C): canExecuteTool(true) → 执行
```

---

### 3.5 executeTool - 工具执行

**文件**: `src/services/tools/StreamingToolExecutor.ts:265-400`

```typescript
private async executeTool(tool: TrackedTool): Promise<void> {
  tool.status = 'executing'
  this.toolUseContext.setInProgressToolUseIDs(prev =>
    new Set(prev).add(tool.id),
  )
  this.updateInterruptibleState()

  const messages: Message[] = []
  const contextModifiers: Array<(context: ToolUseContext) => ToolUseContext> = []

  const collectResults = async () => {
    // ========== 检查是否已被取消 ==========
    const initialAbortReason = this.getAbortReason(tool)
    if (initialAbortReason) {
      messages.push(
        this.createSyntheticErrorMessage(
          tool.id,
          initialAbortReason,
          tool.assistantMessage,
        ),
      )
      tool.results = messages
      tool.contextModifiers = contextModifiers
      tool.status = 'completed'
      this.updateInterruptibleState()
      return
    }

    // ========== 创建工具级 AbortController ==========
    // 子控制器，允许 siblingAbortController 杀死运行中的 subprocess
    const toolAbortController = createChildAbortController(
      this.siblingAbortController,
    )
    
    // 监听 abort 事件，向上传播到父控制器
    toolAbortController.signal.addEventListener(
      'abort',
      () => {
        if (
          toolAbortController.signal.reason !== 'sibling_error' &&
          !this.toolUseContext.abortController.signal.aborted &&
          !this.discarded
        ) {
          this.toolUseContext.abortController.abort(
            toolAbortController.signal.reason,
          )
        }
      },
      { once: true },
    )

    // ========== 执行工具 ==========
    const generator = runToolUse(
      tool.block,
      tool.assistantMessage,
      this.canUseTool,
      { ...this.toolUseContext, abortController: toolAbortController },
    )

    // 追踪当前工具是否产生了错误结果
    let thisToolErrored = false

    for await (const update of generator) {
      // 检查是否被兄弟工具错误或用户中断取消
      const abortReason = this.getAbortReason(tool)
      if (abortReason && !thisToolErrored) {
        messages.push(
          this.createSyntheticErrorMessage(
            tool.id,
            abortReason,
            tool.assistantMessage,
          ),
        )
        break
      }

      // 检查结果是否为错误
      const isErrorResult =
        update.message.type === 'user' &&
        Array.isArray(update.message.message.content) &&
        update.message.message.content.some(
          _ => _.type === 'tool_result' && _.is_error === true,
        )

      if (isErrorResult) {
        thisToolErrored = true
        
        // 只有 Bash 错误会取消兄弟工具
        // Read/WebFetch 等是独立的 — 一个失败不应影响其他
        if (tool.block.name === BASH_TOOL_NAME) {
          this.hasErrored = true
          this.erroredToolDescription = this.getToolDescription(tool)
          this.siblingAbortController.abort('sibling_error')
        }
      }

      // 收集消息
      if (update.message) {
        // 进度消息立即产出
        if (update.message.type === 'progress') {
          tool.pendingProgress.push(update.message)
          if (this.progressAvailableResolve) {
            this.progressAvailableResolve()
            this.progressAvailableResolve = undefined
          }
        } else {
          messages.push(update.message)
        }
      }
      
      // 收集上下文修改器
      if (update.contextModifier) {
        contextModifiers.push(update.contextModifier.modifyContext)
      }
    }
    
    tool.results = messages
    tool.contextModifiers = contextModifiers
    tool.status = 'completed'
    this.updateInterruptibleState()

    // 非并发工具应用上下文修改器
    if (!tool.isConcurrencySafe && contextModifiers.length > 0) {
      for (const modifier of contextModifiers) {
        this.toolUseContext = modifier(this.toolUseContext)
      }
    }
  }

  const promise = collectResults()
  tool.promise = promise
}
```

---

### 3.6 错误处理与取消

#### 3.6.1 getAbortReason

**文件**: `src/services/tools/StreamingToolExecutor.ts:210-231`

```typescript
private getAbortReason(
  tool: TrackedTool,
): 'sibling_error' | 'user_interrupted' | 'streaming_fallback' | null {
  // 流式降级
  if (this.discarded) {
    return 'streaming_fallback'
  }
  
  // 兄弟工具错误
  if (this.hasErrored) {
    return 'sibling_error'
  }
  
  // 用户中断
  if (this.toolUseContext.abortController.signal.aborted) {
    if (this.toolUseContext.abortController.signal.reason === 'interrupt') {
      // 检查工具的 interruptBehavior
      if (this.getToolInterruptBehavior(tool) === 'cancel') {
        return 'user_interrupted'
      }
      return null  // 'block' 工具不应被取消
    }
    return 'user_interrupted'
  }
  
  return null
}
```

#### 3.6.2 createSyntheticErrorMessage

**文件**: `src/services/tools/StreamingToolExecutor.ts:153-205`

```typescript
private createSyntheticErrorMessage(
  toolUseId: string,
  reason: 'sibling_error' | 'user_interrupted' | 'streaming_fallback',
  assistantMessage: AssistantMessage,
): Message {
  // 用户中断：使用 REJECT_MESSAGE
  if (reason === 'user_interrupted') {
    return createUserMessage({
      content: [{
        type: 'tool_result',
        content: withMemoryCorrectionHint(REJECT_MESSAGE),
        is_error: true,
        tool_use_id: toolUseId,
      }],
      toolUseResult: 'User rejected tool use',
      sourceToolAssistantUUID: assistantMessage.uuid,
    })
  }
  
  // 流式降级
  if (reason === 'streaming_fallback') {
    return createUserMessage({
      content: [{
        type: 'tool_result',
        content: '<tool_use_error>Error: Streaming fallback - tool execution discarded</tool_use_error>',
        is_error: true,
        tool_use_id: toolUseId,
      }],
      toolUseResult: 'Streaming fallback - tool execution discarded',
      sourceToolAssistantUUID: assistantMessage.uuid,
    })
  }
  
  // 兄弟工具错误
  const desc = this.erroredToolDescription
  const msg = desc
    ? `Cancelled: parallel tool call ${desc} errored`
    : 'Cancelled: parallel tool call errored'
  
  return createUserMessage({
    content: [{
      type: 'tool_result',
      content: `<tool_use_error>${msg}</tool_use_error>`,
      is_error: true,
      tool_use_id: toolUseId,
    }],
    toolUseResult: msg,
    sourceToolAssistantUUID: assistantMessage.uuid,
  })
}
```

---

### 3.7 中断行为

**文件**: `src/services/tools/StreamingToolExecutor.ts:233-260`

```typescript
private getToolInterruptBehavior(tool: TrackedTool): 'cancel' | 'block' {
  const definition = findToolByName(this.toolDefinitions, tool.block.name)
  if (!definition?.interruptBehavior) return 'block'
  try {
    return definition.interruptBehavior()
  } catch {
    return 'block'
  }
}

private updateInterruptibleState(): void {
  const executing = this.tools.filter(t => t.status === 'executing')
  this.toolUseContext.setHasInterruptibleToolInProgress?.(
    executing.length > 0 &&
      executing.every(t => this.getToolInterruptBehavior(t) === 'cancel'),
  )
}
```

**工具的 interruptBehavior**：

```typescript
// SleepTool
const sleepTool = {
  name: 'Sleep',
  interruptBehavior: () => 'cancel',  // 可以取消
}

// BashTool (取决于命令)
const bashTool = {
  name: 'Bash',
  interruptBehavior: () => {
    // 长时间运行的命令可以取消
    if (isLongRunningCommand(command)) return 'cancel'
    return 'block'
  },
}

// FileEditTool
const fileEditTool = {
  name: 'FileEdit',
  interruptBehavior: () => 'block',  // 不能取消，会损坏文件
}
```

---

### 3.8 getCompletedResults / getRemainingResults

**文件**: `src/services/tools/StreamingToolExecutor.ts:401-450`

```typescript
/**
 * 获取已完成工具的结果 (按接收顺序)
 */
*getCompletedResults(): Generator<MessageUpdate> {
  for (const tool of this.tools) {
    if (tool.status === 'completed' || tool.status === 'yielded') {
      // 产出进度消息
      for (const progress of tool.pendingProgress) {
        yield { message: progress, newContext: this.toolUseContext }
      }
      tool.pendingProgress = []
      
      // 产出结果消息
      if (tool.results) {
        for (const message of tool.results) {
          yield { message, newContext: this.toolUseContext }
        }
      }
      tool.status = 'yielded'
    }
  }
}

/**
 * 获取剩余未产出的结果 (用于非流式路径)
 */
async *getRemainingResults(): AsyncGenerator<MessageUpdate> {
  while (true) {
    // 等待所有工具完成
    const pendingTools = this.tools.filter(
      t => t.status !== 'completed' && t.status !== 'yielded',
    )
    
    if (pendingTools.length === 0) break
    
    // 等待下一个工具完成
    await Promise.race(pendingTools.map(t => t.promise))
    
    // 产出已完成的结果
    for (const result of this.getCompletedResults()) {
      yield result
    }
    
    // 有进度可用时唤醒
    if (this.progressAvailableResolve) {
      const promise = new Promise<void>(resolve => {
        this.progressAvailableResolve = resolve
      })
      await promise
    }
  }
}
```

---

## 4. 与 toolOrchestration 对比

### 4.1 StreamingToolExecutor (流式)

```typescript
// 流式执行
const executor = new StreamingToolExecutor(tools, canUseTool, context)

// 工具随到随执行
for (const toolBlock of toolUseBlocks) {
  executor.addTool(toolBlock, assistantMessage)
}

// 实时产出结果
for (const result of executor.getCompletedResults()) {
  yield result.message
}
```

**优势**：
- 工具随到随执行，无需等待所有工具收集完成
- 实时产出进度消息
- 更好的并发控制粒度

### 4.2 runTools (传统)

```typescript
// 传统执行
for await (const update of runTools(toolUseBlocks, messages, canUseTool, context)) {
  yield update.message
}
```

**分区逻辑**：

```typescript
function partitionToolCalls(toolCalls: ToolUseBlock[]): Batch[] {
  return toolCalls.reduce((acc: Batch[], toolUse) => {
    const tool = findToolByName(context.tools, toolUse.name)
    const isConcurrencySafe = tool?.isConcurrencySafe(...) ?? false
    
    if (isConcurrencySafe && acc[acc.length - 1]?.isConcurrencySafe) {
      acc[acc.length - 1]!.blocks.push(toolUse)  // 合并到前一批
    } else {
      acc.push({ isConcurrencySafe, blocks: [toolUse] })  // 新批次
    }
    return acc
  }, [])
}
```

---

## 5. 设计思想总结

### 5.1 并发安全设计原则

```
1. 只读工具可以并发
2. 写入工具必须串行
3. Bash 命令动态判断 (只读命令可并发)
4. 一个 Bash 错误取消所有兄弟工具 (隐式依赖链)
```

### 5.2 AbortController 层次

```
toolUseContext.abortController (父)
    │
    └── siblingAbortController (兄弟级)
            │
            ├── toolAbortController #1 (工具 1)
            ├── toolAbortController #2 (工具 2)
            └── toolAbortController #3 (工具 3)
```

**取消传播**：
- 父控制器 abort → 所有子控制器 abort
- 兄弟控制器 abort ('sibling_error') → 所有兄弟工具 abort
- 工具控制器 abort → 仅该工具 abort (可选择是否向上传播)

### 5.3 错误级联

```
Bash 工具错误
    ↓
this.hasErrored = true
this.erroredToolDescription = "Bash(cmd...)"
siblingAbortController.abort('sibling_error')
    ↓
所有正在执行的工具收到 abort 信号
    ↓
生成 synthetic error message
```

**为什么 Bash 错误特殊**：
- Bash 命令常有隐式依赖链 (mkdir 失败 → 后续命令无意义)
- Read/WebFetch 等是独立的，一个失败不应影响其他

### 5.4 进度消息处理

```typescript
// 进度消息单独存储，立即产出
if (update.message.type === 'progress') {
  tool.pendingProgress.push(update.message)
  if (this.progressAvailableResolve) {
    this.progressAvailableResolve()
    this.progressAvailableResolve = undefined
  }
}
```

**设计 rationale**：
- 进度消息需要实时显示 (如 Bash 输出)
- 与结果消息分离，避免阻塞
- 使用信号量唤醒 `getRemainingResults`

---

## 6. 边界情况处理

| 情况 | 处理方式 |
|------|----------|
| 工具不存在 | 立即返回错误结果 |
| isConcurrencySafe 抛出异常 | 视为不并发安全 |
| 用户中断 (ESC) | 检查 interruptBehavior，'cancel' 工具被取消 |
| Bash 错误 | 取消所有兄弟工具 |
| 流式降级 | discard() 丢弃所有待处理结果 |
| 进度消息 | 单独存储，立即产出 |

---

## 7. 总结

`StreamingToolExecutor` 是 Claude Code 工具执行的核心组件，具有以下特点：

1. **流式执行**：工具随到随执行，无需等待收集完成
2. **并发控制**：并发安全工具并行，非并发安全工具串行
3. **错误级联**：Bash 错误取消所有兄弟工具
4. **中断支持**：尊重工具的 interruptBehavior
5. **进度追踪**：实时产出进度消息
6. **层次取消**：父子 AbortController 层次结构

这套设计确保了工具执行的高效性、安全性和可观测性。
