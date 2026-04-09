from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app.db import UsersRepository
from app.services.auth import hash_password, verify_password
from app.web.deps import get_users_repo

router = APIRouter()


def render(request: Request, template: str, context: dict) -> object:
    return request.app.state.templates.TemplateResponse(request, template, context)


@router.get("/register")
async def register_page(request: Request) -> object:
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=303)
    return render(request, "register.html", {"title": "Регистрация", "error": None})


@router.post("/register")
async def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    users_repo: UsersRepository = Depends(get_users_repo),
) -> object:
    email = email.strip().lower()
    if len(password) < 6:
        return render(
            request,
            "register.html",
            {"title": "Регистрация", "error": "Пароль должен быть не короче 6 символов."},
        )

    user_id = await users_repo.create_user(email=email, password_hash=hash_password(password))
    if not user_id:
        return render(
            request,
            "register.html",
            {"title": "Регистрация", "error": "Пользователь с таким email уже существует."},
        )

    request.session["user_id"] = user_id
    return RedirectResponse("/", status_code=303)


@router.get("/login")
async def login_page(request: Request) -> object:
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=303)
    return render(request, "login.html", {"title": "Вход", "error": None})


@router.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    users_repo: UsersRepository = Depends(get_users_repo),
) -> object:
    email = email.strip().lower()
    user = await users_repo.get_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        return render(request, "login.html", {"title": "Вход", "error": "Неверные данные."})

    request.session["user_id"] = user["id"]
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
async def logout(request: Request) -> object:
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
