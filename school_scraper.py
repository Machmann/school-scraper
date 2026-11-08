import os
import json
import re
import urllib.request
import urllib.error

# ==================== 1. 抓取模块 ====================
def fetch_school_events():
    """
    抓取目标学校网页文本
    """
    schools_config = {
        "FWG_KW": {
            "name": "Friedrich-Wilhelm-Gymnasium (KW)",
            "url": "https://fwg.dahme-spreewald.de/fwg/start"
        },
        "Gesamtschule_KW": {
            "name": "Gesamtschule KW (Oberstufe)",
            "url": "https://gesamtschule-kw.de"
        }
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    scraped_data = {}
    
    for key, info in schools_config.items():
        try:
            req = urllib.request.Request(info["url"], headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                html_text = response.read().decode('utf-8', errors='ignore')
                
                # 清洗 HTML 标签，保留纯文本供 AI 分析
                clean_text = re.sub(r'<script.*?>.*?</script>', '', html_text, flags=re.DOTALL)
                clean_text = re.sub(r'<style.*?>.*?</style>', '', clean_text, flags=re.DOTALL)
                clean_text = re.sub(r'<[^>]+>', ' ', clean_text)
                clean_text = ' '.join(clean_text.split())[:3500]  # 截取前 3500 字
                
                scraped_data[info["name"]] = clean_text
        except Exception as e:
            print(f"[{info['name']}] 抓取异常: {e}")
            
    return scraped_data

# ==================== 2. LLM 结构化提取模块 ====================
def extract_events_with_llm(scraped_data, api_key=None, model_name="gemini-1.5-flash"):
    """
    调用 Google Gemini API (免费版) 提取 JSON 结构化活动
    """
    # 支持 GEMINI_API_KEY 或 GOOGLE_API_KEY 环境变量
    api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        print("\n[提示] 未检测到 GEMINI_API_KEY 环境变量，使用演示模拟数据运行...")
        return [
            {
                "school": "Friedrich-Wilhelm-Gymnasium (KW)",
                "event_name": "Tag der offenen Tür (开放日)",
                "date": "2027-01-22 15:30-18:30",
                "target_group": "未来7年级新生及家长",
                "summary": "入校实地参观与教学特色介绍",
                "url": "https://fwg.dahme-spreewald.de/fwg/start"
            },
            {
                "school": "Gesamtschule KW (Oberstufe)",
                "event_name": "Informationsabend zur gymnasialen Oberstufe (高中部宣讲会)",
                "date": "2027-01-15 18:00-20:00",
                "target_group": "10年级毕业生及家长",
                "summary": "介绍高中阶段课程设置与入学申请要求",
                "url": "https://gesamtschule-kw.de"
            }
        ]

    prompt = f"""
    请分析以下学校网页的文本内容，提取发生在今天之后或即将举行的活动（如 Tag der offenen Tür, Infoveranstaltung, Sportfest, Elternabend 等）。
    忽略过去的历史活动。如果某所学校没有提及即将举行的活动，请不要虚构。

    网页文本数据：
    {json.dumps(scraped_data, ensure_ascii=False)}

    请严格按以下 JSON 数组格式输出提取结果（只返回 JSON 数组，不要任何多余标记或文本说明）：
    [
      {{
        "school": "学校名称",
        "event_name": "活动名称",
        "date": "YYYY-MM-DD 或具体时间描述",
        "target_group": "目标人群",
        "summary": "简短摘要",
        "url": "网址"
      }}
    ]
    """
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            raw_content = result["candidates"][0]["content"]["parts"][0]["text"].strip()
            
            # 清理可能的 markdown 代码块标记
            if raw_content.startswith("```"):
                raw_content = re.sub(r'^```(?:json)?\s*', '', raw_content)
                raw_content = re.sub(r'\s*```$', '', raw_content)
                
            return json.loads(raw_content)
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode('utf-8', errors='ignore')
        print(f"Google Gemini API 请求错误 ({e.code}): {error_msg}")
        return []
    except Exception as e:
        print(f"数据解析失败: {e}")
        return []

# ==================== 3. 消息推送模块 ====================
def send_telegram_notification(events, bot_token=None, chat_id=None):
    """
    推送格式化消息至 Telegram Bot
    """
    if not events:
        print("未发现新活动。")
        return

    bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
    
    message_lines = ["🏫 **KW 及周边 Gymnasium 最新活动简报**\n"]
    for item in events:
        message_lines.append(f"📌 **{item['school']}**")
        message_lines.append(f"🎉 活动：{item['event_name']}")
        message_lines.append(f"📅 时间：{item['date']}")
        message_lines.append(f"👥 对象：{item['target_group']}")
        message_lines.append(f"📝 简介：{item['summary']}")
        message_lines.append(f"🔗 [点击查看官网]({item.get('url', '')})\n")
        
    full_message = "\n".join(message_lines)
    
    if not bot_token or not chat_id:
        print("\n================ [ Telegram 消息格式输出预览 ] ================")
        print(full_message)
        print("==============================================================")
        return

    telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": full_message,
        "parse_mode": "Markdown"
    }
    
    try:
        req = urllib.request.Request(
            telegram_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            print("Telegram 推送成功！")
    except Exception as e:
        print(f"Telegram 推送失败: {e}")

# ==================== 主入口与测试 ====================
if __name__ == "__main__":
    print(">>> [1/3] 开始抓取学校网页数据...")
    scraped_text = fetch_school_events()
    
    print("\n>>> [2/3] 开始使用大模型提取结构化数据...")
    parsed_events = extract_events_with_llm(scraped_text)
    
    print("\n>>> [3/3] 部署推送/展示格式化预览...")
    send_telegram_notification(parsed_events)
