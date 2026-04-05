# CM-05 - Token 管理与上下文窗口

## 1. 概述

Token 管理是 Claude Code 上下文管理系统的核心约束。所有上下文管理策略（压缩、恢复、注入）都围绕 Token 预算展开。

### 1.1 核心概念

| 概念 | 描述 |
|------|------|
| **Token** | LLM 处理文本的基本单位，英文约 4 字符/token，中文约 1.5 字符/token |
| **上下文窗口** | 模型单次请求能处理的最大 token 数量 |
| **Token 预算** | 为不同用途分配的 token 配额 |
| **Prompt Cache** | 缓存 system prompt、tools 等不变内容，减少 token 消耗 |

### 1.2 Token 估算方法

```typescript
// 粗略估算：4 字符/token
export function roughTokenCountEstimation(text: string): number {
  return Math.ceil(text.length / 4)
}

// 消息数组估算
export function roughTokenCountEstimationForMessages(messages: Message[]): number {
  return roughTokenCountEstimation(jsonStringify(messages))
}

// 带估算的 token 计数（包含 API 响应）
export function tokenCountWithEstimation(messages: Message[]): number {
  const apiTokens = tokenCountFromLastAPIResponse(messages)
  const estimatedTokens = roughTokenCountEstimationForMessages(messages)
  return Math.max(apiTokens, estimatedTokens)
}
```

---

## 2. 压缩 Token 预算

### 2.1 压缩后恢复预算

```typescript
// 核心常量（src/services/compact/compact.ts）
export const POST_COMPACT_MAX_FILES_TO_RESTORE = 5      // 最多恢复 5 个文件
export const POST_COMPACT_TOKEN_BUDGET = 50_000         // 文件恢复总预算
export const POST_COMPACT_MAX_TOKENS_PER_FILE = 5_000   // 单文件预算
export const POST_COMPACT_MAX_TOKENS_PER_SKILL = 5_000  // 单 skill 预算
export const POST_COMPACT_SKILLS_TOKEN_BUDGET = 25_000  // Skills 总预算
```

### 2.2 预算分配

```
压缩后 Token 预算分配（总计约 75K+）：

┌─────────────────────────────────────────────────────────┐
│ 文件恢复预算：50,000 tokens                              │
│ ├── 最多 5 个文件                                         │
│ └── 每个文件最多 5,000 tokens                            │
├─────────────────────────────────────────────────────────┤
│ Skills 预算：25,000 tokens                               │
│ ├── 最多约 5 个 skills                                    │
│ └── 每个 skill 最多 5,000 tokens                         │
├─────────────────────────────────────────────────────────┤
│ Plan attachment：~1,000 tokens（计划文件）               │
│ Plan mode attachment：~500 tokens（模式指令）            │
│ Async agents：~500 tokens/agent（任务状态）              │
│ Delta attachments：~5,000 tokens（tools、agents、MCP）  │
│ Hook messages：~2,000 tokens（SessionStart hooks）      │
│ Summary message：~2,000 tokens（压缩摘要）               │
│ Boundary marker：~200 tokens（边界标记）                 │
└─────────────────────────────────────────────────────────┘

总计：约 85,000+ tokens（压缩后固定开销）
```

### 2.3 文件恢复预算执行

```typescript
// 1. 选择最近的文件
const recentFiles = Object.entries(readFileState)
  .filter(...)
  .sort((a, b) => b.timestamp - a.timestamp)
  .slice(0, POST_COMPACT_MAX_FILES_TO_RESTORE)  // 最多 5 个

// 2. 并行读取
const results = await Promise.all(
  recentFiles.map(async file => {
    return await generateFileAttachment(
      file.filename,
      { ...toolUseContext, fileReadingLimits: { maxTokens: POST_COMPACT_MAX_TOKENS_PER_FILE } },
      ...
    )
  }),
)

// 3. 按总预算过滤
let usedTokens = 0
return results.filter((result): result is AttachmentMessage => {
  if (result === null) return false
  const attachmentTokens = roughTokenCountEstimation(jsonStringify(result))
  if (usedTokens + attachmentTokens <= POST_COMPACT_TOKEN_BUDGET) {
    usedTokens += attachmentTokens
    return true
  }
  return false
})
```

### 2.4 Skills 预算执行

