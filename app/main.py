from typing import Union
from fastapi import FastAPI

from app.controllers import users_router 
from app.db.database import lifespan
from app.dto.users import UserIn
from app.models.users import User

app = FastAPI(title="Divvy App", lifespan=lifespan)

app.include_router(users_router.router)
