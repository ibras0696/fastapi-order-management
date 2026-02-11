"""Эндпоинты аутентификации."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.session import get_db
from app.schemas.auth import Token, UserCreate, UserOut
from app.services.users import authenticate_user, create_user, get_user_by_email

router = APIRouter()


@router.post("/register/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> UserOut:
    """Зарегистрировать пользователя.

    Parameters
    ----------
    payload : UserCreate
        Данные регистрации (email, password).

    Returns
    -------
    UserOut
        Созданный пользователь.

    Raises
    ------
    HTTPException
        400, если email уже зарегистрирован.
    """

    existing = get_user_by_email(db, payload.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="email already registered",
        )
    user = create_user(db, email=payload.email, password=payload.password)
    return UserOut(id=user.id, email=user.email)


@router.post("/token/", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    """Получить JWT токен по email/паролю (OAuth2 Password Flow).

    Notes
    -----
    В Swagger UI это `application/x-www-form-urlencoded` поля:
    `username` (email) и `password`.

    Returns
    -------
    Token
        Access token.

    Raises
    ------
    HTTPException
        401, если логин/пароль неверные.
    """

    user = authenticate_user(db, email=form_data.username, password=form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="incorrect email or password",
        )
    token = create_access_token(subject=user.email)
    return Token(access_token=token)
