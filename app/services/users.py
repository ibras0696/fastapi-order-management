"""User-related business logic."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User


def get_user_by_email(db: Session, email: str) -> User | None:
    """Найти пользователя по email.

    Parameters
    ----------
    db : sqlalchemy.orm.Session
        Сессия БД.
    email : str
        Email пользователя.

    Returns
    -------
    User | None
        Пользователь или None.
    """

    return db.query(User).filter(User.email == email).one_or_none()


def create_user(db: Session, email: str, password: str) -> User:
    """Создать пользователя.

    Parameters
    ----------
    db : sqlalchemy.orm.Session
        Сессия БД.
    email : str
        Email пользователя.
    password : str
        Пароль в открытом виде.

    Returns
    -------
    User
        Созданный пользователь.
    """

    user = User(email=email, hashed_password=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Проверить логин/пароль.

    Parameters
    ----------
    db : sqlalchemy.orm.Session
        Сессия БД.
    email : str
        Email пользователя.
    password : str
        Пароль в открытом виде.

    Returns
    -------
    User | None
        Пользователь при успехе, иначе None.
    """

    user = get_user_by_email(db, email=email)
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
