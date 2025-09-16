from sqlalchemy.orm import Session
from app.db.base import Project
from app.schemas.project import ProjectCreate, ProjectUpdate
from typing import List, Optional


def get_project(db: Session, project_id: int) -> Optional[Project]:
    return db.query(Project).filter(Project.project_id == project_id).first()

def get_projects(db: Session, skip: int = 0, limit: int = 100) -> List[Project]:
    return db.query(Project).offset(skip).limit(limit).all()
def get_projects_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[Project]:
    return db.query(Project).filter(Project.created_by == user_id).offset(skip).limit(limit).all()



def create_project(db: Session, project: ProjectCreate) -> Project:
    db_project = Project(**project.dict())
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project

def update_project(db: Session, project_id: int, project: ProjectUpdate) -> Optional[Project]:
    db_project = get_project(db, project_id)
    if db_project:
        update_data = project.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_project, key, value)
        db.commit()
        db.refresh(db_project)
    return db_project

def delete_project(db: Session, project_id: int) -> Optional[Project]:
    db_project = get_project(db, project_id)
    if db_project:
        db.delete(db_project)
        db.commit()
    return db_project

