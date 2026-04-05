# MP-01-01 - REPL 与用户输入入口详解

## 1. 概述

REPL（Read-Eval-Print Loop）是 Claude Code 与用户交互的主要入口，负责接收用户输入、解析命令类型、分发到不同的处理路径。本文档详细讲解从用户按下回车到消息进入处理队列的完整流程。

**核心文件**:
- `src/REPL.tsx` (注：实际代码位于 `src/utils/handlePromptSubmit.ts` 和 `src/utils/processUserInput/processUserInput.ts`)
- `src/utils/handlePromptSubmit.ts`
- `src/utils/processUserInput/processUserInput.ts`

---

## 2. 输入处理总览

### 2.1 流程图

```
用户输入 (handlePromptSubmit)
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 1: 输入验证与预处理                                   │
│  1. 解析粘贴内容引用 ([Pasted text #N])                      │
│  2. 过滤未引用的图像                                         │
│  3. 展开粘贴内容引用                                          │
│  4. 检测退出命令 (exit/quit/:q 等)                            │
│  5. 检测 slash 命令并分发                                      │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 2: 命令分发                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Prompt 模式  │  │   Bash 模式  │  │  Slash 命令  │      │
│  │  (普通对话)   │  │  (shell 命令) │  │  (/help 等)  │      │
│  └───────┬──────┘  └───────┬──────┘  └───────┬──────┘      │
└──────────┼─────────────────┼─────────────────┼──────────────┘
           │                 │                 │
           ▼                 ▼                 ▼
    processTextPrompt   processBash    processSlashCommand
           │                 │                 │
           └─────────────────┴─────────────────┘
                           │
                           ▼
                  executeUserInput (统一执行)
                           │
                           ▼
                         onQuery (进入 Query 循环)
```

### 2.2 核心类型定义

```typescript
// src/utils/handlePromptSubmit.ts:92-118

export type HandlePromptSubmitParams = BaseExecutionParams & {
  // 用户输入 (直接提交时为 string，队列处理时为 undefined)
  input?: string
  
  // 输入模式：prompt(普通对话), bash(shell 命令), task-notification(任务通知)
  mode?: PromptInputMode
  
  // 粘贴的内容 (图像、大段文本)
  pastedContents?: Record<number, PastedContent>
  
  // UI 辅助函数
  helpers: PromptInputHelpers
  onInputChange: (value: string) => void
  setPastedContents: React.Dispatch<...>
  
  // 控制流
  abortController?: AbortController | null
  addNotification?: (...) => void
  setMessages?: (...) => void
  streamMode?: SpinnerMode
  hasInterruptibleToolInProgress?: boolean
  uuid?: UUID
  
  /**
   * 跳过 slash 命令解析 (用于远程消息，如 CCR 会话)
   * 防止 "exit" 等词意外杀死本地会话
   */
  skipSlashCommands?: boolean
}
```

---

## 3. handlePromptSubmit 详解

### 3.1 函数签名与入口

**文件**: `src/utils/handlePromptSubmit.ts:120-387`

```typescript
export async function handlePromptSubmit(
  params: HandlePromptSubmitParams,
): Promise<void>
```

这是用户输入处理的**第一道关卡**，所有用户输入都从这里进入系统。

### 3.2 执行流程分步解析

#### Step 1: 队列处理器路径 (快速路径)

```typescript
// src/utils/handlePromptSubmit.ts:148-172

// 队列处理器路径：命令已预验证，直接执行
// 跳过所有输入验证、引用解析和排队逻辑
if (queuedCommands?.length) {
  startQueryProfile()  // 启动性能分析
  await executeUserInput({
    queuedCommands,
    messages,
    mainLoopModel,
    // ... 传递上下文
  })
  return
}
```

**设计思想**：队列中的命令已经过验证，无需重复处理，直接进入执行阶段。这支持了命令批处理和后台任务。

---

#### Step 2: 基础参数提取与图像过滤

