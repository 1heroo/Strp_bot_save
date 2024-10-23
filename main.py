import asyncio
import logging
import sys
import pytz
from apscheduler.job import Job
from bs4 import BeautifulSoup
from handlers.add_model_handlers import (
    handle_first_selection,
    handle_second_selection,
    handle_invalid_dates,
)
from handlers.schedules_handlers import (
    send_message,
    send_schedule_list,
    remove_schedule,
    handle_change_time,
    update_schedule_time,
)
from markups import create_date_keyboard, create_hours_keyboard, send_main_menu
from schedules import *
from states import CurrentState, cookies, proxies
from callback_datas import MainMenu, Schedule
from datetime import datetime, timedelta
from os import getenv
from decouple import config

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from aiogram.types.keyboard_button import KeyboardButton
from aiogram.fsm.context import FSMContext


TOKEN = config("MIHAIL_BOT_TOKEN")

dp = Dispatcher()
router = Router()
dp.include_router(router)


@router.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await send_main_menu(message)


@router.callback_query(MainMenu.filter(F.action == "add_model"))
async def add_model_handler(callback: CallbackQuery, state: FSMContext) -> None:
    print(schedules)             # DEBUG
    print(scheduler.get_jobs())  # DEBUG

    await state.set_state(CurrentState.model)
    message = callback.message

    if message.text == "📍 Главное меню":
        await message.edit_text("✍️ Напишите НИК МОДЕЛИ")
    else:
        await message.answer("✍️ Напишите НИК МОДЕЛИ")
    await message.answer(
        "Нажмите на кнопку ниже, чтобы выйти из диалога",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="◀️ Вернуться в главное меню")]],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )


@router.message(CurrentState.model)
async def model_handler(message: Message, state: FSMContext) -> None:
    if message.text == "◀️ Вернуться в главное меню":
        await send_main_menu(message, state)
        return
    await state.update_data(model=message.text)
    await state.set_state(CurrentState.count)

    await message.answer("🤖 Напиши количество ботов 🤖")


@router.message(CurrentState.count)
async def count_handler(message: Message, state: FSMContext) -> None:
    await state.update_data(count=message.text)
    await state.set_state(CurrentState.date)

    await message.answer(
        "🗓 Выберите дату НАЧАЛА СТРИМА 🗓",
        reply_markup=await create_date_keyboard(),
    )


