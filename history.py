import json
import os
import time

HISTORY_FILE = "user_histories.json"
MAX_HISTORY_LENGTH = 20
MAX_HISTORY_FILE_SIZE = 10 * 1024 * 1024  # 10 МБ
INACTIVITY_DAYS = 30

user_histories = {}

def save_histories(user_histories):
    cleanup_histories(user_histories)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(user_histories, f, ensure_ascii=False, indent=2)

def load_histories():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def cleanup_histories(user_histories):
    now = time.time()
    # Очистка по времени неактивности
    to_delete = []
    for user_id, data in user_histories.items():
        last_active = data.get("last_active")
        if last_active and now - last_active > INACTIVITY_DAYS * 24 * 3600:
            to_delete.append(user_id)
    for user_id in to_delete:
        del user_histories[user_id]
    # Очистка по размеру файла
    if os.path.exists(HISTORY_FILE) and os.path.getsize(HISTORY_FILE) > MAX_HISTORY_FILE_SIZE:
        # Удаляем самых старых пользователей, пока файл не станет меньше лимита
        sorted_users = sorted(user_histories.items(), key=lambda x: x[1].get("last_active", 0))
        while os.path.getsize(HISTORY_FILE) > MAX_HISTORY_FILE_SIZE and sorted_users:
            oldest_user = sorted_users.pop(0)[0]
            del user_histories[oldest_user]

# Загружаем истории при импорте
user_histories.update(load_histories()) 