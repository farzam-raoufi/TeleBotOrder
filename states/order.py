# states/order.py
from aiogram.fsm.state import State, StatesGroup

class OrderStates(StatesGroup):
    waiting_for_confirmation = State()