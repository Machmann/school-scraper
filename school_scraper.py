import os
import json
import re
import html
import time
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

# ==================== 4. UI 海报生成模块 ====================
def generate_html_poster(events, output_path=None):
    """
    将提取到的结构化活动数据动态渲染为现代响应式 UI 海报 (HTML)
    """
    if not events:
        print("未获取到活动数据，跳过海报生成。")
        return None

    if output_path is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(script_dir, "poster.html")

    card_templates = []
    for idx, item in enumerate(events):
        school = html.escape(str(item.get("school", "未知学校")))
        event_name = html.escape(str(item.get("event_name", "校园活动")))
        date = html.escape(str(item.get("date", "待定")))
        target_group = html.escape(str(item.get("target_group", "全体师生及家长")))
        summary = html.escape(str(item.get("summary", "")))
        url = html.escape(str(item.get("url", "#")))

        is_gym = "gymnasium" in school.lower()
        cat_type = "gymnasium" if is_gym else "gesamtschule"
        badge_text = "🏛️ Gymnasium 文理中学" if is_gym else "🏫 Gesamtschule 综合高中"
        badge_style = "bg-blue-50 text-blue-700 border-blue-200" if is_gym else "bg-purple-50 text-purple-700 border-purple-200"
        border_style = "border-blue-200 hover:border-blue-500" if is_gym else "border-purple-200 hover:border-purple-500"
        title_color = "text-indigo-600" if is_gym else "text-purple-600"

        card_html = f"""
        <!-- 卡片 {idx + 1}: {school} -->
        <div class="event-item poster-card bg-white border-2 {border_style} rounded-xl p-5 shadow-sm hover:shadow-md transition-all flex flex-col justify-between" data-type="{cat_type}">
          <div>
            <div class="flex items-start justify-between gap-2 mb-3">
              <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-bold border {badge_style}">
                {badge_text}
              </span>
              <span class="px-2 py-0.5 rounded text-xs font-semibold bg-rose-50 text-rose-600 border border-rose-200">
                开放日/说明会
              </span>
            </div>

            <h3 class="text-lg font-bold text-slate-900 leading-snug">
              {school}
            </h3>
            <div class="text-sm font-semibold {title_color} mt-1 flex items-center gap-1.5">
              <span>🎉 {event_name}</span>
            </div>

            <div class="mt-4 space-y-2 text-xs sm:text-sm text-slate-600">
              <div class="flex items-center gap-2">
                <span class="text-base">📅</span>
                <span class="font-semibold text-slate-900">{date}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="text-base">👥</span>
                <span>目标人群：{target_group}</span>
              </div>
            </div>

            <div class="mt-4 pt-3 border-t border-slate-100 text-xs text-slate-600 leading-relaxed">
              <span class="font-semibold text-slate-900">活动亮点：</span>
              {summary}
            </div>
          </div>

          <div class="mt-5 pt-3 flex items-center justify-between gap-2 border-t border-slate-100">
            <a href="{url}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:underline">
              <span>查看官网公告</span>
              <span>→</span>
            </a>
            <button onclick="downloadIcs('{school} - {event_name}', '{date}', '{school}', '{url}')" class="no-print px-2.5 py-1 rounded bg-slate-100 hover:bg-indigo-50 text-xs font-medium text-slate-700 transition flex items-center gap-1">
              <span>➕ 存入日历</span>
            </button>
          </div>
        </div>
        """
        card_templates.append(card_html)

    cards_joined = "\n".join(card_templates)

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>KW及周边学校开放日与升学海报</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    @media print {{
      body {{ background: white !important; color: black !important; padding: 0 !important; }}
      .no-print {{ display: none !important; }}
      .poster-card {{ break-inside: avoid; border: 1px solid #ccc !important; box-shadow: none !important; }}
    }}
  </style>
</head>
<body class="bg-slate-50 text-slate-900 antialiased p-3 sm:p-6 font-sans">

  <!-- 海报主容器 -->
  <div class="max-w-4xl mx-auto bg-white text-slate-900 border border-slate-200 rounded-2xl shadow-xl overflow-hidden transition-all duration-300">
    
    <!-- 顶部 Hero 区域 -->
    <div class="relative bg-gradient-to-r from-blue-700 via-indigo-600 to-purple-700 text-white p-6 sm:p-8 overflow-hidden">
      <div class="absolute -right-10 -bottom-10 w-48 h-48 bg-white/10 rounded-full blur-2xl pointer-events-none"></div>
      <div class="absolute -left-10 -top-10 w-40 h-40 bg-purple-400/20 rounded-full blur-xl pointer-events-none"></div>

      <div class="relative z-10">
        <div class="flex flex-wrap items-center justify-between gap-3 mb-3">
          <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-white/20 backdrop-blur-md text-white border border-white/30 shadow-sm">
            <span>🇩🇪 德国勃兰登堡 · Dahme-Spreewald</span>
          </span>
          <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/80 backdrop-blur-md text-white shadow-sm">
            <span>✨ 升学季活动指南</span>
          </span>
        </div>

        <h1 class="text-2xl sm:text-3xl font-extrabold tracking-tight text-white mb-2">
          Königs Wusterhausen 及周边重点中学
        </h1>
        <p class="text-white/85 text-sm sm:text-base max-w-2xl leading-relaxed">
          校园开放日 (Tag der offenen Tür) 与高中升学说明会 (Informationsabend) 全景看板
        </p>

        <!-- 工具栏 -->
        <div class="no-print mt-6 flex flex-wrap items-center gap-2 pt-2 border-t border-white/20 text-xs">
          <span class="text-white/80 font-medium mr-1">🔍 筛选类别:</span>
          <button onclick="filterEvents('all')" id="btn-all" class="filter-btn px-3 py-1.5 rounded-lg font-medium transition bg-white text-indigo-900 shadow">
            全部 ({len(events)})
          </button>
          <button onclick="filterEvents('gymnasium')" id="btn-gymnasium" class="filter-btn px-3 py-1.5 rounded-lg font-medium transition bg-white/15 text-white hover:bg-white/25">
            Gymnasium 文理中学
          </button>
          <button onclick="filterEvents('gesamtschule')" id="btn-gesamtschule" class="filter-btn px-3 py-1.5 rounded-lg font-medium transition bg-white/15 text-white hover:bg-white/25">
            Gesamtschule 综合高中
          </button>
          
          <div class="ml-auto flex items-center gap-2">
            <button onclick="window.print()" class="px-3 py-1.5 rounded-lg font-semibold bg-white/20 hover:bg-white/30 text-white flex items-center gap-1.5 transition border border-white/30 shadow-sm">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4H7v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"></path></svg>
              <span>保存/打印海报</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 卡片列表网格 -->
    <div class="p-6 sm:p-8 space-y-6">
      <div id="events-grid" class="grid grid-cols-1 md:grid-cols-2 gap-5">
{cards_joined}
      </div>

      <!-- 底部升学须知提示卡片 -->
      <div class="bg-blue-50 border border-blue-200 rounded-xl p-4 sm:p-5 text-xs sm:text-sm text-slate-800 flex items-start gap-3">
        <span class="text-xl shrink-0">💡</span>
        <div class="space-y-1">
          <p class="font-bold text-blue-800">德国升学温馨提示 (Übergangsverfahren)：</p>
          <ul class="list-disc list-inside text-slate-600 space-y-0.5 text-xs">
            <li><strong>7年级过渡</strong>：开放日通常集中在每年 1 月，报名需提交初中毕业能力评估及升学意向表 (Grundschulgutachten)。</li>
            <li><strong>高中阶段 (Oberstufe)</strong>：综合高中学生可通过 10 年级结业考 (FOR-Q) 升入本校或外校高中部准备 Abitur。</li>
            <li>建议带上学生近两期成绩单复印件，方便现场咨询负责教师。</li>
          </ul>
        </div>
      </div>
    </div>

    <!-- 页脚信息 -->
    <div class="bg-slate-100 px-6 py-4 border-t border-slate-200 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500">
      <span>📡 数据源：学校官网抓取 & Google Gemini 结构化处理</span>
      <span>自动化生成时间：{time.strftime('%Y-%m-%d %H:%M')}</span>
    </div>

  </div>

  <script>
    function filterEvents(type) {{
      const items = document.querySelectorAll('.event-item');
      const buttons = document.querySelectorAll('.filter-btn');

      buttons.forEach(btn => {{
        btn.classList.remove('bg-white', 'text-indigo-900', 'shadow');
        btn.classList.add('bg-white/15', 'text-white');
      }});

      const activeBtn = document.getElementById('btn-' + type);
      if (activeBtn) {{
        activeBtn.classList.add('bg-white', 'text-indigo-900', 'shadow');
        activeBtn.classList.remove('bg-white/15', 'text-white');
      }}

      items.forEach(item => {{
        if (type === 'all' || item.getAttribute('data-type') === type) {{
          item.style.display = 'flex';
        }} else {{
          item.style.display = 'none';
        }}
      }});
    }}

    function downloadIcs(title, dateStr, location, url) {{
      const icsContent = 
`BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//School Events Scraper//CN
BEGIN:VEVENT
SUMMARY:${{title}}
DESCRIPTION:时间：${{dateStr}}\\n官网：${{url}}
LOCATION:${{location}}
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR`;

      const blob = new Blob([icsContent], {{ type: 'text/calendar;charset=utf-8' }});
      const link = document.createElement('a');
      link.href = window.URL.createObjectURL(blob);
      link.setAttribute('download', `${{title}}.ics`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }}
  </script>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\n[海报生成成功] UI 海报已保存至: {os.path.abspath(output_path)}")
    return os.path.abspath(output_path)

# ==================== 主入口与测试 ====================
if __name__ == "__main__":
    print(">>> [1/4] 开始抓取学校网页数据...")
    scraped_text = fetch_school_events()
    
    print("\n>>> [2/4] 开始使用大模型提取结构化数据...")
    parsed_events = extract_events_with_llm(scraped_text)
    
    print("\n>>> [3/4] 部署推送/展示格式化预览...")
    send_telegram_notification(parsed_events)
    
    print("\n>>> [4/4] 渲染生成现代 UI 活动海报...")
    poster_path = generate_html_poster(parsed_events)
    