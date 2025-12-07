from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from fastapi import HTTPException, status, Depends
from dotenv import load_dotenv
from app.models.users import RefreshToken
from bson import ObjectId
import random

import os

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

ACCESS_TOKEN_EXPIRE_MINUTES = 1
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def hash_password(password):
    if len(password.encode("utf-8")) > 72:
        password = password[:72]
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.now() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def create_refresh_token(data: dict):
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"sub": data["sub"], "exp": expire, "type": "refresh"}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    refresh_token_doc = RefreshToken(
        token=encoded_jwt,
        user_id=ObjectId(data["sub"]),
        expires_at=expire
    )
    await refresh_token_doc.insert()
    
    return encoded_jwt

async def verify_refresh_token(refresh_token: str):
    try:
        token_doc = await RefreshToken.find_one({
            "token": refresh_token,
            "expires_at": {"$gt": datetime.now()}
        })
        
        if not token_doc:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token. Please login again!!!")
        
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token. Please remove token and login again!!!")
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid refresh token. Please remove token and login again!!!")
        return user_id
    except Exception as e:
        raise e

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid or expired access token. Please refresh token!!!")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalid or expired. Please refresh token!!!")

async def revoke_refresh_token(refresh_token: str):
    """Xóa refresh token"""
    token_doc = await RefreshToken.find_one({"token": refresh_token})
    if token_doc:
        await token_doc.delete()

async def revoke_all_user_tokens(user_id: str):
    """Xóa tất cả refresh tokens của user"""
    await RefreshToken.find({
        "user_id": ObjectId(user_id)
    }).delete()

def generate_otp_secret():
    return random.randint(100000, 999999)