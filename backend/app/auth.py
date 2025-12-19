from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
import hashlib
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, crud
import os

class Settings:
    def __init__(self):
        self.secret_key = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 30
        env_file_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        if os.path.exists(env_file_path):
            try:
                with open(env_file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            if key == "SECRET_KEY":
                                self.secret_key = value
            except Exception as e:
                print(f"Предупреждение: не удалось прочитать .env файл: {e}")

settings = Settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def _prehash_password(password: str) -> bytes:
    return hashlib.sha256(password.encode('utf-8')).digest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        password_prehashed = _prehash_password(plain_password)
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_prehashed, hashed_bytes)
    except Exception as e:
        print(f"Ошибка при проверке пароля: {e}")
        return False


def get_password_hash(password: str) -> str:
    password_prehashed = _prehash_password(password)
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_prehashed, salt)
    return hashed.decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def authenticate_user(db: Session, email: str, password: str):
    user = crud.get_user_by_email(db, email=email)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = crud.get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


