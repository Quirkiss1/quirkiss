from sqlalchemy.orm import Session
from sqlalchemy import desc
from app import models, schemas
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import random
import string


def get_user(db: Session, user_id: int) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.email == email).first()


def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    from app.auth import get_password_hash
    user_data = user.dict()
    password = user_data.pop("password")
    db_user = models.User(
        **user_data,
        hashed_password=get_password_hash(password)
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, user_id: int, user_update: schemas.UserUpdate) -> Optional[models.User]:
    from app.auth import get_password_hash
    db_user = get_user(db, user_id)
    if db_user:
        update_data = user_update.dict(exclude_unset=True)
        if "password" in update_data:
            update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
        for key, value in update_data.items():
            setattr(db_user, key, value)
        db.commit()
        db.refresh(db_user)
    return db_user


def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[models.User]:
    return db.query(models.User).offset(skip).limit(limit).all()


def get_order(db: Session, order_id: int) -> Optional[models.Order]:
    update_pending_orders_status(db)
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if order:
        _ = order.delivery
    return order


def get_orders(db: Session, skip: int = 0, limit: int = 100) -> List[models.Order]:
    update_pending_orders_status(db)
    orders = db.query(models.Order).order_by(desc(models.Order.created_at)).offset(skip).limit(limit).all()
    for order in orders:
        _ = order.delivery
    return orders


def generate_drone_id() -> str:
    return f"DRONE-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"


def update_pending_orders_status(db: Session):
    now = datetime.now(timezone.utc)
    one_minute_ago = now - timedelta(minutes=1)
    two_minutes_ago = now - timedelta(minutes=2)
    pending_orders = db.query(models.Order).filter(
        models.Order.status == "pending",
        models.Order.created_at <= one_minute_ago
    ).all()
    
    for order in pending_orders:
        order.status = "in_delivery"
        
        existing_delivery = get_delivery_by_order(db, order.id)
        if not existing_delivery:
            drone_id = generate_drone_id()
            estimated_arrival = now + timedelta(minutes=1)
            
            delivery = models.Delivery(
                order_id=order.id,
                drone_id=drone_id,
                status="in_transit",
                estimated_arrival=estimated_arrival
            )
            db.add(delivery)
            print(f"🚁 Создана доставка для заказа #{order.id}, дрон: {drone_id}, статус: in_transit")
        else:
            existing_delivery.status = "in_transit"
            if not existing_delivery.estimated_arrival:
                existing_delivery.estimated_arrival = now + timedelta(minutes=1)
            print(f"🚁 Обновлена доставка для заказа #{order.id}, статус: in_transit")
    
    in_delivery_orders = db.query(models.Order).filter(
        models.Order.status == "in_delivery",
        models.Order.created_at <= two_minutes_ago
    ).all()
    
    for order in in_delivery_orders:
        order.status = "delivered"
        
        delivery = get_delivery_by_order(db, order.id)
        if delivery:
            delivery.status = "delivered"
            delivery.actual_arrival = now
            print(f"✅ Доставка завершена для заказа #{order.id}, дрон: {delivery.drone_id}")
        else:
            drone_id = generate_drone_id()
            delivery = models.Delivery(
                order_id=order.id,
                drone_id=drone_id,
                status="delivered",
                actual_arrival=now
            )
            db.add(delivery)
            print(f"✅ Создана запись о завершенной доставке для заказа #{order.id}, дрон: {drone_id}")
    
    updated_count = len(pending_orders) + len(in_delivery_orders)
    if updated_count > 0:
        try:
            db.commit()
            for order in pending_orders + in_delivery_orders:
                db.refresh(order)
                delivery = get_delivery_by_order(db, order.id)
                if delivery:
                    db.refresh(delivery)
            print(f"✅ Обновлено статусов заказов в БД: {updated_count}")
        except Exception as e:
            db.rollback()
            print(f"❌ Ошибка при сохранении статусов в БД: {e}")
            raise
    
    return updated_count


def get_orders_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[models.Order]:
    update_pending_orders_status(db)
    orders = db.query(models.Order).filter(models.Order.user_id == user_id).order_by(desc(models.Order.created_at)).offset(skip).limit(limit).all()
    for order in orders:
        _ = order.delivery
    return orders


def create_order(db: Session, order: schemas.OrderCreate) -> models.Order:
    category_prices = {
        "food": 199,
        "medicine": 399,
        "parcels": 299,
        "tech": 499,
        "gifts": 599,
        "documents": 149
    }
    
    price = category_prices.get(order.category, 199)
    
    db_order = models.Order(
        **order.dict(),
        price=price,
        status="pending"
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order


def update_order(db: Session, order_id: int, order_update: schemas.OrderUpdate) -> Optional[models.Order]:
    db_order = get_order(db, order_id)
    if db_order:
        update_data = order_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_order, key, value)
        db.commit()
        db.refresh(db_order)
    return db_order


def delete_order(db: Session, order_id: int) -> bool:
    db_order = get_order(db, order_id)
    if db_order:
        db.delete(db_order)
        db.commit()
        return True
    return False


def get_delivery(db: Session, delivery_id: int) -> Optional[models.Delivery]:
    return db.query(models.Delivery).filter(models.Delivery.id == delivery_id).first()


def get_delivery_by_order(db: Session, order_id: int) -> Optional[models.Delivery]:
    return db.query(models.Delivery).filter(models.Delivery.order_id == order_id).first()


def create_delivery(db: Session, delivery: schemas.DeliveryCreate) -> models.Delivery:
    db_delivery = models.Delivery(**delivery.dict())
    db.add(db_delivery)
    db.commit()
    db.refresh(db_delivery)
    return db_delivery


def update_delivery(db: Session, delivery_id: int, delivery_update: schemas.DeliveryUpdate) -> Optional[models.Delivery]:
    db_delivery = get_delivery(db, delivery_id)
    if db_delivery:
        update_data = delivery_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_delivery, key, value)
        db.commit()
        db.refresh(db_delivery)
    return db_delivery


def get_deliveries(db: Session, skip: int = 0, limit: int = 100) -> List[models.Delivery]:
    return db.query(models.Delivery).order_by(desc(models.Delivery.created_at)).offset(skip).limit(limit).all()


