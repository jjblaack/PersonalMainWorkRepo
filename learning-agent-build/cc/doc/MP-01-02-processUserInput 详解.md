# MP-01-02 - processUserInput 详解

## 1. 概述

`processUserInput` 是用户输入处理的核心引擎，负责将原始用户输入转换为系统内部消息格式，并在多个关键时刻通过 Hook 系统扩展功能。

**核心文件**:
- `src/utils/processUserInput/processUserInput.ts`
- `src/utils/processUserInput/processTextPrompt.ts`
- `src/utils/processUserInput/processSlashCommand.tsx`
- `src/utils/processUserInput/processBashCommand.tsx`

---

## 2. 架构设计

### 2.1 两阶段处理模型

```
┌─────────────────────────────────────────────────────────────┐
│                   processUserInput                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Phase 1: processUserInputBase (基础处理)                   │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ 1. 输入标准化 (字符串 → ContentBlockParam[])          │ │
│  │ 2. 图像处理 ( resize/downsample)                      │ │
│  │ 3. 粘贴图像处理 (存储到磁盘)                           │ │
│  │ 4. Ultraplan 关键词检测与路由                          │ │
│  │ 5. 附件提取 (CLAUDE.md, IDE 选区，任务等)               │ │
│  │ 6. 命令分发 (Text/Bash/Slash)                          │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  Phase 2: UserPromptSubmit Hooks (扩展处理)                │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ 遍历所有注册的 UserPromptSubmit Hook:                 │ │
│  │ - blockingError: 阻塞错误，阻止提交                    │ │
│  │ - preventContinuation: 阻止继续，保留原始 prompt       │ │
│  │ - additionalContexts: 添加额外上下文                   │ │
│  │ - hook_success: Hook 成功执行的附加消息                │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 函数签名

```typescript
// src/utils/processUserInput/processUserInput.ts:85-140

export async function processUserInput({
  input: string | Array<ContentBlockParam>,  // 用户输入
  preExpansionInput?: string,                // 展开前的输入 (用于关键词检测)
  mode: PromptInputMode,                     // 输入模式
  setToolJSX: SetToolJSXFn,                  // 设置 JSX 工具 UI
  context: ProcessUserInputContext,          // 工具使用上下文
  pastedContents?: Record<number, PastedContent>,  // 粘贴内容
  ideSelection?: IDESelection,               // IDE 选区
  messages?: Message[],                      // 当前消息历史
  setUserInputOnProcessing?: (prompt?: string) => void,
  uuid?: string,
  isAlreadyProcessing?: boolean,
  querySource?: QuerySource,
  canUseTool?: CanUseToolFn,
  skipSlashCommands?: boolean,               // 跳过 slash 命令解析
  bridgeOrigin?: boolean,                    // 来自桥接的远程消息
  isMeta?: boolean,                          // 是否为元消息 (系统生成)
  skipAttachments?: boolean,                 // 跳过附件注入
}): Promise<ProcessUserInputBaseResult>
```

### 2.3 返回类型

```typescript
// src/utils/processUserInput/processUserInput.ts:64-83

