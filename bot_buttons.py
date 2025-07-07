from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

def get_main_reply_keyboard():
    keyboard = [
        ["Погода", "О боте"],
        ["Сбросить контекст"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_main_inline_keyboard():
    keyboard = [
        [InlineKeyboardButton("Сайт", url="https://example.com")],
        [InlineKeyboardButton("Поддержка", callback_data="support")]
    ]
    return InlineKeyboardMarkup(keyboard) 