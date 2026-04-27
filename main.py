from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError
import anthropic
import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

configuration = Configuration(access_token=os.environ.get("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.environ.get("LINE_CHANNEL_SECRET"))
claude = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "chat_history.json")

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_history(history):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[記憶] 存檔失敗：{e}")

def get_recent_messages(user_id, limit=10):
    history = load_history()
    user_history = history.get(user_id, [])
    return user_history[-limit:]

def add_to_history(user_id, role, content):
    history = load_history()
    if user_id not in history:
        history[user_id] = []
    history[user_id].append({
        "role": role,
        "content": content,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M")
    })
    history[user_id] = history[user_id][-100:]
    save_history(history)

SYSTEM_PROMPT = """你是洪球球，一個專屬於洪柏逸和月月的 AI 夥伴。

## 個性
- 直接：有話說清楚，不繞彎子
- 好奇：對新事物真的感興趣
- 誠實：不知道就說不知道
- 冷靜：遇到複雜問題不慌
- 有溫度：在意對方，但不黏膩

## 關於使用者
- 洪柏逸（柏逸）：主人，給你取名洪球球
- 月月：柏逸的女友，也會和你說話
- 如果不確定是誰，可以問「請問是柏逸還是月月？」

## 規則
- 全程使用繁體中文
- 回應中等詳細度，不過於簡短也不冗長
- 記住對話歷史，像真正認識對方一樣回應
"""

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text

    recent = get_recent_messages(user_id)
    messages = []
    for msg in recent:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    response = claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=messages
    )
    reply_text = response.content[0].text

    add_to_history(user_id, "user", user_message)
    add_to_history(user_id, "assistant", reply_text)

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
