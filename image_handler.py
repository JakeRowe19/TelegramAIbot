# type: ignore
import os
import logging
import base64
from telegram import Update
from telegram.ext import ContextTypes
from dotenv import load_dotenv
from history import user_histories, MAX_HISTORY_LENGTH

load_dotenv()

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
VISION_MODEL = "google/gemini-2.0-flash-exp:free"

import openai
client = openai.OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

MAX_MESSAGE_LENGTH = 4096

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.photo or not update.message.from_user:
        return
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    file_path = f"temp_{photo.file_id}.jpg"
    await file.download_to_drive(file_path)

    with open(file_path, "rb") as image_file:
        image_bytes = image_file.read()
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    # Используем подпись пользователя, если она есть, иначе стандартный промпт
    user_text = update.message.caption if update.message.caption else "Опиши, что изображено на картинке. Ответь на русском языке, кратко и понятно."
    if "на русском" not in user_text.lower():
        user_text += " Ответь на русском языке."

    user_id = update.message.from_user.id

    # Добавляем caption пользователя в историю (если есть)
    if update.message.caption:
        if user_id not in user_histories:
            user_histories[user_id] = []
        user_histories[user_id].append({"role": "user", "content": update.message.caption})

    # Обрезаем историю, если она превышает MAX_HISTORY_LENGTH
    if user_id in user_histories and len(user_histories[user_id]) > MAX_HISTORY_LENGTH:
        user_histories[user_id] = [user_histories[user_id][0]] + user_histories[user_id][-(MAX_HISTORY_LENGTH-1):]

    try:
        completion = client.chat.completions.create(  # type: ignore
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": f"data:image/jpeg;base64,{image_base64}"}
                    ]
                }
            ]
        )
        bot_reply = completion.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Vision API error: {e}")
        bot_reply = "Не удалось распознать изображение."

    # Добавляем ответ бота в историю
    if user_id not in user_histories:
        user_histories[user_id] = []
    user_histories[user_id].append({"role": "assistant", "content": bot_reply})

    # Отправляем ответ частями, если он слишком длинный
    for i in range(0, len(bot_reply), MAX_MESSAGE_LENGTH):
        await update.message.reply_text(bot_reply[i:i+MAX_MESSAGE_LENGTH])

    os.remove(file_path) 