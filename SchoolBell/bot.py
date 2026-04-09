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
    admin_fact_actions_kb,
    admin_confirm_delete_kb,
    admin_search_results_kb,
    admin_weight_kb,
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


class SearchStates(StatesGroup):
    waiting_for_fact_id = State()
    waiting_for_query = State()


class EditStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_image = State()
    waiting_for_year = State()
    waiting_for_weight = State()


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def is_local_image(value: str | None) -> bool:
    if not value:
        return False
    p = Path(value)
    if p.is_absolute() and p.exists():
        return True
    p2 = BASE_DIR / value
    return p2.exists()


async def send_fact_message(target_message: types.Message, fact, with_admin_controls: bool = False):
    if not fact:
        await target_message.answer("Карточка не найдена.")
        return

    content = fact["content"] or "Без текста"
    image = fact["image"]

    if with_admin_controls:
        meta = (
            f"\n\n<b>— Служебно —</b>\n"
            f"ID: <b>{fact['id']}</b>\n"
            f"Категория: <b>{fact['category'] or '—'}</b>\n"
            f"Год: <b>{fact['year'] or '—'}</b>\n"
            f"Вес: <b>{fact['weight'] or 1}</b>\n"
            f"Активна: <b>{'Да' if fact['is_active'] == 1 else 'Нет'}</b>"
        )
        content = content + meta

    markup = admin_fact_actions_kb(fact["id"], fact["is_active"]) if with_admin_controls else None

    if image:
        if is_local_image(image):
            img_path = Path(image)
            if not img_path.is_absolute():
                img_path = BASE_DIR / image
            await target_message.answer_photo(
                photo=FSInputFile(str(img_path)),
                caption=content[:1024],
                parse_mode="HTML",
                reply_markup=markup
            )
        else:
            await target_message.answer_photo(
                photo=image,
                caption=content[:1024],
                parse_mode="HTML",
                reply_markup=markup
            )
    else:
        await target_message.answer(
            content,
            parse_mode="HTML",
            reply_markup=markup
        )

async def send_random_year_fact(message: types.Message):
    year = random.randint(1900, 2024)

    fact = db.get_random_fact(message.from_user.id, year)

    if not fact:
        await message.answer("Пока нет фактов для случайного года 😢")
        return

    db.add_view(message.from_user.id, fact["id"])
    user_last_fact[message.from_user.id] = fact["id"]

    is_fav = db.is_favorite(message.from_user.id, fact["id"])

    text = f"📅 Год: {year}\n\n{fact['content']}"

    await message.answer_photo(
        photo=fact["image"],
        caption=text,
        reply_markup=fact_kb(is_fav)
    )

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


async def send_random_fact(message: types.Message):
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

    content = fact["content"] or "Без текста"
    image = fact["image"]

    if image:
        if is_local_image(image):
            img_path = Path(image)
            if not img_path.is_absolute():
                img_path = BASE_DIR / image
            await message.answer_photo(
                photo=FSInputFile(str(img_path)),
                caption=content[:1024],
                reply_markup=fact_kb(is_fav)
            )
        else:
            await message.answer_photo(
                photo=image,
                caption=content[:1024],
                reply_markup=fact_kb(is_fav)
            )
    else:
        await message.answer(
            content,
            reply_markup=fact_kb(is_fav)
        )


# ---------------- ADMIN ADD FACT ----------------
@dp.message(F.text == "➕ Добавить карточку")
async def admin_add_fact_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await state.clear()
    await state.set_state(AddFactStates.waiting_for_image)
    await message.answer("Отправь фото для карточки.")


