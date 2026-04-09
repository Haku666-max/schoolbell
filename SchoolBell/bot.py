import asyncio
import json
import random
from pathlib import Path

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile

from db import Database
from keyboards import (
    main_menu,
    admin_menu,
    fact_kb,
    admin_category_kb,
    admin_weight_kb,
    admin_fact_actions_kb,
    admin_confirm_delete_kb,
    admin_search_results_kb,
)


BASE_DIR = Path(__file__).resolve().parent


def load_token():
    with open(BASE_DIR / "token.txt", "r", encoding="utf-8") as f:
        return f.read().strip()


def load_admin_id():
    with open(BASE_DIR / "admin_config.json", "r", encoding="utf-8") as f:
        return json.load(f)["admin_id"]


BOT_TOKEN = load_token()
ADMIN_ID = load_admin_id()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
db = Database(str(BASE_DIR / "school_facts.db"))
db.init()

user_last_fact = {}


class AddFactStates(StatesGroup):
    waiting_for_image = State()
    waiting_for_content = State()
    waiting_for_category = State()
    waiting_for_year = State()
    waiting_for_weight = State()


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


@dp.message(Command("start"))
async def start(message: types.Message):
    if is_admin(message.from_user.id):
        await message.answer("👨‍💻 Админка", reply_markup=admin_menu())
        return

    await message.answer(
        "🎉 Хочешь узнать, что происходило в мире в год твоего рождения?\n\n"
        "Напиши свой год рождения 👇"
    )


# ---------------- ДОБАВЛЕНИЕ КАРТОЧКИ ----------------

@dp.message(F.text == "➕ Добавить карточку")
async def add_fact_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await state.set_state(AddFactStates.waiting_for_image)
    await message.answer("Отправь фото")


@dp.message(AddFactStates.waiting_for_image, F.photo)
async def add_fact_image(message: types.Message, state: FSMContext):
    await state.update_data(image=message.photo[-1].file_id)
    await state.set_state(AddFactStates.waiting_for_content)
    await message.answer("Теперь отправь текст")


@dp.message(AddFactStates.waiting_for_content)
async def add_fact_text(message: types.Message, state: FSMContext):
    await state.update_data(content=message.text)
    await state.set_state(AddFactStates.waiting_for_category)
    await message.answer("Выбери категорию", reply_markup=admin_category_kb())


@dp.callback_query(F.data.startswith("cat:"))
async def add_fact_category(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(category=callback.data.split(":")[1])
    await state.set_state(AddFactStates.waiting_for_year)
    await callback.message.answer("Теперь отправь год")


@dp.message(AddFactStates.waiting_for_year)
async def add_fact_year(message: types.Message, state: FSMContext):
    await state.update_data(year=int(message.text))
    await state.set_state(AddFactStates.waiting_for_weight)
    await message.answer("Выбери вес", reply_markup=admin_weight_kb())


@dp.callback_query(F.data.startswith("weight:"))
async def add_fact_weight(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()

    fact_id = db.add_fact(
        content=data["content"],
        image=data["image"],
        category=data["category"],
        year=data["year"],
        weight=int(callback.data.split(":")[1])
    )

    await state.clear()
    await callback.message.answer(f"✅ Карточка создана ID: {fact_id}")
    await callback.answer()


# ---------------- ПОЛЬЗОВАТЕЛЬ ----------------

@dp.message(F.text == "🎲 Факт моего года")
async def fact_my_year(message: types.Message):
    user = db.get_user(message.from_user.id)
    fact = db.get_random_fact(message.from_user.id, user["birth_year"])

    await message.answer_photo(
        fact["image"],
        caption=fact["content"],
        reply_markup=fact_kb(False)
    )


@dp.message(F.text == "🌍 Случайный год")
async def fact_random_year(message: types.Message):
    year = random.randint(1900, 2024)
    fact = db.get_random_fact(message.from_user.id, year)

    if not fact:
        await message.answer("Нет фактов 😢")
        return

    await message.answer_photo(
        fact["image"],
        caption=f"📅 {year}\n\n{fact['content']}",
        reply_markup=fact_kb(False)
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())