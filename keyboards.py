from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🍽 Сегодня",
                    callback_data="today"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📷 Добавить еду",
                    callback_data="add_food"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ Настройки",
                    callback_data="settings"
                )
            ]
        ]
    )


def confirm_meal():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Добавить",
                    callback_data="meal_confirm"
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="meal_cancel"
                )
            ]
        ]
    )


def amount_type_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚖️ Ввести граммы",
                    callback_data="amount_grams"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🥣 Одна порция",
                    callback_data="amount_portion"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="meal_cancel"
                )
            ]
        ]
    )


def settings_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔥 Калории",
                    callback_data="set_calories"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🥩 Белок",
                    callback_data="set_protein"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🥑 Жиры",
                    callback_data="set_fat"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🍞 Углеводы",
                    callback_data="set_carbs"
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data="back_main"
                )
            ]
        ]
    )


def cancel_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="cancel_action"
                )
            ]
        ]
    )


def today_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📷 Добавить еду",
                    callback_data="add_food"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Удалить последний",
                    callback_data="delete_last"
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data="back_main"
                )
            ]
        ]
    )
