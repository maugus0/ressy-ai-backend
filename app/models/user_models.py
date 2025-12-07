from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, model_validator


def validate_password_strength(password: str) -> str:
    """Enforce strong password policy."""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not any(c.isupper() for c in password):
        raise ValueError("Password must include an uppercase letter")
    if not any(c.islower() for c in password):
        raise ValueError("Password must include a lowercase letter")
    if not any(c.isdigit() for c in password):
        raise ValueError("Password must include a number")
    return password


def _require_non_empty(value: str | None, field_name: str) -> str:
    if value is None:
        raise ValueError(f"{field_name} cannot be empty")
    cleaned = str(value).strip()
    if not cleaned:
        raise ValueError(f"{field_name} cannot be empty")
    return cleaned


class BaseUserCreateRequest(BaseModel):
    email: EmailStr
    password: str
    role_id: int
    model_config = ConfigDict(extra="ignore")

    @field_validator("password")
    def password_complexity(cls, value: str):
        return validate_password_strength(value)

    @field_validator("email")
    def normalize_email(cls, value: EmailStr):
        return value.lower()


class BaseUserUpdateRequest(BaseModel):
    email: EmailStr | None = None
    password: str | None = None
    role_id: int | None = None
    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="after")
    def at_least_one_field(self):
        if self.email is None and self.password is None and self.role_id is None:
            raise ValueError("At least one of email, password, or role_id must be provided")
        if self.password is not None:
            self.password = validate_password_strength(self.password)
        if self.email is not None:
            self.email = self.email.lower()
        return self


class BasePasswordResetRequest(BaseModel):
    new_password: str
    model_config = ConfigDict(extra="ignore")

    @field_validator("new_password")
    def password_complexity(cls, value: str):
        return validate_password_strength(value)


class BaseRoleUpdateRequest(BaseModel):
    role_id: int
    model_config = ConfigDict(extra="ignore")


class BaseBulkCreateRequest(BaseModel):
    users: list[BaseUserCreateRequest]
    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="after")
    def non_empty(self):
        if not self.users:
            raise ValueError("users list cannot be empty")
        return self
