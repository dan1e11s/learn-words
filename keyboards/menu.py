from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Добавить слова")],
        [KeyboardButton(text="Пройти тест")],
        [KeyboardButton(text="Посмотреть прогресс")],
    ],
    resize_keyboard=True,
)
