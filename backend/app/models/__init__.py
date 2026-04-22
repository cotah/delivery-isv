"""Registry central de modelos SQLAlchemy.

Imports aqui garantem que relationships por string (ex: relationship("Category"))
resolvam em qualquer import path. Sem isso, requests HTTP tocando só Store falham
com InvalidRequestError quando Category/City ainda não foram importados.

O alembic/env.py tem pattern análogo pra autogenerate funcionar. Este __init__.py
é o equivalente em runtime.
"""

from app.models.addon import Addon
from app.models.addon_group import AddonGroup
from app.models.address import Address
from app.models.category import Category
from app.models.city import City
from app.models.customer import Customer
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.order_item_addon import OrderItemAddon
from app.models.order_status_log import OrderStatusLog
from app.models.product import Product
from app.models.product_addon_group import ProductAddonGroup
from app.models.product_variation import ProductVariation
from app.models.store import Store

__all__ = [
    "Addon",
    "AddonGroup",
    "Address",
    "Category",
    "City",
    "Customer",
    "Order",
    "OrderItem",
    "OrderItemAddon",
    "OrderStatusLog",
    "Product",
    "ProductAddonGroup",
    "ProductVariation",
    "Store",
]
