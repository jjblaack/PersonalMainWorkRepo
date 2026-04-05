# Claude Code 项目分析 - 查询引擎与 LLM 集成

> 本文档深入分析 Claude Code 的查询引擎，这是与 Anthropic API 交互的核心组件，负责处理所有 LLM 调用。

---

## 目录

1. [查询引擎概述](#1-查询引擎概述)
2. [QueryEngine.ts 详细分析](#2-queryenginets-详细分析)
3. [LLM API 调用流程](#3-llm-api-调用流程)
4. [流式响应处理](#4-流式响应处理)
5. [Tool Call 循环机制](#5-tool-call-循环机制)
6. [思考模式](#6-思考模式)
7. [重试逻辑](#7-重试逻辑)
8. [Token 计数与追踪](#8-token 计数与追踪)
9. [错误处理](#9-错误处理)
10. [query.ts 分析](#10-queryts-分析)

---

## 1. 查询引擎概述

### 1.1 查询引擎的职责

QueryEngine 是 Claude Code 与 Anthropic API 交互的核心组件，负责：

- 构建和发送 API 请求
- 处理流式响应
- 管理 Tool Call 循环
- 追踪 Token 使用和成本
- 处理错误和重试
- 支持思考模式

### 1.2 核心文件

| 文件 | 行数 | 职责 |
|------|------|------|
| QueryEngine.ts | ~1,295 | 查询引擎主逻辑 |
| query.ts | ~2,000+ | 高层查询接口 |
| cost-tracker.ts | ~300+ | 成本追踪 |

### 1.3 在系统中的地位

```
┌─────────────────────────────────────────────────────────────┐
│  用户输入 / 命令                                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  commands.ts / tools.ts                                      │
│  (命令/工具调用)                                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  QueryEngine.ts                                              │
│  (查询引擎 - 本文档核心)                                      │
│  - 构建 API 请求                                              │
│  - 处理流式响应                                               │
│  - Tool Call 循环                                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Anthropic API                                               │
│  - messages.create()                                         │
│  - 流式响应                                                  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  components/                                                 │
│  (UI 渲染响应)                                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. QueryEngine.ts 详细分析

### 2.1 文件概况

**位置**: `src/QueryEngine.ts`
**行数**: ~1,295 行
**导入依赖**: ~85 个

### 2.2 核心类结构

```typescript
// QueryEngine 类结构 (推断)

class QueryEngine {
  // 配置
  private model: string;
  private maxTokens: number;
  private systemPrompt: string;
  private temperature: number;
  
  // 状态
  private conversation: SDKMessage[];
  private tokenCount: TokenCount;
  private cost: number;
  
  // 工具
  private tools: Tools;
  private canUseTool: CanUseToolFn;
  
  // 回调
  private onMessage: (message: Message) => void;
  private onProgress: (progress: string) => void;
  private onError: (error: Error) => void;
  
  // 核心方法
  async send(messages: SDKMessage[], options: QueryOptions) {
    // 1. 构建请求
    const request = this.buildRequest(messages);
    
    // 2. 发送 API 请求
    const response = await this.callAPI(request);
    
    // 3. 处理响应
    return this.handleResponse(response);
  }
  
  private buildRequest(messages: SDKMessage[]): APIRequest {
    // 构建 API 请求体
    return {
      model: this.model,
      max_tokens: this.maxTokens,
      messages: this.formatMessages(messages),
      system: this.systemPrompt,
      tools: this.getToolSchemas(),
      stream: true,
    };
  }
  
  private async callAPI(request: APIRequest) {
    // 调用 Anthropic API
    return anthropic.messages.create(request);
  }
  
  private async handleResponse(response: APIResponse) {
    // 处理流式响应
    for await (const chunk of response.stream) {
      this.handleChunk(chunk);
    }
  }
}
```

### 2.3 关键导入

```typescript
// src/QueryEngine.ts:1-100

// 特性标志
import { feature } from 'bun:bundle';

// API 和成本追踪
import { accumulateUsage, updateUsage } from './services/api/claude.js';
import { getModelUsage, getTotalAPIDuration, getTotalCost } from './cost-tracker.js';

// 消息处理
import { localCommandOutputToSDKAssistantMessage } from './utils/messages/mappers.js';
import { buildSystemInitMessage } from './utils/messages/systemInit.js';
import { countToolCalls } from './utils/messages.js';

// 模型管理
import { getMainLoopModel, parseUserSpecifiedModel } from './utils/model/model.js';

// 系统提示
import { fetchSystemPromptParts } from './utils/queryContext.js';
import { asSystemPrompt } from './utils/systemPromptType.js';

// 思考模式
import { shouldEnableThinkingByDefault, type ThinkingConfig } from './utils/thinking.js';
```

---

## 3. LLM API 调用流程

### 3.1 请求构建流程

```typescript
// API 请求构建 (推断)

interface APIRequest {
  model: string;                                    // 模型名称
  max_tokens: number;                               // 最大 token 数
  messages: FormattedMessage[];                     // 消息列表
  system: string;                                   // 系统提示
  tools: ToolSchema[];                              // 工具 Schema
  tool_choice?: { type: string; name?: string };    // 工具选择
  stream: boolean;                                  // 流式响应
  thinking?: { type: string };                      // 思考模式配置
}

function buildRequest(messages: SDKMessage[], options: QueryOptions): APIRequest {
  return {
    // 模型
    model: options.model || 'claude-sonnet-4-20250514',
    
    // Token 限制
    max_tokens: options.maxTokens || 8192,
    
    // 消息格式化
    messages: messages.map(msg => ({
      role: msg.role,
      content: formatContent(msg.content),
    })),
    
    // 系统提示
    system: buildSystemPrompt(options.systemPromptParts),
    
    // 工具 Schema
    tools: getTools().map(tool => ({
      name: tool.name,
      description: tool.description,
      input_schema: tool.inputSchema,
    })),
    
    // 流式响应
    stream: true,
    
    // 思考模式 (如果启用)
    thinking: options.thinking && { type: 'enabled' },
  };
}
```

### 3.2 消息格式化

```typescript
// 消息格式转换 (推断)

function formatMessages(messages: SDKMessage[]): FormattedMessage[] {
  return messages.map(msg => {
    switch (msg.role) {
      case 'user':
        return {
          role: 'user',
          content: formatUserContent(msg.content),
        };
      
      case 'assistant':
        return {
          role: 'assistant',
          content: formatAssistantContent(msg.content),
        };
      
      case 'system':
        // 系统消息特殊处理
        return null;  // 系统消息放入 system 字段
      
      default:
        throw new Error(`Unknown role: ${msg.role}`);
    }
  }).filter(Boolean);
}

function formatUserContent(content: Content): ContentBlockParam[] {
  if (typeof content === 'string') {
    return [{ type: 'text', text: content }];
  }
  
  if (Array.isArray(content)) {
    return content.map(block => {
      if (block.type === 'image') {
        return {
          type: 'image',
          source: {
            type: 'base64',
            media_type: block.media_type,
            data: block.data,
          },
        };
      }
      return block;
    });
  }
  
  return content;
}
```

### 3.3 系统提示构建

```typescript
// 系统提示构建 (推断)

async function buildSystemPrompt(parts: SystemPromptParts): Promise<string> {
  const sections = [];
  
  // 1. 基础系统提示
  sections.push(BASE_SYSTEM_PROMPT);
  
  // 2. 工具描述
  sections.push(formatToolDescriptions(parts.tools));
  
  // 3. 记忆提示 (如果启用)
  if (parts.memory) {
    const memoryPrompt = await loadMemoryPrompt(parts.memoryDir);
    sections.push(memoryPrompt);
  }
  
  // 4. 项目特定提示 (CLAUDE.md)
  if (parts.projectContext) {
    sections.push(formatProjectContext(parts.projectContext));
  }
  
  // 5. 技能提示
  if (parts.skills) {
    sections.push(formatSkills(parts.skills));
  }
  
  return sections.join('\n\n');
}
```

---

## 4. 流式响应处理

### 4.1 流式事件类型

```typescript
// Anthropic API 流式事件 (推断)

type StreamEvent =
  | { type: 'message_start'; message: Message }
  | { type: 'content_block_start'; index: number; content_block: ContentBlock }
  | { type: 'content_block_delta'; index: number; delta: Delta }
  | { type: 'content_block_stop'; index: number }
  | { type: 'message_delta'; delta: Delta; usage: Usage }
  | { type: 'message_stop' }
  | { type: 'error'; error: Error };

type Delta =
  | { type: 'text_delta'; text: string }
  | { type: 'input_json_delta'; partial_json: string }
  | { type: 'thinking_delta'; thinking: string }
  | { type: 'signature_delta'; signature: string };
```

### 4.2 流式处理实现

```typescript
// 流式响应处理 (推断)

async function handleStream(response: APIResponse, callbacks: Callbacks) {
  let currentContent = '';
  let currentToolCall: ToolCall | null = null;
  let thinkingContent = '';
  
  for await (const event of response.stream) {
    switch (event.type) {
      case 'message_start':
        callbacks.onStart?.(event.message);
        break;
      
      case 'content_block_start':
        if (event.content_block.type === 'tool_use') {
          currentToolCall = {
            id: event.content_block.id,
            name: event.content_block.name,
            input: '',
          };
        }
        break;
      
      case 'content_block_delta':
        const delta = event.delta;
        
        if (delta.type === 'text_delta') {
          currentContent += delta.text;
          callbacks.onText?.(delta.text);
        }
        
        if (delta.type === 'input_json_delta') {
          if (currentToolCall) {
            currentToolCall.input += delta.partial_json;
          }
        }
        
        if (delta.type === 'thinking_delta') {
          thinkingContent += delta.thinking;
          callbacks.onThinking?.(delta.thinking);
        }
        break;
      
      case 'content_block_stop':
        if (currentToolCall) {
          callbacks.onToolCall?.({
            ...currentToolCall,
            input: JSON.parse(currentToolCall.input || '{}'),
          });
          currentToolCall = null;
        }
        break;
      
      case 'message_delta':
        callbacks.onUsage?.(event.usage);
        break;
      
      case 'message_stop':
        callbacks.onComplete?.();
        break;
      
      case 'error':
        callbacks.onError?.(event.error);
        break;
    }
  }
}
```

### 4.3 增量输出渲染

```typescript
// 增量渲染到终端 (推断)

function createStreamingRenderer() {
  let lines = 0;
  
  return {
    onText(text: string) {
      // 增量显示文本
      process.stdout.write(text);
    },
    
    onThinking(thinking: string) {
      // 显示思考内容 (如果启用)
      if (config.showThinking) {
        process.stdout.write(chalk.gray(thinking));
      }
    },
    
    onToolCall(toolCall: ToolCall) {
      // 显示工具调用
      console.log(`\n🔧 Using ${toolCall.name}...`);
    },
    
    onComplete() {
      console.log();  // 换行
    },
  };
}
```

---

## 5. Tool Call 循环机制

### 5.1 Tool Call 检测

```typescript
// Tool Call 检测 (推断)

function hasToolCalls(response: APIResponse): boolean {
  return response.content.some(block => block.type === 'tool_use');
}

function extractToolCalls(response: APIResponse): ToolCall[] {
  return response.content
    .filter(block => block.type === 'tool_use')
    .map(block => ({
      id: block.id,
      name: block.name,
      input: block.input,
    }));
}
```

### 5.2 Tool Call 循环实现

```typescript
// Tool Call 循环 (推断)

async function processWithToolCallLoop(
  initialMessages: SDKMessage[],
  options: QueryOptions
): Promise<FinalResponse> {
  let messages = [...initialMessages];
  let continueLoop = true;
  let iterationCount = 0;
  const maxIterations = options.maxToolCallIterations || 10;
  
  while (continueLoop && iterationCount < maxIterations) {
    iterationCount++;
    
    // 1. 发送请求
    const response = await queryEngine.send(messages, options);
    
    // 2. 检查是否有 Tool Call
    const toolCalls = extractToolCalls(response);
    
    if (toolCalls.length === 0) {
      // 没有 Tool Call，返回最终响应
      return {
        content: response.content,
        usage: response.usage,
      };
    }
    
    // 3. 执行工具
    const toolResults = await Promise.all(
      toolCalls.map(async (toolCall) => {
        // 查找工具
        const tool = findTool(toolCall.name);
        if (!tool) {
          return {
            tool_use_id: toolCall.id,
            content: [{ type: 'text', text: `Unknown tool: ${toolCall.name}` }],
            is_error: true,
          };
        }
        
        // 执行工具
        try {
          const result = await tool.execute(toolCall.input, {
            sessionId: options.sessionId,
            onProgress: (progress) => {
              options.onProgress?.(progress);
            },
          });
          
          return {
            tool_use_id: toolCall.id,
            content: result.content,
            is_error: !result.success,
          };
        } catch (error) {
          return {
            tool_use_id: toolCall.id,
            content: [{ type: 'text', text: errorMessage(error) }],
            is_error: true,
          };
        }
      })
    );
    
    // 4. 添加工具结果到消息
    messages = [
      ...messages,
      {
        role: 'assistant',
        content: response.content,
      },
      {
        role: 'user',
        content: toolResults.map(result => ({
          type: 'tool_result',
          ...result,
        })),
      },
    ];
    
    // 5. 继续循环
    continueLoop = true;
  }
  
  // 达到最大迭代次数
  throw new Error('Max tool call iterations reached');
}
```

### 5.3 循环终止条件

```typescript
// 循环终止条件 (推断)

function shouldContinueLoop(response: APIResponse, state: LoopState): boolean {
  // 1. 检查是否有 Tool Call
  if (!hasToolCalls(response)) {
    return false;  // 没有工具调用，结束
  }
  
  // 2. 检查迭代次数
  if (state.iterationCount >= state.maxIterations) {
    return false;  // 达到最大迭代次数
  }
  
  // 3. 检查 token 使用
  if (state.tokenUsage >= state.maxTokens) {
    return false;  // 达到 token 限制
  }
  
  // 4. 检查是否重复调用相同工具 (防止死循环)
  if (isRepeatingToolCall(response, state.history)) {
    return false;  // 检测到重复
  }
  
  return true;  // 继续循环
}
```

---

## 6. 思考模式 (Thinking Mode)

### 6.1 思考模式概述

思考模式允许模型在生成响应之前先进行"思考"，显示推理过程。

### 6.2 思考模式配置

```typescript
// 思考模式配置 (推断)

interface ThinkingConfig {
  enabled: boolean;           // 是否启用
  budget_tokens?: number;     // 思考 token 预算
}

function getThinkingConfig(model: string, options: QueryOptions): ThinkingConfig {
  // 某些模型默认启用思考
  if (shouldEnableThinkingByDefault(model)) {
    return {
      enabled: true,
      budget_tokens: options.thinkingBudget || 1024,
    };
  }
  
  // 用户显式启用
  if (options.enableThinking) {
    return { enabled: true, budget_tokens: options.thinkingBudget };
  }
  
  return { enabled: false };
}
```

### 6.3 思考内容处理

```typescript
// 思考内容处理 (推断)

function handleThinkingDelta(thinking: string, callbacks: Callbacks) {
  // 累积思考内容
  state.thinkingContent += thinking;
  
  // 显示思考内容 (如果配置允许)
  if (config.showThinking) {
    // 以灰色显示在终端
    process.stdout.write(chalk.gray(thinking));
  }
  
  // 发送到 UI
  callbacks.onThinking?.(thinking);
}
```

---

## 7. 重试逻辑

### 7.1 错误分类

```typescript
// 错误分类 (推断)

type APIErrorType =
  | 'RATE_LIMIT'          // 速率限制
  | 'SERVER_ERROR'        // 服务器错误 (5xx)
  | 'TIMEOUT'             // 超时
  | 'CONNECTION_ERROR'    // 连接错误
  | 'INVALID_REQUEST'     // 无效请求 (4xx)
  | 'AUTH_ERROR';         // 认证错误

function categorizeError(error: unknown): APIErrorType {
  if (error.status === 429) return 'RATE_LIMIT';
  if (error.status >= 500) return 'SERVER_ERROR';
  if (error.code === 'ETIMEDOUT') return 'TIMEOUT';
  if (error.code === 'ECONNRESET') return 'CONNECTION_ERROR';
  if (error.status === 401) return 'AUTH_ERROR';
  if (error.status >= 400) return 'INVALID_REQUEST';
  return 'UNKNOWN';
}
```

### 7.2 重试策略

```typescript
// 重试策略 (推断)

interface RetryConfig {
  maxRetries: number;
  baseDelay: number;
  maxDelay: number;
  retryableErrors: APIErrorType[];
}

const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxRetries: 3,
  baseDelay: 1000,      // 1 秒
  maxDelay: 30000,      // 30 秒
  retryableErrors: ['RATE_LIMIT', 'SERVER_ERROR', 'TIMEOUT', 'CONNECTION_ERROR'],
};

async function withRetry<T>(
  fn: () => Promise<T>,
  config: RetryConfig = DEFAULT_RETRY_CONFIG
): Promise<T> {
  let lastError: unknown;
  
  for (let attempt = 0; attempt <= config.maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      const errorType = categorizeError(error);
      
      // 检查是否可重试
      if (!config.retryableErrors.includes(errorType)) {
        throw error;  // 不可重试的错误，直接抛出
      }
      
      // 达到最大重试次数
      if (attempt === config.maxRetries) {
        throw error;
      }
      
      // 计算延迟 (指数退避 + 抖动)
      const delay = Math.min(
        config.baseDelay * Math.pow(2, attempt),
        config.maxDelay
      );
      const jitter = Math.random() * 0.3 * delay;
      
      console.log(`Retry attempt ${attempt + 1}/${config.maxRetries} in ${Math.round(delay + jitter)}ms`);
      
      await sleep(delay + jitter);
    }
  }
  
  throw lastError;
}
```

### 7.3 速率限制处理

```typescript
// 速率限制特殊处理 (推断)

async function handleRateLimit(error: RateLimitError): Promise<void> {
  // 从响应头获取重试时间
  const retryAfter = error.headers?.['retry-after'];
  
  if (retryAfter) {
    const delay = parseRetryAfter(retryAfter);
    console.log(`Rate limited. Retrying after ${delay}s`);
    await sleep(delay * 1000);
  } else {
    // 默认退避
    await sleep(5000);
  }
}
```

---

## 8. Token 计数与追踪

### 8.1 Token 使用追踪

```typescript
// Token 追踪 (推断)

interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
  cache_read_input_tokens?: number;
  cache_creation_input_tokens?: number;
}

interface AccumulatedUsage {
  total_input: number;
  total_output: number;
  total_cache_read: number;
  total_cache_write: number;
  total_tokens: number;
}

function accumulateUsage(current: TokenUsage, accumulated: AccumulatedUsage): AccumulatedUsage {
  return {
    total_input: accumulated.total_input + current.input_tokens,
    total_output: accumulated.total_output + current.output_tokens,
    total_cache_read: accumulated.total_cache_read + (current.cache_read_input_tokens || 0),
    total_cache_write: accumulated.total_cache_write + (current.cache_creation_input_tokens || 0),
    total_tokens: accumulated.total_tokens + current.input_tokens + current.output_tokens,
  };
}
```

### 8.2 成本计算

```typescript
// 成本追踪 (推断)

// src/cost-tracker.ts

interface ModelPricing {
  input_price_per_million: number;
  output_price_per_million: number;
  cache_read_price_per_million?: number;
  cache_write_price_per_million?: number;
}

const PRICING: Record<string, ModelPricing> = {
  'claude-sonnet-4-20250514': {
    input_price_per_million: 3.0,
    output_price_per_million: 15.0,
  },
  'claude-opus-4-20250514': {
    input_price_per_million: 15.0,
    output_price_per_million: 75.0,
  },
  // ... 更多模型
};

function calculateCost(usage: TokenUsage, model: string): number {
  const pricing = PRICING[model];
  if (!pricing) return 0;
  
  const inputCost = (usage.input_tokens / 1_000_000) * pricing.input_price_per_million;
  const outputCost = (usage.output_tokens / 1_000_000) * pricing.output_price_per_million;
  
  let cacheCost = 0;
  if (usage.cache_read_input_tokens) {
    cacheCost += (usage.cache_read_input_tokens / 1_000_000) * (pricing.cache_read_price_per_million || 0);
  }
  if (usage.cache_creation_input_tokens) {
    cacheCost += (usage.cache_creation_input_tokens / 1_000_000) * (pricing.cache_write_price_per_million || 0);
  }
  
  return inputCost + outputCost + cacheCost;
}
```

### 8.3 成本显示

```typescript
// 成本显示 (推断)

function formatCost(cost: number): string {
  if (cost < 0.01) {
    return `$${cost.toFixed(4)}`;
  }
  return `$${cost.toFixed(2)}`;
}

// 在 UI 中显示
function renderCostDisplay(usage: TokenUsage, model: string) {
  const cost = calculateCost(usage, model);
  const totalTokens = usage.input_tokens + usage.output_tokens;
  
  return (
    <Box>
      <Text>Tokens: {totalTokens.toLocaleString()}</Text>
      <Text>Cost: {formatCost(cost)}</Text>
    </Box>
  );
}
```

---

## 9. 错误处理

### 9.1 错误类型

```typescript
// 错误类型定义 (推断)

class APIError extends Error {
  status?: number;
  code?: string;
  headers?: Record<string, string>;
}

class RateLimitError extends APIError {
  status = 429;
}

class ServerError extends APIError {
  status: number;  // 500-599
}

class TimeoutError extends APIError {
  code = 'ETIMEDOUT';
}

class AuthenticationError extends APIError {
  status = 401;
}
```

### 9.2 错误消息格式化

```typescript
// 错误消息处理 (推断)

function formatErrorMessage(error: unknown): string {
  if (error instanceof APIError) {
    switch (error.status) {
      case 401:
        return 'Authentication failed. Please check your API key.';
      case 403:
        return 'Access denied. Check your permissions.';
      case 429:
        return 'Rate limit exceeded. Please wait before retrying.';
      case 500:
      case 502:
      case 503:
        return 'API server error. Please try again later.';
      default:
        return `API error: ${error.message}`;
    }
  }
  
  if (error instanceof TimeoutError) {
    return 'Request timed out. Please check your connection.';
  }
  
  if (error instanceof Error) {
    return error.message;
  }
  
  return 'An unknown error occurred';
}
```

---

## 10. query.ts 分析

### 10.1 高层查询接口

```typescript
// src/query.ts (简化推断)

/**
 * 高层查询函数
 */
export async function query(
  messages: SDKMessage[],
  options: QueryOptions = {}
): Promise<QueryResult> {
  // 1. 创建查询引擎实例
  const engine = new QueryEngine({
    model: options.model || getDefaultModel(),
    maxTokens: options.maxTokens,
    systemPrompt: options.systemPrompt,
  });
  
  // 2. 执行查询
  const result = await engine.send(messages, {
    ...options,
    onProgress: options.onProgress,
    onToolCall: options.onToolCall,
  });
  
  // 3. 记录使用
  recordUsage(result.usage);
  
  return result;
}

/**
 * 简化的查询函数 (用于工具内部调用)
 */
export async function simpleQuery(
  prompt: string,
  options: SimpleQueryOptions = {}
): Promise<string> {
  const result = await query([
    { role: 'user', content: prompt },
  ], options);
  
  return extractTextContent(result.content);
}
```

---

## 总结

QueryEngine 是 Claude Code 与 LLM 交互的核心桥梁，具有以下特点：

1. **流式处理**: 实时显示响应内容
2. **Tool Call 循环**: 自动处理多轮工具调用
3. **重试机制**: 优雅处理 API 错误
4. **成本追踪**: 实时计算和显示成本
5. **思考模式**: 支持显示推理过程
6. **错误处理**: 友好的错误消息

这个引擎使得 Claude Code 能够高效、可靠地与 Anthropic API 通信，为用户提供流畅的交互体验。

---

*最后更新：2026-04-02*
