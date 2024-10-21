from aiogram.filters.callback_data import CallbackData


class MainMenu(CallbackData, prefix="main_menu"):
    action: str


class Schedule(CallbackData, prefix="schedule"):
    action: str
    start_id: str | None = None
    end_id: str | None = None
