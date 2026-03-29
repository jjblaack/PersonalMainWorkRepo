import os
import sys
import re
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

def extract_gemini_content_selenium(url):
    """
    使用 Selenium 从 Gemini 对话链接中提取内容（支持 JavaScript 渲染）
    """
    # 设置 Chrome 选项
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # 无头模式
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')

    # 设置 WebDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        print("正在加载页面...")
        driver.get(url)

        # 等待页面加载完成，等待主要对话容器出现
        try:
            # 等待页面内容加载 - 根据 Gemini 页面结构调整选择器
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # 等待特定的对话内容元素出现
            # 根据 Gemini 界面更新选择器
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )

            # 获取页面源码
            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')

            # 尝试查找对话相关的元素
            # 根据实际的 Gemini 页面结构调整选择器
            # 查找可能包含对话消息的元素
            conversation_elements = soup.find_all(['div', 'section', 'article'], attrs={
                'class': lambda x: x and (
                    'conversation' in x.lower() or
                    'message' in x.lower() or
                    'chat' in x.lower() or
                    'response' in x.lower() or
                    'bubble' in x.lower() or
                    'contents' in x.lower()
                )
            })

            if not conversation_elements:
                # 更广泛的选择器来捕获对话元素
                selectors = [
                    '[data-message-author-role]',  # 基于角色的数据属性
                    '[jsname*="message"]',        # 基于jsname的消息元素
                    '.gemi-content',              # Gemini 内容类
                    '.ql-editor',                 # 富文本编辑器内容
                    '[role="listitem"]',          # 列表项（可能是消息）
                    'div[data-testid*="message"]' # 使用 testid
                ]

                for selector in selectors:
                    elements = soup.select(selector)
                    if elements:
                        conversation_elements = elements
                        break

            if not conversation_elements:
                # 最后的备用方案：获取主要内容区域
                main_content = soup.find('main') or soup.find('body')
                if main_content:
                    # 提取主要区域内的段落和其他文本元素
                    conversation_elements = main_content.find_all(['div', 'p', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])

            return conversation_elements

        except Exception as e:
            print(f"页面加载过程中出现错误: {e}")
            # 即使等待失败，也尝试获取现有内容
            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            main_content = soup.find('main') or soup.find('body')
            if main_content:
                return main_content.find_all(['div', 'p', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            return []

    finally:
        driver.quit()

def extract_gemini_content_static(url):
    """
    使用 requests 从 Gemini 对话链接中提取内容（静态内容）
    """
    import requests

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # 尝试查找对话相关的元素
        conversation_elements = soup.find_all(['div', 'section', 'article'], attrs={
            'class': lambda x: x and (
                'conversation' in x.lower() or
                'message' in x.lower() or
                'chat' in x.lower() or
                'response' in x.lower()
            )
        })

        if not conversation_elements:
            # 如果没有找到特定类名的元素，则尝试通用的选择器
            conversation_elements = soup.find_all(['p', 'div', 'span'])

        return conversation_elements
    except Exception as e:
        print(f"获取网页内容时出现错误: {e}")
        return []

def convert_to_markdown(content_elements):
    """
    将提取的内容转换为 Markdown 格式
    """
    markdown_content = []

    # 添加标题
    markdown_content.append("# Gemini 对话记录\n")

    if content_elements:
        # 收集所有文本内容
        all_texts = []
        for element in content_elements:
            text = element.get_text().strip()
            if text and len(text) > 10:  # 过滤掉过短的文本片段
                # 过滤掉常见的界面元素文字
                skip_keywords = ['sign in', 'sign up', 'login', 'sign in with', 'google', 'account', 'gemini', 'loading', 'share']
                if not any(keyword in text.lower() for keyword in skip_keywords):
                    all_texts.append(text)

        # 按照文本长度和结构进行分析，识别问答对
        i = 0
        while i < len(all_texts):
            current_text = all_texts[i]

            # 判断当前文本是否是问题
            is_question = (
                any(q_keyword in current_text.lower() for q_keyword in ['?', '如何', '什么', '为什么', '怎么', 'what', 'how', 'why', 'which', 'which']) or
                any(q_keyword in current_text[:100].lower() for q_keyword in ['问题', '问', '请教', '请问', 'question'])
            )

            if is_question:
                markdown_content.append(f"\n#### Q: {current_text}\n")
                i += 1
            else:
                # 如果没有明确的问题标记，我们尝试通过内容结构推断
                # 检查下一个文本是否看起来像是答案
                if i + 1 < len(all_texts):
                    next_text = all_texts[i + 1]

                    # 如果当前文本比较简洁，下一个文本较长，可能当前是问题
                    if len(current_text) < len(next_text) and len(current_text) < 150:
                        markdown_content.append(f"\n#### Q: {current_text}\n")
                        markdown_content.append(f"\n#### A: {next_text}\n")
                        i += 2
                    else:
                        # 否则认为这是一个长的回答
                        markdown_content.append(f"\n#### A: {current_text}\n")
                        i += 1
                else:
                    # 最后一个文本，通常是一个回答
                    markdown_content.append(f"\n#### A: {current_text}\n")
                    i += 1

    if len(markdown_content) <= 1:
        # 如果转换后内容仍然很少，使用备用方案
        markdown_content = ["# Gemini 对话记录\n"]
        all_text = []
        for element in content_elements:
            text = element.get_text().strip()
            if text and len(text) > 10:
                skip_keywords = ['sign in', 'sign up', 'login', 'sign in with', 'google', 'account']
                if not any(keyword in text.lower() for keyword in skip_keywords):
                    all_text.append(text)

        # 简单分组，每两个为一组（问题和答案）
        for j, text in enumerate(all_text):
            if j % 2 == 0:
                markdown_content.append(f"\n#### Q: {text}\n")
            else:
                markdown_content.append(f"\n#### A: {text}\n")

        if len(all_text) == 0:
            markdown_content.append("未能从链接中提取到有意义的内容，请确认链接是否可访问。\n")

    return "\n".join(markdown_content)

def save_to_file(content, filename):
    """
    将 Markdown 内容保存到文件
    """
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Markdown 文件已保存为: {filename}")

def main():
    if len(sys.argv) != 2:
        print("使用方法: python gemini_to_md.py <gemini_conversation_url>")
        sys.exit(1)

    url = sys.argv[1]

    # 验证 URL 格式
    parsed_url = urlparse(url)
    if not parsed_url.scheme or not parsed_url.netloc:
        print("错误: 请输入有效的 URL")
        sys.exit(1)

    print("正在获取 Gemini 对话内容...")

    # 首先尝试使用 Selenium 获取内容（支持 JavaScript）
    content_elements = extract_gemini_content_selenium(url)

    # 如果 Selenium 方法没有提取到足够的内容，则回退到静态方法
    if not content_elements or len(content_elements) == 0:
        print("Selenium 方法未获取到足够内容，尝试静态方法...")
        content_elements = extract_gemini_content_static(url)

    if not content_elements:
        print("错误: 无法获取对话内容，请检查链接是否可访问")
        sys.exit(1)

    print("正在转换为 Markdown 格式...")
    markdown_content = convert_to_markdown(content_elements)

    # 生成输出文件名
    filename = "gemini_conversation.md"

    # 检查文件是否存在，如存在则添加数字后缀
    counter = 1
    original_filename = filename
    while os.path.exists(filename):
        name, ext = os.path.splitext(original_filename)
        filename = f"{name}_{counter}{ext}"
        counter += 1

    save_to_file(markdown_content, filename)

if __name__ == "__main__":
    main()