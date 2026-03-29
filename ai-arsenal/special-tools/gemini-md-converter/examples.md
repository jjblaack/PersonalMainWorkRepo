# 使用示例

## 基本用法

```bash
# 安装依赖
pip install -r requirements.txt

# 运行转换器
python gemini_to_md.py https://gemini.google.com/app/conversation/your-conversation-id
```

## 示例输出

当您运行工具时，它将生成类似以下的 Markdown 文件：

```markdown
# Gemini 对话记录

#### Q: 如何学习Python编程？

#### A: 学习Python编程可以从基础语法开始，推荐使用官方文档和在线教程。

#### Q: 有哪些好的Python学习资源？

#### A: 推荐官方Python文档、Real Python网站、以及一些流行的在线课程平台。
```

## 常见问题

Q: 为什么我的链接无法转换？
A: 可能原因包括：链接不可访问、页面结构发生变化或需要登录才能查看内容。

Q: 转换后的格式不正确怎么办？
A: 请手动调整生成的 Markdown 文件，或者提交问题以便我们改进工具。

Q: 是否支持其他AI对话平台？
A: 当前版本专门针对Gemini对话，未来可能会扩展支持其他平台。