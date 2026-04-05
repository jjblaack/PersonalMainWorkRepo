# Claude Code 项目分析 - Bridge 桥接系统

> 本文档深度分析 Claude Code 的 Bridge 桥接系统，包括远程会话建立、认证机制、消息传递和与 REPL 的集成。

---

## 目录

1. [Bridge 系统概述](#1-bridge-系统概述)
2. [核心架构](#2-核心架构)
3. [远程会话建立](#3-远程会话建立)
4. [认证与 JWT 机制](#4-认证与 jwt-机制)
5. [消息传递协议](#5-消息传递协议)
6. [与 REPL 集成](#6-与-repl-集成)
7. [类型定义](#7-类型定义)
8. [关键组件分析](#8-关键组件分析)

---

## 1. Bridge 系统概述

### 1.1 设计目标

Bridge 桥接系统是 Claude Code 的远程会话核心组件，实现以下目标：

| 目标 | 说明 |
|------|------|
| **远程访问** | 通过 claude.ai 界面控制本地代码环境 |
| **双向通信** | 本地 CLI 与远程服务实时同步 |
| **安全认证** | OAuth + JWT 多层认证机制 |
| **会话管理** | 支持多会话并发和生命周期管理 |
| **故障恢复** | 自动重连和令牌刷新机制 |

### 1.2 使用场景

```
远程用户 (claude.ai)
       │
       │ WebSocket
       ▼
Claude.ai 服务器
       │
       │ 工作轮询
       ▼
本地 Bridge 循环
       │
       │ 工具执行
       ▼
本地文件系统/命令
```

---

## 2. 核心架构

### 2.1 组件层次

```
┌─────────────────────────────────────────────────────────────┐
│  Bridge Main (bridgeMain.ts)                                │
│  - 环境注册                                                  │
│  - 工作轮询                                                  │
│  - 会话管理                                                  │
│  - 心跳维护                                                  │
└─────────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐
│ Bridge API      │ │ Bridge      │ │ JWT Utils       │
│ (bridgeApi.ts)  │ │ Messaging   │ │ (jwtUtils.ts)   │
│ - 环境注册       │ │ (bridgeMsg) │ │ - Token 解码     │
│ - 工作轮询       │ │ - 消息解析   │ │ - Token 刷新     │
│ - 心跳发送       │ │ - 事件路由   │ │ - 过期检查       │
└─────────────────┘ └─────────────┘ └─────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  REPL Bridge (replBridge.ts)                                │
│  - 双向同步                                                  │
│  - 控制命令处理                                              │
│  - 历史记录同步                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 目录结构

```
src/bridge/
├── bridgeApi.ts                 # Bridge API 客户端
├── bridgeConfig.ts              # Bridge 配置
├── bridgeDebug.ts               # 调试工具
├── bridgeEnabled.ts             # Bridge 启用检查
├── bridgeMain.ts                # 主循环控制器
├── bridgeMessaging.ts           # 消息处理
├── bridgePermissionCallbacks.ts # 权限回调
├── bridgePointer.ts             # 指针工具
├── bridgeStatusUtil.ts          # 状态工具
├── bridgeUI.ts                  # Bridge UI
├── capacityWake.ts              # 容量唤醒
├── codeSessionApi.ts            # 代码会话 API
├── createSession.ts             # 会话创建
├── debugUtils.ts                # 调试工具
├── envLessBridgeConfig.ts       # 无 env 配置
├── flushGate.ts                 # 刷新门控
├── inboundAttachments.ts        # 入站附件
├── inboundMessages.ts           # 入站消息
├── initReplBridge.ts            # 初始化 REPL Bridge
├── jwtUtils.ts                  # JWT 工具
├── pollConfig.ts                # 轮询配置
├── pollConfigDefaults.ts        # 默认轮询配置
├── remoteBridgeCore.ts          # 远程核心
├── replBridge.ts                # REPL Bridge
├── replBridgeHandle.ts          # REPL Bridge 句柄
├── replBridgeTransport.ts       # REPL Bridge 传输
├── sessionIdCompat.ts           # 会话 ID 兼容
├── sessionRunner.ts             # 会话运行器
├── trustedDevice.ts             # 可信设备
├── types.ts                     # 类型定义
├── workSecret.ts                # 工作密钥
└── index.ts                     # 入口
```

---

## 3. 远程会话建立

### 3.1 环境注册流程

```typescript
// src/bridge/bridgeApi.ts (简化)

export async function registerBridgeEnvironment(
  oauthToken: string,
  config: BridgeConfig,
): Promise<EnvironmentRegistration> {
  const response = await fetch('/api/bridge/register', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${oauthToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      machine_name: config.machineName,
      branch: config.branch,
      git_repo_url: config.gitRepoUrl,
      max_sessions: config.maxSessions,
      spawn_mode: config.spawnMode,
    }),
  })
  
  const data = await response.json()
  
  return {
    environmentId: data.environment_id,
    environmentSecret: data.environment_secret,
  }
}
```

### 3.2 工作轮询

```typescript
// src/bridge/bridgeMain.ts (简化)

export async function runBridgeLoop(
  config: BridgeConfig,
  oauthToken: string,
): Promise<void> {
  // 1. 注册环境
  const { environmentId, environmentSecret } = 
    await registerBridgeEnvironment(oauthToken, config)
  
  let isRunning = true
  let reconnectAttempts = 0
  const maxReconnectAttempts = 5
  
  while (isRunning) {
    try {
      // 2. 轮询工作
      const work = await pollForWork(environmentId, environmentSecret)
      
      if (work.items.length > 0) {
        // 3. 确认工作
        await acknowledgeWork(environmentId, environmentSecret, work.id)
        
        // 4. 处理工作项
        for (const item of work.items) {
          await handleWorkItem(item, config)
        }
      }
      
      reconnectAttempts = 0
      
      // 5. 等待下次轮询
      await sleep(work.pollAfterMs)
      
    } catch (error) {
      reconnectAttempts++
      
      if (reconnectAttempts >= maxReconnectAttempts) {
        throw new Error('Max reconnect attempts reached')
      }
      
      // 指数退避
      const backoffMs = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000)
      await sleep(backoffMs)
    }
  }
}
```

### 3.3 会话创建

```typescript
// src/bridge/createSession.ts (简化)

export async function createSessionFromWork(
  workItem: WorkItem,
  config: BridgeConfig,
): Promise<Session> {
  const workSecret = parseWorkSecret(workItem.work_secret)
  
  // 创建 WebSocket 连接
  const ws = new WebSocket(
    `${workSecret.api_base_url}/api/session/${workItem.session_id}`,
    {
      headers: {
        'Authorization': `Bearer ${workSecret.session_ingress_token}`,
      },
    }
  )
  
  // 等待连接打开
  await new Promise((resolve, reject) => {
    ws.onopen = resolve
    ws.onerror = reject
  })
  
  // 创建会话句柄
  const session = {
    id: workItem.session_id,
    ws,
    workSecret,
    createdAt: Date.now(),
  }
  
  return session
}
```

### 3.4 会话管理

```typescript
// src/bridge/sessionRunner.ts (简化)

export class SessionRunner {
  private sessions = new Map<string, Session>()
  private maxSessions: number
  
  constructor(maxSessions: number = 5) {
    this.maxSessions = maxSessions
  }
  
  async startSession(workItem: WorkItem): Promise<void> {
    if (this.sessions.size >= this.maxSessions) {
      throw new Error('Max sessions reached')
    }
    
    const session = await createSessionFromWork(workItem)
    this.sessions.set(session.id, session)
    
    // 启动会话处理
    this.processSessionMessages(session)
  }
  
  private async processSessionMessages(session: Session): Promise<void> {
    session.ws.onmessage = async (event) => {
      const message = JSON.parse(event.data)
      await this.handleSessionMessage(session, message)
    }
    
    session.ws.onclose = () => {
      this.sessions.delete(session.id)
    }
  }
  
  private async handleSessionMessage(
    session: Session,
    message: BridgeMessage,
  ): Promise<void> {
    switch (message.type) {
      case 'user_message':
        await this.forwardToREPL(session, message)
        break
      case 'control_request':
        await this.handleControlRequest(session, message)
        break
    }
  }
}
```

---

## 4. 认证与 JWT 机制

### 4.1 多层认证体系

```
┌─────────────────────────────────────────────────────────────┐
│  认证层次                                                    │
├─────────────────────────────────────────────────────────────┤
│  OAuth Token                                                 │
│  - 用于环境注册和 API 调用                                     │
│  - 长期有效，可刷新                                           │
├─────────────────────────────────────────────────────────────┤
│  JWT Token                                                   │
│  - 用于会话特定操作 (心跳、消息)                               │
│  - 短期有效 (通常 1 小时)                                       │
│  - 自动刷新机制                                               │
├─────────────────────────────────────────────────────────────┤
│  Work Secret                                                 │
│  - 包含会话 ingress token                                     │
│  - 工作项特定                                                 │
│  - 一次性使用                                                 │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 JWT 工具函数

**文件**: `src/bridge/jwtUtils.ts`

```typescript
// JWT 解码 (不验证签名)

export function decodeJwtPayload(token: string): Record<string, unknown> {
  const parts = token.split('.')
  if (parts.length !== 3) {
    throw new Error('Invalid JWT format')
  }
  
  const payload = parts[1]
  const decoded = Buffer.from(payload, 'base64').toString('utf-8')
  return JSON.parse(decoded)
}

// 提取 JWT 过期时间

export function decodeJwtExpiry(token: string): number | null {
  const payload = decodeJwtPayload(token)
  const exp = payload.exp as number | undefined
  return exp ?? null
}

// Token 刷新调度器

export function createTokenRefreshScheduler(
  getToken: () => string | null,
  refresh: () => Promise<string>,
  options: { refreshBeforeExpiryMs: number } = { refreshBeforeExpiryMs: 300000 }
): () => void {
  let timeoutId: ReturnType<typeof setTimeout> | null = null
  
  const scheduleRefresh = () => {
    const token = getToken()
    if (!token) return
    
    const expiry = decodeJwtExpiry(token)
    if (!expiry) return
    
    const now = Date.now() / 1000
    const timeToExpiry = expiry - now
    const refreshIn = Math.max(0, timeToExpiry * 1000 - options.refreshBeforeExpiryMs)
    
    timeoutId = setTimeout(async () => {
      try {
        await refresh()
        scheduleRefresh()
      } catch (error) {
        console.error('Token refresh failed:', error)
      }
    }, refreshIn)
  }
  
  scheduleRefresh()
  
  return () => {
    if (timeoutId) clearTimeout(timeoutId)
  }
}
```

### 4.3 认证流程

```
启动阶段
    │
    ▼
检查 OAuth 登录状态
    │
    ▼
使用 OAuth Token 注册环境
    │
    ▼
获取 environment_id 和 environment_secret
    │
    ▼
轮询工作 (使用 environment_secret)
    │
    ▼
接收工作项 (包含 work_secret)
    │
    ▼
解析 work_secret 获取 session_ingress_token
    │
    ▼
建立 WebSocket 连接 (使用 JWT)
    │
    ▼
自动 Token 刷新调度
    │
    ▼
会话终止时清理
```

---

## 5. 消息传递协议

### 5.1 通信层次

```
┌─────────────────────────────────────────────────────────────┐
│  WebSocket 层                                                 │
│  - 实时双向通信                                               │
│  - 二进制/文本消息                                            │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  SDK 消息层                                                   │
│  - 标准化消息格式                                             │
│  - 类型：user/assistant/tool_use/tool_result/system         │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  控制消息层                                                   │
│  - 权限请求/响应                                              │
│  - 中断请求                                                   │
│  - 模型设置                                                   │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 消息类型

```typescript
// src/bridge/types.ts (简化)

export type BridgeMessage =
  | UserMessage
  | AssistantMessage
  | ToolUseMessage
  | ToolResultMessage
  | SystemMessage
  | ControlRequest
  | ControlResponse

export interface UserMessage {
  type: 'user_message'
  id: string
  content: string
  timestamp: string
}

export interface ControlRequest {
  type: 'control_request'
  action: 'interrupt' | 'set_model' | 'set_permission_mode'
  payload: unknown
}

export interface ControlResponse {
  type: 'control_response'
  requestId: string
  success: boolean
  error?: string
}
```

### 5.3 消息处理

```typescript
// src/bridge/bridgeMessaging.ts (简化)

export async function handleIngressMessage(
  message: BridgeMessage,
  session: Session,
): Promise<void> {
  // 回声检测
  if (isEcho(message, session)) {
    return
  }
  
  // UUID 去重
  if (isDuplicate(message.id)) {
    return
  }
  
  // 消息路由
  switch (message.type) {
    case 'user_message':
      await forwardToREPL(message)
      break
    case 'control_request':
      await handleControlRequest(message, session)
      break
    case 'assistant_message':
    case 'tool_use_message':
    case 'tool_result_message':
      await syncToRemote(message)
      break
  }
}

// 回声检测
function isEcho(message: BridgeMessage, session: Session): boolean {
  // 检查是否为本机发送的消息
  return message.id.startsWith(session.id)
}

// UUID 去重
const seenMessageIds = new Set<string>()
const MAX_SEEN_IDS = 10000

function isDuplicate(messageId: string): boolean {
  if (seenMessageIds.has(messageId)) {
    return true
  }
  
  seenMessageIds.add(messageId)
  
  if (seenMessageIds.size > MAX_SEEN_IDS) {
    const firstId = seenMessageIds.values().next().value
    seenMessageIds.delete(firstId)
  }
  
  return false
}
```

### 5.4 消息过滤

```typescript
// 仅转发符合桥接要求的消息类型

const BRIDGE_ALLOWED_TYPES = new Set([
  'user_message',
  'assistant_message',
  'tool_use_message',
  'tool_result_message',
  'system_message',
  'control_request',
  'control_response',
])

export function isBridgeAllowedType(type: string): boolean {
  return BRIDGE_ALLOWED_TYPES.has(type)
}
```

---

## 6. 与 REPL 集成

### 6.1 REPL Bridge 架构

```typescript
// src/bridge/replBridge.ts (简化)

export interface REPLBridgeState {
  active: boolean         // Bridge 是否激活
  outboundOnly: boolean   // 仅出站模式
  sessionActive: boolean  // 会话是否活跃
  reconnecting: boolean   // 是否重连中
  environmentId?: string  // 环境 ID
  sessionId?: string      // 会话 ID
  sessionUrl?: string     // 会话 URL
  error?: string          // 错误消息
}

export class REPLBridge {
  private state: REPLBridgeState
  private messageQueue: Array<BridgeMessage> = []
  
  // 激活 Bridge
  async activate(config: BridgeConfig): Promise<void> {
    this.state.active = true
    
    // 注册环境
    const registration = await registerBridgeEnvironment(
      this.oauthToken,
      config
    )
    
    this.state.environmentId = registration.environmentId
    
    // 启动轮询
    this.startPolling()
  }
  
  // 启动轮询
  private startPolling(): void {
    const poll = async () => {
      try {
        const work = await pollForWork(
          this.state.environmentId!,
          this.environmentSecret
        )
        
        if (work.items.length > 0) {
          await this.processWork(work)
        }
        
        this.state.reconnecting = false
      } catch (error) {
        this.state.reconnecting = true
        this.state.error = error.message
      }
      
      // 下次轮询
      setTimeout(poll, this.pollIntervalMs)
    }
    
    poll()
  }
  
  // 处理工作项
  private async processWork(work: WorkResponse): Promise<void> {
    for (const item of work.items) {
      await this.acknowledgeWork(item.id)
      
      // 创建会话
      const session = await createSessionFromWork(item)
      await this.startSession(session)
    }
  }
  
  // 启动会话
  private async startSession(session: Session): Promise<void> {
    this.state.sessionId = session.id
    this.state.sessionActive = true
    
    // 同步历史消息
    await this.syncMessageHistory(session)
    
    // 监听消息
    session.ws.onmessage = (event) => {
      this.handleSessionMessage(session, JSON.parse(event.data))
    }
  }
  
  // 同步历史消息
  private async syncMessageHistory(session: Session): Promise<void> {
    const history = getREPLMessageHistory()
    
    for (const message of history) {
      if (isBridgeAllowedType(message.type)) {
        session.ws.send(JSON.stringify(message))
      }
    }
  }
  
  // 处理会话消息
  private handleSessionMessage(
    session: Session,
    message: BridgeMessage,
  ): void {
    switch (message.type) {
      case 'user_message':
        // 转发到 REPL
        this.enqueueREPLMessage(message)
        break
      case 'control_request':
        // 处理控制请求
        this.handleControlRequest(session, message)
        break
    }
  }
  
  // 控制请求处理
  private async handleControlRequest(
    session: Session,
    request: ControlRequest,
  ): Promise<void> {
    switch (request.action) {
      case 'interrupt':
        await this.sendSIGINT()
        break
      case 'set_model':
        await this.setModel(request.payload as ModelSetting)
        break
      case 'set_permission_mode':
        await this.setPermissionMode(request.payload as PermissionMode)
        break
    }
    
    // 发送响应
    session.ws.send(JSON.stringify({
      type: 'control_response',
      requestId: request.id,
      success: true,
    }))
  }
  
  // 发送 SIGINT
  private async sendSIGINT(): Promise<void> {
    process.kill(process.pid, 'SIGINT')
  }
  
  // 设置模型
  private async setModel(model: ModelSetting): Promise<void> {
    setMainLoopModelOverride(model)
  }
  
  // 设置权限模式
  private async setPermissionMode(mode: PermissionMode): Promise<void> {
    setAppState(prev => ({
      ...prev,
      toolPermissionContext: {
        ...prev.toolPermissionContext,
        mode,
      },
    }))
  }
  
  // 排队 REPL 消息
  private enqueueREPLMessage(message: BridgeMessage): void {
    this.messageQueue.push(message)
    this.flushMessageQueue()
  }
  
  // 刷新消息队列
  private flushMessageQueue(): void {
    while (this.messageQueue.length > 0) {
      const message = this.messageQueue.shift()!
      processREPLMessage(message)
    }
  }
}
```

### 6.2 控制请求类型

```typescript
// 支持的控制请求

type ControlAction =
  | 'interrupt'              // 中断当前操作
  | 'set_model'              // 更改模型
  | 'set_permission_mode'    // 更改权限模式
  | 'approve_tool'           // 批准工具使用
  | 'deny_tool'              // 拒绝工具使用

interface ControlRequestPayloads {
  interrupt: {}
  set_model: { model: ModelSetting }
  set_permission_mode: { mode: PermissionMode }
  approve_tool: { toolUseId: string }
  deny_tool: { toolUseId: string; reason?: string }
}
```

### 6.3 双向同步

```
本地 REPL                          Bridge                         远程 claude.ai
    │                               │                                 │
    │  ─── 用户输入 ───────────────► │  ─── 转发 ────────────────────► │
    │                               │                                 │
    │ ◄─── 工具执行结果 ─────────── │ ◄─── 转发 ───────────────────── │
    │                               │                                 │
    │  ─── 助手响应 ──────────────► │  ─── 转发 ────────────────────► │
    │                               │                                 │
    │ ◄─── 控制请求 (中断) ──────── │ ◄─── 用户点击中断 ────────────── │
    │                               │                                 │
```

---

## 7. 类型定义

### 7.1 核心类型

**文件**: `src/bridge/types.ts`

```typescript
// 工作密钥
export type WorkSecret = {
  version: number
  session_ingress_token: string
  api_base_url: string
  sources: Array<{
    type: string
    git_info?: {
      type: string
      repo: string
      ref?: string
      token?: string
    }
  }>
  auth: Array<{
    type: string
    token: string
  }>
}

// Bridge 配置
export interface BridgeConfig {
  dir: string
  machineName: string
  branch: string
  gitRepoUrl: string | null
  maxSessions: number
  spawnMode: SpawnMode  // 'single-session' | 'worktree' | 'same-dir'
  verbose: boolean
  sandbox: boolean
  bridgeId: string
  workerType: string
  environmentId: string
}

// 工作轮询响应
export interface WorkResponse {
  id: string
  items: WorkItem[]
  pollAfterMs: number
}

// 工作项
export interface WorkItem {
  id: string
  session_id: string
  work_secret: string
  created_at: string
}

// 会话状态
export type SessionState = 
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'disconnected'
  | 'error'
```

### 7.2 桥接状态

```typescript
// REPL Bridge 状态
export interface REPLBridgeState {
  // 配置状态
  enabled: boolean        // 配置启用
  explicit: boolean       // 命令启用
  outboundOnly: boolean   // 仅出站
  
  // 连接状态
  connected: boolean      // 环境已注册
  sessionActive: boolean  // 会话活跃
  reconnecting: boolean   // 重连中
  
  // 标识符
  environmentId?: string
  sessionId?: string
  
  // URL
  connectUrl?: string     // 连接 URL
  sessionUrl?: string     // 会话 URL
  
  // 错误
  error?: string
}
```

---

## 8. 关键组件分析

### 8.1 Bridge Main

**文件**: `src/bridge/bridgeMain.ts`

Bridge 主循环是整个系统的核心控制器：

```typescript
// 主循环伪代码

export async function runBridgeLoop(
  config: BridgeConfig,
  oauthToken: string,
): Promise<void> {
  const { environmentId, environmentSecret } = 
    await registerBridgeEnvironment(oauthToken, config)
  
  const sessionRunner = new SessionRunner(config.maxSessions)
  let reconnectAttempts = 0
  
  while (true) {
    try {
      // 轮询工作
      const work = await pollForWork(environmentId, environmentSecret)
      
      // 处理工作项
      for (const item of work.items) {
        await sessionRunner.startSession(item)
      }
      
      // 重置重连计数
      reconnectAttempts = 0
      
      // 等待下次轮询
      await sleep(work.pollAfterMs)
      
    } catch (error) {
      reconnectAttempts++
      
      if (reconnectAttempts > MAX_RECONNECT_ATTEMPTS) {
        throw error
      }
      
      // 指数退避
      const backoff = Math.min(
        1000 * Math.pow(2, reconnectAttempts),
        30000
      )
      await sleep(backoff)
    }
  }
}
```

### 8.2 Bridge API 客户端

**文件**: `src/bridge/bridgeApi.ts`

```typescript
// API 接口定义

export interface BridgeApiClient {
  // 环境注册
  registerBridgeEnvironment(
    oauthToken: string,
    config: BridgeConfig,
  ): Promise<EnvironmentRegistration>
  
  // 工作轮询
  pollForWork(
    environmentId: string,
    environmentSecret: string,
  ): Promise<WorkResponse>
  
  // 确认工作
  acknowledgeWork(
    environmentId: string,
    environmentSecret: string,
    workId: string,
  ): Promise<void>
  
  // 停止工作
  stopWork(
    environmentId: string,
    environmentSecret: string,
    workId: string,
  ): Promise<void>
  
  // 心跳
  heartbeatWork(
    environmentId: string,
    environmentSecret: string,
    workId: string,
  ): Promise<void>
  
  // 权限响应
  sendPermissionResponseEvent(
    environmentId: string,
    environmentSecret: string,
    workId: string,
    response: PermissionResponse,
  ): Promise<void>
}
```

### 8.3 心跳机制

```typescript
// 心跳保持连接活跃

async function heartbeatWork(
  environmentId: string,
  environmentSecret: string,
  workId: string,
): Promise<void> {
  await fetch('/api/bridge/heartbeat', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${environmentSecret}`,
    },
    body: JSON.stringify({
      environment_id: environmentId,
      work_id: workId,
    }),
  })
}

// 定期心跳
function startHeartbeat(
  environmentId: string,
  environmentSecret: string,
  workId: string,
  intervalMs: number = 30000,
): () => void {
  const intervalId = setInterval(() => {
    heartbeatWork(environmentId, environmentSecret, workId)
      .catch(console.error)
  }, intervalMs)
  
  return () => clearInterval(intervalId)
}
```

### 8.4 会话生命周期

```
会话创建
    │
    ▼
解析 work_secret
    │
    ▼
建立 WebSocket 连接
    │
    ▼
同步历史消息
    │
    ▼
┌─────────────────────────────────────┐
│           会话活跃期                 │
│                                     │
│  接收用户消息 → 转发 REPL            │
│  接收控制请求 → 处理并响应           │
│  发送助手响应 → 转发远程             │
│  发送心跳 → 保持活跃                 │
└─────────────────────────────────────┘
    │
    ▼
WebSocket 关闭 / 错误
    │
    ▼
清理会话资源
    │
    ▼
通知服务器会话结束
```

---

## 9. 安全性考虑

### 9.1 令牌管理

```typescript
// 安全令牌处理

// 1. 令牌不记录日志
function logBridgeActivity(event: string, data: unknown) {
  // 移除敏感字段
  const sanitized = sanitize(data)
  logger.info(event, sanitized)
}

function sanitize(data: unknown): unknown {
  if (typeof data === 'object' && data !== null) {
    const result = { ...data }
    delete result.token
    delete result.session_ingress_token
    delete result.environment_secret
    return result
  }
  return data
}

// 2. 令牌内存存储 (不写磁盘)
let workSecretMemory: WorkSecret | null = null

function clearWorkSecret(): void {
  workSecretMemory = null
}

// 3. 会话终止时清理令牌
function cleanupSession(session: Session): void {
  session.ws.close()
  clearWorkSecret()
}
```

### 9.2 输入验证

```typescript
// 验证入站消息

function validateIngressMessage(message: unknown): ValidationResult {
  if (typeof message !== 'object' || message === null) {
    return { valid: false, error: 'Message must be an object' }
  }
  
  const msg = message as Record<string, unknown>
  
  // 必需字段
  if (typeof msg.type !== 'string') {
    return { valid: false, error: 'Missing type field' }
  }
  
  if (typeof msg.id !== 'string') {
    return { valid: false, error: 'Missing id field' }
  }
  
  // 类型白名单
  if (!BRIDGE_ALLOWED_TYPES.has(msg.type)) {
    return { valid: false, error: `Unknown message type: ${msg.type}` }
  }
  
  return { valid: true }
}
```

---

## 10. 总结

Bridge 桥接系统是 Claude Code 实现远程会话能力的核心组件：

### 架构特点

| 方面 | 实现 | 收益 |
|------|------|------|
| 通信协议 | WebSocket + 轮询 | 实时双向 + 可靠发现 |
| 认证机制 | OAuth + JWT + Work Secret | 多层安全 |
| 会话管理 | 最大会话数限制 | 资源保护 |
| 故障恢复 | 指数退避重连 | 弹性连接 |
| 令牌刷新 | 自动调度器 | 无中断续期 |

### 关键设计决策

1. **轮询而非推送发现**: 简化服务器架构，客户端控制轮询频率
2. **JWT 短期令牌**: 降低令牌泄露风险，自动刷新保持体验
3. **回声过滤**: 避免消息循环和重复处理
4. **控制请求分离**: 用户消息和控制命令分开处理
5. **双向同步**: 本地状态和远程 UI 保持一致

---

*最后更新：2026-04-02*
