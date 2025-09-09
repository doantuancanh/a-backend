from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from app.db.base import TaskStatus

class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    deadline: Optional[datetime] = None
    status: Optional[TaskStatus] = TaskStatus.pending
    link: Optional[str] = None

class TaskCreate(TaskBase):
    project_id: int

class TaskUpdate(TaskBase):
    pass

class TaskInDBBase(TaskBase):
    task_id: int
    project_id: int
    created_at: datetime

    class Config:
        orm_mode = True

class Task(TaskInDBBase):
    pass

