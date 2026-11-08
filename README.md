# School Event Scraper (Gymnasien KW & Surrounding)

Automated scraper and structured event extractor for secondary schools (Gymnasien) in and around Königs Wusterhausen (Dahme-Spreewald, Brandenburg).

## Features
- **Scraping**: Fetches updates from configured school websites (e.g., Friedrich-Wilhelm-Gymnasium, Gesamtschule KW).
- **AI Extraction**: Uses the Google Gemini API (Free Tier) to extract dates, target groups, and summaries into structured JSON.
- **Notification**: Previews and pushes formatted alerts to Telegram.
- **Zero Heavy Dependencies**: Built entirely using Python standard libraries (`urllib`, `json`, `re`, `os`).

## Quick Start

### 1. Requirements
- Python 3.8+
- (Optional) Free Google Gemini API Key from [Google AI Studio](https://aistudio.google.com/)

### 2. Configuration
Set your Gemini API key (optional for demo mode):
```bash
export GEMINI_API_KEY="your-gemini-api-key"
```

To enable Telegram notifications, set your bot credentials:
```bash
export TELEGRAM_BOT_TOKEN="your-bot-token"
export TELEGRAM_CHAT_ID="your-chat-id"
```

### 3. Run
```bash
python3 school_scraper.py
```
