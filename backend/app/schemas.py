from pydantic import BaseModel, EmailStr
from datetime import datetime
from decimal import Decimal
from typing import Optional


class UserBase(BaseModel):
    email: EmailStr
    phone: str
    full_name: str


class UserCreate(UserBase):
    password: str
    default_delivery_address: Optional[str] = None
    default_delivery_city: Optional[str] = None


class UserUpdate(BaseModel):
    phone: Optional[str] = None
    full_name: Optional[str] = None
    default_delivery_address: Optional[str] = None
    default_delivery_city: Optional[str] = None
    password: Optional[str] = None


class UserResponse(UserBase):
    id: int
    default_delivery_address: Optional[str] = None
    default_delivery_city: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


class OrderBase(BaseModel):
    category: str
    description: str
    delivery_address: str
    delivery_time: Optional[str] = "asap"
    comment: Optional[str] = None
    weight: Optional[float] = None


class OrderCreate(OrderBase):
    user_id: Optional[int] = None


class OrderUpdate(BaseModel):
    status: Optional[str] = None
    description: Optional[str] = None
    delivery_address: Optional[str] = None
    delivery_time: Optional[str] = None
    comment: Optional[str] = None
    weight: Optional[float] = None


class DeliveryBase(BaseModel):
    order_id: int
    drone_id: Optional[str] = None
    estimated_arrival: Optional[datetime] = None


class DeliveryCreate(DeliveryBase):
    pass


class DeliveryUpdate(BaseModel):
    status: Optional[str] = None
    drone_id: Optional[str] = None
    estimated_arrival: Optional[datetime] = None
    actual_arrival: Optional[datetime] = None


class DeliveryResponse(DeliveryBase):
    id: int
    status: str
    actual_arrival: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class OrderResponse(OrderBase):
    id: int
    user_id: int
    status: str
    price: Decimal
    created_at: datetime
    updated_at: Optional[datetime] = None
    delivery: Optional[DeliveryResponse] = None
    
    class Config:
        from_attributes = True


