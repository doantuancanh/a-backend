from pydantic import BaseModel, EmailStr
from typing import Optional
from app.db.base import UserRole

class UserBase(BaseModel):
    email: EmailStr
    name: str
    telegram_id: Optional[str] = None
    role: Optional[UserRole] = UserRole.member
    is_active: Optional[bool] = True

class UserCreate(UserBase):
    password: str

class UserUpdate(UserBase):
    password: Optional[str] = None

class UserInDBBase(UserBase):
    user_id: int

    class Config:
        orm_mode = True

class User(UserInDBBase):
    pass

