from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

from config import settings
from db import WordsRepository, create_pool
from handlers import register_handlers


async def run_health_server() -> asyncio.base_events.Server | None:
    port_raw = os.getenv("PORT")
    if not port_raw:
        return None

    try:
        port = int(port_raw)
    except ValueError:
        logging.warning("Invalid PORT value: %s", port_raw)
        return None

    async def handle_client(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            await reader.read(1024)
            writer.write(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/plain; charset=utf-8\r\n"
                b"Content-Length: 2\r\n"
                b"Connection: close\r\n\r\n"
                b"OK"
            )
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle_client, host="0.0.0.0", port=port)
    logging.info("Health server started on port %s", port)
    return server


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
    health_server = await run_health_server()

    try:
        await dp.start_polling(bot, repository=repo)
    finally:
        if health_server is not None:
            health_server.close()
            await health_server.wait_closed()
        await bot.session.close()
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
