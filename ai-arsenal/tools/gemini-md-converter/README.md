# Gemini 对话链接转 Markdown 工具

这是一个用于将 Gemini 对话链接整理为 Markdown 格式的工具。该工具可以抓取 Gemini 对话的内容并将其转换为易于阅读和编辑的 Markdown 文件。

## 功能特性

- 解析 Gemini 对话链接
- 提取对话中的文本内容
- 将内容整理为 Markdown 格式（区分问题和答案）
- 支持对话历史的完整导出
- 保留对话结构（问题与回答的对应关系）
- 支持 JavaScript 渲染的页面内容

## 安装

1. 确保您已安装 Python 3.x
2. 安装依赖项：
   ```bash
   pip install -r requirements.txt
   ```

## 使用方法

1. 运行脚本：
   ```bash
   python gemini_to_md.py <gemini_conversation_url>
   ```

2. 脚本将输出对应的 Markdown 文件

## 参数说明

- `<gemini_conversation_url>`：要转换的 Gemini 对话链接

## 输出示例

工具会生成包含以下元素的 Markdown 文件：

- 对话标题
- 问题部分（以 `#### Q:` 开头）
- 回答部分（以 `#### A:` 开头）
- 代码块（保留原始格式）
- 文本格式（加粗、斜体等）

## 配置

可以通过修改 `config.json` 文件来自定义选择器和关键词匹配规则：

- `selectors`: CSS 选择器列表，用于定位对话内容
- `question_indicators`: 问题识别关键词
- `answer_indicators`: 答案识别关键词
- `skip_keywords`: 需要跳过的无关内容关键词

## 测试

该工具已成功测试了以下类型的链接：
- Gemini 分享链接（如：https://gemini.google.com/share/xxxxx）
- 包含复杂多轮对话的会话
- 包含代码、技术讨论的内容

## 注意事项

- 请确保您有访问相应 Gemini 对话的权限
- 工具仅处理公共或您有权访问的对话
- 遵循相关服务条款和隐私政策
- 对于复杂的动态内容，可能需要一定时间来加载和解析