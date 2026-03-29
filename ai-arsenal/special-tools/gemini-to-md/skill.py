"""
Gemini对话转Markdown技能

根据Claude技能文档 (https://code.claude.com/docs/en/skills) 创建
"""

def run(url: str) -> str:
    """
    将Gemini对话链接转换为Markdown格式

    Args:
        url: Gemini对话链接

    Returns:
        转换后的Markdown内容或使用说明
    """
    if not url or not url.strip():
        return """# Gemini对话转Markdown工具

## 用途
将Gemini对话链接转换为结构化的Markdown格式。

## 使用方法
```
/gemini-to-md <gemini_conversation_url>
```

## 说明
由于安全限制，Claude无法直接访问外部链接。本技能指导您使用本地工具完成转换：

1. 转到本地工具目录：
   ```
   cd tool/gemini-md-converter/
   ```

2. 安装依赖（首次使用时）：
   ```
   pip install -r requirements.txt
   ```

3. 运行转换：
   ```
   python gemini_to_md.py "<your_gemini_link>"
   ```

或者使用便捷脚本：
   ```
   ./convert.sh "<your_gemini_link>"
   ```

## 本地工具特性
- 支持JavaScript渲染的页面内容
- 智能识别问题和答案
- 生成结构化的Markdown输出
- 可配置的解析规则
"""

    # 清理URL
    url = url.strip()

    # 验证URL格式
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return f"错误：'{url}' 不是有效的URL格式。请提供完整的链接（例如 https://gemini.google.com/share/xxx）。"

    # 检查是否是Gemini链接
    if 'gemini' not in url.lower() and 'google' not in url.lower():
        return f"警告：'{url}' 似乎不是Gemini对话链接。请确认链接的有效性。"

    return f"""# Gemini对话转Markdown

## 检测到链接
`{url}`

## 操作说明

由于安全限制，Claude无法直接访问外部链接。请使用本地工具完成转换：

### 步骤1：打开终端并导航到工具目录
```bash
cd tool/gemini-md-converter/
```

### 步骤2：安装依赖（如果尚未安装）
```bash
pip install -r requirements.txt
```

### 步骤3：运行转换命令
```bash
python gemini_to_md.py "{url}"
```

或者使用便捷脚本：
```bash
./convert.sh "{url}"
```

## 本地工具功能
- 自动处理JavaScript渲染的动态内容
- 智能识别对话中的问题和答案
- 生成结构化的Markdown格式 (`#### Q:` 和 `#### A:`)
- 支持复杂的技术对话内容
- 生成的文件保存为 `gemini_conversation.md` 或带序号的变体

## 完整文档
请参考 `tool/gemini-md-converter/GUIDE.md` 了解更多详细信息。
"""


# 可选：提供技能的元数据
__doc__ = "将Gemini对话链接转换为Markdown格式 - 本地工具辅助"
__author__ = "Claude Code Assistant"
__version__ = "1.0.0"