```typescript
// src/utils/handlePromptSubmit.ts:174-186

const input = params.input ?? ''
const mode = params.mode ?? 'prompt'
const rawPastedContents = params.pastedContents ?? {}

// ========== 关键设计：图像引用追踪 ==========
// 图像仅在文本中被引用时才发送
// 删除行内 [Image #N] pill 会丢弃对应图像
const referencedIds = new Set(parseReferences(input).map(r => r.id))
const pastedContents = Object.fromEntries(
  Object.entries(rawPastedContents).filter(
    ([, c]) => c.type !== 'image' || referencedIds.has(c.id),
  ),
)
```

**核心逻辑分析**:

```typescript
// parseReferences 实现 (src/history.ts)
// 解析 [Pasted text #1], [Image #2] 等引用格式
const referencePattern = 
  /\[(Pasted text|Image|\.\.\.Truncated text) #(\d+)(?: \+\d+ lines)?(\.)*\]/g

export function parseReferences(input: string): Array<{ 
  id: number
  match: string
  index: number
}> {
  return [...input.matchAll(referencePattern)]
    .map(match => ({
      id: parseInt(match[2] || '0'),
      match: match[0],
      index: match.index!,
    }))
    .filter(match => match.id > 0)
}
```

**为什么这样设计**：
1. 用户可能在输入框中粘贴图像，但随后删除了 `[Image #N]` pill
2. 如果不检查引用，会发送无用图像，浪费 token
3. 只有通过 pill 显式引用的图像才会进入上下文

---

#### Step 3: 空输入与退出命令检测

```typescript
// src/utils/handlePromptSubmit.ts:188-211

// 空输入检查
if (input.trim() === '') {
  return  // 静默返回
}

// ========== 退出命令检测 ==========
// 处理 exit 命令，触发 /exit 命令而非直接 process.exit
// 跳过远程桥接消息 — iOS 上输入的 "exit" 不应杀死本地会话
if (
  !skipSlashCommands &&
  ['exit', 'quit', ':q', ':q!', ':wq', ':wq!'].includes(input.trim())
) {
  const exitCommand = commands.find(cmd => cmd.name === 'exit')
  if (exitCommand) {
    // 递归调用，提交 /exit 命令
    void handlePromptSubmit({
      ...params,
      input: '/exit',
    })
  } else {
    exit()  // 回退到直接退出
  }
  return
}
```

**设计细节**：
- 支持 vim 风格的退出命令 (`:q`, `:wq`)
- 通过 `/exit` 命令触发反馈对话框，而非直接退出
- `skipSlashCommands` 防止远程会话意外终止

---

#### Step 4: 粘贴内容展开与遥测

```typescript
// src/utils/handlePromptSubmit.ts:213-225

// ========== 粘贴内容展开 ==========
// 在入队或立即命令分发前展开引用
// 确保 queued commands 和 immediate commands 都收到展开后的文本
const finalInput = expandPastedTextRefs(input, pastedContents)

// 解析被引用的文本粘贴 (不包含图像)
const pastedTextRefs = parseReferences(input).filter(
  r => pastedContents[r.id]?.type === 'text',
)

// 遥测：记录粘贴文本的使用情况
const pastedTextCount = pastedTextRefs.length
const pastedTextBytes = pastedTextRefs.reduce(
  (sum, r) => sum + (pastedContents[r.id]?.content.length ?? 0),
  0,
)
logEvent('tengu_paste_text', { pastedTextCount, pastedTextBytes })
```

**展开逻辑** (src/history.ts:362-382):

```typescript
export function expandPastedTextRefs(
  input: string,
  pastedContents: Record<number, PastedContent>,
): string {
  const refs = parseReferences(input)
  let expanded = input
  
  // 反向替换 (保持 offset 有效)
  for (let i = refs.length - 1; i >= 0; i--) {
    const ref = refs[i]!
    const content = pastedContents[ref.id]
    if (content?.type !== 'text') continue
    
    expanded =
      expanded.slice(0, ref.index) +
      content.content +
      expanded.slice(ref.index + ref.match.length)
  }
  
  return expanded
}
```

**为什么反向替换**：
- 如果正向替换，第一个替换会改变后续引用的索引位置
- 反向替换确保每个 `ref.index` 始终有效

