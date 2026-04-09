import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage

from db import Database
from keyboards import main_menu, fact_kb

def load_token():
    with open("token.txt") as f:
        return f.read().strip()

bot = Bot(token=load_token())
dp = Dispatcher(storage=MemoryStorage())
db = Database()
db.init()

user_last_fact = {}

# --- START ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "🎉 Хочешь узнать, что происходило в мире в год твоего рождения?\n\n"
        "Введи свой год рождения 👇"
    )

# --- YEAR ---
@dp.message()
async def set_year(message: types.Message):
    user = db.get_user(message.from_user.id)

    if not user:
        if not message.text.isdigit():
            await message.answer("Введи год цифрами 🙏")
            return

        year = int(message.text)
        db.save_user(message.from_user.id, year)

        await message.answer(
            f"🔥 Отлично! Теперь ты будешь получать факты из {year} года!",
            reply_markup=main_menu()
        )
        return

    # --- MAIN MENU ---
    if message.text == "🎲 Получить факт":
        await send_fact(message)

    elif message.text == "⭐ Избранное":
        favs = db.get_favorites(message.from_user.id)

        if not favs:
            await message.answer("У тебя пока нет избранных фактов")
            return

        for f in favs:
            await message.answer_photo(
                photo=f["image"],
                caption=f["content"]
            )

    elif message.text == "📊 Моя статистика":
        views, favs = db.get_stats(message.from_user.id)

        await message.answer(
            f"📊 Твоя статистика:\n\n"
            f"Просмотрено: {views}\n"
            f"В избранном: {favs}"
        )

# --- SEND FACT ---
async def send_fact(message: types.Message):
    user = db.get_user(message.from_user.id)

    fact = db.get_random_fact(message.from_user.id, user["birth_year"])

    db.add_view(message.from_user.id, fact["id"])
    user_last_fact[message.from_user.id] = fact["id"]

    is_fav = db.is_favorite(message.from_user.id, fact["id"])

    await message.answer_photo(
        photo=fact["image"],
        caption=fact["content"],
        reply_markup=fact_kb(is_fav)
    )

# --- CALLBACKS ---
@dp.callback_query()
async def callbacks(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    if callback.data == "next":
        await send_fact(callback.message)

    elif callback.data == "fav":
        fact_id = user_last_fact.get(user_id)

        if not fact_id:
            return

        if db.is_favorite(user_id, fact_id):
            db.remove_favorite(user_id, fact_id)
        else:
            db.add_favorite(user_id, fact_id)

        await callback.answer("Обновлено ⭐")

# --- RUN ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())