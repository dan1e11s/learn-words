from __future__ import annotations

import random
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from db.repository import WordsRepository
from services.srs import compute_next_review, progress_gain

router = Router()


class TestState(StatesGroup):
    active = State()


def normalize_korean(text: str) -> str:
    return " ".join((text or "").strip().split()).lower()


def build_options_keyboard(options: list[str]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=option, callback_data=f"ans:{idx}")] for idx, option in enumerate(options)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def send_next_question(
    message: Message,
    state: FSMContext,
    repository: WordsRepository,
) -> None:
    data = await state.get_data()
    queue: list[dict[str, Any]] = data.get("queue", [])
    if not queue:
        correct = data.get("correct_answers", 0)
        total = data.get("total_questions", 0)
        await message.answer(f"Тест завершен.\nРезультат: {correct}/{total}.")
        await state.clear()
        return

    question = queue.pop(0)
    data["queue"] = queue
    data["current"] = question
    await state.update_data(**data)

    if question["qtype"] == "choice":
        wrong_options = await repository.get_random_russian_options(
            user_id=message.from_user.id,
            exclude_word_id=question["id"],
            limit=10,
        )
        wrong_options = list(dict.fromkeys([opt for opt in wrong_options if opt != question["russian"]]))
        picked_wrong = wrong_options[:3]
        options = picked_wrong + [question["russian"]]
        random.shuffle(options)
        correct_idx = options.index(question["russian"])
        await state.update_data(correct_choice_index=correct_idx)
        await message.answer(
            f"Выбери перевод:\n<b>{question['korean']}</b>",
            reply_markup=build_options_keyboard(options),
        )
    else:
        await message.answer(f"Введи корейское слово для перевода:\n<b>{question['russian']}</b>")


@router.message(F.text == "Пройти тест")
async def start_test(
    message: Message,
    state: FSMContext,
    repository: WordsRepository,
) -> None:
    rows = await repository.get_test_words(user_id=message.from_user.id, limit=30)
    if not rows:
        await message.answer("Нет слов для теста. Добавь слова или повтори позже.")
        return

    queue: list[dict[str, Any]] = []
    for row in rows:
        qtype = random.choice(["choice", "input"])
        queue.append(
            {
                "id": row["id"],
                "korean": row["korean"],
                "russian": row["russian"],
                "times_tested": row["times_tested"],
                "progress": row["progress"],
                "interval_days": row["interval_days"],
                "qtype": qtype,
            }
        )
    random.shuffle(queue)

    await state.set_state(TestState.active)
    await state.update_data(queue=queue, total_questions=len(queue), correct_answers=0)
    await message.answer(f"Начинаем тест. Вопросов: {len(queue)}.")
    await send_next_question(message, state, repository)


@router.message(TestState.active, F.text.regexp(r"^/stop$"))
async def stop_test(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Тест остановлен.")


@router.message(TestState.active, F.text.startswith("ans:"))
async def block_manual_callback_text(message: Message) -> None:
    await message.answer("Используй кнопки ответа ниже.")


@router.callback_query(TestState.active, F.data.startswith("ans:"))
async def process_choice_answer(callback, state: FSMContext, repository: WordsRepository) -> None:
    data = await state.get_data()
    current = data.get("current")
    if not current:
        await callback.answer("Вопрос уже закрыт.")
        return

    picked = int(callback.data.split(":", maxsplit=1)[1])
    correct_idx = data.get("correct_choice_index")
    is_correct = picked == correct_idx

    gain = progress_gain(current["qtype"], current["times_tested"])
    was_mastered = current["progress"] >= 100
    new_progress = min(100, current["progress"] + gain) if is_correct else current["progress"]
    became_mastered = (not was_mastered) and new_progress >= 100
    interval_days, next_review = compute_next_review(
        was_already_mastered=was_mastered or became_mastered,
        current_interval_days=current["interval_days"],
        is_correct=is_correct and (was_mastered or became_mastered),
    )

    await repository.update_word_after_answer(
        word_id=current["id"],
        is_correct=is_correct,
        progress_delta=gain,
        new_interval_days=interval_days,
        new_next_review=next_review,
    )

    if is_correct:
        data["correct_answers"] = data.get("correct_answers", 0) + 1
        await callback.message.answer("Верно!")
    else:
        await callback.message.answer(f"Неверно. Правильный ответ: {current['russian']}")
    await state.update_data(**data)
    await callback.answer()
    await send_next_question(callback.message, state, repository)


@router.message(TestState.active)
async def process_input_answer(
    message: Message,
    state: FSMContext,
    repository: WordsRepository,
) -> None:
    data = await state.get_data()
    current = data.get("current")
    if not current:
        await message.answer("Текущий вопрос не найден. Запусти тест снова.")
        await state.clear()
        return
    if current["qtype"] != "input":
        await message.answer("Для этого вопроса выбери вариант кнопкой.")
        return

    user_answer = normalize_korean(message.text or "")
    correct_answer = normalize_korean(current["korean"])
    is_correct = user_answer == correct_answer

    gain = progress_gain(current["qtype"], current["times_tested"])
    was_mastered = current["progress"] >= 100
    new_progress = min(100, current["progress"] + gain) if is_correct else current["progress"]
    became_mastered = (not was_mastered) and new_progress >= 100
    interval_days, next_review = compute_next_review(
        was_already_mastered=was_mastered or became_mastered,
        current_interval_days=current["interval_days"],
        is_correct=is_correct and (was_mastered or became_mastered),
    )

    await repository.update_word_after_answer(
        word_id=current["id"],
        is_correct=is_correct,
        progress_delta=gain,
        new_interval_days=interval_days,
        new_next_review=next_review,
    )

    if is_correct:
        data["correct_answers"] = data.get("correct_answers", 0) + 1
        await message.answer("Верно!")
    else:
        await message.answer(f"Неверно. Правильный ответ: {current['korean']}")
    await state.update_data(**data)
    await send_next_question(message, state, repository)
