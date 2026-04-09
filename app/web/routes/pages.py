from __future__ import annotations

import random
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.db import TestSessionRepository, WordsRepository
from app.services.parser import parse_words_batch
from app.services.srs import compute_next_review, progress_gain
from app.web.deps import current_user_id_dep, get_test_repo, get_words_repo

router = APIRouter()

FILTERS = {
    "all": (0, 100, None, "Все слова"),
    "new": (0, 49, None, "Прогресс 0-49%"),
    "learning": (50, 99, None, "Прогресс 50-99%"),
    "mastered": (100, 100, None, "Заученные (100%)"),
}


def normalize_korean(text: str) -> str:
    return " ".join((text or "").strip().split()).lower()


def render(request: Request, template: str, context: dict[str, Any]) -> object:
    return request.app.state.templates.TemplateResponse(request, template, context)


def build_choice_options(correct: str, wrong: list[str]) -> tuple[list[str], int]:
    options = wrong[:3] + [correct]
    options = list(dict.fromkeys(options))
    while len(options) < 4:
        options.append(correct)
    random.shuffle(options)
    return options, options.index(correct)


@router.get("/")
async def index(request: Request) -> object:
    if not request.session.get("user_id"):
        return RedirectResponse("/login", status_code=303)
    return render(request, "index.html", {"title": "Главная"})


@router.get("/words/add")
async def words_add_page(request: Request, user_id: int = Depends(current_user_id_dep)) -> object:
    return render(request, "add_words.html", {"title": "Добавить слова", "error": None, "ok": None})


@router.post("/words/add")
async def words_add_submit(
    request: Request,
    raw_words: str = Form(...),
    user_id: int = Depends(current_user_id_dep),
    words_repo: WordsRepository = Depends(get_words_repo),
) -> object:
    pairs, errors = parse_words_batch(raw_words)
    if not pairs:
        return render(
            request,
            "add_words.html",
            {
                "title": "Добавить слова",
                "error": "\n".join(errors[:10]) if errors else "Проверь формат ввода.",
                "ok": None,
            },
        )

    inserted = await words_repo.add_words(user_id=user_id, pairs=pairs)
    skipped = len(pairs) - inserted
    msg = f"Добавлено: {inserted}. Пропущено дубликатов: {skipped}."
    if errors:
        msg += f" Ошибки: {'; '.join(errors[:5])}"
    return render(request, "add_words.html", {"title": "Добавить слова", "error": None, "ok": msg})


@router.get("/progress")
async def progress_page(
    request: Request,
    filter: str = "all",
    user_id: int = Depends(current_user_id_dep),
    words_repo: WordsRepository = Depends(get_words_repo),
) -> object:
    key = filter if filter in FILTERS else "all"
    min_p, max_p, days, title = FILTERS[key]
    rows = await words_repo.get_progress_rows(
        user_id=user_id,
        progress_min=min_p,
        progress_max=max_p,
        last_days=days,
        limit=200,
    )
    return render(
        request,
        "progress.html",
        {"title": "Прогресс", "rows": rows, "active_filter": key, "filter_title": title},
    )


@router.post("/test/start")
async def test_start(
    request: Request,
    user_id: int = Depends(current_user_id_dep),
    words_repo: WordsRepository = Depends(get_words_repo),
    test_repo: TestSessionRepository = Depends(get_test_repo),
) -> object:
    rows = await words_repo.get_test_words(user_id=user_id, limit=30)
    if not rows:
        return RedirectResponse("/test/current?empty=1", status_code=303)

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
    session_id = await test_repo.start_session(user_id=user_id, queue=queue)
    request.session["test_session_id"] = session_id
    return RedirectResponse("/test/current", status_code=303)


