"""Бизнес-логика заказов."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.schemas.orders import OrderItem, OrderStatus
from app.services.outbox import add_outbox_event


def calculate_total_price(items: list[OrderItem]) -> float:
    """Посчитать итоговую сумму заказа.

    Parameters
    ----------
    items : list[OrderItem]
        Список товаров.

    Returns
    -------
    float
        Итоговая сумма.
    """

    return float(sum(item.price * item.quantity for item in items))


async def create_order(db: AsyncSession, user_id: int, items: list[OrderItem]) -> Order:
    """Создать заказ.

    Parameters
    ----------
    db : sqlalchemy.ext.asyncio.AsyncSession
        Async сессия БД.
    user_id : int
        Идентификатор пользователя.
    items : list[OrderItem]
        Список товаров.

    Returns
    -------
    Order
        Созданный заказ.
    """

    total_price = calculate_total_price(items)
    order = Order(
        user_id=user_id,
        items=[item.model_dump() for item in items],
        total_price=total_price,
        status=OrderStatus.PENDING.value,
    )
    db.add(order)
    await db.flush()

    add_outbox_event(
        db,
        event_type="new_order",
        aggregate_id=order.id,
        payload={"order_id": order.id},
    )

    await db.commit()
    await db.refresh(order)
    return order


async def get_order(db: AsyncSession, order_id: str) -> Order | None:
    """Получить заказ по id."""

    result = await db.execute(select(Order).where(Order.id == order_id))
    return result.scalar_one_or_none()


async def list_orders_by_user(db: AsyncSession, user_id: int) -> list[Order]:
    """Получить список заказов пользователя."""

    result = await db.execute(
        select(Order)
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
    )
    return list(result.scalars().all())


async def update_order_status(
    db: AsyncSession,
    order: Order,
    status: OrderStatus,
) -> Order:
    """Обновить статус заказа."""

    order.status = status.value
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order
