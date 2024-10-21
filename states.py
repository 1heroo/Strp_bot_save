from aiogram.fsm.state import State, StatesGroup

cookies = open("cookies.txt").read().splitlines()
proxies = open("proxies.txt").read().splitlines()


class CurrentState(StatesGroup):
    menu = State()
    new_start = State()
    new_end = State()
    new_hours = State()
    model = State()
    count = State()
    date = State()
    hours = State()
    minutes = State()
