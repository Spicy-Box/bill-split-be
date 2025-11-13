from typing import Union
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.controllers import users_router, bills_router
from app.db.database import lifespan
from app.dto.users import UserIn
from app.models.users import User

app = FastAPI(title="Divvy App", lifespan=lifespan)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Divvy App",
        version="1.0.1",
        description="API documentation for Divvy App. To use protected endpoints:\n1. Call /users/login to get access_token\n2. Click 'Authorize' button above\n3. Enter 'Bearer {your_access_token}' or just '{your_access_token}'\n4. Now you can use protected endpoints",
        routes=app.routes,
    )
    # Override the OAuth2PasswordBearer scheme to use Bearer token
    openapi_schema["components"]["securitySchemes"] = {
        "OAuth2PasswordBearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter your JWT access_token. Get it from /users/login endpoint. Format: Bearer {token} or just {token}"
        }
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

origins = [
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users_router.router)
app.include_router(bills_router.router)
