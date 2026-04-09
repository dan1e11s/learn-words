from __future__ import annotations

from aiogram import F, Router
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from db.repository import WordsRepository

router = Router()


FILTERS = {
    "all": (0, 100, None, "Все слова"),
    "new": (0, 49, None, "Прогресс 0-49%"),
    "learning": (50, 99, None, "Прогресс 50-99%"),
    "mastered": (100, 100, None, "Заученные (100%)"),
    "recent7": (0, 100, 7, "Повторялись за 7 дней"),
}


def build_progress_filters() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Все", callback_data="progress:all"),
                InlineKeyboardButton(text="0-49%", callback_data="progress:new"),
            ],
            [
                InlineKeyboardButton(text="50-99%", callback_data="progress:learning"),
                InlineKeyboardButton(text="100%", callback_data="progress:mastered"),
            ],
            [InlineKeyboardButton(text="За 7 дней", callback_data="progress:recent7")],
        ]
    )


def format_progress(rows) -> str:
    lines = []
    for row in rows[:50]:
        lines.append(
            f"{row['korean']} - {row['russian']} | "
            f"{row['progress']}% | попыток: {row['times_tested']}"
        )
    return "\n".join(lines) if lines else "Нет слов по выбранному фильтру."


@router.message(F.text == "Посмотреть прогресс")
async def progress_menu(message: Message) -> None:
    await message.answer("Выбери фильтр прогресса:", reply_markup=build_progress_filters())


@router.callback_query(F.data.startswith("progress:"))
async def progress_show(callback, repository: WordsRepository) -> None:
    filter_key = callback.data.split(":", maxsplit=1)[1]
    if filter_key not in FILTERS:
        await callback.answer("Неизвестный фильтр.")
        return
    min_p, max_p, days, title = FILTERS[filter_key]
    rows = await repository.get_progress_rows(
        user_id=callback.from_user.id,
        progress_min=min_p,
        progress_max=max_p,
        last_days=days,
    )
    text = f"{title}:\n\n{format_progress(rows)}"
    await callback.message.answer(text)
    await callback.answer()
