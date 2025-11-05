from typing import List
from fastapi import APIRouter, HTTPException, status, Depends

from app.dto.users import UserIn, UserOut, LoginRequest, UserUpdate
from app.models.users import User
from pwdlib import PasswordHash

from app.dto.base import ReponseWrapper

from app.utils.auth import verify_password, create_access_token, create_refresh_token, hash_password, get_current_user, verify_refresh_token, revoke_refresh_token, revoke_all_user_tokens


router = APIRouter(prefix='/users', tags=["Users"])

@router.get("/", response_model=ReponseWrapper[List[UserOut]], status_code=status.HTTP_200_OK, description="Get list of all users")
async def get_users_list():
  try:
    users = await User.find({}).to_list()
    return ReponseWrapper(message="Users retrieved successfully", data=users)
  except Exception as e:
    raise e
  
@router.get("/{user_id}", response_model=ReponseWrapper[UserOut], description="Get user by ID", status_code=status.HTTP_200_OK)
async def get_user_by_id(user_id: str):
  try:
    user = await User.get(user_id)
    if not user:
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return ReponseWrapper(message="User retrieved successfully", data=user)
  except Exception as e:
    raise e

@router.post("/", response_model=ReponseWrapper[UserOut], description="Create a new user", status_code=201)
async def create_user(data: UserIn):
  try:
    data.password = hash_password(data.password)
    checkUser = await User.find_one(User.email == data.email)
    if checkUser:
      raise HTTPException(status_code=400, detail="User with this email already exists")
    new_user = User(**data.model_dump())
    await new_user.insert()
    return ReponseWrapper(message="User created successfully", data=new_user)
  except Exception as e:
    raise e

@router.put("/{user_id}", response_model=ReponseWrapper[UserOut], description="Update user by ID", status_code=status.HTTP_200_OK)
async def update_user(user_id: str, data: UserUpdate, current_user: str = Depends(get_current_user)):
    try:
        user = await User.get(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        elif str(user.id) != current_user:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this user")

        update_data = data.model_dump(exclude_unset=True)
        if "password" in update_data:
            update_data["password"] = hash_password(update_data["password"])

        await user.set(update_data)
        return ReponseWrapper(message="User updated successfully", data=user)
    except Exception as e:
        raise e


@router.delete("/{user_id}", response_model=ReponseWrapper[UserOut], description="Delete user by ID", status_code=status.HTTP_200_OK)
async def delete_user(user_id: str, current_user: str = Depends(get_current_user)):
  try:
    user = await User.get(user_id)
    if not user:
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    elif str(user.id) != current_user:
      raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this user")
    await user.delete()
    return ReponseWrapper(message="User deleted successfully", data=user)
  except Exception as e:
    raise e
  
@router.post("/login", response_model=ReponseWrapper[dict], description="User login", status_code=status.HTTP_200_OK)
async def login_user(data:LoginRequest):
  try:
    user = await User.find_one(User.email == data.email)
    if not user or not verify_password(data.password, user.password):
      raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = await create_refresh_token(data={"sub": str(user.id)})
    
    return ReponseWrapper(message="Login successful", data={
      "access_token": access_token,
      "refresh_token": refresh_token,
      "token_type": "bearer"
    })
  except Exception as e:
    raise e
  
@router.post("/refresh", response_model=ReponseWrapper[dict], description="Refresh access token", status_code=status.HTTP_200_OK)
async def refresh_access_token(refresh_token: str):
  try:
    user_id = await verify_refresh_token(refresh_token=refresh_token)
    access_token = create_access_token(data={"sub": user_id})  
    return ReponseWrapper(message="Access token refreshed successfully", data={
      "access_token": access_token,
      "token_type": "bearer"
    })
  except Exception as e:
    raise e
  
@router.get("/current/me", response_model=ReponseWrapper[UserOut], description="Get current user", status_code=status.HTTP_200_OK)
async def get_current_user_info(current_user: str = Depends(get_current_user)):
  try:
    user = await User.get(current_user)
    if not user:
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return ReponseWrapper(message="Current user retrieved successfully", data=user)
  except Exception as e:
    raise e
  
@router.post("/logout", response_model=ReponseWrapper[dict], description="User logout", status_code=status.HTTP_200_OK)
async def logout_user(refresh_token: str, current_user: str = Depends(get_current_user)):
  try:
    await revoke_refresh_token(refresh_token)
    return ReponseWrapper(message="Logout successful", data={})
  except Exception as e:
    raise e

@router.post("/logout-all", response_model=ReponseWrapper[dict], description="Logout from all devices", status_code=status.HTTP_200_OK)
async def logout_all_devices(current_user: str = Depends(get_current_user)):
  try:
    await revoke_all_user_tokens(current_user)
    return ReponseWrapper(message="Logged out from all devices successfully", data={})
  except Exception as e:
    raise e