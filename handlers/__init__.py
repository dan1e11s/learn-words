from aiogram import Dispatcher

from . import add_words, common, progress, test_words


def register_handlers(dp: Dispatcher) -> None:
    dp.include_router(common.router)
    dp.include_router(add_words.router)
    dp.include_router(test_words.router)
    dp.include_router(progress.router)
