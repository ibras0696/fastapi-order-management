"""Эндпоинты заказов."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.db.redis import get_redis_client
from app.models.user import User
from app.schemas.orders import OrderCreate, OrderOut, OrderStatusUpdate
from app.services.orders import (
    create_order,
    get_order,
    list_orders_by_user,
    update_order_status,
)
from app.services.orders_cache import get_order_from_cache, set_order_cache

router = APIRouter()


def _to_order_out(order) -> OrderOut:
    """Преобразовать модель Order в схему ответа."""

    return OrderOut(
        id=order.id,
        user_id=order.user_id,
        items=order.items,
        total_price=order.total_price,
        status=order.status,
    )


@router.post("/orders/", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order_endpoint(
    payload: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderOut:
    """Создать заказ (только авторизованные).

    Parameters
    ----------
    payload : OrderCreate
        Список товаров (items) для заказа.

    Returns
    -------
    OrderOut
        Созданный заказ.

    Raises
    ------
    HTTPException
        401, если нет/невалидный токен.
    """

    order = create_order(db, user_id=current_user.id, items=payload.items)
    out = _to_order_out(order)
    set_order_cache(get_redis_client(), out)
    return out


@router.get("/orders/{order_id}/", response_model=OrderOut)
def get_order_endpoint(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderOut:
    """Получить заказ по `order_id` (с кешированием).

    Parameters
    ----------
    order_id : str
        UUID заказа.

    Returns
    -------
    OrderOut
        Заказ.

    Raises
    ------
    HTTPException
        401, если нет/невалидный токен.
        403, если заказ принадлежит другому пользователю.
        404, если заказ не найден.
    """

    cached = get_order_from_cache(get_redis_client(), order_id=order_id)
    if cached is not None:
        if cached.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="forbidden",
            )
        return cached

    order = get_order(db, order_id=order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="order not found",
        )
    if order.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    out = _to_order_out(order)
    set_order_cache(get_redis_client(), out)
    return out


@router.patch("/orders/{order_id}/", response_model=OrderOut)
def update_order_status_endpoint(
    order_id: str,
    payload: OrderStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderOut:
    """Обновить статус заказа.

    Parameters
    ----------
    order_id : str
        UUID заказа.
    payload : OrderStatusUpdate
        Новый статус заказа.

    Returns
    -------
    OrderOut
        Обновлённый заказ.

    Raises
    ------
    HTTPException
        401, если нет/невалидный токен.
        403, если заказ принадлежит другому пользователю.
        404, если заказ не найден.
    """

    order = get_order(db, order_id=order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="order not found",
        )
    if order.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    order = update_order_status(db, order=order, status=payload.status)
    out = _to_order_out(order)
    set_order_cache(get_redis_client(), out)
    return out


@router.get("/orders/user/{user_id}/", response_model=list[OrderOut])
def list_user_orders_endpoint(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[OrderOut]:
    """Получить список заказов пользователя.

    Parameters
    ----------
    user_id : int
        Идентификатор пользователя.

    Returns
    -------
    list[OrderOut]
        Список заказов пользователя.

    Raises
    ------
    HTTPException
        401, если нет/невалидный токен.
        403, если запрашивается не свой `user_id`.
    """

    if user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    orders = list_orders_by_user(db, user_id=user_id)
    out_orders = [_to_order_out(order) for order in orders]
    redis_client = get_redis_client()
    for order_out in out_orders:
        set_order_cache(redis_client, order_out)
    return out_orders
