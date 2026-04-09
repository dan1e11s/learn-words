from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from keyboards.menu import MAIN_MENU

router = Router()


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    await message.answer(
        "Привет! Я помогу учить корейские слова.\n"
        "Выбери действие в меню ниже.",
        reply_markup=MAIN_MENU,
    )
