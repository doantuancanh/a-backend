from sqlalchemy import (Column, Integer, String, DateTime, ForeignKey, Enum as SQLAlchemyEnum, Boolean)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()

class UserRole(enum.Enum):
    admin = "admin"
    member = "member"

class ProjectStatus(enum.Enum):
    active = "active"
    inactive = "inactive"

class TaskStatus(enum.Enum):
    pending = "pending"
    done = "done"

class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    telegram_id = Column(String, unique=True, index=True, nullable=True)
    role = Column(SQLAlchemyEnum(UserRole), nullable=False, default=UserRole.member)
    is_active = Column(Boolean(), default=True)
    projects = relationship("Project", back_populates="created_by_user")

class PotentialProject(Base):
    __tablename__ = "potential_projects"
    potential_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    chain = Column(String)
    source = Column(String)
    discovered_at = Column(DateTime, server_default=func.now())

class Project(Base):
    __tablename__ = "projects"
    project_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    chain = Column(String)
    source = Column(String)
    status = Column(SQLAlchemyEnum(ProjectStatus), nullable=False, default=ProjectStatus.active)
    created_at = Column(DateTime, server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.user_id"))
    created_by_user = relationship("User", back_populates="projects")
    tasks = relationship("Task", back_populates="project")

class Task(Base):
    __tablename__ = "tasks"
    task_id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.project_id"))
    title = Column(String, nullable=False)
    description = Column(String)
    deadline = Column(DateTime)
    status = Column(SQLAlchemyEnum(TaskStatus), nullable=False, default=TaskStatus.pending)
    link = Column(String)
    created_at = Column(DateTime, server_default=func.now())
    project = relationship("Project", back_populates="tasks")

