"""Healthcheck эндпоинты."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict:
    """Вернуть статус приложения.

    Returns
    -------
    dict
        JSON со статусом.
    """

    return {"status": "ok"}