@router.callback_query(CurrentState.date)
async def date_handler(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    is_first = data.get("first", True)

    date_key = "start_date" if is_first else "end_date"
    await state.update_data(**{date_key: callback.data})

    await state.set_state(CurrentState.hours)

    await callback.message.edit_text(
        text="🕒 Выберите часы 🕒",
        reply_markup=await create_hours_keyboard(),
    )


@router.callback_query(CurrentState.hours)
async def hours_handler(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    is_first = data.get("first", True)

    if is_first:
        await handle_first_selection(callback, state)
    else:
        await handle_second_selection(callback, state)


@router.callback_query(CurrentState.minutes)
async def minutes_handler(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    is_first = data.get("first", True)
    model = data.get("model")

    data_key = "start_date" if is_first else "end_date"
    old_date = data.get(data_key)
    await state.update_data(
        **{
            data_key: moscow_tz.localize(
                old_date + timedelta(minutes=float(callback.data))
            )
        }
    )

    if is_first:
        data = await state.get_data()
        for schedule in schedules:
            if schedule["model"] == model:
                if schedule["end_time"] > data.get("start_date"):
                    await handle_invalid_dates(callback, state)
                    return
        await state.update_data(first=False)
        await state.set_state(CurrentState.date)
        await callback.message.edit_text(
            text="🗓 Выберите дату КОНЦА СТРИМА 🗓",
            reply_markup=await create_date_keyboard(),
        )
    else:
        data = await state.get_data()
        end_date = data.get("end_date")
        start_date = data.get("start_date")
        if start_date > end_date:
            await handle_invalid_dates(callback, state)
        else:
            schedule_task(start_date, end_date, data.get("model"), data.get("count"))
            await state.clear()
            await send_main_menu(message=callback.message, text="✅ Данные сохранены! ")


@router.callback_query(MainMenu.filter(F.action == "check_works"))
async def check_works_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await send_schedule_list(callback)


@router.callback_query(F.data == "short_list")
async def short_list_handler(callback: CallbackQuery, state: FSMContext) -> None:
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
    }

    response = await client.get(
        "https://stripchat.com/girls/popular", headers=headers
    )

    soup = BeautifulSoup(response.text, "html.parser")

    short_list = [
        schedule | {"rating": "Не в топ 37", "online": "Не онлайн"}
        for schedule in schedules
    ]

    for index, model in enumerate(soup.find_all("div", class_="model-list-item")):
        nick = model.find("span", class_="model-list-item-username").text.lower()
        for schedule in short_list:
            if nick == schedule["model"]:
                schedule["rating"] = index + 1

    for model in short_list:
        model["online"] = (
            "Онлайн"
            if (
                await client.get(
                    f"https://stripchat.com/api/front/v2/users/username/{nick}"
                )
            ).json()["item"]["isOnline"]
            else "Не онлайн"
        )
    await callback.message.edit_text(
        text="\n".join(
            [
                f"{schedule['model']} - {schedule['rating']} || {schedule['online']}: {schedule['start_time'].strftime('%Y-%m-%d %H:%M')} - {schedule['end_time'].strftime('%Y-%m-%d %H:%M')}"
                for schedule in short_list
            ]
        )
    )


@router.callback_query(Schedule.filter(F.action == "edit_info"))
async def schedules_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    data = Schedule.unpack(callback.data)
    current_schedule = next(
        schedule for schedule in schedules if schedule["start_id"] == data.start_id
    )

    start_time = current_schedule["start_time"].strftime("%Y-%m-%d %H:%M")
    end_time = current_schedule["end_time"].strftime("%Y-%m-%d %H:%M")
    status_icon = (
        "🔴"
        if moscow_tz.localize(datetime.strptime(start_time, "%Y-%m-%d %H:%M"))
        > datetime.now(moscow_tz)
        else "🟢"
    )

    await send_message(
        callback,
        f"""ID: {data.start_id} - {current_schedule["model"]}
Начало: {start_time}
Конец: {end_time}
Статус: {status_icon}
Кол-во ботов: {current_schedule['count']}""",
        InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="❌Удалить запись",
                        callback_data=Schedule(
                            action="remove_confirmation",
                            start_id=data.start_id,
                            end_id=data.end_id,
                        ).pack(),
                    )
                ],
                (
                    [
                        InlineKeyboardButton(
                            text="🛠 Изменить время старта",
                            callback_data=Schedule(
                                action="change_start",
                                start_id=data.start_id,
                                end_id=data.end_id,
                            ).pack(),
                        )
                    ]
                    if status_icon == "🔴"
                    else []
                ),
                [
                    InlineKeyboardButton(
                        text="🛠 Изменить время конца",
                        callback_data=Schedule(
                            action="change_end",
                            start_id=data.start_id,
                            end_id=data.end_id,
                        ).pack(),
                    )
                ],
            ]
        ),
    )


@router.callback_query(
    Schedule.filter(
        F.action.in_(
            [
                "remove_confirmation",
                "cancel_remove",
                "remove",
                "change_start",
                "change_end",
            ]
        )
    )
)
async def handle_schedule_actions(callback: CallbackQuery, state: FSMContext) -> None:
    data = Schedule.unpack(callback.data)

    action_map = {
        "remove_confirmation": lambda: send_message(
            callback,
            "Вы уверены, что хотите удалить запись?",
            InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="✅ Да",
                            callback_data=Schedule(
                                action="remove",
                                start_id=data.start_id,
                                end_id=data.end_id,
                            ).pack(),
                        ),
                        InlineKeyboardButton(
                            text="❌ Нет",
                            callback_data=Schedule(action="cancel_remove").pack(),
                        ),
                    ]
                ]
            ),
        ),
        "cancel_remove": lambda: send_message(callback, "Действие отменено"),
        "remove": lambda: remove_schedule(callback, data),
        "change_start": lambda: handle_change_time(
            callback, state, "change_start", "Выберите новую ДАТУ СТАРТА"
        ),
        "change_end": lambda: handle_change_time(
            callback, state, "change_end", "Выберите новую ДАТУ КОНЦА"
        ),
    }

    await action_map[data.action]()


@router.callback_query(CurrentState.new_hours)
async def new_hours_schedule_handler(
    callback: CallbackQuery, state: FSMContext
) -> None:
    data = await state.get_data()
    await state.update_data(date=callback.data)
    action = data["action"]
    await state.set_state(
        CurrentState.new_start if action == "change_start" else CurrentState.new_end
    )

    await send_message(
        callback,
        f"Выберите новое ВРЕМЯ {'СТАРТА' if action == 'change_start' else 'КОНЦА'}",
        await create_hours_keyboard(),
    )


