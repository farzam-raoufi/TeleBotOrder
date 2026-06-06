import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

from database import init_db
from handlers.admin import admin_router
from handlers.order import order_router, process_expired_orders
from handlers.user import user_router

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


async def scheduler(bot: Bot):
    while True:
        try:
            await process_expired_orders(bot)
        except Exception as e:
            logging.error(f"خطا در scheduler: {e}")

        await asyncio.sleep(3)


async def main():
    await init_db()
    # اجرای scheduler
    scheduler_task = asyncio.create_task(scheduler(bot))

    try:
        print("robot started")
        await dp.start_polling(bot)
    finally:
        scheduler_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
