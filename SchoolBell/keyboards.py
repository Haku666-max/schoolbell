from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎲 Получить факт")],
            [KeyboardButton(text="⭐ Избранное"), KeyboardButton(text="📊 Моя статистика")]
        ],
        resize_keyboard=True
    )


def admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛠 Админка")],
            [KeyboardButton(text="📊 Общая статистика"), KeyboardButton(text="📦 Кол-во карточек")],
            [KeyboardButton(text="🏠 Обычное меню")]
        ],
        resize_keyboard=True
    )


def fact_kb(is_fav: bool):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔁 Ещё", callback_data="next"),
                InlineKeyboardButton(
                    text="⭐ Убрать из избранного" if is_fav else "⭐ В избранное",
                    callback_data="fav"
                )
            ]
        ]
    )