export type ProcessUserInputBaseResult = {
  messages: (
    | UserMessage
    | AssistantMessage
    | AttachmentMessage
    | SystemMessage
    | ProgressMessage
  )[]                                    // 生成的消息列表
  shouldQuery: boolean                   // 是否需要查询模型
  allowedTools?: string[]                // 额外允许的工具
  model?: string                         // 模型覆盖
  effort?: EffortValue                   // 努力程度
  resultText?: string                    // 非交互模式输出
  nextInput?: string                     // 下一个输入 (命令链)
  submitNextInput?: boolean              // 是否提交下一个输入
}
```

---

## 3. Phase 1: 基础处理详解

### 3.1 输入标准化与图像处理

**文件**: `src/utils/processUserInput/processUserInput.ts:300-345`

```typescript
async function processUserInputBase(...): Promise<ProcessUserInputBaseResult> {
  let inputString: string | null = null
  let precedingInputBlocks: ContentBlockParam[] = []
  const imageMetadataTexts: string[] = []

  // 标准化输入：处理图像块大小调整
  let normalizedInput: string | ContentBlockParam[] = input

  if (typeof input === 'string') {
    inputString = input
  } else if (input.length > 0) {
    // ========== 数组输入处理 (来自 SDK/VS Code) ==========
    queryCheckpoint('query_image_processing_start')
    
    const processedBlocks: ContentBlockParam[] = []
    for (const block of input) {
      if (block.type === 'image') {
        // 调整图像大小以符合 API 限制
        const resized = await maybeResizeAndDownsampleImageBlock(block)
        
        // 收集图像元数据 (用于 isMeta 消息)
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
    
    // 提取最后的文本块和前面的块
    const lastBlock = processedBlocks[processedBlocks.length - 1]
    if (lastBlock?.type === 'text') {
      inputString = lastBlock.text
      precedingInputBlocks = processedBlocks.slice(0, -1)
    } else {
      precedingInputBlocks = processedBlocks
    }
  }
  
  if (inputString === null && mode !== 'prompt') {
    throw new Error(`Mode: ${mode} requires a string input.`)
  }
}
```

**设计细节**：

1. **为什么需要标准化**：
   - 字符串输入来自 CLI
   - 数组输入来自 SDK/VS Code (可能包含多个 content blocks)
   - 统一处理后，后续逻辑无需区分输入来源

2. **precedingInputBlocks 用途**：
   - 在 slash 命令处理时，保留图像块在命令前面
   - 确保命令和关联图像一起传递给模型

---

### 3.2 粘贴图像处理

**文件**: `src/utils/processUserInput/processUserInput.ts:351-420`

```typescript
// 提取图像内容
const imageContents = pastedContents
  ? Object.values(pastedContents).filter(isValidImagePaste)
  : []
const imagePasteIds = imageContents.map(img => img.id)

// ========== 存储图像到磁盘 ==========
// Claude 可以引用路径 (用于 CLI 工具操作、PR 上传等)
const storedImagePaths = pastedContents
  ? await storeImages(pastedContents)
  : new Map<number, string>()

// ========== 并行调整所有粘贴图像的大小 ==========
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
    logEvent('tengu_pasted_image_resize_attempt', {
      original_size_bytes: pastedImage.content.length,
    })
    const resized = await maybeResizeAndDownsampleImageBlock(imageBlock)
    return {
      resized,
      originalDimensions: pastedImage.dimensions,
      sourcePath: pastedImage.sourcePath ?? storedImagePaths.get(pastedImage.id),
    }
  }),
)
queryCheckpoint('query_pasted_image_processing_end')

// 收集结果 (保持顺序)
const imageContentBlocks: ContentBlockParam[] = []
for (const { resized, originalDimensions, sourcePath } of imageProcessingResults) {
  // 收集元数据 (优先使用调整后的尺寸)
  if (resized.dimensions) {
    const metadataText = createImageMetadataText(resized.dimensions, sourcePath)
    imageMetadataTexts.push(metadataText)
  } else if (originalDimensions) {
    const metadataText = createImageMetadataText(originalDimensions, sourcePath)
    imageMetadataTexts.push(metadataText)
  } else if (sourcePath) {
    imageMetadataTexts.push(`[Image source: ${sourcePath}]`)
  }
  imageContentBlocks.push(resized.block)
}
```

**为什么并行处理**：
- 图像调整是 CPU 密集型操作
- 用户可能同时粘贴多张图像
- `Promise.all` 可以充分利用多核 CPU

**图像存储路径**：
- 存储在 `~/.claude/image-cache/` 目录
- 文件名格式：`{sessionId}_{imageId}.png`
- 模型可以通过路径引用图像 (如 `open image.png`)

---

### 3.3 桥接安全命令覆盖

**文件**: `src/utils/processUserInput/processUserInput.ts:422-453`

```typescript
// ========== 桥接安全命令覆盖 ==========
// 移动/网页客户端设置 bridgeOrigin 且 skipSlashCommands=true
// (防御意外退出词和立即命令快速路径)
// 在此处解析命令 — 如果通过 isBridgeSafeCommand，清除 skip
let effectiveSkipSlash = skipSlashCommands

