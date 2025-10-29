from datetime import date
import datetime
from typing import Optional
from beanie import Document
from bson import ObjectId
from pydantic import ConfigDict, EmailStr, Field


class User(Document):
  email: EmailStr
  first_name: str
  last_name: str
  phone: str = Field(None, max_length=11)
  dob: date
  password: str
  
  class Settings:
    name = "users"