```typescript
// 1. 按调用时间排序（最近优先）
const skills = Array.from(invokedSkills.values())
  .sort((a, b) => b.invokedAt - a.invokedAt)
  
  // 2. 截断每个 skill
  .map(skill => ({
    name: skill.skillName,
    path: skill.skillPath,
    content: truncateToTokens(skill.content, POST_COMPACT_MAX_TOKENS_PER_SKILL),
  }))
  
  // 3. 按总预算过滤
  .filter(skill => {
    const tokens = roughTokenCountEstimation(skill.content)
    if (usedTokens + tokens > POST_COMPACT_SKILLS_TOKEN_BUDGET) {
      return false
    }
    usedTokens += tokens
    return true
  })
```

---

## 3. 自动压缩触发

### 3.1 触发条件

```typescript
// 当上下文 token 数量超过阈值时触发
async function autoCompactIfNeeded(): Promise<void> {
  const currentTokenCount = tokenCountWithEstimation(messages)
  
  if (currentTokenCount >= autoCompactThreshold) {
    await compactConversation(messages, context, cacheSafeParams, ..., true)
  }
}
```

### 3.2 压缩后评估

```typescript
const truePostCompactTokenCount = roughTokenCountEstimationForMessages([
  boundaryMarker,
  ...summaryMessages,
  ...postCompactFileAttachments,
  ...hookMessages,
])

const willRetriggerNextTurn =
  recompactionInfo !== undefined &&
  truePostCompactTokenCount >= recompactionInfo.autoCompactThreshold
```

**Rationale**：
- `truePostCompactTokenCount` 是压缩后实际上下文大小
- 包括 boundary、summary、attachments、hooks
- 不包括 system prompt、tools、userContext（这些通过 API usage.input_tokens 计算）
- 如果仍超过阈值，下一轮会再次触发压缩

### 3.3 Telemetry 记录

```typescript
logEvent('tengu_compact', {
  preCompactTokenCount,
  postCompactTokenCount: compactionCallTotalTokens,
  truePostCompactTokenCount,
  autoCompactThreshold: recompactionInfo?.autoCompactThreshold ?? -1,
  willRetriggerNextTurn,
  isAutoCompact,
  // ...
})
```

---

## 4. Prompt Cache 管理

### 4.1 Cache Sharing 机制

```typescript
// 压缩时使用 forked agent 复用主对话的 prompt cache
const promptCacheSharingEnabled = getFeatureValue_CACHED_MAY_BE_STALE(
  'tengu_compact_cache_prefix',
  true,  // 默认启用
)

if (promptCacheSharingEnabled) {
  const result = await runForkedAgent({
    promptMessages: [summaryRequest],
    cacheSafeParams,
    canUseTool: createCompactCanUseTool(),
    querySource: 'compact',
    forkLabel: 'compact',
    maxTurns: 1,
    skipCacheWrite: true,
  })
}
```

### 4.2 Cache Key 组成

Prompt Cache 的 key 由以下部分组成：

```
Cache Key = hash(system + tools + messages_prefix + model + thinking_config)
```

**压缩时的特殊处理**：
- Forked agent 发送与主对话相同的 cache-key params
- 不设置 `maxOutputTokens`（会改变 budget_tokens 计算，导致 cache miss）
- 复用主对话已缓存的 system prompt 和 tools

### 4.3 Cache 命中率监控

```typescript
logEvent('tengu_compact_cache_sharing_success', {
  preCompactTokenCount,
  outputTokens: result.totalUsage.output_tokens,
  cacheReadInputTokens: result.totalUsage.cache_read_input_tokens,
  cacheCreationInputTokens: result.totalUsage.cache_creation_input_tokens,
  cacheHitRate:
    result.totalUsage.cache_read_input_tokens > 0
      ? result.totalUsage.cache_read_input_tokens /
        (result.totalUsage.cache_read_input_tokens +
          result.totalUsage.cache_creation_input_tokens +
          result.totalUsage.input_tokens)
      : 0,
})
```

### 4.4 实验数据

```
实验（Jan 2026）发现：
- promptCacheSharingEnabled = false：98% cache miss
- 每天浪费约 38B tokens（~0.76% fleet cache_creation）
- 主要集中在 ephemeral envs（CCR/GHA/SDK）
  - 冷 GB cache
  - 3P providers 禁用 GrowthBook

结论：默认启用 cache sharing（true）
```

---

## 5. 上下文窗口控制策略

### 5.1 多层级控制

