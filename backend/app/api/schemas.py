import re
from datetime import datetime
from typing import Any, Optional
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
        if "@" not in v or "." not in v:
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
    account_balance_paise: int = 10000000
    account_balance_inr: float = 100000.0
    subscription_tier: str = "FREE"
    notifications_enabled: bool
    theme: str
    created_at: Optional[str] = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class CreateUserRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=128)
    email: str = Field(..., max_length=256)
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field("user", pattern=r"^(user|admin|trader)$")
    api_ucc: Optional[str] = Field("HACK342", max_length=64)
    initial_balance_inr: float = Field(100000.0, ge=0, le=10000000.0)
    subscription_tier: str = Field("FREE", pattern=r"^(FREE|PRO|ENTERPRISE)$")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if not re.match(email_regex, v):
            raise ValueError("Invalid email format")
        return v


class UpdateUserAdminRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=128)
    email: Optional[str] = Field(None, max_length=256)
    role: Optional[str] = Field(None, pattern=r"^(user|admin|trader)$")
    api_ucc: Optional[str] = Field(None, max_length=64)
    account_balance_inr: Optional[float] = Field(None, ge=0)
    subscription_tier: Optional[str] = Field(None, pattern=r"^(FREE|PRO|ENTERPRISE)$")
    is_active: Optional[bool] = None

    @field_validator("email")
    @classmethod
    def validate_opt_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip().lower()
        email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if not re.match(email_regex, v):
            raise ValueError("Invalid email format")
        return v


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int
    skip: int
    limit: int


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


# ============================================================================
# Subscription & Payment Schemas
# ============================================================================

class SubscriptionPlanResponse(BaseModel):
    id: str
    name: str
    code: str
    description: str
    price_inr: float
    price_paise: int
    billing_cycle: str
    features: list[str]


class BuySubscriptionRequest(BaseModel):
    strategy_id: Optional[str] = None
    plan_code: Optional[str] = Field(None, description="FREE, PRO, or ENTERPRISE")
    billing_cycle: str = Field("monthly", pattern=r"^(monthly|annual)$")
    payment_method: str = Field("WALLET", pattern=r"^(WALLET|UPI|CREDIT_CARD|NET_BANKING)$")
    payment_reference: Optional[str] = None


class BuySubscriptionResponse(BaseModel):
    subscription_id: int
    status: str
    plan_tier: str
    strategy_id: Optional[str]
    amount_paid_inr: float
    subscribed_at: str
    expires_at: Optional[str]
    payment_reference: str
    remaining_balance_inr: float
    message: str


class CancelSubscriptionRequest(BaseModel):
    subscription_id: int


class WalletTopUpRequest(BaseModel):
    amount_inr: float = Field(..., ge=100.0, le=1000000.0)
    payment_method: str = Field("UPI", pattern=r"^(UPI|CREDIT_CARD|NET_BANKING)$")
    payment_reference: Optional[str] = None


class PaymentTransactionResponse(BaseModel):
    id: str
    user_id: str
    amount_inr: float
    payment_method: str
    status: str
    transaction_type: str
    reference_id: str
    remarks: str
    created_at: str
