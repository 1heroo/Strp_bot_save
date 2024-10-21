from datetime import datetime
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from callback_datas import Schedule
from schedules import schedules, scheduler, update_bots, moscow_tz
from states import CurrentState
from markups import create_date_keyboard, send_main_menu
from aiogram.fsm.context import FSMContext


async def send_message(
        callback: CallbackQuery, text: str, keyboard: InlineKeyboardMarkup = None
) -> None:
    await callback.message.answer(text=text, reply_markup=keyboard)


def create_schedule_button(schedule) -> InlineKeyboardButton:
    status_icon = "🔴" if schedule["start_time"] > datetime.now(moscow_tz) else "🟢"
    return InlineKeyboardButton(
        text=f"{status_icon} {schedule['model']}",
        callback_data=Schedule(
            action="edit_info", start_id=schedule["start_id"], end_id=schedule["end_id"]
        ).pack(),
    )


async def send_schedule_list(callback: CallbackQuery) -> None:
    if not schedules:
        await send_message(callback, "❌ Нет запланированых ботов для моделей. ❌")
        return

    keyboard = []

    for i in range(0, len(schedules), 2):
        row = [create_schedule_button(schedules[i])]

        if i + 1 < len(schedules):
            row.append(create_schedule_button(schedules[i + 1]))

        keyboard.append(row)

    keyboard.append(
        [InlineKeyboardButton(text="Краткий список", callback_data="short_list")]
    )

    await send_message(
        callback,
        "Запланированые стримы",
        keyboard=InlineKeyboardMarkup(inline_keyboard=keyboard),
    )


async def remove_schedule(callback: CallbackQuery, data) -> None:
    current_schedule = next(
        schedule for schedule in schedules if schedule["start_id"] == data.start_id
    )

    try:
        scheduler.remove_job(data.start_id)
    except:
        try:
            func = scheduler.get_job(data.end_id).func
            await func(current_schedule["model"], 0)
            scheduler.remove_job(data.end_id)
        except:
            print("Задача уже удалена")

    # Вызов end_stream для очистки ресурсов
    await end_stream(current_schedule['model'])

    schedules.remove(current_schedule)
    await send_main_menu(callback.message, text="Данные изменены!")


async def end_stream(model: str) -> None:
    # Остановить всех ботов для данной модели
    await update_bots(model, 0)
    # Удалить задачу из списка
    schedules[:] = [s for s in schedules if s['model'] != model]
    print(f"Stream for model {model} ended and resources cleaned up.")


async def handle_change_time(
        callback: CallbackQuery, state: FSMContext, action: str, date_prompt: str
) -> None:
    await state.set_state(CurrentState.new_hours)

    if action == "change_start":
        await state.update_data(
            start_id=Schedule.unpack(callback.data).start_id, action=action
        )
    else:
        await state.update_data(
            end_id=Schedule.unpack(callback.data).end_id, action=action
        )

    await send_message(callback, date_prompt, await create_date_keyboard())


async def update_schedule_time(
        callback: CallbackQuery, state: FSMContext, is_start: bool
) -> None:
    data = await state.get_data()
    print(data)
    time_key = "start_time" if is_start else "end_time"
    id_key = "start_id" if is_start else "end_id"

    date = datetime.strptime(data.get("date"), "%Y-%m-%d")
    hours = datetime.strptime(callback.data, "%H:%M").time()
    current_schedule = next(
        schedule for schedule in schedules if schedule[id_key] == data[id_key]
    )
    current_schedule[time_key] = datetime.combine(date, hours)

    scheduler.remove_job(data[id_key])
    scheduler.add_job(
        update_bots,
        "date",
        run_date=datetime.combine(date, hours),
        args=[current_schedule["model"], current_schedule["count"] if is_start else 0],
        id=data[id_key],
        misfire_grace_time=3600 * 23,
    )

    await send_main_menu(callback.message, text="Данные изменены!")
