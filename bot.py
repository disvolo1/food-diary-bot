import asyncio
import logging
import os

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message, CallbackQuery

from database import (
    init_db,
    get_user,
    create_user,
    update_user_goals,
    add_meal,
    get_today_totals,
    get_today_meals,
    delete_last_meal,
)

from gemini import analyze_food_image

from keyboards import (
    main_menu,
    confirm_meal,
    amount_type_keyboard,
    settings_menu,
    cancel_keyboard,
    today_keyboard,
)


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")


logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

dp = Dispatcher()


# ============================================================
# STATES
# ============================================================

class SetupStates(StatesGroup):
    calories = State()
    protein = State()
    fat = State()
    carbs = State()


class MealStates(StatesGroup):
    waiting_photo = State()
    waiting_amount = State()


class SettingsStates(StatesGroup):
    calories = State()
    protein = State()
    fat = State()
    carbs = State()


# ============================================================
# TEMPORARY MEAL DATA
# ============================================================

pending_meals = {}


# ============================================================
# HELPERS
# ============================================================

def format_number(value):
    value = float(value)

    if value.is_integer():
        return str(int(value))

    return f"{value:.1f}"


def progress_bar(current, goal, length=10):
    if goal <= 0:
        return "░" * length

    percentage = min(current / goal, 1)

    filled = round(percentage * length)

    return "█" * filled + "░" * (length - filled)


def build_today_text(user, totals):
    calories_goal = user["calories_goal"] or 0
    protein_goal = user["protein_goal"] or 0
    fat_goal = user["fat_goal"] or 0
    carbs_goal = user["carbs_goal"] or 0

    calories = totals["calories"]
    protein = totals["protein"]
    fat = totals["fat"]
    carbs = totals["carbs"]

    calories_left = max(calories_goal - calories, 0)
    protein_left = max(protein_goal - protein, 0)
    fat_left = max(fat_goal - fat, 0)
    carbs_left = max(carbs_goal - carbs, 0)

    return (
        "🍽 <b>Сегодня</b>\n\n"

        f"🔥 <b>{format_number(calories)}</b> / "
        f"{format_number(calories_goal)} ккал\n"
        f"{progress_bar(calories, calories_goal)}\n\n"

        f"🥩 <b>{format_number(protein)}</b> / "
        f"{format_number(protein_goal)} г белка\n"
        f"{progress_bar(protein, protein_goal)}\n\n"

        f"🥑 <b>{format_number(fat)}</b> / "
        f"{format_number(fat_goal)} г жиров\n"
        f"{progress_bar(fat, fat_goal)}\n\n"

        f"🍞 <b>{format_number(carbs)}</b> / "
        f"{format_number(carbs_goal)} г углеводов\n"
        f"{progress_bar(carbs, carbs_goal)}\n\n"

        "──────────────\n\n"

        "<b>Осталось:</b>\n\n"

        f"🔥 {format_number(calories_left)} ккал\n"
        f"🥩 {format_number(protein_left)} г белка\n"
        f"🥑 {format_number(fat_left)} г жиров\n"
        f"🍞 {format_number(carbs_left)} г углеводов"
    )


async def show_main_menu(message: Message):
    await message.answer(
        "🍽 <b>Дневник питания</b>\n\n"
        "Отправь фотографию этикетки, "
        "и я добавлю её в твой дневник.",
        reply_markup=main_menu()
    )


# ============================================================
# START
# ============================================================

@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):

    telegram_id = message.from_user.id

    user = await get_user(telegram_id)

    if not user:
        await create_user(telegram_id)

        await state.set_state(SetupStates.calories)

        await message.answer(
            "👋 <b>Привет!</b>\n\n"
            "Давай настроим твой дневник питания.\n\n"
            "🔥 Сколько калорий тебе нужно в день?\n\n"
            "<i>Напиши число, например 2200</i>",
            reply_markup=cancel_keyboard()
        )

        return

    if not user["calories_goal"]:
        await state.set_state(SetupStates.calories)

        await message.answer(
            "🔥 Сколько калорий тебе нужно в день?",
            reply_markup=cancel_keyboard()
        )

        return

    await show_main_menu(message)


# ============================================================
# INITIAL SETUP
# ============================================================

