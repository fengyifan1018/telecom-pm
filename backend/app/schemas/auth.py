from typing import Optional

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    is_active: bool
    wecom_userid: Optional[str] = None

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    username: str
    password: str
    display_name: str
    role: str


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    wecom_userid: Optional[str] = None


class ChangePassword(BaseModel):
    old_password: str
    new_password: str