@dp.message(AddFactStates.waiting_for_image, F.photo)
async def admin_add_fact_image(message: types.Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    await state.update_data(image=file_id)
    await state.set_state(AddFactStates.waiting_for_content)
    await message.answer("Теперь отправь текст карточки целиком.")


@dp.message(AddFactStates.waiting_for_image)
async def admin_add_fact_image_invalid(message: types.Message):
    await message.answer("Нужно отправить именно фото.")


@dp.message(AddFactStates.waiting_for_content)
async def admin_add_fact_content(message: types.Message, state: FSMContext):
    text = (message.html_text or message.text or "").strip()
    if not text:
        await message.answer("Текст не должен быть пустым.")
        return

    await state.update_data(content=text)
    await state.set_state(AddFactStates.waiting_for_category)
    await message.answer("Теперь выбери категорию.", reply_markup=admin_category_kb())


@dp.callback_query(F.data.startswith("cat:"))
async def admin_add_fact_category(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    current_state = await state.get_state()
    if current_state != AddFactStates.waiting_for_category.state:
        await callback.answer()
        return

    category = callback.data.split(":", 1)[1]
    await state.update_data(category=category)
    await state.set_state(AddFactStates.waiting_for_year)
    await callback.message.answer("Теперь отправь год, к которому относится факт. Например: 2001")
    await callback.answer()


@dp.message(AddFactStates.waiting_for_year)
async def admin_add_fact_year(message: types.Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("Год должен быть числом.")
        return

    year = int(text)
    if year < 1900 or year > 2026:
        await message.answer("Укажи корректный год. Например: 2001")
        return

    await state.update_data(year=year)
    await state.set_state(AddFactStates.waiting_for_weight)
await message.answer(
    "Выбери вес карточки:",
    reply_markup=admin_weight_kb()
)

@dp.callback_query(F.data.startswith("weight:"))
async def admin_add_fact_weight(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()

    if "content" not in data:
        return

    weight = int(callback.data.split(":")[1])

    fact_id = db.add_fact(
        content=data["content"],
        image=data["image"],
        category=data["category"],
        year=data["year"],
        weight=weight
    )

    await state.clear()

    fact = db.get_fact_by_id(fact_id)

    await callback.message.answer(f"✅ Карточка сохранена. ID: {fact_id}")
    await send_fact_message(callback.message, fact, with_admin_controls=True)

    await callback.answer()

# ---------------- ADMIN LIST / SEARCH ----------------
@dp.message(F.text == "📚 Последние карточки")
async def admin_last_facts(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    facts = db.get_last_facts(10)
    if not facts:
        await message.answer("В базе пока нет карточек.")
        return

    await message.answer(
        "📚 Последние карточки:",
        reply_markup=admin_search_results_kb(facts)
    )


@dp.message(F.text == "🔎 Найти по ID")
async def admin_search_by_id_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await state.clear()
    await state.set_state(SearchStates.waiting_for_fact_id)
    await message.answer("Отправь ID карточки.")


@dp.message(SearchStates.waiting_for_fact_id)
async def admin_search_by_id_process(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("ID должен быть числом.")
        return

    fact = db.get_fact_by_id(int(text))
    await state.clear()

    if not fact:
        await message.answer("Карточка не найдена.", reply_markup=admin_menu())
        return

    await send_fact_message(message, fact, with_admin_controls=True)


@dp.message(F.text == "🔍 Найти по слову")
async def admin_search_by_text_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await state.clear()
    await state.set_state(SearchStates.waiting_for_query)
    await message.answer("Отправь слово или фразу для поиска.")


@dp.message(SearchStates.waiting_for_query)
async def admin_search_by_text_process(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    query = (message.text or "").strip()
    if not query:
        await message.answer("Запрос не должен быть пустым.")
        return

    facts = db.search_facts_by_text(query, 15)
    await state.clear()

    if not facts:
        await message.answer("Ничего не найдено.", reply_markup=admin_menu())
        return

    await message.answer(
        f"Найдено карточек: {len(facts)}",
        reply_markup=admin_search_results_kb(facts)
    )


# ---------------- ADMIN STATS ----------------
@dp.message(F.text == "📊 Общая статистика")
async def admin_global_stats(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    total_users = db.get_total_users()
    users_with_year = db.get_users_with_year()
    total_facts = db.get_facts_count()
    active_facts = db.get_active_facts_count()
    total_views = db.get_total_views()
    total_favorites = db.get_total_favorites()

    await message.answer(
        "📊 Общая статистика:\n\n"
        f"Пользователей: {total_users}\n"
        f"Указали год рождения: {users_with_year}\n"
        f"Всего карточек: {total_facts}\n"
        f"Активных карточек: {active_facts}\n"
        f"Всего просмотров: {total_views}\n"
        f"Добавлений в избранное: {total_favorites}",
        reply_markup=admin_menu()
    )


@dp.message(F.text == "📦 Кол-во карточек")
async def admin_cards_count(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        f"📦 Всего карточек: {db.get_facts_count()}\n"
        f"✅ Активных карточек: {db.get_active_facts_count()}",
        reply_markup=admin_menu()
    )


# ---------------- ADMIN OPEN / EDIT / DELETE ----------------
@dp.callback_query(F.data == "noop")
async def noop_callback(callback: types.CallbackQuery):
    await callback.answer()


@dp.callback_query(F.data.startswith("open_fact:"))
async def admin_open_fact(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    fact_id = int(callback.data.split(":", 1)[1])
    fact = db.get_fact_by_id(fact_id)

    if not fact:
        await callback.message.answer("Карточка не найдена.")
        await callback.answer()
        return

    await send_fact_message(callback.message, fact, with_admin_controls=True)
    await callback.answer()


@dp.callback_query(F.data.startswith("delete_fact:"))
async def admin_delete_fact_prompt(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    fact_id = int(callback.data.split(":", 1)[1])
    await callback.message.answer(
        f"Удалить карточку #{fact_id}?",
        reply_markup=admin_confirm_delete_kb(fact_id)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("confirm_delete:"))
async def admin_delete_fact_confirm(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    fact_id = int(callback.data.split(":", 1)[1])
    db.delete_fact(fact_id)
    await callback.message.answer(f"🗑 Карточка #{fact_id} удалена.", reply_markup=admin_menu())
    await callback.answer()


@dp.callback_query(F.data.startswith("cancel_delete:"))
async def admin_cancel_delete(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    fact_id = int(callback.data.split(":", 1)[1])
    fact = db.get_fact_by_id(fact_id)
    if fact:
        await send_fact_message(callback.message, fact, with_admin_controls=True)
    else:
        await callback.message.answer("Удаление отменено.")
    await callback.answer()


@dp.callback_query(F.data.startswith("toggle_active:"))
async def admin_toggle_active(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    fact_id = int(callback.data.split(":", 1)[1])
    db.toggle_fact_active(fact_id)
    fact = db.get_fact_by_id(fact_id)
    await callback.message.answer("✅ Активность карточки обновлена.")
    await send_fact_message(callback.message, fact, with_admin_controls=True)
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_text:"))
async def admin_edit_text_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    fact_id = int(callback.data.split(":", 1)[1])
    await state.clear()
    await state.set_state(EditStates.waiting_for_text)
    await state.update_data(fact_id=fact_id)
    await callback.message.answer(f"Отправь новый текст для карточки #{fact_id}")
    await callback.answer()


@dp.message(EditStates.waiting_for_text)
async def admin_edit_text_save(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    fact_id = data["fact_id"]
    text = (message.html_text or message.text or "").strip()

    if not text:
        await message.answer("Текст не должен быть пустым.")
        return

    db.update_fact_content(fact_id, text)
    await state.clear()

    fact = db.get_fact_by_id(fact_id)
    await message.answer("✅ Текст обновлён.", reply_markup=admin_menu())
    await send_fact_message(message, fact, with_admin_controls=True)


@dp.callback_query(F.data.startswith("edit_image:"))
async def admin_edit_image_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    fact_id = int(callback.data.split(":", 1)[1])
    await state.clear()
    await state.set_state(EditStates.waiting_for_image)
    await state.update_data(fact_id=fact_id)
    await callback.message.answer(f"Отправь новое фото для карточки #{fact_id}")
    await callback.answer()


@dp.message(EditStates.waiting_for_image, F.photo)
async def admin_edit_image_save(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    fact_id = data["fact_id"]
    file_id = message.photo[-1].file_id

    db.update_fact_image(fact_id, file_id)
    await state.clear()

    fact = db.get_fact_by_id(fact_id)
    await message.answer("✅ Фото обновлено.", reply_markup=admin_menu())
    await send_fact_message(message, fact, with_admin_controls=True)


@dp.message(EditStates.waiting_for_image)
async def admin_edit_image_invalid(message: types.Message):
    await message.answer("Нужно отправить именно фото.")


@dp.callback_query(F.data.startswith("edit_category:"))
async def admin_edit_category_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    fact_id = int(callback.data.split(":", 1)[1])
    await state.clear()
    await state.update_data(edit_category_fact_id=fact_id)
    await callback.message.answer(
        f"Выбери новую категорию для карточки #{fact_id}",
        reply_markup=admin_category_kb()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("cat:"))
async def admin_edit_category_process(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    data = await state.get_data()
    fact_id = data.get("edit_category_fact_id")

    # если это не режим редактирования категории — значит это обработчик добавления карточки
    current_state = await state.get_state()
    if not fact_id and current_state == AddFactStates.waiting_for_category.state:
        return

    if not fact_id:
        await callback.answer()
        return

    category = callback.data.split(":", 1)[1]
    db.update_fact_category(fact_id, category)
    await state.clear()

    fact = db.get_fact_by_id(fact_id)
    await callback.message.answer("✅ Категория обновлена.")
    await send_fact_message(callback.message, fact, with_admin_controls=True)
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_year:"))
async def admin_edit_year_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    fact_id = int(callback.data.split(":", 1)[1])
    await state.clear()
    await state.set_state(EditStates.waiting_for_year)
    await state.update_data(fact_id=fact_id)
    await callback.message.answer(f"Отправь новый год для карточки #{fact_id}")
    await callback.answer()


@dp.message(EditStates.waiting_for_year)
async def admin_edit_year_save(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    fact_id = data["fact_id"]
    text = (message.text or "").strip()

    if not text.isdigit():
        await message.answer("Год должен быть числом.")
        return

    year = int(text)
    if year < 1900 or year > 2026:
        await message.answer("Укажи корректный год.")
        return

    db.update_fact_year(fact_id, year)
    await state.clear()

    fact = db.get_fact_by_id(fact_id)
    await message.answer("✅ Год обновлён.", reply_markup=admin_menu())
    await send_fact_message(message, fact, with_admin_controls=True)


@dp.callback_query(F.data.startswith("edit_weight:"))
async def admin_edit_weight_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    fact_id = int(callback.data.split(":", 1)[1])
    await state.clear()
    await state.set_state(EditStates.waiting_for_weight)
    await state.update_data(fact_id=fact_id)
    await callback.message.answer(f"Отправь новый вес для карточки #{fact_id}")
    await callback.answer()


@dp.message(EditStates.waiting_for_weight)
async def admin_edit_weight_save(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    fact_id = data["fact_id"]
    text = (message.text or "").strip()

    if not text.isdigit():
        await message.answer("Вес должен быть числом.")
        return

    weight = int(text)
    if weight < 1:
        await message.answer("Вес должен быть не меньше 1.")
        return

    db.update_fact_weight(fact_id, weight)
    await state.clear()

    fact = db.get_fact_by_id(fact_id)
    await message.answer("✅ Вес обновлён.", reply_markup=admin_menu())
    await send_fact_message(message, fact, with_admin_controls=True)


# ---------------- USER / ADMIN ROOT TEXT ----------------
@dp.message(F.text == "🏠 Пользовательское меню")
async def switch_to_user_menu(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    user = db.get_user(message.from_user.id)
    if user and user["birth_year"]:
        await message.answer("Открываю пользовательское меню.", reply_markup=main_menu())
    else:
        await message.answer(
            "Чтобы использовать пользовательский режим, сначала введи свой год рождения цифрами.",
            reply_markup=admin_menu()
        )


@dp.message(F.text)
async def handle_all(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    text = (message.text or "").strip()

    # если админ в состоянии FSM — не мешаем
    current_state = await state.get_state()
    if current_state:
        # состояния уже обрабатываются отдельными хендлерами
        return

    if is_admin(user_id):
        if text in {
            "🛠 Админка",
            "➕ Добавить карточку",
            "📚 Последние карточки",
            "🔎 Найти по ID",
            "🔍 Найти по слову",
            "📊 Общая статистика",
            "📦 Кол-во карточек",
            "🏠 Пользовательское меню",
        }:
            if text == "🛠 Админка":
                await message.answer("👨‍💻 Админ-панель", reply_markup=admin_menu())
            return

    user = db.get_user(user_id)

    if not user or not user["birth_year"]:
        if not text.isdigit():
            await message.answer(
                "🎉 Хочешь узнать, что происходило в мире в год твоего рождения?\n\n"
                "Напиши свой год рождения цифрами 👇"
            )
            return

        year = int(text)
        if year < 1900 or year > 2026:
            await message.answer("Введи корректный год, например: 2001")
            return

        db.save_user(user_id, year)

        if is_admin(user_id):
            await message.answer(f"✅ Год рождения сохранён: {year}", reply_markup=admin_menu())
        else:
            await message.answer(
                f"🔥 Отлично! Теперь ты будешь получать факты из {year} года!",
                reply_markup=main_menu()
            )
        return

    if text == "🎲 Факт моего года":
        await send_random_fact(message)
        return

    if text == "⭐ Избранное":
        favs = db.get_favorites(user_id)

        if not favs:
            await message.answer("У тебя пока нет избранных фактов")
            return

        for fact in favs:
            content = fact["content"] or "Без текста"
            image = fact["image"]
            is_fav = db.is_favorite(user_id, fact["id"])

            if image:
                if is_local_image(image):
                    img_path = Path(image)
                    if not img_path.is_absolute():
                        img_path = BASE_DIR / image
                    await message.answer_photo(
                        photo=FSInputFile(str(img_path)),
                        caption=content[:1024],
                        reply_markup=fact_kb(is_fav)
                    )
                else:
                    await message.answer_photo(
                        photo=image,
                        caption=content[:1024],
                        reply_markup=fact_kb(is_fav)
                    )
            else:
                await message.answer(content, reply_markup=fact_kb(is_fav))
        return

    if text == "📊 Моя статистика":
        views, favs = db.get_stats(user_id)
        await message.answer(
            f"📊 Твоя статистика:\n\n"
            f"Просмотрено фактов: {views}\n"
            f"В избранном: {favs}"
        )
        return

    if text == "🌍 Случайный год":
        await send_random_year_fact(message)
        return

    if is_admin(user_id):
        await message.answer("Выбери действие из админского меню.", reply_markup=admin_menu())
        return

    await message.answer("Выбери действие из меню ниже.", reply_markup=main_menu())


# ---------------- FACT CALLBACKS ----------------
@dp.callback_query(F.data == "next")
async def callback_next(callback: types.CallbackQuery):
    await callback.answer()
    await send_random_fact(callback.message)


@dp.callback_query(F.data == "fav")
async def callback_fav(callback: types.CallbackQuery):
    user_id = callback.from_user.id
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


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())