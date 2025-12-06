from datetime import date
from pydantic import BaseModel, EmailStr, Field
from beanie import PydanticObjectId
from typing import Optional

class UserIn(BaseModel):
  first_name: str = Field(..., examples=["Nguyen"])
  last_name: str = Field(..., examples=["An"])
  email: EmailStr = Field(..., examples=["nguyen.an@example.com"])
  phone: str = Field(min_length=10, max_length=11, examples=["0901234567"])
  password: str = Field(..., examples=["NguyenAn@123"])
  dob: date = Field(..., examples=["1990-01-15"])
  
class UserOut(BaseModel):
  id: PydanticObjectId
  first_name: str = Field(..., examples=["Nguyen"])
  last_name: str = Field(..., examples=["An"])
  email: EmailStr = Field(..., examples=["nguyen.an@example.com"])
  phone: str = Field(min_length=10, max_length=11, examples=["0901234567"])
  dob: date = Field(..., examples=["1990-01-15"])

class LoginRequest(BaseModel):
  email: EmailStr = Field(..., examples=["nguyen.an@example.com"])
  password: str = Field(..., examples=["NguyenAn@123"])
  
class UserUpdate(BaseModel):
  first_name: Optional[str] = Field(None, examples=["Nguyen"])
  last_name: Optional[str] = Field(None, examples=["An"])
  email: Optional[EmailStr] = Field(None, examples=["nguyen.an@example.com"])
  phone: Optional[str] = Field(None, min_length=10, max_length=11, examples=["0901234567"])
  password: Optional[str] = Field(None, examples=["NguyenAn@123"])
  dob: Optional[date] = Field(None, examples=["1990-01-15"])

class OtpCode(BaseModel):
  email: EmailStr = Field(..., examples=["nguyen.an@example.com"])
  code : str = Field(..., examples=["654321"])
  create_at: date = Field(..., examples=["2025-12-31"])

class ForgotPasswordRequest(BaseModel):
  email: EmailStr

class ResetPasswordRequest(BaseModel):
  email: EmailStr
  code: str
  new_password: str
    
class LoginResponse(BaseModel):
  id: PydanticObjectId
  email: EmailStr
  first_name: str
  last_name: str
  phone: str
  dob: date
  access_token: str
  refresh_token: str

class TokenResponse(BaseModel):
  access_token: str
  refresh_token: str
  token_type: str