---

#### Step 5: Slash 命令处理 (本地 JSX 命令)

```typescript
// src/utils/handlePromptSubmit.ts:227-311

// 处理本地 JSX 立即命令 (如 /config, /doctor)
// 跳过远程桥接消息 — CCR 客户端的 slash 命令是纯文本
if (!skipSlashCommands && finalInput.trim().startsWith('/')) {
  const trimmedInput = finalInput.trim()
  const spaceIndex = trimmedInput.indexOf(' ')
  const commandName = spaceIndex === -1 
    ? trimmedInput.slice(1) 
    : trimmedInput.slice(1, spaceIndex)
  const commandArgs = spaceIndex === -1 
    ? '' 
    : trimmedInput.slice(spaceIndex + 1).trim()

  // 查找立即命令 (immediate = true)
  const immediateCommand = commands.find(
    cmd =>
      cmd.immediate &&
      isCommandEnabled(cmd) &&
      (cmd.name === commandName ||
        cmd.aliases?.includes(commandName) ||
        getCommandName(cmd) === commandName),
  )

  // 如果是 JSX 命令且 queryGuard 活跃，立即执行
  if (
    immediateCommand &&
    immediateCommand.type === 'local-jsx' &&
    (queryGuard.isActive || isExternalLoading)
  ) {
    // ... 执行命令，渲染 JSX UI
  }
}
```

**命令类型区分**：

| 类型 | 特征 | 执行方式 |
|------|------|----------|
| `local-jsx` | 渲染 React 组件 | 立即执行，显示 UI |
| `query` | 需要模型参与 | 进入 query 循环 |
| `local` | 纯本地命令 | 立即执行，输出文本 |

---

#### Step 6: 队列逻辑 (queryGuard 活跃时)

```typescript
// src/utils/handlePromptSubmit.ts:313-351

// 如果 queryGuard 活跃 (有查询正在执行) 或有外部加载
if (queryGuard.isActive || isExternalLoading) {
  // 只允许 prompt 和 bash 模式命令入队
  if (mode !== 'prompt' && mode !== 'bash') {
    return
  }

  // ========== 中断可中断的工具 ==========
  // 当所有执行中的工具都有 'cancel' interruptBehavior 时
  if (params.hasInterruptibleToolInProgress) {
    logEvent('tengu_cancel', {
      source: 'interrupt_on_submit',
      streamMode: params.streamMode,
    })
    params.abortController?.abort('interrupt')
  }

  // ========== 入队 ==========
  // 图像在 processUserInput 执行时调整大小 (不在此处烘焙)
  enqueue({
    value: finalInput.trim(),
    preExpansionValue: input.trim(),
    mode,
    pastedContents: hasImages ? pastedContents : undefined,
    skipSlashCommands,
    uuid,
  })

  // 清空输入框
  onInputChange('')
  setCursorOffset(0)
  setPastedContents({})
  resetHistory()
  clearBuffer()
  return
}
```

**设计思想**：
- queryGuard 确保同一时间只有一个 query 在执行
- 新输入在后台排队，等当前查询完成后自动执行
- 支持用户连续输入多个命令

---

#### Step 7: 直接执行路径 (Happy Path)

```typescript
// src/utils/handlePromptSubmit.ts:353-387

// 启动查询性能分析
startQueryProfile()

// ========== 构建 QueuedCommand ==========
// 统一路径：直接用户输入也转为 QueuedCommand
// 确保图像通过 processUserInput 调整大小
const cmd: QueuedCommand = {
  value: finalInput,
  preExpansionValue: input,
  mode,
  pastedContents: hasImages ? pastedContents : undefined,
  skipSlashCommands,
  uuid,
}

// ========== 执行统一入口 ==========
await executeUserInput({
  queuedCommands: [cmd],
  messages,
  mainLoopModel,
  // ...
})
```

**统一设计**：
- 无论输入来源 (直接用户输入、队列、远程)，最终都转为 `QueuedCommand`
- 统一通过 `executeUserInput` 处理，代码复用

---

## 4. executeUserInput 详解

### 4.1 函数签名与职责