@dp.message(SetupStates.calories)
async def setup_calories(message: Message, state: FSMContext):

    try:
        calories = float(message.text.replace(",", "."))
    except (ValueError, AttributeError):
        await message.answer(
            "❌ Введи число.\n\n"
            "Например: <b>2200</b>"
        )
        return

    if calories <= 0:
        await message.answer("❌ Значение должно быть больше 0.")
        return

    await state.update_data(calories=calories)
    await state.set_state(SetupStates.protein)

    await message.answer(
        "🥩 <b>Сколько белка тебе нужно в день?</b>\n\n"
        "Например: <b>150</b> г"
    )


@dp.message(SetupStates.protein)
async def setup_protein(message: Message, state: FSMContext):

    try:
        protein = float(message.text.replace(",", "."))
    except (ValueError, AttributeError):
        await message.answer(
            "❌ Введи число.\n\n"
            "Например: <b>150</b>"
        )
        return

    if protein <= 0:
        await message.answer("❌ Значение должно быть больше 0.")
        return

    await state.update_data(protein=protein)
    await state.set_state(SetupStates.fat)

    await message.answer(
        "🥑 <b>Сколько жиров тебе нужно в день?</b>\n\n"
        "Например: <b>70</b> г"
    )


@dp.message(SetupStates.fat)
async def setup_fat(message: Message, state: FSMContext):

    try:
        fat = float(message.text.replace(",", "."))
    except (ValueError, AttributeError):
        await message.answer(
            "❌ Введи число.\n\n"
            "Например: <b>70</b>"
        )
        return

    if fat <= 0:
        await message.answer("❌ Значение должно быть больше 0.")
        return

    await state.update_data(fat=fat)
    await state.set_state(SetupStates.carbs)

    await message.answer(
        "🍞 <b>Сколько углеводов тебе нужно в день?</b>\n\n"
        "Например: <b>250</b> г"
    )


@dp.message(SetupStates.carbs)
async def setup_carbs(message: Message, state: FSMContext):

    try:
        carbs = float(message.text.replace(",", "."))
    except (ValueError, AttributeError):
        await message.answer(
            "❌ Введи число.\n\n"
            "Например: <b>250</b>"
        )
        return

    if carbs <= 0:
        await message.answer("❌ Значение должно быть больше 0.")
        return

    data = await state.get_data()

    await update_user_goals(
        telegram_id=message.from_user.id,
        calories=data["calories"],
        protein=data["protein"],
        fat=data["fat"],
        carbs=carbs
    )

    await state.clear()

    await message.answer(
        "✅ <b>Готово!</b>\n\n"
        f"🔥 {format_number(data['calories'])} ккал\n"
        f"🥩 {format_number(data['protein'])} г белка\n"
        f"🥑 {format_number(data['fat'])} г жиров\n"
        f"🍞 {format_number(carbs)} г углеводов\n\n"
        "Теперь просто отправляй мне "
        "фотографии этикеток 📷",
        reply_markup=main_menu()
    )


# ============================================================
# ADD FOOD
# ============================================================

@dp.callback_query(F.data == "add_food")
async def add_food_callback(
    callback: CallbackQuery,
    state: FSMContext
):

    await callback.answer()

    await state.set_state(MealStates.waiting_photo)

    await callback.message.edit_text(
        "📷 <b>Отправь фотографию этикетки</b>\n\n"
        "Я прочитаю калории, белки, жиры и углеводы."
    )


