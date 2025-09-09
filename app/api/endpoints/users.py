from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.api import deps
from app.crud import crud_user
from app.schemas.user import User, UserCreate, UserUpdate
from app.db.base import User as DBUser, UserRole

router = APIRouter()

def get_current_active_user(current_user: DBUser = Depends(deps.get_current_user)) -> DBUser:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def get_current_active_admin(current_user: DBUser = Depends(get_current_active_user)) -> DBUser:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="The user doesn't have enough privileges")
    return current_user

@router.post("/", response_model=User)
def create_user(
    *, 
    db: Session = Depends(deps.get_db), 
    user_in: UserCreate, 
    current_user: DBUser = Depends(get_current_active_admin)
):
    user = crud_user.get_user_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(status_code=400, detail="The user with this email already exists in the system.")
    user = crud_user.create_user(db, user=user_in)
    return user

@router.get("/", response_model=List[User])
def read_users(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: DBUser = Depends(get_current_active_admin)
):
    users = crud_user.get_users(db, skip=skip, limit=limit)
    return users

@router.get("/{user_id}", response_model=User)
def read_user_by_id(
    user_id: int,
    db: Session = Depends(deps.get_db),
    current_user: DBUser = Depends(get_current_active_admin)
):
    user = crud_user.get_user(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/{user_id}", response_model=User)
def update_user(
    *,
    db: Session = Depends(deps.get_db),
    user_id: int,
    user_in: UserUpdate,
    current_user: DBUser = Depends(get_current_active_admin)
):
    user = crud_user.get_user(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user = crud_user.update_user(db, user_id=user_id, user=user_in)
    return user

@router.delete("/{user_id}", response_model=User)
def delete_user(
    user_id: int,
    db: Session = Depends(deps.get_db),
    current_user: DBUser = Depends(get_current_active_admin)
):
    user = crud_user.delete_user(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