**文件**: `src/utils/handlePromptSubmit.ts:396-610`

```typescript
async function executeUserInput(params: ExecuteUserInputParams): Promise<void>
```

**职责**：
- 统一处理所有命令 (无论来源)
- 管理 AbortController
- 调用 `processUserInput` 处理每个命令
- 调用 `onQuery` 进入 query 循环

### 4.2 核心执行流程

```typescript
// src/utils/handlePromptSubmit.ts:419-440

// ========== 创建 AbortController ==========
// 总是创建新的 AbortController — queryGuard 保证没有并发调用
const abortController = createAbortController()
setAbortController(abortController)

// 创建上下文工厂函数
function makeContext(): ProcessUserInputContext {
  return getToolUseContext(messages, [], abortController, mainLoopModel)
}

// ========== try-finally 保护 ==========
try {
  // 1. 在 processUserInput 之前保留 guard
  // 防止并发 executeUserInput 调用
  queryGuard.reserve()
  queryCheckpoint('query_process_user_input_start')
  
  const newMessages: Message[] = []
  let shouldQuery = false
  let allowedTools: string[] | undefined
  let model: string | undefined
  let effort: EffortValue | undefined
  
  // ...
} finally {
  // 安全网：如果 processUserInput 抛出或 onQuery 被跳过，释放 guard
  queryGuard.cancelReservation()
  setUserInputOnProcessing(undefined)
}
```

### 4.3 命令循环处理

```typescript
// src/utils/handlePromptSubmit.ts:451-522

const commands = queuedCommands ?? []

// 计算本 turn 的 workload 标签
const firstWorkload = commands[0]?.workload
const turnWorkload =
  firstWorkload !== undefined &&
  commands.every(c => c.workload === firstWorkload)
    ? firstWorkload
    : undefined

// ========== 在 AsyncLocalStorage 上下文中运行 ==========
// 这是正确传播 workload 的唯一方式
// void-detached 后台 agent 在调用时捕获 ALS 上下文
await runWithWorkload(turnWorkload, async () => {
  // 遍历所有命令
  for (let i = 0; i < commands.length; i++) {
    const cmd = commands[i]!
    const isFirst = i === 0
    
    // ========== 调用 processUserInput ==========
    const result = await processUserInput({
      input: cmd.value,
      preExpansionInput: cmd.preExpansionValue,
      mode: cmd.mode,
      setToolJSX,
      context: makeContext(),
      pastedContents: isFirst ? cmd.pastedContents : undefined,  // 只有第一个命令带附件
      messages,
      isAlreadyProcessing: !isFirst,  // 第一个之后的命令标记为"已在处理中"
      skipAttachments: !isFirst,  // 避免重复注入上下文
      // ...
    })
    
    // 收集消息
    newMessages.push(...result.messages)
    
    // 只从第一个命令提取 shouldQuery/allowedTools 等
    if (isFirst) {
      shouldQuery = result.shouldQuery
      allowedTools = result.allowedTools
      model = result.model
      effort = result.effort
    }
  }
})
```

**关键设计点**：

1. **第一个命令特殊处理**：
   - 只有第一个命令携带 `pastedContents` (图像)
   - 只有第一个命令注入 `ideSelection` 和 attachments
   - 后续命令跳过附件，避免重复

2. **AsyncLocalStorage 上下文**：
   - 后台 agent (executeForkedSlashCommand, AgentTool) 在调用时捕获 ALS 上下文
   - 每个 await 之后的 continuation 都保留 worklod 标签
   - 进程级全局变量会在 detached 闭包的第一个 await 时被覆盖

3. **workload 计算**：
   - 当**所有**命令的 workload 一致时才使用
   - 人类用户 + 定时任务混合时，workload 为 undefined

### 4.4 调用 onQuery 进入 Query 循环