@dp.message(MealStates.waiting_photo, F.photo)
async def receive_food_photo(
    message: Message,
    state: FSMContext
):

    processing_message = await message.answer(
        "🔎 <b>Читаю этикетку...</b>"
    )

    try:
        photo = message.photo[-1]

        file = await bot.get_file(photo.file_id)

        image_bytes = await bot.download_file(
            file.file_path
        )

        image_data = image_bytes.read()

        result = await analyze_food_image(image_data)

    except Exception as e:

        logging.exception(e)

        await processing_message.edit_text(
            "❌ Не получилось прочитать этикетку.\n\n"
            "Попробуй сфотографировать её ближе и "
            "при хорошем освещении."
        )

        return

    await processing_message.delete()

    telegram_id = message.from_user.id

    pending_meals[telegram_id] = {
        "data": result
    }

    calories = result.get("calories")
    protein = result.get("protein")
    fat = result.get("fat")
    carbs = result.get("carbs")
    basis = result.get("basis")

    if any(
        value is None
        for value in [calories, protein, fat, carbs]
    ):
        await message.answer(
            "⚠️ <b>Не удалось полностью прочитать этикетку.</b>\n\n"
            "Попробуй отправить фотографию, где таблица "
            "КБЖУ хорошо видна."
        )

        return

    text = (
        f"📦 <b>{result.get('name', 'Продукт')}</b>\n\n"

        f"🔥 {format_number(calories)} ккал\n"
        f"🥩 {format_number(protein)} г белка\n"
        f"🥑 {format_number(fat)} г жиров\n"
        f"🍞 {format_number(carbs)} г углеводов\n\n"
    )

    if basis == "100g":
        text += "📏 Значения указаны на <b>100 г</b>.\n\n"
        text += "Сколько ты съел?"

        await state.set_state(MealStates.waiting_amount)

        await message.answer(
            text,
            reply_markup=amount_type_keyboard()
        )

    elif basis == "100ml":
        text += "📏 Значения указаны на <b>100 мл</b>.\n\n"
        text += "Напиши, сколько мл ты выпил."

        await state.set_state(MealStates.waiting_amount)

        await message.answer(
            text,
            reply_markup=amount_type_keyboard()
        )

    elif basis == "portion":
        text += "📏 Значения указаны за <b>порцию</b>.\n\n"
        text += "Сколько порций ты съел?"

        await state.set_state(MealStates.waiting_amount)

        await message.answer(
            text,
            reply_markup=amount_type_keyboard()
        )

    else:
        text += "📦 Значения указаны за упаковку.\n\n"
        text += "Сколько упаковок ты съел?"

        await state.set_state(MealStates.waiting_amount)

        await message.answer(
            text,
            reply_markup=amount_type_keyboard()
        )


# ============================================================
# AMOUNT
# ============================================================

@dp.callback_query(
    MealStates.waiting_amount,
    F.data == "amount_grams"
)
async def amount_grams(
    callback: CallbackQuery,
    state: FSMContext
):

    await callback.answer()

    await state.update_data(amount_type="grams")

    await callback.message.edit_text(
        "⚖️ <b>Сколько грамм?</b>\n\n"
        "Напиши число, например: <b>250</b>"
    )


@dp.callback_query(
    MealStates.waiting_amount,
    F.data == "amount_portion"
)
async def amount_portion(
    callback: CallbackQuery,
    state: FSMContext
):

    await callback.answer()

    await state.update_data(amount_type="portion")

    await callback.message.edit_text(
        "🥣 <b>Сколько порций?</b>\n\n"
        "Напиши число, например: <b>2</b>"
    )


@dp.message(MealStates.waiting_amount)
async def receive_amount(
    message: Message,
    state: FSMContext
):

    try:
        amount = float(message.text.replace(",", "."))
    except (ValueError, AttributeError):
        await message.answer(
            "❌ Введи число.\n\n"
            "Например: <b>150</b>"
        )
        return

    if amount <= 0:
        await message.answer(
            "❌ Значение должно быть больше 0."
        )
        return

    telegram_id = message.from_user.id

    if telegram_id not in pending_meals:
        await state.clear()

        await message.answer(
            "Сессия добавления еды закончилась.\n"
            "Нажми 📷 Добавить еду ещё раз.",
            reply_markup=main_menu()
        )

        return

    meal = pending_meals[telegram_id]["data"]

    state_data = await state.get_data()

    amount_type = state_data.get(
        "amount_type",
        "grams"
    )

    basis = meal.get("basis")

    multiplier = 1

    if basis == "100g" or basis == "100ml":

        multiplier = amount / 100

    elif basis in ("portion", "package"):

        multiplier = amount

    calories = meal["calories"] * multiplier
    protein = meal["protein"] * multiplier
    fat = meal["fat"] * multiplier
    carbs = meal["carbs"] * multiplier

    pending_meals[telegram_id]["calculated"] = {
        "name": meal["name"],
        "calories": calories,
        "protein": protein,
        "fat": fat,
        "carbs": carbs,
        "amount": amount,
        "amount_type": amount_type
    }

    text = (
        "🍽 <b>Проверь приём пищи</b>\n\n"

        f"📦 {meal['name']}\n"
        f"⚖️ {format_number(amount)} "
        f"{'г' if amount_type == 'grams' else 'порций'}\n\n"

        f"🔥 {format_number(calories)} ккал\n"
        f"🥩 {format_number(protein)} г белка\n"
        f"🥑 {format_number(fat)} г жиров\n"
        f"🍞 {format_number(carbs)} г углеводов"
    )

    await message.answer(
        text,
        reply_markup=confirm_meal()
    )


# ============================================================
# CONFIRM MEAL
# ============================================================

