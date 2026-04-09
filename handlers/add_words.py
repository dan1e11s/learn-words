from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from db.repository import WordsRepository
from services.parser import parse_words_batch

router = Router()


class AddWordsState(StatesGroup):
    waiting_batch = State()


@router.message(F.text == "Добавить слова")
async def add_words_prompt(message: Message, state: FSMContext) -> None:
    await state.set_state(AddWordsState.waiting_batch)
    await message.answer(
        "Отправь слова в формате:\n"
        "слово - перевод\n"
        "слово - перевод, перевод, перевод"
    )


@router.message(AddWordsState.waiting_batch)
async def add_words_save(
    message: Message,
    state: FSMContext,
    repository: WordsRepository,
) -> None:
    pairs, errors = parse_words_batch(message.text or "")
    if not pairs:
        await message.answer(
            "Не удалось распознать слова.\n"
            + ("\n".join(errors[:10]) if errors else "Проверь формат и попробуй снова.")
        )
        return

    inserted = await repository.add_words(user_id=message.from_user.id, pairs=pairs)
    skipped = len(pairs) - inserted

    response = [f"Добавлено новых слов: {inserted}."]
    if skipped > 0:
        response.append(f"Пропущено дубликатов: {skipped}.")
    if errors:
        response.append("Ошибки в строках:\n" + "\n".join(errors[:10]))

    await message.answer("\n".join(response))
    await state.clear()
