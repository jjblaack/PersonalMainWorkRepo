# Markdown to PPT/PDF 转换工具

## 概述

这是一个用于将Markdown文档转换为PowerPoint演示文稿和PDF文件的工具集。该工具支持多种转换方式，允许您轻松地从Markdown文本创建专业的演示文稿。

## 系统要求

- **Pandoc**: 必需，用于格式转换
- **LaTeX** (可选): 用于高质量PDF输出
- **Node.js** (可选): 用于运行JavaScript版本
- **Python 3** (可选): 用于运行Python版本

### 安装依赖

#### 1. 安装Pandoc

**macOS**:
```bash
brew install pandoc
```

**Windows (使用Chocolatey)**:
```bash
choco install pandoc
```

**Ubuntu/Debian**:
```bash
sudo apt install pandoc
```

#### 2. 安装LaTeX (用于PDF输出)

**macOS**:
```bash
# 完整版 (较大)
brew install --cask mactex-no-gui

# 或者基础版 (较小)
brew install --cask basictex
```

**Ubuntu/Debian**:
```bash
sudo apt install texlive-full
```

#### 3. (可选) 安装Node.js依赖
```bash
npm install -g
```

## 使用方法

### JavaScript版本

1. **转换为PowerPoint**:
```bash
node converter.js sample-presentation.md output.pptx pptx
```

2. **转换为PDF**:
```bash
node converter.js sample-presentation.md output.pdf pdf
```

3. **转换为HTML幻灯片 (reveal.js)**:
```bash
node converter.js sample-presentation.md slides.html html --presentation
```

4. **使用自定义主题**:
```bash
# 使用山水画水墨风格主题
node converter.js sample-presentation.md slides-ink.html html --presentation --theme landscape-ink
```

5. **使用npm脚本**:
```bash
# 转换为PPTX
npm run convert:pptx

# 转换为PDF
npm run convert:pdf

# 转换为HTML幻灯片
npm run convert:html

# 使用山水画水墨风格
npm run convert:ink-theme

# 运行所有转换
npm run demo

# 运行水墨风格演示
npm run demo-ink
```

### Python版本

1. **转换为PowerPoint**:
```bash
python3 converter.py sample-presentation.md output.pptx pptx
```

2. **转换为PDF**:
```bash
python3 converter.py sample-presentation.md output.pdf pdf
```

3. **转换为HTML幻灯片**:
```bash
python3 converter.py sample-presentation.md slides.html html --presentation
```

4. **使用自定义主题**:
```bash
# 使用山水画水墨风格主题
python3 converter.py sample-presentation.md slides-ink.html html --presentation --theme landscape-ink
```

## Markdown语法提示

您的Markdown文件应包含以下元数据头:

```markdown
---
title: 演示文稿标题
author: 作者姓名
date: 日期
---

# 幻灯片标题

内容...

---

# 新幻灯片

更多内容...
```

使用 `---` 来分隔不同的幻灯片页面。

### 支持的元素

- 标题 (#, ##, ###)
- 列表 (有序和无序)
- 代码块
- 表格
- 强调文本
- 链接和图片
- 引用块

## 自定义主题

本工具支持自定义主题，让您的演示文稿具有独特的视觉风格。

### 当前可用主题

1. **山水画水墨风格** (`landscape-ink`):
   - 采用中国传统水墨画美学
   - 宣纸般的米白背景
   - 淡雅的墨色配色
   - 添加了中国风装饰元素

### 应用主题

使用 `--theme` 参数指定主题:

```bash
# JavaScript版本
node converter.js input.md output.html html --presentation --theme landscape-ink

# Python版本
python3 converter.py input.md output.html html --presentation --theme landscape-ink
```

### 创建自定义主题

1. 在 `themes` 目录下创建新的CSS文件
2. 参考 `themes/landscape-ink.css` 文件的样式定义
3. 使用reveal.js的CSS类来自定义外观
4. 保存为 `.css` 文件，去掉主题名中的后缀

## 高级功能

### 批量转换

您可以同时转换为多种格式:

```bash
# 先生成PPTX
node converter.js sample-presentation.md output.pptx pptx
# 然后生成PDF
node converter.js sample-presentation.md output.pdf pdf
# 最后生成带水墨主题的HTML幻灯片
node converter.js sample-presentation.md slides-ink.html html --presentation --theme landscape-ink
```

### 集成到工作流程

您可以将此工具集成到自动化工作流程中:

```bash
#!/bin/bash
# 自动转换脚本示例
MARKDOWN_FILE=$1
THEME=${2:-"landscape-ink"}  # 默认使用水墨风格
BASENAME=$(basename "$MARKDOWN_FILE" .md)

node converter.js "$MARKDOWN_FILE" "${BASENAME}.pptx" pptx
node converter.js "$MARKDOWN_FILE" "${BASENAME}.pdf" pdf
node converter.js "$MARKDOWN_FILE" "${BASENAME}-${THEME}.html" html --presentation --theme "$THEME"

echo "转换完成！输出文件：${BASENAME}.pptx, ${BASENAME}.pdf, ${BASENAME}-${THEME}.html"
```

## 故障排除

### 缺少依赖项错误

如果您收到缺少依赖项的错误，请确保已正确安装Pandoc和LaTeX。

### PDF转换失败

如果PDF转换失败，请检查：
1. LaTeX是否已正确安装
2. 是否有足够的磁盘空间
3. 输入文件是否有正确的格式

### 输出格式问题

如果输出格式不符合预期：
1. 检查Markdown语法是否正确
2. 确保使用了适当的分隔符 `---` 来分隔幻灯片
3. 查看Pandoc文档了解支持的格式选项

### 主题未生效

如果自定义主题没有应用：
1. 检查主题文件是否存在且路径正确
2. 确保使用了 `--presentation` 参数（主题仅适用于HTML幻灯片）
3. 查看控制台输出确认命令是否正确执行

## 示例

我们提供了一个水墨风格的示例文件 `sample-presentation.md`，要运行演示请先安装依赖：

### 安装依赖

在运行任何转换命令之前，必须安装必要的依赖：

**macOS**:
```bash
# 安装pandoc（必需）
brew install pandoc

# 可选：安装LaTeX以支持PDF输出
brew install --cask basictex  # 或 mactex-no-gui（完整版）
```

**Ubuntu/Debian**:
```bash
# 安装pandoc（必需）
sudo apt update
sudo apt install pandoc

# 可选：安装LaTeX以支持PDF输出
sudo apt install texlive-full
```

**Windows**:
```bash
# 使用Chocolatey安装pandoc（必需）
choco install pandoc
```

### 运行演示

安装依赖后，您可以运行演示：

```bash
# 运行水墨风格演示
npm run demo-ink
```

这将在安装了必要工具后生成带有山水画水墨风格的HTML幻灯片供您查看。

### 手动测试

如果您不想使用npm脚本，也可以直接运行：

```bash
# 使用山水画水墨风格生成HTML幻灯片
node converter.js sample-presentation.md slides-ink.html html --presentation --theme landscape-ink
```

生成的 `slides-ink.html` 文件可以直接在浏览器中打开查看水墨风格效果。