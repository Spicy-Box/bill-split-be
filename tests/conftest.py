import pytest
from unittest.mock import Mock
from fastapi import BackgroundTasks
from beanie import PydanticObjectId
from datetime import date

from app.dto.users import UserIn, LoginRequest, ForgotPasswordRequest, ResetPasswordRequest


@pytest.fixture
def sample_user_data():
    return UserIn(
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        phone="0123456789",
        password="password123",
        dob=date(1990, 1, 1)
    )


@pytest.fixture
def sample_login_data():
    return LoginRequest(
        email="john.doe@example.com",
        password="password123"
    )


@pytest.fixture
def sample_forgot_password_data():
    return ForgotPasswordRequest(email="john.doe@example.com")


@pytest.fixture
def sample_reset_password_data():
    return ResetPasswordRequest(
        email="john.doe@example.com",
        code="123456",
        new_password="newpassword123"
    )


@pytest.fixture
def mock_background_tasks():
    return Mock(spec=BackgroundTasks)


@pytest.fixture
def sample_object_id():
    return PydanticObjectId()