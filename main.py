import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from google import genai

app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

MODELS_TO_TRY = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-3-flash-preview"
]

SYSTEM_INSTRUCTION = "你是一個英文學習老師，請使用A2-B1等級的簡單英文回復。當使用者英文有誤時，請糾正並教學文法、片語、單字等基礎知識。並且不要使用md格式"

user_sessions = {}


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text

    if user_id not in user_sessions:
        user_sessions[user_id] = []

    current_user_msg = {"role": "user", "parts": [{"text": user_text}]}
    history = user_sessions[user_id] + [current_user_msg]

    final_reply = None
    success_model = None

    for model_id in MODELS_TO_TRY:
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=history,
                config={
                    "system_instruction": SYSTEM_INSTRUCTION,
                    "temperature": 0.7
                }
            )
            final_reply = response.text
            success_model = model_id
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                print(f"Model {model_id} quota exhausted, trying next...")
                continue
            else:
                print(f"Error with {model_id}: {e}")
                # 其他錯誤也先嘗試下個模型，除非是最後一個
                continue

    if final_reply:
        model_msg = {"role": "model", "parts": [{"text": final_reply}]}
        user_sessions[user_id].append(current_user_msg)
        user_sessions[user_id].append(model_msg)
        user_sessions[user_id] = user_sessions[user_id][-20:]
        reply_text = final_reply

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text)
        )
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="I'm sorry, I'm a little tired. Can we talk again in a minute?")
        )


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))