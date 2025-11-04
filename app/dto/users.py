from datetime import date
from pydantic import BaseModel, EmailStr, Field
from beanie import PydanticObjectId

class UserIn(BaseModel):
  first_name: str = Field(..., examples=["Lo"])
  last_name: str = Field(..., examples=["Vuong"])
  email: EmailStr = Field(..., examples=["lodaide@gmail.com"])
  phone: str = Field(min_length=10, max_length=11, examples=["0696969696"])
  password: str = Field(..., examples=["lovuongdaide123"])
  dob: date = Field(..., examples=["1969-06-09"])
  
class UserOut(BaseModel):
  id: PydanticObjectId
  first_name: str = Field(..., examples=["Lo"])
  last_name: str = Field(..., examples=["Vuong"])
  email: EmailStr = Field(..., examples=["lodaide@gmail.com"])
  phone: str = Field(min_length=10, max_length=11, examples=["0696969696"])
  dob: date = Field(..., examples=["1969-06-09"])

class LoginRequest(BaseModel):
  email: EmailStr = Field(..., examples=["lodaide@gmail.com"])
  password: str = Field(..., examples=["lovuongdaide123"])