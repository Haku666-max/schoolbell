import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from db import Database
from keyboards import (
    mode_keyboard,
    after_result_keyboard,
    admin_keyboard,
    admin_preview_keyboard,
    admin_cancel_keyboard,
    admin_tone_keyboard,
    admin_category_keyboard,
    admin_reply_keyboard,
    admin_facts_list_keyboard,
    admin_fact_actions_keyboard,
    confirm_delete_keyboard,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
IMAGES_DIR = BASE_DIR / "images"
IMAGES_DIR.mkdir(exist_ok=True)

db = Database(str(BASE_DIR / "school_facts.db"))
dp = Dispatcher()


def load_token(filename: str = "token.txt") -> str:
    token_path = BASE_DIR / filename
    if not token_path.exists():
        raise RuntimeError(f"Файл {filename} не найден: {token_path}")

    token = token_path.read_text(encoding="utf-8").strip()

    if not token or token == "PASTE_YOUR_BOT_TOKEN_HERE":
        raise RuntimeError("В token.txt нет реального токена.")

    return token


def load_admin_id() -> int:
    config_path = BASE_DIR / "admin_config.json"
    if not config_path.exists():
        raise RuntimeError("Файл admin_config.json не найден.")

    data = json.loads(config_path.read_text(encoding="utf-8"))
    return int(data["admin_id"])


ADMIN_ID = load_admin_id()


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def current_year() -> int:
    return datetime.now().year


def is_valid_year(text: str) -> bool:
    return text.isdigit() and 1950 <= int(text) <= current_year()


class AddFactStates(StatesGroup):
    waiting_for_image = State()
    waiting_for_content = State()
    waiting_for_category = State()
    waiting_for_changed_after = State()
    waiting_for_tone = State()
    waiting_for_confirm = State()


class EditFactStates(StatesGroup):
    waiting_for_new_text = State()
    waiting_for_new_image = State()
    waiting_for_new_year = State()


def format_admin_preview(data: dict) -> str:
    return (
        f"📝 <b>Предпросмотр карточки</b>\n\n"
        f"{data['content']}\n\n"
        f"<b>Категория:</b> {data['category']}\n"
        f"<b>Год:</b> {data['changed_after']}\n"
        f"<b>Тон:</b> {data['tone']}"
    )


def get_main_reply_keyboard(user_id: int):
    if is_admin(user_id):
        return admin_reply_keyboard()
    return None


async def send_fact_to_admin(target, fact: dict):
    meta = (
        f"\n\n<b>— Служебно —</b>\n"
        f"ID: <b>{fact['id']}</b>\n"
        f"Категория: <b>{fact.get('category', '')}</b>\n"
        f"Год: <b>{fact.get('changed_after', '')}</b>\n"
        f"Тон: <b>{fact.get('tone', '')}</b>"
    )
    caption = (fact.get("content", "") or "").strip() + meta
    image_path = fact.get("image", "").strip()
    abs_image_path = BASE_DIR / image_path if image_path else None

    if abs_image_path and abs_image_path.exists():
        await target.answer_photo(
            photo=FSInputFile(abs_image_path),
            caption=caption[:1024],
            parse_mode="HTML",
            reply_markup=admin_fact_actions_keyboard(fact["id"])
        )
    else:
        await target.answer(
            caption,
            parse_mode="HTML",
            reply_markup=admin_fact_actions_keyboard(fact["id"])
        )


@dp.message(Command("start"))
async def cmd_start(message: Message):
    db.upsert_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username or "",
        first_name=message.from_user.first_name or "",
    )

    await message.answer(
        "Привет. Напиши год окончания школы, например: <b>2012</b>",
        parse_mode="HTML",
        reply_markup=get_main_reply_keyboard(message.from_user.id),
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Команды:\n"
        "/start — начать\n"
        "/mode — выбрать режим\n"
        "/more — получить ещё факты\n"
        "/admin — админка",
        reply_markup=get_main_reply_keyboard(message.from_user.id),
    )


@dp.message(Command("mode"))
async def cmd_mode(message: Message):
    await message.answer("Выбери режим:", reply_markup=mode_keyboard())


@dp.message(Command("more"))
async def cmd_more(message: Message):
    await send_facts(message)


@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return

    await message.answer("Админ-панель:", reply_markup=admin_keyboard())


@dp.message(F.text == "🛠 Админка")
async def open_admin_from_reply_button(message: Message):
    if not is_admin(message.from_user.id):
        return

    await message.answer("Админ-панель:", reply_markup=admin_keyboard())


@dp.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    total_users = db.get_total_users()
    users_with_year = db.get_users_with_year()

    await callback.message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"Всего пользователей: <b>{total_users}</b>\n"
        f"Указали год выпуска: <b>{users_with_year}</b>",
        parse_mode="HTML",
    )
    await callback.answer()