@dp.callback_query(F.data == "meal_confirm")
async def meal_confirm(
    callback: CallbackQuery,
    state: FSMContext
):

    await callback.answer()

    telegram_id = callback.from_user.id

    if telegram_id not in pending_meals:
        await callback.message.edit_text(
            "❌ Приём пищи больше недоступен.",
            reply_markup=main_menu()
        )

        return

    meal = pending_meals[telegram_id]["calculated"]

    await add_meal(
        telegram_id=telegram_id,
        name=meal["name"],
        calories=meal["calories"],
        protein=meal["protein"],
        fat=meal["fat"],
        carbs=meal["carbs"],
        amount=meal["amount"],
        amount_unit=meal["amount_type"]
    )

    del pending_meals[telegram_id]

    await state.clear()

    user = await get_user(telegram_id)

    totals = await get_today_totals(telegram_id)

    calories_left = max(
        user["calories_goal"] - totals["calories"],
        0
    )

    protein_left = max(
        user["protein_goal"] - totals["protein"],
        0
    )

    fat_left = max(
        user["fat_goal"] - totals["fat"],
        0
    )

    carbs_left = max(
        user["carbs_goal"] - totals["carbs"],
        0
    )

    text = (
        "✅ <b>Добавлено</b>\n\n"

        f"📦 {meal['name']}\n"
        f"🔥 {format_number(meal['calories'])} ккал\n\n"

        "<b>Осталось сегодня:</b>\n\n"

        f"🔥 {format_number(calories_left)} ккал\n"
        f"🥩 {format_number(protein_left)} г белка\n"
        f"🥑 {format_number(fat_left)} г жиров\n"
        f"🍞 {format_number(carbs_left)} г углеводов"
    )

    await callback.message.edit_text(
        text,
        reply_markup=main_menu()
    )


@dp.callback_query(F.data == "meal_cancel")
async def meal_cancel(
    callback: CallbackQuery,
    state: FSMContext
):

    await callback.answer()

    telegram_id = callback.from_user.id

    pending_meals.pop(
        telegram_id,
        None
    )

    await state.clear()

    await callback.message.edit_text(
        "❌ Добавление отменено.",
        reply_markup=main_menu()
    )


# ============================================================
# TODAY
# ============================================================

@dp.callback_query(F.data == "today")
async def today_callback(
    callback: CallbackQuery
):

    await callback.answer()

    telegram_id = callback.from_user.id

    user = await get_user(telegram_id)

    if not user:
        await callback.message.edit_text(
            "Сначала нажми /start"
        )
        return

    totals = await get_today_totals(
        telegram_id
    )

    meals = await get_today_meals(
        telegram_id
    )

    text = build_today_text(
        user,
        totals
    )

    if meals:

        text += "\n\n<b>Приёмы пищи:</b>\n"

        for meal in meals:

            text += (
                f"\n• {meal['name']} — "
                f"{format_number(meal['calories'])} ккал"
            )

    else:

        text += (
            "\n\n<i>Сегодня пока ничего "
            "не добавлено.</i>"
        )

    await callback.message.edit_text(
        text,
        reply_markup=today_keyboard()
    )


# ============================================================
# DELETE LAST MEAL
# ============================================================

@dp.callback_query(F.data == "delete_last")
async def delete_last_callback(
    callback: CallbackQuery
):

    await callback.answer()

    telegram_id = callback.from_user.id

    deleted = await delete_last_meal(
        telegram_id
    )

    if deleted:

        await callback.message.edit_text(
            "🗑 <b>Последний приём пищи удалён.</b>",
            reply_markup=main_menu()
        )

    else:

        await callback.message.edit_text(
            "Сегодня ещё нет приёмов пищи.",
            reply_markup=main_menu()
        )


# ============================================================
# SETTINGS
# ============================================================

@dp.callback_query(F.data == "settings")
async def settings_callback(
    callback: CallbackQuery
):

    await callback.answer()

    telegram_id = callback.from_user.id

    user = await get_user(telegram_id)

    text = (
        "⚙️ <b>Настройки</b>\n\n"

        f"🔥 Калории: {format_number(user['calories_goal'])}\n"
        f"🥩 Белок: {format_number(user['protein_goal'])} г\n"
        f"🥑 Жиры: {format_number(user['fat_goal'])} г\n"
        f"🍞 Углеводы: {format_number(user['carbs_goal'])} г"
    )

    await callback.message.edit_text(
        text,
        reply_markup=settings_menu()
    )


