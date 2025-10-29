from datetime import date
from pydantic import BaseModel, EmailStr, Field
from beanie import PydanticObjectId

class UserIn(BaseModel):
  first_name: str
  last_name: str
  email: EmailStr
  phone: str = Field(min_length=10, max_length=11)
  password: str
  dob: date
  
class UserOut(BaseModel):
  id: PydanticObjectId
  first_name: str
  last_name: str
  email: EmailStr
  phone: str = Field(min_length=10, max_length=11)
  dob: date