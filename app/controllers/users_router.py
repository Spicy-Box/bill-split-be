from typing import List
from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from datetime import datetime

from app.dto.users import LoginResponse, UserIn, UserOut, LoginRequest, UserUpdate, ForgotPasswordRequest, ResetPasswordRequest, TokenResponse, VerifyOtpRequest, ChangePasswordRequest
from app.models.users import User, OtpCode
from pwdlib import PasswordHash

from app.dto.base import ReponseWrapper
from app.services.gmail import send_email_background

from app.utils.auth import verify_password, create_access_token, create_refresh_token, hash_password, get_current_user, verify_refresh_token, revoke_refresh_token, revoke_all_user_tokens, generate_otp_secret


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

@router.post("/create-user", response_model=ReponseWrapper[UserOut], description="Signup", status_code=201)
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

@router.put("/update-user", response_model=ReponseWrapper[UserOut], description="Update user by ID", status_code=status.HTTP_200_OK)
async def update_user(data: UserUpdate, current_user: str = Depends(get_current_user)):
    try:
        user = await User.get(current_user)
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
async def delete_user(user_id: str):
  try:
    user = await User.get(user_id)
    if not user:
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await user.delete()
    return ReponseWrapper(message="User deleted successfully", data=user)
  except Exception as e:
    raise e
  
@router.post("/login", response_model=ReponseWrapper[LoginResponse], description="User login", status_code=status.HTTP_200_OK)
async def login_user(data:LoginRequest):
  try:
    user: User = await User.find_one(User.email == data.email)
    if not user or not verify_password(data.password, user.password):
      raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = await create_refresh_token(data={"sub": str(user.id)})
    
    return ReponseWrapper(message="Login successful", data=LoginResponse(
      id=user.id,
      email=user.email,
      first_name=user.first_name,
      last_name=user.last_name,
      phone=user.phone,
      dob=user.dob,
      access_token=access_token,
      refresh_token=refresh_token
      ))
  except Exception as e:
    raise e
  
@router.post("/refresh", response_model=ReponseWrapper[TokenResponse], description="Refresh access token", status_code=status.HTTP_200_OK)
async def refresh_access_token(refresh_token: str):
  try:
    user_id = await verify_refresh_token(refresh_token=refresh_token)
    access_token = create_access_token(data={"sub": user_id})  
    return ReponseWrapper(message="Access token refreshed successfully", data=TokenResponse(
      access_token=access_token,
      refresh_token=refresh_token,
      token_type="bearer"
      ))
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

@router.post("/forgot-password", response_model=ReponseWrapper[dict], status_code=status.HTTP_200_OK)
async def forgot_password(data: ForgotPasswordRequest, background_tasks: BackgroundTasks):
    email = data.email
    user = await User.find_one(User.email == str(email))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User with this email does not exist")
    
    otp_code = generate_otp_secret()
    check_otp_code = await OtpCode.find_one(OtpCode.email == email)
    if check_otp_code:
      raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Please don't spam the email") 
    new_otp_code = OtpCode(
        email=email,
        code=str(otp_code)
    )
    await new_otp_code.insert()

    background_tasks.add_task(
      send_email_background,
      email_to=email,
      subject="🔐 Password Reset OTP Code",
      body=f"""
      <html>
        <body style="font-family: Arial, sans-serif; background-color: #f9f9f9; padding: 20px;">
          <div style="max-width: 500px; margin: auto; background: white; border-radius: 10px; padding: 25px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
            <h2 style="color: #2c3e50; text-align: center;">Password Reset Request</h2>
            <p style="font-size: 15px; color: #333;">
              Hello 👋,<br><br>
              You recently requested to reset your password. Use the OTP code below to complete the process:
            </p>
            <div style="text-align: center; margin: 25px 0;">
              <span style="display: inline-block; background: #3498db; color: white; font-size: 22px; font-weight: bold; letter-spacing: 3px; padding: 12px 25px; border-radius: 8px;">
                {otp_code}
              </span>
            </div>
            <p style="font-size: 14px; color: #555;">
              This code will expire in <b>10 minute</b>.  
              If you didn’t request this, you can safely ignore this email.
            </p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
            <p style="font-size: 12px; color: #888; text-align: center;">
              © {datetime.now} SpicyBox Team — All rights reserved.
            </p>
          </div>
        </body>
      </html>
      """
    )
    return ReponseWrapper(message="OTP code sent to email successfully", data={})

@router.post("/verify-otp", response_model=ReponseWrapper[TokenResponse], status_code=status.HTTP_200_OK, description="Verify OTP code and return access token")
async def verify_otp(data: VerifyOtpRequest):
  """
  Verify OTP code sent to email. If valid, returns access_token and refresh_token.
  """
  try:
    email = data.email
    code = data.code
    
    otp_record = await OtpCode.find_one(OtpCode.email == email)
    if not otp_record or otp_record.code != code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP code")
    
    user = await User.find_one(User.email == email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User with this email does not exist")
    
    # Delete OTP after successful verification
    await otp_record.delete()
    
    # Generate tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = await create_refresh_token(data={"sub": str(user.id)})
    
    return ReponseWrapper(message="OTP verified successfully", data=TokenResponse(
      access_token=access_token,
      refresh_token=refresh_token,
      token_type="bearer"
    ))
  except Exception as e:
    raise e

@router.post("/change-password", response_model=ReponseWrapper[dict], status_code=status.HTTP_200_OK, description="Change password using access token")
async def change_password(data: ChangePasswordRequest, current_user: str = Depends(get_current_user)):
  """
  Change user password. Requires valid access token in Authorization header.
  """
  try:
    user = await User.get(current_user)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Update password
    user.password = hash_password(data.new_password)
    await user.save()
    
    return ReponseWrapper(message="Password changed successfully", data={})
  except Exception as e:
    raise e

# Deprecated: Use /verify-otp and /change-password instead
# @router.post("/reset-password", response_model=ReponseWrapper[TokenResponse], status_code=status.HTTP_200_OK)
# async def reset_password(data: ResetPasswordRequest):
#   email = data.email
#   code = data.code
#   new_password = data.new_password
#   try:
#     otp_record = await OtpCode.find_one(OtpCode.email == email)
#     if not otp_record or otp_record.code != code:
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP code")
#     user = await User.find_one(User.email == email)
#     if not user:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User with this email does not exist")
#     user.password = hash_password(new_password)
#     await user.save()
#     await otp_record.delete()
#     access_token = create_access_token(data={"sub": str(user.id)})
#     refresh_token = await create_refresh_token(data={"sub": str(user.id)})
#     return ReponseWrapper(message="Change password and login successful", data=TokenResponse(
#       access_token=access_token,
#       refresh_token=refresh_token,
#       token_type="bearer"
#       ))
#   except Exception as e:
#     raise e

