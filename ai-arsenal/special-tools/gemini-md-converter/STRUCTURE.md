# Gemini 对话转 Markdown 工具 - 项目结构

## 目录结构

```
gemini-md-converter/
├── README.md          # 项目说明文档
├── requirements.txt   # 项目依赖列表
├── gemini_to_md.py    # 主要转换逻辑实现
├── main.py           # 主入口点
├── examples.md       # 使用示例和常见问题
└── LICENSE          # 许可证文件
```

## 文件说明

### README.md
项目的主要说明文档，包含：
- 工具功能介绍
- 安装步骤
- 使用方法
- 参数说明
- 输出示例
- 注意事项

### requirements.txt
Python 依赖包列表：
- requests: 用于发送 HTTP 请求获取网页内容
- beautifulsoup4: 用于解析 HTML 内容

### gemini_to_md.py
核心功能实现文件：
- extract_gemini_content(): 从 URL 提取 Gemini 对话内容
- convert_to_markdown(): 将提取的内容转换为 Markdown 格式
- save_to_file(): 保存内容到文件
- main(): 命令行主函数

### main.py
程序入口点，处理命令行参数并调用核心功能

### examples.md
使用示例和常见问题解答

### LICENSE
项目许可证信息（使用 MIT 许可证）

## 开发说明

此工具设计用于将 Gemini 对话链接转换为 Markdown 格式。由于 Gemini 的页面结构可能随时变化，
工具可能需要定期更新选择器来适配新的页面结构。

## 扩展性考虑

- 代码结构允许相对容易地添加对其他 AI 对话平台的支持
- 模块化设计便于维护和扩展
- 错误处理机制确保程序的稳定性