from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from datetime import timedelta
import asyncio
from app.database import get_db, engine, Base, SessionLocal
from app import models, schemas, crud
from app.auth import (
    authenticate_user, 
    create_access_token, 
    get_current_active_user,
    get_password_hash,
    settings
)

try:
    Base.metadata.create_all(bind=engine)
    print("✅ Таблицы базы данных проверены/созданы")
except Exception as e:
    print(f"⚠️  Предупреждение: не удалось создать таблицы: {e}")
    print("⚠️  Убедитесь, что база данных создана и PostgreSQL запущен")

app = FastAPI(
    title="DroneDelivery API",
    description="API для сервиса доставки дронами",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def update_orders_status_background():
    while True:
        try:
            db = SessionLocal()
            try:
                updated = crud.update_pending_orders_status(db)
                if updated > 0:
                    print(f"🔄 Фоновая задача: обновлено {updated} заказов в БД")
            finally:
                db.close()
        except Exception as e:
            print(f"❌ Ошибка в фоновой задаче обновления статусов: {e}")
        
        await asyncio.sleep(10)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(update_orders_status_background())
    print("✅ Фоновая задача обновления статусов заказов запущена")


@app.get("/")
async def root():
    return {"message": "DroneDelivery API", "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/auth/register", response_model=schemas.UserResponse, status_code=201)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    try:
        if not user.email or not user.phone or not user.full_name or not user.password:
            raise HTTPException(status_code=400, detail="Все обязательные поля должны быть заполнены")
        
        if len(user.password) < 6:
            raise HTTPException(status_code=400, detail="Пароль должен содержать минимум 6 символов")
        db_user = crud.get_user_by_email(db, email=user.email)
        if db_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        new_user = crud.create_user(db=db, user=user)
        return new_user
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = str(e)
        print(f"Ошибка при регистрации: {error_detail}")
        print(traceback.format_exc())
        if "database" in error_detail.lower() or "connection" in error_detail.lower():
            raise HTTPException(status_code=500, detail="Ошибка подключения к базе данных. Проверьте настройки.")
        raise HTTPException(status_code=500, detail=f"Ошибка сервера при регистрации")


@app.post("/auth/login", response_model=schemas.Token)
def login(user_credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    try:
        user = authenticate_user(db, user_credentials.email, user_credentials.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Ошибка при входе: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")


@app.get("/users/me", response_model=schemas.UserResponse)
def read_user_me(current_user: models.User = Depends(get_current_active_user)):
    return current_user


@app.patch("/users/me", response_model=schemas.UserResponse)
def update_user_me(
    user_update: schemas.UserUpdate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return crud.update_user(db, user_id=current_user.id, user_update=user_update)


@app.get("/users/", response_model=List[schemas.UserResponse])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = crud.get_users(db, skip=skip, limit=limit)
    return users


@app.get("/users/{user_id}", response_model=schemas.UserResponse)
def read_user(user_id: int, db: Session = Depends(get_db)):
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@app.post("/orders/", response_model=schemas.OrderResponse, status_code=201)
def create_order(
    order: schemas.OrderCreate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if not order.delivery_address and current_user.default_delivery_address:
        order.delivery_address = current_user.default_delivery_address
    
    order_data = order.dict()
    order_data["user_id"] = current_user.id
    order_create = schemas.OrderCreate(**order_data)
    return crud.create_order(db=db, order=order_create)


@app.get("/orders/", response_model=List[schemas.OrderResponse])
def read_orders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    orders = crud.get_orders(db, skip=skip, limit=limit)
    return orders


@app.get("/orders/my", response_model=List[schemas.OrderResponse])
def read_my_orders(
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    orders = crud.get_orders_by_user(db, user_id=current_user.id, skip=skip, limit=limit)
    return orders


@app.get("/orders/{order_id}", response_model=schemas.OrderResponse)
def read_order(order_id: int, db: Session = Depends(get_db)):
    db_order = crud.get_order(db, order_id=order_id)
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return db_order


@app.patch("/orders/{order_id}", response_model=schemas.OrderResponse)
def update_order(order_id: int, order_update: schemas.OrderUpdate, db: Session = Depends(get_db)):
    db_order = crud.update_order(db, order_id=order_id, order_update=order_update)
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return db_order


@app.delete("/orders/{order_id}", status_code=204)
def delete_order(order_id: int, db: Session = Depends(get_db)):
    success = crud.delete_order(db, order_id=order_id)
    if not success:
        raise HTTPException(status_code=404, detail="Order not found")
    return None


@app.post("/deliveries/", response_model=schemas.DeliveryResponse, status_code=201)
def create_delivery(delivery: schemas.DeliveryCreate, db: Session = Depends(get_db)):
    order = crud.get_order(db, order_id=delivery.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    existing_delivery = crud.get_delivery_by_order(db, order_id=delivery.order_id)
    if existing_delivery:
        raise HTTPException(status_code=400, detail="Delivery already exists for this order")
    
    return crud.create_delivery(db=db, delivery=delivery)


@app.get("/deliveries/", response_model=List[schemas.DeliveryResponse])
def read_deliveries(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    deliveries = crud.get_deliveries(db, skip=skip, limit=limit)
    return deliveries


@app.get("/deliveries/{delivery_id}", response_model=schemas.DeliveryResponse)
def read_delivery(delivery_id: int, db: Session = Depends(get_db)):
    db_delivery = crud.get_delivery(db, delivery_id=delivery_id)
    if db_delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    return db_delivery


@app.get("/orders/{order_id}/delivery", response_model=schemas.DeliveryResponse)
def read_order_delivery(order_id: int, db: Session = Depends(get_db)):
    db_delivery = crud.get_delivery_by_order(db, order_id=order_id)
    if db_delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found for this order")
    return db_delivery


@app.patch("/deliveries/{delivery_id}", response_model=schemas.DeliveryResponse)
def update_delivery(delivery_id: int, delivery_update: schemas.DeliveryUpdate, db: Session = Depends(get_db)):
    db_delivery = crud.update_delivery(db, delivery_id=delivery_id, delivery_update=delivery_update)
    if db_delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    return db_delivery


