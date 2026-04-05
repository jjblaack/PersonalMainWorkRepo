# Markdown to PPT/PDF Converter

这是一个用于将Markdown文档转换为PowerPoint演示文稿和PDF文件的工具集。支持多种转换方式，包括Pandoc、reveal.js等技术。

## 功能特性

- 将Markdown文档转换为PPTX格式
- 将Markdown文档转换为PDF格式
- 支持HTML幻灯片展示（基于reveal.js）
- 可自定义模板和样式
- **新增**: 支持山水画水墨风格等自定义主题

## 技术栈

- Pandoc: 用于格式转换
- reveal.js: 用于HTML幻灯片
- Node.js: 用于reveal-md工具
- LaTeX: 用于高质量PDF输出（可选）

## 安装依赖

```bash
# 安装Pandoc（必须）- 用于格式转换
# macOS
brew install pandoc

# Windows (使用Chocolatey)
choco install pandoc

# Ubuntu/Debian
sudo apt install pandoc

# 安装Node.js依赖（可选，如已安装npm则不需要额外操作）
npm install -g

# 如果需要LaTeX支持PDF输出（可选）
# macOS
brew install --cask mactex-no-gui
# 或者安装更小的版本
brew install --cask basictex

# Ubuntu/Debian
sudo apt install texlive-full
```

## 使用方法

### 1. 使用Pandoc转换

```bash
# 转换为PPTX
pandoc input.md -o output.pptx

# 转换为PDF（需要LaTeX）
pandoc input.md -o output.pdf

# 转换为reveal.js HTML幻灯片
pandoc input.md -t revealjs -o output.html -V revealjs-url=https://unpkg.com/reveal.js@4.3.1/
```

### 2. 使用JavaScript转换器

```bash
# 转换为PPTX
node converter.js input.md output.pptx pptx

# 转换为PDF
node converter.js input.md output.pdf pdf

# 转换为HTML幻灯片
node converter.js input.md slides.html html --presentation

# 使用自定义主题（例如山水画水墨风格）
node converter.js input.md slides-ink.html html --presentation --theme landscape-ink
```

### 3. 使用npm脚本

```bash
# 转换为PPTX
npm run convert:pptx

# 转换为PDF
npm run convert:pdf

# 转换为HTML幻灯片
npm run convert:html

# 使用水墨风格主题
npm run convert:ink-theme

# 运行所有转换
npm run demo
```

## 示例Markdown格式

```markdown
---
title: 演示文稿标题
author: 作者姓名
date: 2026-04-06
---

# 幻灯片标题

内容...

---

# 另一张幻灯片

更多内容...
```

## 自定义主题

项目包含一个**山水画水墨风格**主题 (`landscape-ink`)，可以通过 `--theme` 参数应用：

```bash
node converter.js input.md output.html html --presentation --theme landscape-ink
```

主题文件位于 `themes/` 目录中，您可以根据需要创建新的主题。