@router.get("/test/current")
async def test_current(
    request: Request,
    empty: int = 0,
    user_id: int = Depends(current_user_id_dep),
    test_repo: TestSessionRepository = Depends(get_test_repo),
    words_repo: WordsRepository = Depends(get_words_repo),
) -> object:
    if empty:
        return render(
            request,
            "test_result.html",
            {"title": "Тест", "result": "Нет слов для теста. Добавь слова или повтори позже."},
        )

    session_id = request.session.get("test_session_id")
    if not session_id:
        return RedirectResponse("/", status_code=303)

    session = await test_repo.get_session(session_id=session_id, user_id=user_id)
    if not session:
        request.session.pop("test_session_id", None)
        return RedirectResponse("/", status_code=303)

    payload = session["payload"]
    queue = payload.get("queue", [])
    current_index = payload.get("current_index", 0)
    correct_count = payload.get("correct_count", 0)
    total = len(queue)

    if current_index >= total:
        mistakes = payload.get("mistakes", [])
        await test_repo.delete_session(session_id=session_id, user_id=user_id)
        request.session.pop("test_session_id", None)
        return render(
            request,
            "test_result.html",
            {
                "title": "Результат",
                "result": f"Тест завершен. Результат: {correct_count}/{total}",
                "mistakes": mistakes,
            },
        )

    current = queue[current_index]
    options = None
    if current["qtype"] == "choice":
        wrong = await words_repo.get_random_russian_options(user_id, current["id"], 10)
        wrong = [w for w in wrong if w != current["russian"]]
        options, correct_idx = build_choice_options(current["russian"], wrong)
        payload["correct_choice_index"] = correct_idx
        payload["current_options"] = options
        await test_repo.save_session(session_id=session_id, payload=payload)

    return render(
        request,
        "test_current.html",
        {
            "title": "Тест",
            "current": current,
            "question_number": current_index + 1,
            "total_questions": total,
            "options": options,
            "error": None,
        },
    )


@router.post("/test/answer")
async def test_answer(
    request: Request,
    answer_choice: int | None = Form(None),
    answer_input: str = Form(""),
    user_id: int = Depends(current_user_id_dep),
    test_repo: TestSessionRepository = Depends(get_test_repo),
    words_repo: WordsRepository = Depends(get_words_repo),
) -> object:
    session_id = request.session.get("test_session_id")
    if not session_id:
        return RedirectResponse("/", status_code=303)
    session = await test_repo.get_session(session_id=session_id, user_id=user_id)
    if not session:
        request.session.pop("test_session_id", None)
        return RedirectResponse("/", status_code=303)

    payload = session["payload"]
    queue = payload.get("queue", [])
    current_index = payload.get("current_index", 0)
    if current_index >= len(queue):
        return RedirectResponse("/test/current", status_code=303)
    current = queue[current_index]

    if current["qtype"] == "choice":
        if answer_choice is None:
            raise HTTPException(status_code=400, detail="Выбери вариант ответа.")
        is_correct = answer_choice == int(payload.get("correct_choice_index", -1))
        current_options = payload.get("current_options", [])
        if 0 <= answer_choice < len(current_options):
            user_answer = current_options[answer_choice]
        else:
            user_answer = f"Вариант #{answer_choice + 1}"
        correct_answer = current["russian"]
    else:
        is_correct = normalize_korean(answer_input) == normalize_korean(current["korean"])
        user_answer = (answer_input or "").strip()
        correct_answer = current["korean"]

    gain = progress_gain(current["qtype"], current["times_tested"])
    was_mastered = current["progress"] >= 100
    new_progress = min(100, current["progress"] + gain) if is_correct else current["progress"]
    became_mastered = (not was_mastered) and new_progress >= 100
    interval_days, next_review = compute_next_review(
        was_already_mastered=was_mastered or became_mastered,
        current_interval_days=current["interval_days"],
        is_correct=is_correct and (was_mastered or became_mastered),
    )
    await words_repo.update_word_after_answer(
        word_id=current["id"],
        is_correct=is_correct,
        progress_delta=gain,
        new_interval_days=interval_days,
        new_next_review=next_review,
    )

    if is_correct:
        payload["correct_count"] = payload.get("correct_count", 0) + 1
    else:
        mistakes = payload.get("mistakes", [])
        mistakes.append(
            {
                "prompt": current["korean"] if current["qtype"] == "choice" else current["russian"],
                "correct_answer": correct_answer,
                "user_answer": user_answer or "Пустой ответ",
                "question_type": current["qtype"],
            }
        )
        payload["mistakes"] = mistakes
    payload["current_index"] = current_index + 1
    payload.pop("correct_choice_index", None)
    payload.pop("current_options", None)
    await test_repo.save_session(session_id=session_id, payload=payload)
    return RedirectResponse("/test/current", status_code=303)
