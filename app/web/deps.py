from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from app.db import TestSessionRepository, UsersRepository, WordsRepository


def get_users_repo(request: Request) -> UsersRepository:
    return UsersRepository(request.app.state.pool)


def get_words_repo(request: Request) -> WordsRepository:
    return WordsRepository(request.app.state.pool)


def get_test_repo(request: Request) -> TestSessionRepository:
    return TestSessionRepository(request.app.state.pool)


def get_current_user_id(request: Request) -> int:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    return int(user_id)


def current_user_id_dep(user_id: int = Depends(get_current_user_id)) -> int:
    return user_id