```
┌─────────────────────────────────────────────────────────┐
│                    上下文窗口控制                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  L1: 系统 Prompt + Tools                                │
│      - System prompt: ~4KB（基础）+ 指令注入             │
│      - Tools schema: ~10-20KB（取决于工具数量）          │
│      - MCP tools: ~5-10KB（额外工具）                    │
│      - 这部分通过 prompt cache 缓存                       │
│                                                         │
│  L2: 用户上下文（CLAUDE.md + 系统信息）                 │
│      - CLAUDE.md: 可变，取决于层级和@include            │
│      - Git status: ~1KB                                 │
│      - Current date: ~50 tokens                         │
│      - 通常总计：5-20KB                                 │
│                                                         │
│  L3: 会话历史                                           │
│      - 用户消息 + 助手响应                               │
│      - Attachments（文件、技能、计划）                   │
│      - 这是压缩的主要对象                                │
│                                                         │
│  L4: 当前请求                                           │
│      - 当前用户输入                                     │
│      - 当前 attachments                                  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 5.2 最大输出 Token 控制

```typescript
// 压缩时的输出 token 限制
const maxOutputTokensOverride = Math.min(
  COMPACT_MAX_OUTPUT_TOKENS,  // 压缩特定限制
  getMaxOutputTokensForModel(context.options.mainLoopModel),
)
```

### 5.3 图像剥离优化

```typescript
// 压缩时剥离图像块，替换为文本标记
export function stripImagesFromMessages(messages: Message[]): Message[] {
  return messages.map(message => {
    if (message.type !== 'user') return message
    
    const content = message.message.content
    if (!Array.isArray(content)) return message
    
    const newContent = content.flatMap(block => {
      if (block.type === 'image') {
        return [{ type: 'text' as const, text: '[image]' }]
      }
      if (block.type === 'document') {
        return [{ type: 'text' as const, text: '[document]' }]
      }
      // 处理 tool_result 内层的图像
      if (block.type === 'tool_result' && Array.isArray(block.content)) {
        const newToolContent = block.content.map(item => {
          if (item.type === 'image') {
            return { type: 'text' as const, text: '[image]' }
          }
          return item
        })
        return [{ ...block, content: newToolContent }]
      }
      return [block]
    })
    
    return { ...message, message: { ...message.message, content: newContent } }
  })
}
```

**收益**：
- 图像块不帮助生成摘要
- 防止压缩请求本身触发 prompt-too-long
- 在 CCD  sessions 中尤其重要（用户频繁附加图像）

---

## 6. Prompt Too Long 处理

### 6.1 错误检测

```typescript
const PROMPT_TOO_LONG_ERROR_MESSAGE = 'Conversation too long. Press esc twice to go up a few messages and try again.'

// 检测 prompt too long 错误
function getPromptTooLongTokenGap(ptlResponse: AssistantMessage): number | undefined {
  // 从错误消息中解析 gap
  const match = ptlResponse.message.content?.match(/prompt too long by (\d+) tokens/)
  if (match) {
    return parseInt(match[1])
  }
  return undefined  // 无法解析（某些 Vertex/Bedrock 格式）
}
```

### 6.2 重试策略

```typescript
const MAX_PTL_RETRIES = 3
const PTL_RETRY_MARKER = '[earlier conversation truncated for compaction retry]'