# ============================================================
# CHANGE SETTINGS
# ============================================================

async def start_setting(
    callback: CallbackQuery,
    state: FSMContext,
    setting_name: str,
    prompt: str
):

    await callback.answer()

    await state.set_state(
        getattr(SettingsStates, setting_name)
    )

    await callback.message.edit_text(
        prompt,
        reply_markup=cancel_keyboard()
    )


@dp.callback_query(F.data == "set_calories")
async def set_calories_callback(
    callback: CallbackQuery,
    state: FSMContext
):

    await start_setting(
        callback,
        state,
        "calories",
        "🔥 <b>Новая дневная норма калорий:</b>"
    )


@dp.callback_query(F.data == "set_protein")
async def set_protein_callback(
    callback: CallbackQuery,
    state: FSMContext
):

    await start_setting(
        callback,
        state,
        "protein",
        "🥩 <b>Новая дневная норма белка:</b>"
    )


@dp.callback_query(F.data == "set_fat")
async def set_fat_callback(
    callback: CallbackQuery,
    state: FSMContext
):

    await start_setting(
        callback,
        state,
        "fat",
        "🥑 <b>Новая дневная норма жиров:</b>"
    )


@dp.callback_query(F.data == "set_carbs")
async def set_carbs_callback(
    callback: CallbackQuery,
    state: FSMContext
):

    await start_setting(
        callback,
        state,
        "carbs",
        "🍞 <b>Новая дневная норма углеводов:</b>"
    )


# ============================================================
# SETTINGS INPUTS
# ============================================================

async def update_single_goal(
    message: Message,
    field: str,
    state: FSMContext
):

    try:
        value = float(
            message.text.replace(",", ".")
        )
    except (ValueError, AttributeError):

        await message.answer(
            "❌ Введи число."
        )

        return

    if value <= 0:

        await message.answer(
            "❌ Значение должно быть больше 0."
        )

        return

    user = await get_user(
        message.from_user.id
    )

    goals = {
        "calories": user["calories_goal"],
        "protein": user["protein_goal"],
        "fat": user["fat_goal"],
        "carbs": user["carbs_goal"]
    }

    goals[field] = value

    await update_user_goals(
        telegram_id=message.from_user.id,
        calories=goals["calories"],
        protein=goals["protein"],
        fat=goals["fat"],
        carbs=goals["carbs"]
    )

    await state.clear()

    await message.answer(
        "✅ <b>Норма обновлена.</b>",
        reply_markup=main_menu()
    )


@dp.message(SettingsStates.calories)
async def settings_calories(
    message: Message,
    state: FSMContext
):

    await update_single_goal(
        message,
        "calories",
        state
    )


@dp.message(SettingsStates.protein)
async def settings_protein(
    message: Message,
    state: FSMContext
):

    await update_single_goal(
        message,
        "protein",
        state
    )


@dp.message(SettingsStates.fat)
async def settings_fat(
    message: Message,
    state: FSMContext
):

    await update_single_goal(
        message,
        "fat",
        state
    )


@dp.message(SettingsStates.carbs)
async def settings_carbs(
    message: Message,
    state: FSMContext
):

    await update_single_goal(
        message,
        "carbs",
        state
    )


# ============================================================
# BACK TO MAIN MENU
# ============================================================

@dp.callback_query(F.data == "back_main")
async def back_main(
    callback: CallbackQuery,
    state: FSMContext
):

    await callback.answer()

    await state.clear()

    await callback.message.edit_text(
        "🍽 <b>Дневник питания</b>\n\n"
        "Что хочешь сделать?",
        reply_markup=main_menu()
    )


@dp.callback_query(F.data == "cancel_action")
async def cancel_action(
    callback: CallbackQuery,
    state: FSMContext
):

    await callback.answer()

    telegram_id = callback.from_user.id

    pending_meals.pop(
        telegram_id,
        None
    )

    await state.clear()

    await callback.message.edit_text(
        "❌ Действие отменено.",
        reply_markup=main_menu()
    )


# ============================================================
# TEXT WITHOUT ACTIVE STATE
# ============================================================

@dp.message(F.text)
async def unknown_text(message: Message):

    await message.answer(
        "Я жду фотографию этикетки 📷\n\n"
        "Или используй меню ниже.",
        reply_markup=main_menu()
    )


# ============================================================
# START BOT
# ============================================================

async def main():

    await init_db()

    logging.info(
        "Food Diary Bot started"
    )

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
