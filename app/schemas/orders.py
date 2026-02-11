"""Схемы для заказов."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class OrderStatus(str, Enum):
    """Статус заказа."""

    PENDING = "PENDING"
    PAID = "PAID"
    SHIPPED = "SHIPPED"
    CANCELED = "CANCELED"


class OrderItem(BaseModel):
    """Товар в заказе.

    Attributes
    ----------
    product_id : int
        Идентификатор товара.
    quantity : int
        Количество (>= 1).
    price : float
        Цена за единицу (> 0).
    """

    product_id: int
    quantity: int = Field(ge=1)
    price: float = Field(gt=0)


class OrderCreate(BaseModel):
    """Запрос на создание заказа."""

    items: list[OrderItem]

    @field_validator("items")
    @classmethod
    def validate_items(cls, value: list[OrderItem]) -> list[OrderItem]:
        """Проверить, что список товаров не пустой."""

        if not value:
            raise ValueError("items must not be empty")
        return value


class OrderOut(BaseModel):
    """Ответ с данными заказа."""

    id: str
    user_id: int
    items: list[OrderItem]
    total_price: float
    status: OrderStatus


class OrderStatusUpdate(BaseModel):
    """Запрос на обновление статуса заказа."""

    status: OrderStatus