let ptlAttempts = 0
for (;;) {
  summaryResponse = await streamCompactSummary({ ... })
  summary = getAssistantMessageText(summaryResponse)
  
  if (!summary?.startsWith(PROMPT_TOO_LONG_ERROR_MESSAGE)) break
  
  ptlAttempts++
  const truncated =
    ptlAttempts <= MAX_PTL_RETRIES
      ? truncateHeadForPTLRetry(messagesToSummarize, summaryResponse)
      : null
  
  if (!truncated) {
    throw new Error(ERROR_MESSAGE_PROMPT_TOO_LONG)
  }
  
  messagesToSummarize = truncated
}
```

### 6.3 截断逻辑

```typescript
export function truncateHeadForPTLRetry(
  messages: Message[],
  ptlResponse: AssistantMessage,
): Message[] | null {
  const groups = groupMessagesByApiRound(input)
  if (groups.length < 2) return null
  
  const tokenGap = getPromptTooLongTokenGap(ptlResponse)
  let dropCount: number
  
  if (tokenGap !== undefined) {
    // 有明确 gap：累加直到覆盖
    let acc = 0
    dropCount = 0
    for (const g of groups) {
      acc += roughTokenCountEstimationForMessages(g)
      dropCount++
      if (acc >= tokenGap) break
    }
  } else {
    // 无法解析 gap：回退到丢弃 20%
    dropCount = Math.max(1, Math.floor(groups.length * 0.2))
  }
  
  // 至少保留一组
  dropCount = Math.min(dropCount, groups.length - 1)
  if (dropCount < 1) return null
  
  const sliced = groups.slice(dropCount).flat()
  
  //  prepend synthetic marker if needed
  if (sliced[0]?.type === 'assistant') {
    return [
      createUserMessage({ content: PTL_RETRY_MARKER, isMeta: true }),
      ...sliced,
    ]
  }
  return sliced
}
```

---

## 7. Token 统计与 Telemetry

### 7.1 完整压缩事件

```typescript
logEvent('tengu_compact', {
  // Token 统计
  preCompactTokenCount,
  postCompactTokenCount: compactionCallTotalTokens,  // compact API 调用总用量
  truePostCompactTokenCount,  // 压缩后实际上下文大小
  
  // Compact API 用量细分
  compactionInputTokens,
  compactionOutputTokens,
  compactionCacheReadTokens,
  compactionCacheCreationTokens,
  compactionTotalTokens: compactionInputTokens + compactionOutputTokens,
  
  // Context 组成分析
  ...tokenStatsToStatsigMetrics(analyzeContext(messages)),
})
```

### 7.2 Context 分析

```typescript
// analyzeContext 遍历每个内容块，统计组成
export function analyzeContext(messages: Message[]): TokenStats {
  let fileTokens = 0
  let skillTokens = 0
  let toolTokens = 0
  let userTokens = 0
  let assistantTokens = 0
  
  for (const message of messages) {
    // 遍历 content blocks
    for (const block of message.message?.content || []) {
      if (block.type === 'tool_result') {
        fileTokens += roughTokenCountEstimation(block.content)
      }
      // ... 其他类型
    }
  }
  
  return { fileTokens, skillTokens, toolTokens, userTokens, assistantTokens }
}
```

**性能注意**：
```typescript
// analyzeContext 遍历每个内容块（~11ms on 4.5K messages）
// 在 compact API call await 之后执行，避免阻塞渲染
const contextStats = await compactConversation(...)
const stats = tokenStatsToStatsigMetrics(analyzeContext(messages))
```

---

## 8. 重新注入 Attachments 的 Token 优化

### 8.1 Skill Listing 不重置

```typescript
// Intentionally NOT resetting sentSkillNames
// 理由：重新注入完整的 skill_listing (~4K tokens) 每次压缩都是纯粹的 cache_creation，
// 边际效益低。模型仍然有 SkillTool schema 和 invoked_skills attachment。
```

**节省**：每次压缩节省约 4K tokens 的 cache_creation

### 8.2 Reinjected Attachments 剥离

```typescript
export function stripReinjectedAttachments(messages: Message[]): Message[] {
  if (feature('EXPERIMENTAL_SKILL_SEARCH')) {
    return messages.filter(
      m =>
        !(
          m.type === 'attachment' &&
          (m.attachment.type === 'skill_discovery' ||
            m.attachment.type === 'skill_listing')
        ),
    )
  }
  return messages
}
```

**Rationale**：
- `skill_discovery`/`skill_listing` 会在压缩后重新注入
- 压缩时保留它们会浪费 tokens
- 污染摘要（包含过时的 skill 建议）

---

## 9. 总结

Token 管理系统的核心策略：

| 策略 | 描述 |
|------|------|
| 预算分配 | 文件恢复 50K、Skills 25K、单文件/单 skill 5K |
| 自动压缩 | 超过阈值触发，压缩后评估是否重触发 |
| Prompt Cache | Forked agent 复用 cache prefix，默认启用 |
| 输出控制 | maxOutputTokens 限制压缩响应长度 |
| 内容剥离 | 图像、reinjected attachments |
| PTL 重试 | 最多 3 次截断重试 |
| Token 统计 | 详细的用量细分和 context 分析 |
| 优化技巧 | sentSkillNames 不重置、diff against preserved |

这套系统确保了在有限 token 预算内，最大化有用上下文的保留，同时通过 cache sharing、内容剥离等策略降低成本。
