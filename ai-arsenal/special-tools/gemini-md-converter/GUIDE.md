# Gemini 对话转 Markdown 工具 - 使用指南

## 快速开始

### 1. 安装依赖
```bash
cd tool/gemini-md-converter
pip install -r requirements.txt
```

### 2. 运行转换
```bash
python gemini_to_md.py <your-gemini-share-url>
```

### 3. 查看输出
工具会在当前目录生成一个 `gemini_conversation.md` 文件（如有重复则添加数字后缀）。

## 高级用法

### 自定义配置
编辑 `config.json` 文件可以自定义以下参数：

```json
{
  "selectors": [
    "[data-message-author-role='user']",
    "[data-message-author-role='model']",
    ".ql-editor",
    "[jsname*='message']",
    ".gem-content",
    "[role='listitem']"
  ],
  "question_indicators": [
    "?",
    "如何",
    "什么",
    "为什么",
    "怎么",
    "what",
    "how",
    "why",
    "which",
    "问题",
    "问",
    "请教",
    "请问"
  ],
  "answer_indicators": [
    "根据",
    "因此",
    "所以",
    "总结",
    "结论",
    "分析",
    "a:",
    "answer:",
    "回答",
    "是的",
    "不是"
  ],
  "skip_keywords": [
    "sign in",
    "sign up",
    "login",
    "sign in with",
    "google",
    "account",
    "gemini",
    "loading",
    "share",
    "menu",
    "settings",
    "profile"
  ]
}
```

## 常见问题

### Q: 转换后的文件全是重复内容怎么办？
A: 这通常是因为工具无法准确识别问题和答案的边界。尝试调整 `config.json` 中的 `selectors` 和关键词匹配规则。

### Q: 提示 "错误: 无法获取对话内容" 怎么办？
A:
1. 检查链接是否有效且可公开访问
2. 确认网络连接正常
3. 确保 ChromeDriver 已正确安装（第一次运行时会自动下载）

### Q: 为什么有些对话内容没有被提取？
A: 可能的原因：
1. Gemini 界面更新，CSS 选择器需要调整
2. 动态加载的内容尚未完全渲染
3. 内容包含在被跳过的关键词列表中

## 工作原理

### 1. 内容提取
- 使用 Selenium 模拟浏览器行为，确保 JavaScript 渲染完成
- 使用 BeautifulSoup 解析 HTML 内容
- 尝试多种 CSS 选择器策略

### 2. 内容分析
- 通过关键词识别判断内容类型（问题或答案）
- 根据文本特征进行分类
- 过滤无关内容（如界面元素、登录提示等）

### 3. Markdown 生成
- 按照 Q&A 结构组织内容
- 保持原有的格式和段落划分
- 添加适当的 Markdown 标题层级

## 性能优化

- 转换大型对话可能需要几分钟，请耐心等待
- 工具会在本地运行，无需上传敏感数据
- 可通过配置文件优化选择器，提高提取准确性

## 故障排除

### ChromeDriver 相关问题
如果遇到 ChromeDriver 相关错误：
1. 确保系统已安装 Chrome 或 Chromium
2. 检查版本兼容性
3. 手动安装 webdriver-manager: `pip install webdriver-manager`

### 权限问题
确保有写入当前目录的权限。

### 网络问题
工具需要访问外部链接，请确保网络连接畅通。