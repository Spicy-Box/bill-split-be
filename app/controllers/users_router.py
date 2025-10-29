from typing import List
from fastapi import APIRouter

from app.dto.users import UserIn, UserOut
from app.models.users import User


router = APIRouter(prefix='/users', tags=["Users"])

@router.get("/", response_model=List[UserOut])
async def get_users_list():
  users = await User.find({}).to_list()
  return users

@router.post("/", response_model=UserOut)
async def create_user(data: UserIn):
  new_user = User(**data.model_dump())
  await new_user.insert()
  return new_user