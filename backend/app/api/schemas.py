import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    email: str = Field(..., max_length=256)
    password: str = Field(..., min_length=8, max_length=128)
    api_ucc: Optional[str] = Field("HACK342", max_length=64)

    @field_validator("email")
    @classmethod
    def validate_and_normalize_email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v:
            raise ValueError("Invalid email format")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    api_ucc: str
    notifications_enabled: bool
    theme: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=128)
    email: Optional[str] = Field(None, max_length=256)
    notifications_enabled: Optional[bool] = None
    theme: Optional[str] = Field(None, pattern=r"^(light|dark)$")

    @field_validator("email")
    @classmethod
    def validate_optional_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip().lower()
        email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if not re.match(email_regex, v):
            raise ValueError("Invalid email format")
        return v


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("New password must be at least 8 characters long")
        if not any(c.isalpha() for c in v):
            raise ValueError("New password must contain at least one letter")
        if not any(c.isdigit() or not c.isalnum() for c in v):
            raise ValueError("New password must contain at least one number or special character")
        return v


class ForgotPasswordRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_reset_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("New password must be at least 8 characters long")
        if not any(c.isalpha() for c in v):
            raise ValueError("New password must contain at least one letter")
        if not any(c.isdigit() or not c.isalnum() for c in v):
            raise ValueError("New password must contain at least one number or special character")
        return v
