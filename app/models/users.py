from datetime import datetime, timedelta, date
from typing import Optional
from beanie import Document, PydanticObjectId
from pydantic import EmailStr, Field
from pymongo import IndexModel

class RefreshToken(Document):
    token: str = Field(..., description="JWT refresh token")
    user_id: PydanticObjectId = Field(..., description="User ID")
    expires_at: datetime = Field(..., description="Token expiration time")
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Settings:
        name = "refresh_tokens"
        indexes = [
            "token",
            "user_id",
            IndexModel([("expires_at", 1)], expireAfterSeconds=0)
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

class OtpCode(Document):
  email: EmailStr
  code: str
  created_at: datetime = Field(default_factory=datetime.utcnow)

  class Settings:
      name = "otp_codes"
      indexes = [
          IndexModel([("created_at", 1)], expireAfterSeconds=600)
      ]