```typescript
// src/utils/handlePromptSubmit.ts:541-571

if (newMessages.length) {
  // 重置历史记录
  resetHistory()
  
  // 清除 JSX 命令
  setToolJSX({
    jsx: null,
    shouldHidePromptInput: false,
    clearLocalJSX: true,
  })

  const primaryCmd = commands[0]
  const primaryMode = primaryCmd?.mode ?? 'prompt'
  const primaryInput = primaryCmd?.value

  // ========== 调用 onQuery 进入核心循环 ==========
  await onQuery(
    newMessages,              // 新生成的消息
    abortController,          // 用于取消
    shouldQuery,              // 是否查询模型
    allowedTools ?? [],       // 额外允许的工具
    model ? resolveSkillModelOverride(model, mainLoopModel) : mainLoopModel,
    primaryMode === 'prompt' ? onBeforeQuery : undefined,
    primaryInput,
    effort,
  )
} else {
  // 本地 slash 命令 (如 /model, /theme) 不生成消息
  queryGuard.cancelReservation()
  setToolJSX({ jsx: null, shouldHidePromptInput: false, clearLocalJSX: true })
  resetHistory()
  setAbortController(null)
}
```

---

## 5. processUserInput 详解

### 5.1 函数签名与职责

**文件**: `src/utils/processUserInput/processUserInput.ts:85-270`

```typescript
export async function processUserInput({
  input,              // 用户输入 (string 或 ContentBlockParam[])
  mode,               // 输入模式
  context,            // 工具使用上下文
  pastedContents,     // 粘贴内容
  ideSelection,       // IDE 选区
  skipSlashCommands,  // 跳过 slash 命令解析
  skipAttachments,    // 跳过附件注入
}): Promise<ProcessUserInputBaseResult>
```

### 5.2 两阶段处理

```typescript
// src/utils/processUserInput/processUserInput.ts:149-176

queryCheckpoint('query_process_user_input_base_start')

// ========== Phase 1: 基础处理 ==========
const result = await processUserInputBase(
  input, mode, setToolJSX, context, pastedContents,
  ideSelection, messages, uuid, isAlreadyProcessing,
  querySource, canUseTool, appState.toolPermissionContext.mode,
  skipSlashCommands, bridgeOrigin, isMeta, skipAttachments,
  preExpansionInput,
)

queryCheckpoint('query_process_user_input_base_end')

if (!result.shouldQuery) {
  return result  // 不需要查询模型，直接返回
}

// ========== Phase 2: 执行 UserPromptSubmit Hooks ==========
queryCheckpoint('query_hooks_start')
const inputMessage = getContentText(input) || ''

for await (const hookResult of executeUserPromptSubmitHooks(
  inputMessage,
  appState.toolPermissionContext.mode,
  context,
  context.requestPrompt,
)) {
  // 处理 blockingError, preventContinuation, additionalContexts
  // ...
}
queryCheckpoint('query_hooks_end')

return result
```

### 5.3 processUserInputBase 核心逻辑

**文件**: `src/utils/processUserInput/processUserInput.ts:281-605`

#### Step 1: 输入标准化与图像处理

```typescript
// src/utils/processUserInput/processUserInput.ts:300-345

let inputString: string | null = null
let precedingInputBlocks: ContentBlockParam[] = []
const imageMetadataTexts: string[] = []

// 标准化输入：处理图像块大小调整
let normalizedInput: string | ContentBlockParam[] = input

if (typeof input === 'string') {
  inputString = input
} else if (input.length > 0) {
  queryCheckpoint('query_image_processing_start')
  
  const processedBlocks: ContentBlockParam[] = []
  for (const block of input) {
    if (block.type === 'image') {
      // 调整图像大小
      const resized = await maybeResizeAndDownsampleImageBlock(block)
      
      // 收集图像元数据
      if (resized.dimensions) {
        const metadataText = createImageMetadataText(resized.dimensions)
        imageMetadataTexts.push(metadataText)
      }
      processedBlocks.push(resized.block)
    } else {
      processedBlocks.push(block)
    }
  }
  
  normalizedInput = processedBlocks
  queryCheckpoint('query_image_processing_end')
  
  // 提取最后的文本块
  const lastBlock = processedBlocks[processedBlocks.length - 1]
  if (lastBlock?.type === 'text') {
    inputString = lastBlock.text
    precedingInputBlocks = processedBlocks.slice(0, -1)
  }
}
```

