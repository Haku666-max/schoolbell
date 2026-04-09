from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def mode_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Серьёзный", callback_data="mode:serious")
    builder.button(text="Мемный", callback_data="mode:funny")
    builder.button(text="Смешанный", callback_data="mode:mixed")
    builder.adjust(1)
    return builder.as_markup()


def after_result_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Ещё факты", callback_data="more")
    builder.button(text="Сменить режим", callback_data="change_mode")
    builder.button(text="Изменить год", callback_data="change_year")
    builder.adjust(1)
    return builder.as_markup()


def admin_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить карточку", callback_data="admin:add_fact")
    builder.button(text="🗂 Карточки", callback_data="admin:facts")
    builder.button(text="📊 Статистика", callback_data="admin:stats")
    builder.button(text="📚 Кол-во карточек", callback_data="admin:facts_count")
    builder.adjust(1)
    return builder.as_markup()


def admin_preview_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Сохранить", callback_data="admin:save_fact")
    builder.button(text="❌ Отмена", callback_data="admin:cancel_fact")
    builder.adjust(1)
    return builder.as_markup()


def admin_cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="admin:cancel_fact")
    builder.adjust(1)
    return builder.as_markup()


def admin_tone_keyboard(prefix: str = "admin_tone") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Серьёзный", callback_data=f"{prefix}:serious")
    builder.button(text="Мемный", callback_data=f"{prefix}:funny")
    builder.button(text="Смешанный", callback_data=f"{prefix}:mixed")
    builder.adjust(1)
    return builder.as_markup()


def admin_category_keyboard(prefix: str = "admin_category") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔬 Science", callback_data=f"{prefix}:science")
    builder.button(text="💻 Technology", callback_data=f"{prefix}:technology")
    builder.button(text="📜 History", callback_data=f"{prefix}:history")
    builder.button(text="➗ Math", callback_data=f"{prefix}:math")
    builder.button(text="😂 Meme", callback_data=f"{prefix}:meme")
    builder.button(text="📦 Other", callback_data=f"{prefix}:other")
    builder.adjust(2)
    return builder.as_markup()


def admin_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛠 Админка")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие"
    )


def admin_facts_list_keyboard(facts: list[dict], page: int, page_size: int = 5) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for fact in facts:
        title = fact.get("title") or fact.get("content", "")[:25] or f"ID {fact['id']}"
        title = title.replace("\n", " ").strip()
        if len(title) > 28:
            title = title[:28] + "..."
        builder.button(
            text=f"#{fact['id']} {title}",
            callback_data=f"fact_open:{fact['id']}"
        )

    if page > 0:
        builder.button(text="⬅️ Назад", callback_data=f"facts_page:{page-1}")
    if len(facts) == page_size:
        builder.button(text="➡️ Далее", callback_data=f"facts_page:{page+1}")

    builder.adjust(1)
    return builder.as_markup()


def admin_fact_actions_keyboard(fact_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Изменить текст", callback_data=f"fact_edit_text:{fact_id}")
    builder.button(text="🖼 Сменить фото", callback_data=f"fact_edit_image:{fact_id}")
    builder.button(text="🗂 Сменить категорию", callback_data=f"fact_edit_category:{fact_id}")
    builder.button(text="🎭 Сменить тон", callback_data=f"fact_edit_tone:{fact_id}")
    builder.button(text="📅 Сменить год", callback_data=f"fact_edit_year:{fact_id}")
    builder.button(text="🗑 Удалить", callback_data=f"fact_delete:{fact_id}")
    builder.button(text="⬅️ К списку", callback_data="facts_page:0")
    builder.adjust(1)
    return builder.as_markup()


def confirm_delete_keyboard(fact_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data=f"fact_delete_confirm:{fact_id}")
    builder.button(text="❌ Отмена", callback_data=f"fact_open:{fact_id}")
    builder.adjust(1)
    return builder.as_markup()