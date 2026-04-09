from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

from config import settings
from db import WordsRepository, create_pool
from handlers import register_handlers


async def on_error(event: ErrorEvent) -> None:
    logging.exception("Unhandled update error: %s", event.exception)
    if event.update.message:
        await event.update.message.answer("Произошла ошибка. Попробуй еще раз.")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    pool = await create_pool()
    repo = WordsRepository(pool)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    register_handlers(dp)
    dp.errors.register(on_error)

    try:
        await dp.start_polling(bot, repository=repo)
    finally:
        await bot.session.close()
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
