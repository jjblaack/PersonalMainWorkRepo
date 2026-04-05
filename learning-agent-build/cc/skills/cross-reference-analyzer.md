---
name: cross-reference-analyzer
description: 跨文件引用分析，追踪模块间的依赖关系和调用链
type: skill
---

# cross-reference-analyzer 技能

## 用途

分析多个文件之间的依赖关系，识别：
1. 模块依赖图
2. 核心枢纽文件（被最多模块依赖）
3. 调用链条
4. 循环依赖检测
5. 接口边界和契约

## 使用方法

```
/cross-reference-analyzer <文件路径或目录>
```

## 输出格式

### 1. 依赖图
```
src/QueryEngine.ts
├── src/tools.ts (导入 Tool 接口)
├── src/services/api/ (调用 Anthropic API)
├── src/Tool.ts (继承基类)
└── src/utils/streaming.ts (流式处理)
```

### 2. 调用链分析
追踪特定功能的完整调用路径：
```
用户输入 → REPL → CommandParser → ToolExecutor → Tool.execute() → Service → API
```

### 3. 核心枢纽识别
列出被最多其他模块依赖的文件：
```
src/Tool.ts - 被 44 个工具依赖
src/tools.ts - 被 3 个模块依赖
src/QueryEngine.ts - 被 2 个模块依赖
```

### 4. 循环依赖警告
检测并报告任何循环依赖

## 执行步骤

1. 解析目标文件的 import/export
2. 递归追踪依赖
3. 构建依赖图
4. 识别枢纽节点
5. 检测循环依赖
6. 生成可视化报告
