# Gemini对话转Markdown技能

## 概述
此技能帮助用户将Gemini对话链接转换为Markdown格式。

## 功能
- 验证输入的URL
- 提供本地工具使用指导
- 指导用户完成Gemini对话到Markdown的转换

## 使用
```
/gemini-to-md <gemini_conversation_url>
```

## 注意
由于安全限制，Claude无法直接访问外部网站。此技能指导用户使用本地工具完成转换任务，本地工具位于项目的 `tool/gemini-md-converter/` 目录。