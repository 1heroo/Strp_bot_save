import json

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from datetime import datetime
from random import choices
import httpx
import pytz

client = httpx.AsyncClient()


scheduler = AsyncIOScheduler()
scheduler.add_jobstore('sqlalchemy', url='sqlite:///jobs.sqlite')
schedules: list = []
moscow_tz = pytz.timezone("Europe/Moscow")


async def update_bots(model: str, count: int) -> None:
    await client.post(
        "http://127.0.0.1:8000/api/update_models",
        json={"models": {model: count}},
        timeout=3600,
    )


async def check_online(model: str, count: int) -> bool:
    online = (
        await client.get(
            "https://stripchatgirls.com/api/front/v2/users/username/" + model
        )
    ).json()["item"]["isOnline"]

    for schedule in schedules:
        if schedule["model"] == model:
            if online:
                if schedule["online"] == False:
                    await update_bots(model, count)
                    schedule["online"] = True
            else:
                if schedule["online"] == True:
                    await update_bots(model, 0)
                    schedule["online"] = False


async def remove_from_list(model):
    try:
        schedules.remove(model)
    except:
        pass


def save_in_adding_cache(start_time, end_time, model, count, start_id, end_id):
    cache_file_path = 'adding_model_cache.json'
    try:
        with open(cache_file_path, 'r', encoding='utf-8') as file:
            cache = json.loads(file.read())
    except:
        cache = {}

    model_obj = {
        'start_time': start_time.isoformat(),
        'end_time': end_time.isoformat(),
        'model': model,
        'count': count,
        'start_id': start_id,
        'end_id': end_id,
    }
    cache.update({model: model_obj})

    with open(cache_file_path, 'w', encoding='utf-8') as file:
        json.dump(cache, file, indent=4, ensure_ascii=False)


def schedule_task(
        start_time: datetime, end_time: datetime, model: str, count: int, start_id: str = None, end_id: str = None
) -> None:
    new_task = False
    if start_id is None:
        new_task = True
        start_id = "".join(choices("123456789", k=15))
    if end_id is None:
        end_id = "".join(choices("123456789", k=15))

    if new_task:
        # добавление в json файл с данными о username модели и count
        save_in_adding_cache(
            start_time=start_time, end_time=end_time, model=model, count=count, start_id=start_id, end_id=end_id)
    scheduler.add_job(
        update_bots,
        "date",
        run_date=start_time,
        args=[model, count],
        id=start_id,
        misfire_grace_time=3600 * 23,
    )
    scheduler.add_job(
        update_bots,
        "date",
        run_date=end_time,
        args=[model, 0],
        id=end_id,
        misfire_grace_time=3600 * 23,
    )

    # Добавить вызов end_stream при завершении стрима
    scheduler.add_job(
        end_stream,
        "date",
        run_date=end_time,
        args=[model],  # Передаем модель для завершения стрима
        misfire_grace_time=3600 * 23,
    )

    scheduler.add_job(
        remove_from_list,
        "date",
        run_date=end_time,
        args=[
            {
                "start_time": start_time,
                "end_time": end_time,
                "model": model,
                "count": count,
                "start_id": start_id,
                "end_id": end_id,
            }
        ],
    )
    scheduler.add_job(
        check_online,
        "interval",
        minutes=1,
        start_date=start_time,
        end_date=end_time,
        args=[model, count],
    )
    schedules.append(
        {
            "start_time": start_time,
            "end_time": end_time,
            "model": model,
            "count": count,
            "start_id": start_id,
            "end_id": end_id,
            "online": True,
        }
    )


async def end_stream(model: str) -> None:
    # Остановить всех ботов для данной модели
    await update_bots(model, 0)
    # Удалить задачу из списка
    schedules[:] = [s for s in schedules if s['model'] != model]
    print(f"Stream for model {model} ended and resources cleaned up.")
