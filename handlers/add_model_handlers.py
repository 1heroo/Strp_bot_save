from datetime import datetime
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from markups import create_date_keyboard, send_main_menu, create_minutes_keyboard
from states import CurrentState


async def handle_first_selection(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    start_date = data.get("start_date")

    await state.update_data(
        start_date=datetime.combine(
            datetime.strptime(start_date, "%Y-%m-%d"),
            datetime.strptime(callback.data, "%H:%M").time(),
        ),
    )
    await state.set_state(CurrentState.minutes)

    await callback.message.edit_text(
        text="🗓 Выберите минуты",
        reply_markup=await create_minutes_keyboard(),
    )


async def handle_second_selection(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    end_date = data.get("end_date")

    await state.update_data(
        end_date=datetime.combine(
            datetime.strptime(end_date, "%Y-%m-%d"),
            datetime.strptime(callback.data, "%H:%M").time(),
        )
    )

    await state.set_state(CurrentState.minutes)

    await callback.message.edit_text(
        text="🗓 Выберите минуты",
        reply_markup=await create_minutes_keyboard(),
    )


async def handle_invalid_dates(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text(
        "❌ Дата начала либо меньше конца либо пересекается с другим. Выберите дату НАЧАЛА СТРИМА 🗓",
        reply_markup=await create_date_keyboard(),
    )
    await state.update_data(start_date=None, end_date=None, first=True)
    await state.set_state(CurrentState.date)
