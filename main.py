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


MODEL_ID = "gemini-2.5-flash-preview-09-2025"
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

    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=user_sessions[user_id] + [current_user_msg],
            config={
                "system_instruction": SYSTEM_INSTRUCTION,
                "temperature": 0.7
            }
        )

        model_reply_text = response.text
        model_msg = {"role": "model", "parts": [{"text": model_reply_text}]}
        user_sessions[user_id].append(current_user_msg)
        user_sessions[user_id].append(model_msg)
        user_sessions[user_id] = user_sessions[user_id][-20:]
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=model_reply_text)
        )

    except Exception as e:
        print(f"Error handling message: {e}")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="I'm sorry, I'm a little tired. Can we talk again in a minute?")
        )


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))