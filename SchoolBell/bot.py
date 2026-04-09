import asyncio
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage

from db import Database
from keyboards import main_menu, fact_kb, admin_menu


def load_token():
    with open("token.txt", "r", encoding="utf-8") as f:
        return f.read().strip()


def load_admin_id():
    with open("admin_config.json", "r", encoding="utf-8") as f:
        return json.load(f)["admin_id"]


BOT_TOKEN = load_token()
ADMIN_ID = load_admin_id()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
db = Database()
db.init()

user_last_fact = {}


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


# -------------------------
# START
# -------------------------
@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id

    if is_admin(user_id):
        await message.answer(
            "👋 Добро пожаловать в админ-режим.\nВыбери действие ниже.",
            reply_markup=admin_menu()
        )
        return

    user = db.get_user(user_id)

    if user and user["birth_year"]:
        await message.answer(
            "🎉 Хочешь узнать, что происходило в мире в год твоего рождения?\n\n"
            "Нажми «🎲 Получить факт», и я покажу тебе случайное событие того года.",
            reply_markup=main_menu()
        )
    else:
        await message.answer(
            "🎉 Хочешь узнать, что происходило в мире в год твоего рождения?\n\n"
            "Напиши свой год рождения 👇"
        )


# -------------------------
# ADMIN PANEL
# -------------------------
async def handle_admin(message: types.Message):
    text = (message.text or "").strip()

    if text == "🛠 Админка":
        await message.answer(
            "👨‍💻 Админ-панель\n\n"
            "Сейчас базовая версия админки активна.",
            reply_markup=admin_menu()
        )
        return

    if text == "📊 Общая статистика":
        # общая статистика по всем пользователям и базе
        cur = db.conn.cursor()

        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM users WHERE birth_year IS NOT NULL")
        users_with_year = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM facts")
        total_facts = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM facts WHERE is_active = 1")
        active_facts = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM views")
        total_views = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM favorites")
        total_favorites = cur.fetchone()[0]

        await message.answer(
            "📊 Общая статистика:\n\n"
            f"Пользователей: {total_users}\n"
            f"Указали год рождения: {users_with_year}\n"
            f"Всего карточек: {total_facts}\n"
            f"Активных карточек: {active_facts}\n"
            f"Всего просмотров: {total_views}\n"
            f"Добавлений в избранное: {total_favorites}"
        )
        return

    if text == "📦 Кол-во карточек":
        cur = db.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM facts")
        total_facts = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM facts WHERE is_active = 1")
        active_facts = cur.fetchone()[0]

        await message.answer(
            f"📦 Карточек в базе: {total_facts}\n"
            f"✅ Активных карточек: {active_facts}"
        )
        return

    if text == "🏠 Обычное меню":
        user = db.get_user(message.from_user.id)

        if user and user["birth_year"]:
            await message.answer(
                "Открываю пользовательское меню.",
                reply_markup=main_menu()
            )
        else:
            await message.answer(
                "У тебя не указан год рождения.\nНапиши его цифрами, например: 2001"
            )
        return

    await message.answer(
        "👨‍💻 Это админский режим.\nВыбери кнопку из меню ниже.",
        reply_markup=admin_menu()
    )


# -------------------------
# SEND FACT
# -------------------------
async def send_fact(message: types.Message):
    user = db.get_user(message.from_user.id)

    if not user or not user["birth_year"]:
        await message.answer("Сначала напиши свой год рождения цифрами, например: 2001")
        return

    fact = db.get_random_fact(message.from_user.id, user["birth_year"])

    if not fact:
        await message.answer("Пока нет фактов для этого года.")
        return

    db.add_view(message.from_user.id, fact["id"])
    user_last_fact[message.from_user.id] = fact["id"]

    is_fav = db.is_favorite(message.from_user.id, fact["id"])

    image = fact["image"]
    content = fact["content"] or "Без текста"

    if image:
        await message.answer_photo(
            photo=image,
            caption=content,
            reply_markup=fact_kb(is_fav)
        )
    else:
        await message.answer(
            content,
            reply_markup=fact_kb(is_fav)
        )


# -------------------------
# MAIN MESSAGE HANDLER
# -------------------------
@dp.message(F.text)
async def handle_all(message: types.Message):
    user_id = message.from_user.id
    text = (message.text or "").strip()

    # --- ADMIN ---
    if is_admin(user_id):
        # админка не должна требовать год рождения
        if text in {"🛠 Админка", "📊 Общая статистика", "📦 Кол-во карточек", "🏠 Обычное меню"}:
            await handle_admin(message)
            return

        # если админ хочет использовать обычный режим
        user = db.get_user(user_id)

        if not user or not user["birth_year"]:
            if text.isdigit():
                year = int(text)
                db.save_user(user_id, year)
                await message.answer(
                    f"✅ Год рождения сохранён: {year}",
                    reply_markup=admin_menu()
                )
                return

            await message.answer(
                "Ты в админ-режиме.\n"
                "Если хочешь использовать пользовательскую часть, сначала введи свой год рождения цифрами.\n"
                "Или пользуйся кнопками админки.",
                reply_markup=admin_menu()
            )
            return

    # --- USER WITHOUT YEAR ---
    user = db.get_user(user_id)

    if not user or not user["birth_year"]:
        if not text.isdigit():
            await message.answer("Введи год рождения цифрами 🙏")
            return

        year = int(text)

        if year < 1900 or year > 2026:
            await message.answer("Введи корректный год рождения, например: 2001")
            return

        db.save_user(user_id, year)

        if is_admin(user_id):
            await message.answer(
                f"✅ Год рождения сохранён: {year}",
                reply_markup=admin_menu()
            )
        else:
            await message.answer(
                f"🔥 Отлично! Теперь ты будешь получать факты из {year} года!",
                reply_markup=main_menu()
            )
        return

    # --- USER MENU ---
    if text == "🎲 Получить факт":
        await send_fact(message)
        return

    if text == "⭐ Избранное":
        favs = db.get_favorites(user_id)

        if not favs:
            await message.answer("У тебя пока нет избранных фактов")
            return

        for f in favs:
            image = f["image"]
            content = f["content"] or "Без текста"
            is_fav = db.is_favorite(user_id, f["id"])

            if image:
                await message.answer_photo(
                    photo=image,
                    caption=content,
                    reply_markup=fact_kb(is_fav)
                )
            else:
                await message.answer(
                    content,
                    reply_markup=fact_kb(is_fav)
                )
        return

    if text == "📊 Моя статистика":
        views, favs = db.get_stats(user_id)

        await message.answer(
            f"📊 Твоя статистика:\n\n"
            f"Просмотрено фактов: {views}\n"
            f"В избранном: {favs}"
        )
        return

    # если админ нажал что-то не из админки, но у него уже есть год
    if is_admin(user_id):
        await handle_admin(message)
        return

    await message.answer("Выбери действие из меню ниже.", reply_markup=main_menu())


# -------------------------
# CALLBACKS
# -------------------------
@dp.callback_query()
async def callbacks(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data

    if data == "next":
        await callback.answer()
        await send_fact(callback.message)
        return

    if data == "fav":
        fact_id = user_last_fact.get(user_id)

        if not fact_id:
            await callback.answer("Карточка не найдена", show_alert=True)
            return

        if db.is_favorite(user_id, fact_id):
            db.remove_favorite(user_id, fact_id)
            await callback.answer("Удалено из избранного")
        else:
            db.add_favorite(user_id, fact_id)
            await callback.answer("Добавлено в избранное")
        return


# -------------------------
# RUN
# -------------------------
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())