#### Step 2: 粘贴图像处理

```typescript
// src/utils/processUserInput/processUserInput.ts:351-420

// 提取图像内容
const imageContents = pastedContents
  ? Object.values(pastedContents).filter(isValidImagePaste)
  : []
const imagePasteIds = imageContents.map(img => img.id)

// 存储图像到磁盘 (供 Claude 引用)
const storedImagePaths = pastedContents
  ? await storeImages(pastedContents)
  : new Map<number, string>()

// 并行调整所有粘贴图像的大小
queryCheckpoint('query_pasted_image_processing_start')
const imageProcessingResults = await Promise.all(
  imageContents.map(async pastedImage => {
    const imageBlock: ImageBlockParam = {
      type: 'image',
      source: {
        type: 'base64',
        media_type: pastedImage.mediaType || 'image/png',
        data: pastedImage.content,
      },
    }
    const resized = await maybeResizeAndDownsampleImageBlock(imageBlock)
    return { resized, originalDimensions: pastedImage.dimensions }
  }),
)
queryCheckpoint('query_pasted_image_processing_end')
```

#### Step 3: Ultraplan 关键词检测

```typescript
// src/utils/processUserInput/processUserInput.ts:464-493

// Ultraplan 关键词检测 — 通过 /ultraplan 路由
// 在 pre-expansion 输入上检测 (粘贴内容中的关键词不触发)
if (
  feature('ULTRAPLAN') &&
  mode === 'prompt' &&
  !context.options.isNonInteractiveSession &&
  inputString !== null &&
  !effectiveSkipSlash &&
  !inputString.startsWith('/') &&
  hasUltraplanKeyword(preExpansionInput ?? inputString)
) {
  logEvent('tengu_ultraplan_keyword', {})
  
  const rewritten = replaceUltraplanKeyword(inputString).trim()
  const { processSlashCommand } = await import('./processSlashCommand.js')
  
  const slashResult = await processSlashCommand(
    `/ultraplan ${rewritten}`,
    precedingInputBlocks,
    imageContentBlocks,
    [],
    context,
    setToolJSX,
    uuid,
  )
  return addImageMetadataMessage(slashResult, imageMetadataTexts)
}
```

**设计细节**：
- 使用 `preExpansionInput` 检测，防止粘贴内容中的 "plan" 触发
- 替换为 "plan" 保持 CCR 提示的语法正确性

#### Step 4: 附件提取

```typescript
// src/utils/processUserInput/processUserInput.ts:495-514

// 附件提取条件：
// - 不是第一个之后的命令 (skipAttachments)
// - 是 prompt 模式或不是 slash 命令
const shouldExtractAttachments =
  !skipAttachments &&
  inputString !== null &&
  (mode !== 'prompt' || effectiveSkipSlash || !inputString.startsWith('/'))

queryCheckpoint('query_attachment_loading_start')
const attachmentMessages = shouldExtractAttachments
  ? await toArray(
      getAttachmentMessages(
        inputString,
        context,
        ideSelection ?? null,
        [],  // queuedCommands - 由 query.ts 处理中途附件
        messages,
        querySource,
      ),
    )
  : []
queryCheckpoint('query_attachment_loading_end')
```

#### Step 5: 命令分发

```typescript
// ========== Bash 命令 ==========
if (inputString !== null && mode === 'bash') {
  const { processBashCommand } = await import('./processBashCommand.js')
  return addImageMetadataMessage(
    await processBashCommand(
      inputString,
      precedingInputBlocks,
      attachmentMessages,
      context,
      setToolJSX,
    ),
    imageMetadataTexts,
  )
}

// ========== Slash 命令 ==========
if (
  inputString !== null &&
  !effectiveSkipSlash &&
  inputString.startsWith('/')
) {
  const { processSlashCommand } = await import('./processSlashCommand.js')
  const slashResult = await processSlashCommand(
    inputString,
    precedingInputBlocks,
    imageContentBlocks,
    attachmentMessages,
    context,
    setToolJSX,
    uuid,
    isAlreadyProcessing,
    canUseTool,
  )
  return addImageMetadataMessage(slashResult, imageMetadataTexts)
}

// ========== 普通 Prompt ==========
return addImageMetadataMessage(
  processTextPrompt(
    normalizedInput,
    imageContentBlocks,
    imagePasteIds,
    attachmentMessages,
    uuid,
    permissionMode,
    isMeta,
  ),
  imageMetadataTexts,
)
```