@router.callback_query(CurrentState.new_start)
async def new_start_schedule_handler(
    callback: CallbackQuery, state: FSMContext
) -> None:
    await update_schedule_time(callback, state, is_start=True)


@router.callback_query(CurrentState.new_end)
async def new_end_schedule_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await update_schedule_time(callback, state, is_start=False)


@router.message(F.text == "◀️ Вернуться в главное меню")
async def back_to_main_menu_handler(message: Message) -> None:
    await send_main_menu(message)


async def check_expired_schedules():
    while True:
        now = datetime.now(moscow_tz)
        expired_schedules = [schedule for schedule in schedules if schedule['end_time'] < now]

        for expired in expired_schedules:
            try:
                # Удаление задачи из планировщика
                scheduler.remove_job(expired['start_id'])
                # Удаление модели из списка
                schedules.remove(expired)
                print(f"Удалена модель {expired['model']}, время истекло")
            except Exception as e:
                print(f"Ошибка при удалении модели: {e}")

        # Задержка на 60 секунд перед следующей проверкой
        await asyncio.sleep(60)


async def restore_from_apscheduler_store():
    try:
        with open('adding_model_cache.json', 'r', encoding='utf-8') as file:
            cache = json.loads(file.read())
    except:
        cache = {}

    jobs = scheduler.get_jobs()
    jobs = list(filter(lambda job: job.name == 'update_bots', jobs))
    print('restoring jobs', jobs)

    jobs_dict = dict()
    for job in jobs:
        model, count = job.args

        if jobs_dict.get(model):
            jobs_dict[model].append(job)
        else:
            jobs_dict[model] = [job]

    restoring_schedules = []
    launched = []

    for model, model_jobs in jobs_dict.items():
        if len(jobs) == 1:
            end_job = model_jobs[-1]
            model, _ = end_job.args

            start_job_json = cache.get(model)
            if start_job_json is None: continue

            print(start_job_json, 'restoring_jobs')

            start_time = datetime.fromisoformat(start_job_json['start_time'])
            if start_time < end_job.next_run_time:
                launched.append({
                    'start_time': start_time,
                    'end_time': end_job.next_run_time,
                    'model': model,
                    'count': start_job_json['count'],
                    'start_id':start_job_json['start_id'],
                    'end_id': end_job.id,
                    'online': False
                })

        elif len(jobs) == 2:
            start_job: Job = min(model_jobs, key=lambda item: item.next_run_time)
            end_job: Job = max(model_jobs, key=lambda item: item.next_run_time)
            print(jobs, 'resporing 2')
            model, count = start_job.args
            restoring_schedules.append({
                'start_time': start_job.next_run_time,
                'end_time': end_job.next_run_time,
                'model': model,
                'count': count,
                'start_id': start_job.id,
                'end_id': end_job.id,
                'online': False
            })
    return launched, restoring_schedules


def remove_duplicate_jobs():
    jobs_key_dict = dict()
    for job in list(filter(lambda item: item.name != 'update_bots', scheduler.get_jobs())):
        arg, *_ = job.args
        key = f'{job.name} {arg}'

        if jobs_key_dict.get(key):
            jobs_key_dict[key].append(job)
        else:
            jobs_key_dict[key] = [job]

    for _, to_be_deleted_jobs in jobs_key_dict.items():
        for job_del in to_be_deleted_jobs[1:]:
            scheduler.remove_job(job_del.id)


async def main() -> None:
    bot = Bot(token=TOKEN)

    await client.post(
        "http://127.0.0.1:8000/api/launch_bots",
        json={"cookies": cookies, "proxies": proxies},
        timeout=360,
    )
    scheduler.start()

    # удаление дублирующихся задач на одну модель
    remove_duplicate_jobs()

    # получение данных расписания и добавление в global schedules
    launched, restoring_schedules = await restore_from_apscheduler_store()
    schedules.extend(restoring_schedules)

    print(schedules)

    for schedule in launched:
        # запуск уже ранее запущенных расписаний
        scheduler.add_job(
            update_bots,
            "date",
            run_date=datetime.now(tz=moscow_tz),
            args=[schedule['model'], schedule['count']],
            id=schedule['start_id'],
            misfire_grace_time=3600 * 23,
        )
    schedules.extend(launched)

    asyncio.create_task(check_expired_schedules())  # Запуск проверки на истекшие модели
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
