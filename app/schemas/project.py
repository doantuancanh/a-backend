from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from app.db.base import ProjectStatus

class ProjectBase(BaseModel):
    name: str
    chain: Optional[str] = None
    source: Optional[str] = None
    status: Optional[ProjectStatus] = ProjectStatus.active

class ProjectCreate(ProjectBase):
    created_by: int

class ProjectUpdate(ProjectBase):
    pass

class ProjectInDBBase(ProjectBase):
    project_id: int
    created_at: datetime
    created_by: int

    class Config:
        orm_mode = True

class Project(ProjectInDBBase):
    pass

