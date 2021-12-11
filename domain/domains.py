from dataclasses import dataclass, field
from typing import List


@dataclass
class AccountReceivable:
    pass


@dataclass
class CouponProduct:
    name: str = ''
    quantity: float = 0.0
    unit_price: float = 0.0
    total: float = 0.0


@dataclass
class Coupon:
    id: str = ''
    aditional_info: str = ''
    customer_id: str = ''
    customer_name: str = ''
    customer_document: str = ''
    vehicle: str = ''
    plate: str = ''
    date: str = ''
    status: str = 'NORMAL'
    products: List[CouponProduct] = field(default_factory=list)

    def is_in_cash(self):
        return self.id == ''

    def is_customer_identified(self):
        return self.customer_id != ''

    @property
    def total(self):
        total_of_products = 0
        for prod in self.products:
            total_of_products += prod.total
        return total_of_products
