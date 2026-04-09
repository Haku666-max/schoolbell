from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)


def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎲 Факт моего года"), KeyboardButton(text="🌍 Случайный год")],
            [KeyboardButton(text="⭐ Избранное"), KeyboardButton(text="📊 Моя статистика")]
        ],
        resize_keyboard=True
    )


def admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛠 Админка"), KeyboardButton(text="🏠 Пользовательское меню")],
            [KeyboardButton(text="➕ Добавить карточку"), KeyboardButton(text="📚 Последние карточки")],
            [KeyboardButton(text="🔎 Найти по ID"), KeyboardButton(text="🔍 Найти по слову")],
            [KeyboardButton(text="📊 Общая статистика"), KeyboardButton(text="📦 Кол-во карточек")]
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

def admin_weight_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1", callback_data="weight:1"),
                InlineKeyboardButton(text="2", callback_data="weight:2"),
                InlineKeyboardButton(text="3", callback_data="weight:3"),
            ],
            [
                InlineKeyboardButton(text="5", callback_data="weight:5"),
                InlineKeyboardButton(text="10", callback_data="weight:10"),
            ]
        ]
    )

def admin_category_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🌍 Мир", callback_data="cat:world"),
                InlineKeyboardButton(text="⚔️ Война", callback_data="cat:war")
            ],
            [
                InlineKeyboardButton(text="🎵 Культура", callback_data="cat:culture"),
                InlineKeyboardButton(text="🔬 Наука", callback_data="cat:science")
            ],
            [
                InlineKeyboardButton(text="💻 Технологии", callback_data="cat:tech"),
                InlineKeyboardButton(text="📦 Другое", callback_data="cat:other")
            ]
        ]
    )


def admin_fact_actions_kb(fact_id: int, is_active: int):
    active_text = "🔴 Выключить" if is_active == 1 else "🟢 Включить"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Текст", callback_data=f"edit_text:{fact_id}"),
                InlineKeyboardButton(text="🖼 Фото", callback_data=f"edit_image:{fact_id}")
            ],
            [
                InlineKeyboardButton(text="🗂 Категория", callback_data=f"edit_category:{fact_id}"),
                InlineKeyboardButton(text="📅 Год", callback_data=f"edit_year:{fact_id}")
            ],
            [
                InlineKeyboardButton(text="⚖️ Вес", callback_data=f"edit_weight:{fact_id}"),
                InlineKeyboardButton(text=active_text, callback_data=f"toggle_active:{fact_id}")
            ],
            [
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_fact:{fact_id}")
            ]
        ]
    )


def admin_confirm_delete_kb(fact_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete:{fact_id}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_delete:{fact_id}")
            ]
        ]
    )


def admin_search_results_kb(facts):
    rows = []
    for fact in facts:
        preview = (fact["content"] or "").replace("\n", " ").strip()
        if len(preview) > 25:
            preview = preview[:25] + "..."
        rows.append([
            InlineKeyboardButton(
                text=f"#{fact['id']} {preview or 'Без текста'}",
                callback_data=f"open_fact:{fact['id']}"
            )
        ])

    if not rows:
        rows = [[InlineKeyboardButton(text="Ничего не найдено", callback_data="noop")]]

    return InlineKeyboardMarkup(inline_keyboard=rows)