if (bridgeOrigin && inputString !== null && inputString.startsWith('/')) {
  const parsed = parseSlashCommand(inputString)
  const cmd = parsed
    ? findCommand(parsed.commandName, context.options.commands)
    : undefined
    
  if (cmd) {
    if (isBridgeSafeCommand(cmd)) {
      effectiveSkipSlash = false  // 允许安全命令
    } else {
      // 已知但不安全的命令 (local-jsx UI 或仅限终端)
      // 返回帮助消息而非让模型看到原始 "/config"
      const msg = `/${getCommandName(cmd)} isn't available over Remote Control.`
      return {
        messages: [
          createUserMessage({ content: inputString, uuid }),
          createCommandInputMessage(
            `<local-command-stdout>${msg}</local-command-stdout>`,
          ),
        ],
        shouldQuery: false,
        resultText: msg,
      }
    }
  }
  // 未知 /foo 或无法解析 — 作为纯文本处理
}
```

**安全命令列表** (`src/commands.ts`):

```typescript
const BRIDGE_SAFE_COMMANDS = new Set([
  '/help',
  '/theme',
  '/model',
  // ... 只读、无副作用的命令
])

export function isBridgeSafeCommand(cmd: Command): boolean {
  return BRIDGE_SAFE_COMMANDS.has(cmd.name) || 
         BRIDGE_SAFE_COMMANDS.has(cmd.aliases?.[0] || '')
}
```

**为什么这样设计**：
- 远程客户端 (如 iOS) 输入 `/exit` 不应杀死本地会话
- 但 `/help` 等只读命令可以安全执行
- 白名单机制确保只有经过审查的命令可以通过

---

### 3.4 Ultraplan 关键词检测

**文件**: `src/utils/processUserInput/processUserInput.ts:455-493`

```typescript
// ========== Ultraplan 关键词路由 ==========
// 通过 /ultraplan 路由
// 在 pre-expansion 输入上检测 (粘贴内容中的关键词不触发)
// 替换为 "plan" 保持 CCR 提示的语法正确性
if (
  feature('ULTRAPLAN') &&
  mode === 'prompt' &&
  !context.options.isNonInteractiveSession &&
  inputString !== null &&
  !effectiveSkipSlash &&
  !inputString.startsWith('/') &&
  !context.getAppState().ultraplanSessionUrl &&
  !context.getAppState().ultraplanLaunching &&
  hasUltraplanKeyword(preExpansionInput ?? inputString)
) {
  logEvent('tengu_ultraplan_keyword', {})
  
  // 替换关键词并调用 /ultraplan
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
    isAlreadyProcessing,
    canUseTool,
  )
  return addImageMetadataMessage(slashResult, imageMetadataTexts)
}
```

**关键词检测逻辑** (`src/utils/ultraplan/keyword.ts`):

```typescript
const ULTRAPLAN_KEYWORDS = [
  /\bplan\b/i,
  /\bstrategy\b/i,
  /\broadmap\b/i,
  // ...
]

export function hasUltraplanKeyword(input: string): boolean {
  // 排除引号内的 "plan" (引用用法)
  // 排除路径中的 /plan (如 /usr/bin/plan)
  return ULTRAPLAN_KEYWORDS.some(regex => regex.test(input))
}

export function replaceUltraplanKeyword(input: string): string {
  // 将 "plan" 替换为其他词，保持语法正确
  return input.replace(/\bplan\b/gi, 'strategy')
}
```

**为什么使用 preExpansionInput**：
- 粘贴内容可能包含 "plan" 这个词
- 如果粘贴代码中有 `plan.execute()`，不应触发 Ultraplan
- 只有在用户输入中显式说 "plan to..." 时才触发

---

### 3.5 附件提取

**文件**: `src/utils/processUserInput/processUserInput.ts:495-514`

```typescript
// 附件提取条件
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