### 5.4 processTextPrompt

**文件**: `src/utils/processUserInput/processTextPrompt.ts:19-100`

```typescript
export function processTextPrompt(
  input: string | Array<ContentBlockParam>,
  imageContentBlocks: ContentBlockParam[],
  imagePasteIds: number[],
  attachmentMessages: AttachmentMessage[],
  uuid?: string,
  permissionMode?: PermissionMode,
  isMeta?: boolean,
): {
  messages: (UserMessage | AttachmentMessage | SystemMessage)[]
  shouldQuery: boolean
} {
  const promptId = randomUUID()
  setPromptId(promptId)  // 设置当前 prompt ID
  
  // 提取用户提示文本用于遥测
  const userPromptText = typeof input === 'string'
    ? input
    : input.find(block => block.type === 'text')?.text || ''
  
  // 启动交互 span (用于追踪)
  startInteractionSpan(userPromptText)
  
  // ========== OTEL 事件记录 ==========
  const otelPromptText = typeof input === 'string'
    ? input
    : input.findLast(block => block.type === 'text')?.text || ''
  
  if (otelPromptText) {
    void logOTelEvent('user_prompt', {
      prompt_length: String(otelPromptText.length),
      prompt: redactIfDisabled(otelPromptText),
      'prompt.id': promptId,
    })
  }
  
  // ========== 关键词检测 ==========
  const isNegative = matchesNegativeKeyword(userPromptText)
  const isKeepGoing = matchesKeepGoingKeyword(userPromptText)
  logEvent('tengu_input_prompt', {
    is_negative: isNegative,
    is_keep_going: isKeepGoing,
  })
  
  // ========== 创建 UserMessage ==========
  if (imageContentBlocks.length > 0) {
    const textContent = typeof input === 'string'
      ? input.trim() ? [{ type: 'text', text: input }] : []
      : input
    
    const userMessage = createUserMessage({
      content: [...textContent, ...imageContentBlocks],
      uuid,
      imagePasteIds: imagePasteIds.length > 0 ? imagePasteIds : undefined,
      permissionMode,
      isMeta: isMeta || undefined,
    })
    
    return {
      messages: [userMessage, ...attachmentMessages],
      shouldQuery: true,
    }
  }
  
  const userMessage = createUserMessage({
    content: input,
    uuid,
    permissionMode,
    isMeta: isMeta || undefined,
  })
  
  return {
    messages: [userMessage, ...attachmentMessages],
    shouldQuery: true,
  }
}
```

---

## 6. Hook 系统 - UserPromptSubmit

### 6.1 Hook 执行流程

```typescript
// src/utils/processUserInput/processUserInput.ts:178-263

for await (const hookResult of executeUserPromptSubmitHooks(
  inputMessage,
  appState.toolPermissionContext.mode,
  context,
  context.requestPrompt,
)) {
  // 跳过进度消息
  if (hookResult.message?.type === 'progress') {
    continue
  }

  // ========== 阻塞错误 ==========
  if (hookResult.blockingError) {
    const blockingMessage = getUserPromptSubmitHookBlockingMessage(
      hookResult.blockingError,
    )
    return {
      messages: [
        createSystemMessage(
          `${blockingMessage}\n\nOriginal prompt: ${input}`,
          'warning',
        ),
      ],
      shouldQuery: false,
    }
  }

  // ========== 阻止继续 ==========
  if (hookResult.preventContinuation) {
    const message = hookResult.stopReason
      ? `Operation stopped by hook: ${hookResult.stopReason}`
      : 'Operation stopped by hook'
    result.messages.push(createUserMessage({ content: message }))
    result.shouldQuery = false
    return result
  }

  // ========== 额外上下文 ==========
  if (hookResult.additionalContexts?.length > 0) {
    result.messages.push(createAttachmentMessage({
      type: 'hook_additional_context',
      content: hookResult.additionalContexts.map(applyTruncation),
      hookName: 'UserPromptSubmit',
    }))
  }
}
```

