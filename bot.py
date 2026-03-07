"""
Gym Workout Telegram Bot
Тренировки + Питание + ИИ-аналитика
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import Database
from handlers import register_handlers
from nutrition_handlers import register_nutrition_handlers
from scheduler import start_schedulers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    db = Database()
    await db.init()

    register_handlers(dp, db)
    register_nutrition_handlers(dp, db)

    await start_schedulers(bot, db)

    logger.info("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
