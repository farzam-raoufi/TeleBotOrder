import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv
import os

from database import init_db
from handlers.user import user_router
from handlers.admin import admin_router
from handlers.order import order_router
# from handlers import user_router, admin_router, callback_router

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=os.getenv("BOT_TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)


dp = Dispatcher()

# Register routers
dp.include_router(admin_router)
dp.include_router(user_router)
dp.include_router(order_router)
# dp.include_router(callback_router)


async def main():
    await init_db()
    print("robot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