**附件类型** (`src/utils/attachments.ts`):

| 附件类型 | 描述 | 触发条件 |
|----------|------|----------|
| `claude_md_injection` | CLAUDE.md 文件注入 | 每次对话 |
| `ide_selection` | IDE 中选代码 | 有 IDE 选区 |
| `todo_list` | 任务列表 | 有活动任务 |
| `plan_file` | 计划文件 | 计划模式 |
| `agent_listing` | Agent 列表 | 提到 @agent |
| `skill_listing` | Skill 列表 | 提到 @skill |
| `mcp_instructions` | MCP 指令 | 有 MCP 服务器 |
| `diagnostic` | LSP 诊断 | 有诊断错误 |
| `hook_additional_context` | Hook 上下文 | Hook 返回 |

---

### 3.6 命令分发

**文件**: `src/utils/processUserInput/processUserInput.ts:516-589`

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

// ========== Agent Mention 检测 ==========
if (inputString !== null && mode === 'prompt') {
  const trimmedInput = inputString.trim()
  
  const agentMention = attachmentMessages.find(
    (m): m is AttachmentMessage<AgentMentionAttachment> =>
      m.attachment.type === 'agent_mention',
  )
  
  if (agentMention) {
    const agentMentionString = `@agent-${agentMention.attachment.agentType}`
    const isSubagentOnly = trimmedInput === agentMentionString
    const isPrefix = trimmedInput.startsWith(agentMentionString) && !isSubagentOnly
    
    logEvent('tengu_subagent_at_mention', {
      is_subagent_only: isSubagentOnly,
      is_prefix: isPrefix,
    })
  }
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

---

## 4. processTextPrompt 详解

### 4.1 函数签名

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
}
```

### 4.2 核心逻辑

```typescript
export function processTextPrompt(...) {
  // ========== 生成 Prompt ID ==========
  const promptId = randomUUID()
  setPromptId(promptId)  // 设置全局 prompt ID
  
  // 提取用户提示文本用于遥测
  const userPromptText = typeof input === 'string'
    ? input
    : input.find(block => block.type === 'text')?.text || ''
  
  // 启动交互 span (用于分布式追踪)
  startInteractionSpan(userPromptText)
  
  // ========== OTEL 事件记录 ==========
  // 对于数组输入，使用最后一个文本块
  // createUserContent 将用户消息放在最后 (在附件之后)
  const otelPromptText = typeof input === 'string'
    ? input
    : input.findLast(block => block.type === 'text')?.text || ''
  
  if (otelPromptText) {
    void logOTelEvent('user_prompt', {
      prompt_length: String(otelPromptText.length),
      prompt: redactIfDisabled(otelPromptText),  // 根据隐私设置脱敏
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
    // 有图像：构建内容块数组
    const textContent = typeof input === 'string'
      ? input.trim() ? [{ type: 'text', text: input }] : []
      : input
    
    const userMessage = createUserMessage({
      content: [...textContent, ...imageContentBlocks],  // 文本在前，图像在后
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
  
  // 无图像：直接创建
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

### 4.3 关键词检测

**文件**: `src/utils/userPromptKeywords.ts`

```typescript
// 负面关键词 — 用于检测用户不满
const NEGATIVE_KEYWORDS = [
  /\b(not|never|wrong|incorrect|bad|terrible|awful)\b/i,
  /\b(fail|failed|failure|error|problem|issue)\b/i,
  // ...
]

// "继续" 关键词 — 用于检测用户希望继续
const KEEP_GOING_KEYWORDS = [
  /\b(continue|keep going|go on|proceed)\b/i,
  /\b(more|again|repeat)\b/i,
  // ...
]

export function matchesNegativeKeyword(text: string): boolean {
  return NEGATIVE_KEYWORDS.some(regex => regex.test(text))
}

export function matchesKeepGoingKeyword(text: string): boolean {
  return KEEP_GOING_KEYWORDS.some(regex => regex.test(text))
}
```

**用途**：
- 负面关键词用于遥测和用户满意度分析
- "继续" 关键词可能触发特殊处理 (如继续生成)

---

## 5. Phase 2: UserPromptSubmit Hooks

### 5.1 Hook 执行流程

**文件**: `src/utils/processUserInput/processUserInput.ts:178-264`

```typescript
// 执行 UserPromptSubmit hooks 并处理阻塞
queryCheckpoint('query_hooks_start')
const inputMessage = getContentText(input) || ''

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
  // 返回系统级错误消息，擦除原始用户输入
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
      allowedTools: result.allowedTools,
    }
  }

  // ========== 阻止继续 ==========
  // 保留原始 prompt 在上下文中
  if (hookResult.preventContinuation) {
    const message = hookResult.stopReason
      ? `Operation stopped by hook: ${hookResult.stopReason}`
      : 'Operation stopped by hook'
    result.messages.push(
      createUserMessage({ content: message }),
    )
    result.shouldQuery = false
    return result
  }

  // ========== 额外上下文 ==========
  if (hookResult.additionalContexts?.length > 0) {
    result.messages.push(
      createAttachmentMessage({
        type: 'hook_additional_context',
        content: hookResult.additionalContexts.map(applyTruncation),
        hookName: 'UserPromptSubmit',
        toolUseID: `hook-${randomUUID()}`,
        hookEvent: 'UserPromptSubmit',
      }),
    )
  }

  // ========== Hook 成功消息 ==========
  if (hookResult.message) {
    switch (hookResult.message.attachment.type) {
      case 'hook_success':
        if (!hookResult.message.attachment.content) {
          break  // 无内容则跳过
        }
        result.messages.push({
          ...hookResult.message,
          attachment: {
            ...hookResult.message.attachment,
            content: applyTruncation(hookResult.message.attachment.content),
          },
        })
        break
      default:
        result.messages.push(hookResult.message)
        break
    }
  }
}
queryCheckpoint('query_hooks_end')
```

### 5.2 输出截断

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

**为什么截断**：
- 防止 Hook 输出过大污染上下文
- 10000 字符约 2500 tokens，合理限制
- 截断标记告知用户输出被截断

### 5.3 Hook 返回类型

**文件**: `src/utils/hooks/types.ts`

```typescript
export type UserPromptSubmitHookResult = {
  message?: AttachmentMessage | ProgressMessage
  
  // 阻塞错误 — 阻止提交，返回错误消息
  blockingError?: string
  
  // 阻止继续 — 保留原始 prompt，添加停止消息
  preventContinuation?: boolean
  stopReason?: string
  
  // 额外上下文 — 添加到对话中
  additionalContexts?: string[]
}
```

---

## 6. 图像元数据消息

### 6.1 addImageMetadataMessage

**文件**: `src/utils/processUserInput/processUserInput.ts:591-605`

```typescript
function addImageMetadataMessage(
  result: ProcessUserInputBaseResult,
  imageMetadataTexts: string[],
): ProcessUserInputBaseResult {
  if (imageMetadataTexts.length > 0) {
    result.messages.push(
      createUserMessage({
        content: imageMetadataTexts.map(text => ({ type: 'text', text })),
        isMeta: true,  // 用户不可见，仅对模型可见
      }),
    )
  }
  return result
}
```

**isMeta 消息特点**：
- 用户界面不显示
- 模型可以看到
- 用于传递技术信息 (如图像尺寸、源路径)

### 6.2 图像元数据格式

```typescript
// src/utils/imageResizer.ts

export function createImageMetadataText(
  dimensions: { width: number; height: number },
  sourcePath?: string,
): string {
  const sizeText = `[Image: ${dimensions.width}x${dimensions.height}]`
  return sourcePath ? `${sizeText} [Source: ${sourcePath}]` : sizeText
}
```

---

## 7. 设计思想总结

### 7.1 关注点分离

```
processUserInput
├── processUserInputBase (纯逻辑，无 Hook)
│   ├── 图像预处理
│   ├── 命令识别
│   └── 消息构建
│
└── UserPromptSubmit Hooks (扩展点)
    ├── 验证 Hook
    ├── 修改 Hook
    └── 上下文注入 Hook
```

### 7.2 统一返回格式

所有命令路径 (Text/Bash/Slash) 返回相同类型：
- `messages`: 消息数组
- `shouldQuery`: 是否查询模型
- `allowedTools`: 额外允许的工具
- 可选字段：`model`, `effort`, `nextInput`

这使得上层 `executeUserInput` 无需区分命令类型。

### 7.3 懒加载优化

```typescript
// 只在需要时导入
const { processBashCommand } = await import('./processBashCommand.js')
const { processSlashCommand } = await import('./processSlashCommand.js')
```

- Bash 命令不常用，懒加载减少启动时间
- Slash 命令处理复杂，懒加载减少内存占用

### 7.4 Checkpoint 打点

```typescript
queryCheckpoint('query_process_user_input_base_start')
queryCheckpoint('query_image_processing_start')
queryCheckpoint('query_image_processing_end')
queryCheckpoint('query_attachment_loading_start')
queryCheckpoint('query_attachment_loading_end')
queryCheckpoint('query_hooks_start')
queryCheckpoint('query_hooks_end')
```

**用途**：
- 性能分析
- 瓶颈定位
- 遥测数据采集

### 7.5 Pre-expansion 输入追踪

```typescript
preExpansionInput?: string  // [Pasted text #N] 展开前的输入
```

**为什么需要**：
- Ultraplan 关键词检测需要区分用户输入和粘贴内容
- 防止粘贴内容中的 "plan" 触发 Ultraplan
- 保持命令检测的准确性

---

## 8. 与其他模块的交互

```
┌─────────────────────────────────────────────────────────────┐
│                      processUserInput                       │
└───────────────────────────┬─────────────────────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
         ▼                  ▼                  ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  ImageResizer   │ │  Attachments    │ │  Hooks          │
│  - resize       │ │  - CLAUDE.md    │ │  - 验证         │
│  - downsample   │ │  - IDE 选区      │ │  - 修改         │
│  - store        │ │  - 任务/计划    │ │  - 上下文注入   │
└─────────────────┘ └─────────────────┘ └─────────────────┘
         │                  │                  │
         └──────────────────┼──────────────────┘
                            │
                            ▼
                  ┌─────────────────┐
                  │ processTextPrompt│
                  │ processBashCommand│
                  │ processSlashCommand│
                  └────────┬─────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  createUserMessage│
                  │  createAttachmentMessage│
                  └─────────────────┘
```

---

## 9. 边界情况处理

| 情况 | 处理方式 |
|------|----------|
| 只有图像无文本 | 创建仅包含图像的 UserMessage |
| 多个图像 | 并行调整大小，顺序保持不变 |
| 粘贴内容引用丢失 | 静默跳过，不报错 |
| 图像调整失败 | 使用原图，可能超过 API 限制 |
| Hook 输出过长 | 截断到 10000 字符 |
| Hook 阻塞 | 返回系统警告，保留原始 prompt |
| 远程输入 | `skipSlashCommands=true`，防止意外命令 |
| 队列中第二个命令 | `skipAttachments=true`，避免重复 |

---

## 10. 总结

`processUserInput` 是用户输入处理的核心引擎，具有以下特点：

1. **两阶段处理**：基础处理 + Hook 扩展
2. **统一返回**：所有命令路径返回相同类型
3. **懒加载优化**：按需导入不常用模块
4. **详细打点**：checkpoint 用于性能分析
5. **边界处理**：各种特殊情况都有妥善处理
6. **可扩展性**：Hook 系统支持第三方扩展

这套设计确保了从简单对话到复杂多模态输入的全场景支持。
