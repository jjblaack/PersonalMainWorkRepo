# PPT-Builder 项目结构

## 目录结构

```
ppt-builder/
├── README.md                 # 项目概述和基本使用说明
├── USAGE.md                  # 详细使用指南
├── install.sh                # 依赖安装脚本
├── converter.js              # JavaScript版本的转换器
├── converter.py              # Python版本的转换器
├── package.json              # npm包配置
├── sample-presentation.md    # 示例Markdown文件（水墨风格主题）
├── themes/                   # 主题文件目录
│   └── landscape-ink.css     # 山水画水墨风格CSS
└── ...
```

## 核心组件

### 1. 转换器脚本

#### converter.js
- JavaScript/Node.js版本的转换器
- 支持命令行参数
- 支持多种输出格式 (PPTX, PDF, HTML)
- 支持自定义主题
- 错误处理和依赖检查

#### converter.py
- Python版本的转换器
- 功能与JavaScript版本相同
- 跨平台兼容
- 面向喜欢Python的用户

### 2. 主题系统

#### themes/landscape-ink.css
- 山水画水墨风格主题
- 仿宣纸背景
- 淡雅墨色配色
- 中国传统艺术元素
- 适配reveal.js框架

### 3. 示例文件

#### sample-presentation.md
- 水墨风格的演示文稿示例
- 包含中文内容
- 展示了不同Markdown元素
- 使用主题相关的内容

## 支持的功能

### 输出格式
- **PPTX**: Microsoft PowerPoint格式
- **PDF**: 便携式文档格式
- **HTML**: 可交互的网页演示文稿

### 主题特性
- **自定义CSS**: 可替换的颜色和布局
- **中式美学**: 体现传统文化元素
- **响应式设计**: 适应不同屏幕尺寸
- **过渡效果**: 流畅的幻灯片切换

## 工作流程

### 1. 准备阶段
- 安装依赖 (pandoc, latex)
- 准备Markdown源文件
- 选择合适的主题

### 2. 转换阶段
- 运行转换器脚本
- 应用所选主题
- 生成目标格式文件

### 3. 输出结果
- PPTX文件可直接在PowerPoint中打开
- PDF文件便于分享和打印
- HTML文件可在浏览器中播放

## 扩展性

### 添加新主题
1. 在 `themes/` 目录下创建新的CSS文件
2. 按照现有主题的结构编写样式
3. 在转换时使用 `--theme` 参数指定新主题

### 支持新格式
- 修改转换器脚本以支持更多格式
- 更新文档说明
- 添加相应的处理逻辑

## 技术依赖

- **Pandoc**: 通用文档转换器
- **reveal.js**: HTML演示框架
- **LaTeX**: PDF排版引擎（可选）
- **Node.js 或 Python**: 脚本执行环境