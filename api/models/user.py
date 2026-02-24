from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from api.core.security import Role

class User(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Role = Role.ANALYST
    is_active: bool = True
    created_at: datetime = datetime.utcnow()
    last_login: Optional[datetime] = None

class UserCreate(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Role = Role.ANALYST

class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[Role] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 1800  # 30 minutes
    user: dict
