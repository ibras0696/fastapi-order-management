"""Бизнес-логика заказов."""

from __future__ import annotations

from sqlalchemy.orm import Session

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


def create_order(db: Session, user_id: int, items: list[OrderItem]) -> Order:
    """Создать заказ.

    Parameters
    ----------
    db : sqlalchemy.orm.Session
        Сессия БД.
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
    db.flush()

    add_outbox_event(
        db,
        event_type="new_order",
        aggregate_id=order.id,
        payload={"order_id": order.id},
    )

    db.commit()
    db.refresh(order)
    return order


def get_order(db: Session, order_id: str) -> Order | None:
    """Получить заказ по id."""

    return db.query(Order).filter(Order.id == order_id).one_or_none()


def list_orders_by_user(db: Session, user_id: int) -> list[Order]:
    """Получить список заказов пользователя."""

    return (
        db.query(Order)
        .filter(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
        .all()
    )


def update_order_status(db: Session, order: Order, status: OrderStatus) -> Order:
    """Обновить статус заказа."""

    order.status = status.value
    db.add(order)
    db.commit()
    db.refresh(order)
    return order
