from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
from callback_datas import MainMenu
from states import CurrentState, cookies
import pytz

moscow_tz = pytz.timezone("Europe/Moscow")


async def send_main_menu(
    message: Message,
    state: FSMContext = None,
    text=f"📍 Главное меню\nДоступные боты: {len(cookies)}",
) -> None:
    add_model_button = InlineKeyboardButton(
        text="📝 Добавить модель", callback_data=MainMenu(action="add_model").pack()
    )
    check_works_button = InlineKeyboardButton(
        text="🖼 Проверить работу", callback_data=MainMenu(action="check_works").pack()
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[add_model_button], [check_works_button]]
    )

    if state:
        await state.clear()
        await state.set_state(CurrentState.menu)
    await message.answer(text=text, reply_markup=keyboard)


async def create_minutes_keyboard() -> InlineKeyboardMarkup:

    minutes = [i for i in range(5, 61, 5)]

    keyboard = [
        [
            InlineKeyboardButton(text=str(minutes[j]), callback_data=str(minutes[j]))
            for j in range(i, min(i + 4, len(minutes)))
        ]
        for i in range(0, len(minutes), 4)
    ]

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def create_date_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=(datetime.now(moscow_tz) + timedelta(days=day)).strftime(
                        "%d/%m/%y"
                    ),
                    callback_data=(
                        datetime.now(moscow_tz) + timedelta(days=day)
                    ).strftime("%Y-%m-%d"),
                )
            ]
            for day in range(7)
        ]
    )


async def create_hours_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"{j:02}:00", callback_data=f"{j:02}:00")
                for j in range((i - 1) * 4, i * 4)
            ]
            for i in range(1, 7)
        ]
    )
