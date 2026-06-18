from typing import Optional
from pydantic import BaseModel

class Product(BaseModel):
    product: str
    cost: float
    stock: Optional[int] = None
