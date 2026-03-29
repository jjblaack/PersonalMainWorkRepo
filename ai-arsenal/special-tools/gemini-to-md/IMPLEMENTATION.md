# Gemini对话转Markdown - Claude技能说明

## 技能概述

**技能名称**: gemini-to-md
**功能**: 将Gemini对话链接转换为Markdown格式
**类型**: 实用工具技能

## 技能结构

### 文件结构
```
.claude/skills/gemini-to-md/
├── skill.py      # 主技能文件（包含run函数）
├── config.yaml   # 技能配置文件
└── README.md     # 技能说明文件
```

### 核心函数
- `run(url: str) -> str`: 主执行函数，接收URL参数并返回处理结果

### 配置文件 (config.yaml)
- 定义技能元数据
- 配置参数要求
- 提供使用示例

## 工作原理

1. 用户在Claude中输入 `/gemini-to-md <url>`
2. Claude调用技能的 `run()` 函数
3. 函数验证URL并提供本地工具使用说明
4. 用户根据说明使用本地工具完成实际转换

## 安全考量

此技能遵循以下安全原则：
- 不直接访问外部URL（避免安全风险）
- 指导用户在本地环境中处理外部链接
- 仅返回文本信息，不执行危险操作

## 使用场景

- 需要将Gemini对话转换为Markdown格式
- 需要结构化保存AI对话内容
- 需要离线查看和编辑对话内容

## 故障排除

### 技能未被识别
- 确认技能位于 `.claude/skills/gemini-to-md/` 目录
- 确认 `skill.py` 文件存在且包含 `run` 函数
- 确认 Claude Code 已重启或重载技能

### 函数调用失败
- 检查 `skill.py` 是否包含正确签名的 `run` 函数
- 确认函数能够处理空参数和无效URL

## 扩展性

此技能架构可轻松扩展：
- 添加更多输入验证
- 支持其他类型的转换
- 集成其他本地工具