### 6.2 输出截断

```typescript
// src/utils/processUserInput/processUserInput.ts:272-279

const MAX_HOOK_OUTPUT_LENGTH = 10000

function applyTruncation(content: string): string {
  if (content.length > MAX_HOOK_OUTPUT_LENGTH) {
    return `${content.substring(0, MAX_HOOK_OUTPUT_LENGTH)}… [output truncated - exceeded ${MAX_HOOK_OUTPUT_LENGTH} characters]`
  }
  return content
}
```

---

## 7. 设计思想总结

### 7.1 统一路径设计

所有输入最终都转为 `QueuedCommand`，统一通过 `executeUserInput` 处理：
- 直接用户输入 → `[{ value, mode, ... }]`
- 队列输入 → `queuedCommands`
- 远程输入 → `[{ value, skipSlashCommands: true, ... }]`

### 7.2 分层处理

```
Level 1: handlePromptSubmit  — UI 层，输入验证，命令分发
Level 2: executeUserInput    — 执行编排，guard 管理，AbortController
Level 3: processUserInput    — 核心处理，Hook 执行
Level 4: process* 函数        — 具体命令处理 (Text/Bash/Slash)
```

### 7.3 并发控制

- **queryGuard**：确保同一时间只有一个 query 在执行
- **AbortController**：每 turn 创建新的，支持用户取消
- **AsyncLocalStorage**：正确传播 workload 标签

### 7.4 性能优化

- **并行图像处理**：`Promise.all` 同时调整所有图像大小
- **Checkpoint 打点**：关键路径插入 `queryCheckpoint` 用于性能分析
- **懒加载**：`await import()` 延迟加载不常用的模块

### 7.5 可扩展性

- **Hook 系统**：第三方可以在 `UserPromptSubmit` 时介入
- **模式系统**：`prompt`/`bash`/`task-notification` 支持不同输入类型
- **队列系统**：支持后台任务和命令批处理

---

## 8. 与其他模块的交互

```
┌─────────────────┐
│  handlePrompt   │
│    Submit       │
└────────┬────────┘
         │
         ├──> queryGuard (并发控制)
         ├──> processUserInput (核心处理)
         │       │
         │       ├──> processTextPrompt (普通对话)
         │       ├──> processBashCommand (Shell 命令)
         │       ├──> processSlashCommand (Slash 命令)
         │       └──> executeUserPromptSubmitHooks (Hooks)
         │
         └──> onQuery (进入 Query 循环)
                 │
                 ├──> query.ts (主循环)
                 ├──> StreamingToolExecutor (工具执行)
                 └──> API 调用
```

---

## 9. 边界情况处理

| 情况 | 处理方式 |
|------|----------|
| 空输入 | 静默返回 |
| 仅图像 (无文本) | 创建仅包含图像的 UserMessage |
| 退出命令 | 转为 `/exit` 命令，触发反馈对话框 |
| 远程输入 | `skipSlashCommands=true`，防止意外命令 |
| 队列输入 | 只有第一个命令带附件，后续跳过 |
| Hook 阻塞 | 返回系统警告消息，保留原始 prompt |
| 并发提交 | queryGuard 排队，顺序执行 |

---

## 10. 总结

用户输入入口系统是 Claude Code 与用户交互的第一道关卡，设计精良：

1. **统一路径**：所有输入最终转为 `QueuedCommand`
2. **分层架构**：UI 层 → 执行层 → 处理层 → 命令层
3. **并发安全**：queryGuard 保证单 query 执行
4. **Hook 扩展**：支持第三方在关键时刻介入
5. **性能优化**：并行处理、懒加载、checkpoint 打点
6. **边界处理**：空输入、退出命令、远程输入等特殊情况

这套设计支撑了从简单对话到复杂批处理命令的全场景需求。
