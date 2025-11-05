from datetime import date
import datetime
from typing import Optional
from beanie import Document, PydanticObjectId
from pydantic import ConfigDict, EmailStr, Field


class RefreshToken(Document):
    token: str = Field(..., description="JWT refresh token")
    user_id: PydanticObjectId = Field(..., description="User ID")
    expires_at: datetime.datetime = Field(..., description="Token expiration time")
    is_active: bool = Field(default=True, description="Token status")
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    
    class Settings:
        name = "refresh_tokens"
        indexes = [
            "token",
            "user_id", 
            "is_active",
            [("user_id", 1), ("is_active", 1)]
        ]

class User(Document):
  email: EmailStr
  first_name: str
  last_name: str
  phone: Optional[str] = Field(default=None, max_length=11)
  dob: date
  password: str
  
  class Settings:
    name = "users"