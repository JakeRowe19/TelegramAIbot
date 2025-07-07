import re
import os
import aiohttp
from dotenv import load_dotenv
from history import user_histories

load_dotenv()
WEATHERAPI_KEY = os.getenv('WEATHERAPI_KEY')

weather_confirmation = {}

# --- Вспомогательные функции для работы с городом ---
def extract_city_from_text(text):
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

def weather_emoji(description):
    desc = description.lower()
    if "ясно" in desc or "солнечно" in desc:
        return "☀️"
    if "облачно" in desc or "пасмурно" in desc:
        return "☁️"
    if "дожд" in desc or "ливень" in desc:
        return "🌧️"
    if "гроза" in desc:
        return "⛈️"
    if "снег" in desc or "метель" in desc:
        return "❄️"
    if "туман" in desc:
        return "🌫️"
    if "ветер" in desc:
        return "💨"
    if "мороз" in desc or "холод" in desc:
        return "🥶"
    if "тепло" in desc or "жарко" in desc:
        return "🌡️"
    return "🌈"

async def get_weatherapi_weather(city, update=None):
    url = f"http://api.weatherapi.com/v1/current.json?key={WEATHERAPI_KEY}&q={city}&lang=ru"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            if "current" in data:
                temp = data["current"]["temp_c"]
                descr = data["current"]["condition"]["text"]
                feels = data["current"]["feelslike_c"]
                emoji = weather_emoji(descr)
                text = f"{emoji} {descr.capitalize()}, {temp}°C (ощущается как {feels}°C)"
                return text
            elif "error" in data:
                return f"Ошибка: {data['error'].get('message', 'Не удалось получить погоду.')}"
    return "Не удалось получить погоду."

async def process_weather_message(update, user_message, user_id, SYSTEM_PROMPT):
    # --- Ожидание ввода города после просьбы ---
    if user_id in weather_confirmation and weather_confirmation[user_id] is None:
        city = user_message.strip()
        await update.message.reply_text(f"Погода в {city}. Всё верно?")
        weather_confirmation[user_id] = city
        return True

    # --- Подтверждение города для погоды ---
    if user_id in weather_confirmation and weather_confirmation[user_id] is not None:
        city = weather_confirmation[user_id]
        if user_message.lower() in ["да", "верно", "да, верно", "yes", "correct"]:
            result = await get_weatherapi_weather(city, update)
            if result:
                await update.message.reply_text(f"Погода в {city}: {result}")
            del weather_confirmation[user_id]
            return True
        elif user_message.lower() in ["нет", "no", "не верно", "неверно"]:
            await update.message.reply_text("Пожалуйста, укажите город для прогноза погоды.")
            weather_confirmation[user_id] = None
            return True

    # --- Обработка погоды с уточнением города и подтверждением ---
    weather_keywords = ["погода", "weather", "дождь", "температура", "осадки", "солнечно", "облачно", "ветер"]
    if any(word in user_message.lower() for word in weather_keywords):
        city = extract_city_from_text(user_message)
        if not city:
            history = user_histories.get(user_id, [])
            city = get_last_city_from_history(history)
            if not city:
                await update.message.reply_text("Пожалуйста, укажите город для прогноза погоды.")
                weather_confirmation[user_id] = None
                return True
            else:
                await update.message.reply_text(f"Погода в {city}. Всё верно?")
                weather_confirmation[user_id] = city
                return True
        else:
            await update.message.reply_text(f"Погода в {city}. Всё верно?")
            weather_confirmation[user_id] = city
            return True
    return False 