import os
import logging
import openai
import asyncio
import nest_asyncio
import re
import time

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler

from dotenv import load_dotenv
from datetime import datetime
from history import user_histories, MAX_HISTORY_LENGTH, save_histories
from bot_buttons import get_main_reply_keyboard, get_main_inline_keyboard

from image_handler import handle_photo
from weather_handler import process_weather_message


load_dotenv()

print("Script started")


# Функция для обработки команды /start
async def start(update: Update, context) -> None:
    await update.message.reply_text(
        'Привет! Я чат-бот. Чем могу помочь?',
        reply_markup=get_main_reply_keyboard()
    )

#Логируются только ошибки
logging.getLogger("httpx").setLevel(logging.WARNING)

# Логи
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Read API keys from environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
AI_model = os.getenv('OPENROUTER_MODEL')

print(f"AI_model: {AI_model}")


if not TELEGRAM_TOKEN or not OPENROUTER_API_KEY:
    raise ValueError("Please set TELEGRAM_BOT_TOKEN and OPENROUTER_API_KEY environment variables.")

# Initialize OpenRouter client
client = openai.OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

SYSTEM_PROMPT = "Ты Telegram ассистент. Всегда отвечай кратко и по делу. Преимущественно используй русский язык."

# --- Вспомогательные функции для работы с городом ---
def extract_city_from_text(text):
    # Ищем слова после 'в' или 'по' и до конца строки/знака препинания
    match = re.search(r"(?:в|по)\s+([А-Яа-яA-Za-z\- ]+)", text)
    if match:
        return match.group(1).strip()
    return None

def get_last_city_from_history(history):
    for msg in reversed(history):
        if msg["role"] == "user":
            city = extract_city_from_text(msg["content"])
            if city:
                return city
    return None

weather_confirmation = {}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.message.from_user:
        return
    user_message = update.message.text
    user_id = update.message.from_user.id
    now = time.time()

    # Сброс контекста по кнопке
    if user_message.lower() == "сбросить контекст":
        user_histories[user_id] = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT}
            ],
            "last_active": now
        }
        save_histories(user_histories)
        await update.message.reply_text("Контекст сброшен!")
        return

    # --- Обработка погоды через weather_handler ---
    handled = await process_weather_message(update, user_message, user_id, SYSTEM_PROMPT)
    if handled:
        return

    # Контекст
    if user_id not in user_histories:
        user_histories[user_id] = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT}
            ],
            "last_active": now
        }
        # Уведомление админу о новом пользователе
        try:
            user_name = update.effective_user.full_name if update.effective_user else str(user_id)
            await context.bot.send_message(chat_id=ADMIN_USER_ID, text=f"👤 Новый пользователь: {user_name} (id: {user_id})")
        except Exception:
            pass

    user_histories[user_id]["messages"].append({"role": "user", "content": user_message})
    user_histories[user_id]["last_active"] = now
    save_histories(user_histories)

    # --- Обработка погоды с уточнением города и подтверждением ---
    weather_keywords = ["погода", "weather", "дождь", "температура", "осадки", "солнечно", "облачно", "ветер"]
    if any(word in user_message.lower() for word in weather_keywords):
        city = extract_city_from_text(user_message)
        if not city:
            city = get_last_city_from_history(user_histories[user_id]["messages"])
            if not city:
                await update.message.reply_text("Пожалуйста, укажите город для прогноза погоды.")
                return
            else:
                await update.message.reply_text(f"Погода в {city}. Всё верно?")
                weather_confirmation[user_id] = city
                return
        else:
            await update.message.reply_text(f"Погода в {city}. Всё верно?")
            weather_confirmation[user_id] = city
            return

    # Проверка на вопрос о погоде
    weather_keywords = ["погода", "weather", "дождь", "температура", "осадки", "солнечно", "облачно", "ветер"]
    if any(word in user_message.lower() for word in weather_keywords):
        today = datetime.now().strftime("%Y-%m-%d")
        user_histories[user_id]["messages"].append({
            "role": "system",
            "content": f"Сегодняшняя дата: {today}. Используй эту дату для ответа на вопросы о погоде."
        })

    # Оставляем только последние MAX_HISTORY_LENGTH сообщений (system prompt + остальные)
    if len(user_histories[user_id]["messages"]) > MAX_HISTORY_LENGTH:
        user_histories[user_id]["messages"] = [user_histories[user_id]["messages"][0]] + user_histories[user_id]["messages"][-(MAX_HISTORY_LENGTH-1):]

    try:
        completion = client.chat.completions.create(
            extra_headers={
                # "HTTP-Referer": "<YOUR_SITE_URL>",  # Optional
                "X-Title": "<BOT>",      # Optional
            },
            extra_body={},
            model=AI_model,
            messages=user_histories[user_id]["messages"]
        )
        bot_reply = completion.choices[0].message.content.strip()
        # Добавляем ответ бота в историю
        user_histories[user_id]["messages"].append({"role": "assistant", "content": bot_reply})
        user_histories[user_id]["last_active"] = now
        save_histories(user_histories)
    except Exception as e:
        logging.error(f"OpenRouter API error: {e}")
        if "rate limit" in str(e).lower() or "429" in str(e):
            bot_reply = "Лимит бесплатных запросов к ИИ исчерпан. Попробуйте позже."
        else:
            bot_reply = "Sorry, I couldn't process your request."
        await update.message.reply_text(bot_reply)

# Глобальный error handler
ADMIN_USER_ID = 420843521
async def error_handler(update, context):
    logging.error(msg := f"Exception while handling an update: {context.error}")
    try:
        if update and getattr(update, 'message', None):
            await update.message.reply_text("Произошла внутренняя ошибка. Попробуйте позже.")
        # Уведомление админу
        error_text = f"❗️ Ошибка у пользователя {getattr(update.effective_user, 'id', 'N/A')}:\n{context.error}"
        await context.bot.send_message(chat_id=ADMIN_USER_ID, text=error_text)
    except Exception:
        pass

async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    # Handle all text messages
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CommandHandler("start", start))
    app.add_error_handler(error_handler)
    logging.info("Bot started.")
    await app.run_polling()

if __name__ == '__main__':
    import asyncio
    import nest_asyncio
    nest_asyncio.apply()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
        

print("Script started2")