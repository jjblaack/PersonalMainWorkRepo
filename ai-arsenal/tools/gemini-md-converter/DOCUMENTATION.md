# Gemini 对话转 Markdown 工具 - 完整文档

## 概述

Gemini 对话转 Markdown 工具是一个专门用于将 Gemini 对话链接转换为结构化 Markdown 文件的 Python 应用程序。它使用 Selenium 来处理 JavaScript 渲染的内容，并通过智能解析算法区分对话中的问题和答案部分。

## 目录结构

```
gemini-md-converter/
├── README.md          # 项目说明
├── GUIDE.md          # 详细使用指南
├── requirements.txt  # 依赖包列表
├── gemini_to_md.py   # 主转换脚本
├── gemini_to_md_enhanced.py  # 增强版转换脚本
├── main.py           # 主入口点
├── config.json       # 配置文件
├── convert.sh        # 使用脚本
├── examples.md       # 示例和常见问题
├── STRUCTURE.md      # 项目结构说明
└── LICENSE           # 许可证
```

## 安装与配置

### 系统要求
- Python 3.7+
- Chrome 或 Chromium 浏览器
- 网络连接（用于首次安装 webdriver）

### 安装步骤

1. 克隆或下载工具目录
2. 安装依赖包：
```bash
pip install -r requirements.txt
```

3. 首次运行时会自动下载 ChromeDriver

## 使用方法

### 基本使用
```bash
python gemini_to_md.py <gemini_share_url>
```

### 使用便捷脚本
```bash
./convert.sh <gemini_share_url>
```

## 技术细节

### 工作流程
1. **内容获取**：使用 Selenium WebDriver 加载页面并等待 JavaScript 渲染
2. **DOM 解析**：使用 BeautifulSoup 解析页面结构
3. **内容提取**：根据预定义的选择器提取对话内容
4. **类型识别**：使用关键词匹配算法区分问题和答案
5. **格式转换**：将内容组织为 Markdown 格式

### 关键技术组件
- Selenium: 用于处理 JavaScript 渲染的动态内容
- BeautifulSoup: 用于解析 HTML 结构
- WebDriver Manager: 自动管理 ChromeDriver 版本

## 配置选项

### 选择器配置
通过 `config.json` 中的 `selectors` 数组可以指定用于定位对话内容的 CSS 选择器。

### 关键词配置
- `question_indicators`: 标识问题的关键词
- `answer_indicators`: 标识答案的关键词
- `skip_keywords`: 需要过滤的无关内容

## 测试验证

该工具已在以下场景下测试通过：
- 基础对话转换
- 复杂多轮对话
- 包含代码和技术术语的对话
- 长对话内容处理

## 常见问题解决

### 无法加载页面
- 确认网络连接正常
- 检查链接是否有效
- 确保 ChromeDriver 安装正确

### 内容提取不准确
- 调整 `config.json` 中的选择器
- 更新关键词匹配规则
- 检查 Gemini 界面是否发生变化

## 扩展性

该工具具有良好的扩展性，可以轻松适配其他类似的服务：
- 修改选择器以适配新平台
- 调整解析逻辑
- 添加新的输出格式

## 许可证

本项目遵循 MIT 许可证，详情请参阅 LICENSE 文件。