@dp.callback_query(F.data == "admin:facts_count")
async def admin_facts_count(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    count = db.get_facts_count()

    await callback.message.answer(
        f"📚 В базе сейчас <b>{count}</b> карточек.",
        parse_mode="HTML",
    )
    await callback.answer()


@dp.callback_query(F.data == "admin:facts")
async def admin_facts_root(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    page = 0
    facts = db.get_last_facts(limit=5, offset=page * 5)
    await callback.message.answer(
        "🗂 <b>Карточки</b>\nВыбери карточку:",
        parse_mode="HTML",
        reply_markup=admin_facts_list_keyboard(facts, page)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("facts_page:"))
async def admin_facts_page(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    page = int(callback.data.split(":")[1])
    facts = db.get_last_facts(limit=5, offset=page * 5)

    if not facts and page > 0:
        page -= 1
        facts = db.get_last_facts(limit=5, offset=page * 5)

    await callback.message.answer(
        f"🗂 <b>Карточки</b> — страница {page + 1}",
        parse_mode="HTML",
        reply_markup=admin_facts_list_keyboard(facts, page)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("fact_open:"))
async def admin_open_fact(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    fact_id = int(callback.data.split(":")[1])
    fact = db.get_fact_by_id(fact_id)

    if not fact:
        await callback.message.answer("Карточка не найдена.")
        await callback.answer()
        return

    await send_fact_to_admin(callback.message, fact)
    await callback.answer()


@dp.callback_query(F.data == "admin:add_fact")
async def admin_add_fact_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    await state.clear()
    await state.set_state(AddFactStates.waiting_for_image)

    await callback.message.answer(
        "Отправь фото для карточки.",
        reply_markup=admin_cancel_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "admin:cancel_fact")
async def admin_cancel_fact(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    await state.clear()
    await callback.message.answer("Действие отменено.")
    await callback.answer()


@dp.message(AddFactStates.waiting_for_image, F.photo)
async def admin_fact_image(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    photo = message.photo[-1]
    file_info = await message.bot.get_file(photo.file_id)

    filename = f"fact_{photo.file_unique_id}.jpg"
    save_path = IMAGES_DIR / filename

    await message.bot.download_file(file_info.file_path, destination=save_path)

    await state.update_data(image=f"images/{filename}")
    await state.set_state(AddFactStates.waiting_for_content)

    await message.answer(
        "Фото сохранено.\nТеперь отправь текст карточки целиком.",
        reply_markup=admin_cancel_keyboard()
    )


@dp.message(AddFactStates.waiting_for_image)
async def admin_fact_image_invalid(message: Message):
    await message.answer("Нужно отправить именно фото.")


@dp.message(AddFactStates.waiting_for_content)
async def admin_fact_content(message: Message, state: FSMContext):
    text = message.html_text or message.text
    text = (text or "").strip()

    if not text:
        await message.answer("Текст карточки не должен быть пустым.")
        return

    await state.update_data(content=text)
    await state.set_state(AddFactStates.waiting_for_category)
    await message.answer(
        "Теперь выбери внутреннюю категорию.",
        reply_markup=admin_category_keyboard()
    )


@dp.callback_query(F.data.startswith("admin_category:"))
async def admin_fact_category(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    current_state = await state.get_state()
    if current_state != AddFactStates.waiting_for_category.state:
        await callback.answer()
        return

    category = callback.data.split(":", 1)[1]
    await state.update_data(category=category)
    await state.set_state(AddFactStates.waiting_for_changed_after)

    await callback.message.answer("Теперь отправь год для фильтрации. Например: 2006")
    await callback.answer()


@dp.message(AddFactStates.waiting_for_changed_after)
async def admin_fact_changed_after(message: Message, state: FSMContext):
    text = message.text.strip()

    if not text.isdigit():
        await message.answer("Год должен быть числом. Например: 2006")
        return

    year = int(text)
    if year < 1900 or year > current_year():
        await message.answer(f"Укажи год в диапазоне 1900–{current_year()}")
        return

    await state.update_data(changed_after=year)
    await state.set_state(AddFactStates.waiting_for_tone)
    await message.answer(
        "Теперь выбери тон карточки.",
        reply_markup=admin_tone_keyboard("admin_tone")
    )


@dp.callback_query(F.data.startswith("admin_tone:"))
async def admin_fact_tone(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    current_state = await state.get_state()
    if current_state != AddFactStates.waiting_for_tone.state:
        await callback.answer()
        return

    tone = callback.data.split(":", 1)[1]
    if tone not in {"serious", "funny", "mixed"}:
        await callback.answer("Некорректный тон", show_alert=True)
        return

    await state.update_data(tone=tone, title="")
    data = await state.get_data()
    await state.set_state(AddFactStates.waiting_for_confirm)

    image_path = BASE_DIR / data["image"]

    if image_path.exists():
        await callback.message.answer_photo(
            photo=FSInputFile(image_path),
            caption=format_admin_preview(data),
            parse_mode="HTML",
            reply_markup=admin_preview_keyboard()
        )
    else:
        await callback.message.answer(
            format_admin_preview(data),
            parse_mode="HTML",
            reply_markup=admin_preview_keyboard()
        )

    await callback.answer()


@dp.callback_query(F.data == "admin:save_fact")
async def admin_save_fact(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    current_state = await state.get_state()
    if current_state != AddFactStates.waiting_for_confirm.state:
        await callback.answer("Нет карточки для сохранения.", show_alert=True)
        return

    data = await state.get_data()

    fact_id = db.add_fact(
        category=data["category"],
        title="",
        content=data["content"],
        changed_after=int(data["changed_after"]),
        tone=data["tone"],
        image=data["image"],
    )

    await state.clear()

    await callback.message.answer(
        f"✅ Карточка сохранена. ID: <b>{fact_id}</b>",
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("fact_delete:"))
async def admin_delete_fact_prompt(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    fact_id = int(callback.data.split(":")[1])
    await callback.message.answer(
        f"Удалить карточку #{fact_id}?",
        reply_markup=confirm_delete_keyboard(fact_id)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("fact_delete_confirm:"))
async def admin_delete_fact_confirm(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    fact_id = int(callback.data.split(":")[1])
    db.delete_fact(fact_id)
    await callback.message.answer(f"🗑 Карточка #{fact_id} удалена.")
    await callback.answer()


@dp.callback_query(F.data.startswith("fact_edit_text:"))
async def admin_edit_text_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    fact_id = int(callback.data.split(":")[1])
    fact = db.get_fact_by_id(fact_id)
    if not fact:
        await callback.answer("Карточка не найдена", show_alert=True)
        return

    await state.clear()
    await state.set_state(EditFactStates.waiting_for_new_text)
    await state.update_data(edit_fact_id=fact_id)

    await callback.message.answer(
        f"Отправь новый текст для карточки #{fact_id}.",
        reply_markup=admin_cancel_keyboard()
    )
    await callback.answer()


@dp.message(EditFactStates.waiting_for_new_text)
async def admin_edit_text_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    text = (message.html_text or message.text or "").strip()
    if not text:
        await message.answer("Текст не должен быть пустым.")
        return

    data = await state.get_data()
    fact_id = int(data["edit_fact_id"])
    db.update_fact_content(fact_id, text)
    await state.clear()

    fact = db.get_fact_by_id(fact_id)
    await message.answer("✅ Текст обновлён.")
    await send_fact_to_admin(message, fact)


@dp.callback_query(F.data.startswith("fact_edit_image:"))
async def admin_edit_image_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    fact_id = int(callback.data.split(":")[1])
    await state.clear()
    await state.set_state(EditFactStates.waiting_for_new_image)
    await state.update_data(edit_fact_id=fact_id)

    await callback.message.answer(
        f"Отправь новое фото для карточки #{fact_id}.",
        reply_markup=admin_cancel_keyboard()
    )
    await callback.answer()


@dp.message(EditFactStates.waiting_for_new_image, F.photo)
async def admin_edit_image_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    fact_id = int(data["edit_fact_id"])

    photo = message.photo[-1]
    file_info = await message.bot.get_file(photo.file_id)
    filename = f"fact_{photo.file_unique_id}.jpg"
    save_path = IMAGES_DIR / filename
    await message.bot.download_file(file_info.file_path, destination=save_path)

    db.update_fact_image(fact_id, f"images/{filename}")
    await state.clear()

    fact = db.get_fact_by_id(fact_id)
    await message.answer("✅ Фото обновлено.")
    await send_fact_to_admin(message, fact)


@dp.message(EditFactStates.waiting_for_new_image)
async def admin_edit_image_invalid(message: Message):
    await message.answer("Нужно отправить именно фото.")


@dp.callback_query(F.data.startswith("fact_edit_category:"))
async def admin_edit_category_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    fact_id = int(callback.data.split(":")[1])
    await state.clear()
    await state.update_data(edit_fact_id=fact_id)

    await callback.message.answer(
        f"Выбери новую категорию для карточки #{fact_id}.",
        reply_markup=admin_category_keyboard("edit_category")
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_category:"))
async def admin_edit_category_save(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    data = await state.get_data()
    fact_id = int(data["edit_fact_id"])
    category = callback.data.split(":")[1]

    db.update_fact_category(fact_id, category)
    await state.clear()

    fact = db.get_fact_by_id(fact_id)
    await callback.message.answer("✅ Категория обновлена.")
    await send_fact_to_admin(callback.message, fact)
    await callback.answer()


@dp.callback_query(F.data.startswith("fact_edit_tone:"))
async def admin_edit_tone_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    fact_id = int(callback.data.split(":")[1])
    await state.clear()
    await state.update_data(edit_fact_id=fact_id)

    await callback.message.answer(
        f"Выбери новый тон для карточки #{fact_id}.",
        reply_markup=admin_tone_keyboard("edit_tone")
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_tone:"))
async def admin_edit_tone_save(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    data = await state.get_data()
    fact_id = int(data["edit_fact_id"])
    tone = callback.data.split(":")[1]

    db.update_fact_tone(fact_id, tone)
    await state.clear()

    fact = db.get_fact_by_id(fact_id)
    await callback.message.answer("✅ Тон обновлён.")
    await send_fact_to_admin(callback.message, fact)
    await callback.answer()


@dp.callback_query(F.data.startswith("fact_edit_year:"))
async def admin_edit_year_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    fact_id = int(callback.data.split(":")[1])
    await state.clear()
    await state.set_state(EditFactStates.waiting_for_new_year)
    await state.update_data(edit_fact_id=fact_id)

    await callback.message.answer(
        f"Отправь новый год для карточки #{fact_id}.",
        reply_markup=admin_cancel_keyboard()
    )
    await callback.answer()


@dp.message(EditFactStates.waiting_for_new_year)
async def admin_edit_year_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("Год должен быть числом.")
        return

    year = int(text)
    if year < 1900 or year > current_year():
        await message.answer(f"Укажи год в диапазоне 1900–{current_year()}")
        return

    data = await state.get_data()
    fact_id = int(data["edit_fact_id"])

    db.update_fact_year(fact_id, year)
    await state.clear()

    fact = db.get_fact_by_id(fact_id)
    await message.answer("✅ Год обновлён.")
    await send_fact_to_admin(message, fact)


@dp.callback_query(F.data.startswith("mode:"))
async def cb_mode(callback: CallbackQuery):
    mode = callback.data.split(":", 1)[1]
    db.set_mode(callback.from_user.id, mode)
    await callback.message.answer(f"Режим сохранён: <b>{mode}</b>", parse_mode="HTML")
    await callback.answer()
    await send_facts(callback.message)


@dp.callback_query(F.data == "more")
async def cb_more(callback: CallbackQuery):
    await callback.answer()
    await send_facts(callback.message)


@dp.callback_query(F.data == "change_mode")
async def cb_change_mode(callback: CallbackQuery):
    await callback.message.answer("Выбери режим:", reply_markup=mode_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "change_year")
async def cb_change_year(callback: CallbackQuery):
    await callback.message.answer("Напиши новый год окончания школы.")
    await callback.answer()


@dp.message(F.text)
async def handle_text(message: Message):
    text = message.text.strip()

    if is_valid_year(text):
        db.upsert_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username or "",
            first_name=message.from_user.first_name or "",
        )
        db.set_graduation_year(message.from_user.id, int(text))
        await message.answer(
            "Год сохранён. Теперь выбери режим:",
            reply_markup=mode_keyboard()
        )
        return

    await message.answer(
        "Отправь год в формате YYYY, например: 2011",
        reply_markup=get_main_reply_keyboard(message.from_user.id),
    )


async def send_facts(message: Message):
    user = db.get_user(message.chat.id)

    if not user or not user["graduation_year"]:
        await message.answer("Сначала отправь год окончания школы.")
        return

    facts = db.get_facts_for_user(
        telegram_id=message.chat.id,
        graduation_year=int(user["graduation_year"]),
        mode=user["selected_mode"] or "mixed",
        limit=5,
    )

    if not facts:
        await message.answer("Пока нет подходящих карточек.")
        return

    for fact in facts:
        image_path = fact.get("image", "").strip()
        abs_image_path = BASE_DIR / image_path if image_path else None
        caption = fact.get("content", "").strip()

        if abs_image_path and abs_image_path.exists():
            await message.answer_photo(
                photo=FSInputFile(abs_image_path),
                caption=caption[:1024],
                parse_mode="HTML",
            )
        else:
            await message.answer(
                caption,
                parse_mode="HTML",
            )

    db.mark_facts_shown(message.chat.id, [fact["id"] for fact in facts])

    await message.answer("Хочешь ещё?", reply_markup=after_result_keyboard())


async def main():
    db.init()
    bot = Bot(load_token())
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")