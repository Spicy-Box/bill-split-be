import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, date
from fastapi import HTTPException, status, BackgroundTasks
from beanie import PydanticObjectId

from app.controllers.users_router import (
    create_user, login_user, forgot_password, reset_password
)
from app.dto.users import UserIn, LoginRequest, ForgotPasswordRequest, ResetPasswordRequest
from app.models.users import User, OtpCode


class TestCreateUser:

    @pytest.fixture
    def sample_user_data(self):
        return UserIn(
            first_name="John",
            last_name="Doe", 
            email="john.doe@example.com",
            phone="0123456789",
            password="password123",
            dob=date(1990, 1, 1)
        )

    @pytest.mark.asyncio
    async def test_create_user_success(self, sample_user_data):
        with patch('app.controllers.users_router.User') as mock_user_model, \
             patch('app.controllers.users_router.hash_password') as mock_hash_password:
            
            mock_hash_password.return_value = "hashed_password123"
            
            mock_user_model.find_one = AsyncMock(return_value=None)
            
            mock_user_instance = Mock()
            mock_user_instance.id = PydanticObjectId()
            mock_user_instance.insert = AsyncMock()
            mock_user_model.return_value = mock_user_instance

            result = await create_user(sample_user_data)

            assert result.message == "User created successfully"
            assert result.data == mock_user_instance
            
            mock_hash_password.assert_called_once_with("password123")
            
            mock_user_model.find_one.assert_called_once()
            
            mock_user_instance.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_email_exists(self, sample_user_data):
        with patch('app.controllers.users_router.User') as mock_user_model, \
             patch('app.controllers.users_router.hash_password') as mock_hash_password:
            
            mock_hash_password.return_value = "hashed_password123"
            
            existing_user = Mock()
            mock_user_model.find_one = AsyncMock(return_value=existing_user)

            with pytest.raises(HTTPException) as exc_info:
                await create_user(sample_user_data)

            assert exc_info.value.status_code == 400
            assert "already exists" in exc_info.value.detail
            
            mock_hash_password.assert_called_once_with("password123")


class TestLoginUser:

    @pytest.fixture
    def login_data(self):
        return LoginRequest(
            email="john.doe@example.com",
            password="password123"
        )

    @pytest.mark.asyncio
    async def test_login_success(self, login_data):
        with patch('app.controllers.users_router.User') as mock_user_model, \
             patch('app.controllers.users_router.verify_password') as mock_verify_password, \
             patch('app.controllers.users_router.create_access_token') as mock_access_token, \
             patch('app.controllers.users_router.create_refresh_token') as mock_refresh_token:
            
            mock_user = Mock()
            mock_user.id = PydanticObjectId()
            mock_user.password = "hashed_password"
            mock_user_model.find_one = AsyncMock(return_value=mock_user)
            
            mock_verify_password.return_value = True
            
            mock_access_token.return_value = "access_token_123"
            mock_refresh_token.return_value = "refresh_token_123"

            result = await login_user(login_data)

            assert result.message == "Login successful"
            assert result.data["access_token"] == "access_token_123" 
            assert result.data["refresh_token"] == "refresh_token_123"
            assert result.data["token_type"] == "bearer"

            mock_user_model.find_one.assert_called_once()
            
            mock_verify_password.assert_called_once_with("password123", "hashed_password")
            
            mock_access_token.assert_called_once()
            mock_refresh_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_login_user_not_found(self, login_data):
        with patch('app.controllers.users_router.User') as mock_user_model:
            
            mock_user_model.find_one = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc_info:
                await login_user(login_data)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Invalid email or password" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, login_data):
        with patch('app.controllers.users_router.User') as mock_user_model, \
             patch('app.controllers.users_router.verify_password') as mock_verify_password:
            
            mock_user = Mock()
            mock_user.password = "hashed_password"
            mock_user_model.find_one = AsyncMock(return_value=mock_user)
            
            mock_verify_password.return_value = False

            with pytest.raises(HTTPException) as exc_info:
                await login_user(login_data)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Invalid email or password" in exc_info.value.detail


class TestForgotPassword:

    @pytest.fixture
    def forgot_password_data(self):
        return ForgotPasswordRequest(email="john.doe@example.com")

    @pytest.fixture
    def mock_background_tasks(self):
        return Mock(spec=BackgroundTasks)

    @pytest.mark.asyncio
    async def test_forgot_password_success(self, forgot_password_data, mock_background_tasks):
        with patch('app.controllers.users_router.User') as mock_user_model, \
             patch('app.controllers.users_router.OtpCode') as mock_otp_model, \
             patch('app.controllers.users_router.generate_otp_secret') as mock_generate_otp:
            
            mock_user = Mock()
            mock_user_model.find_one = AsyncMock(return_value=mock_user)
            
            mock_otp_model.find_one = AsyncMock(return_value=None)
            
            mock_generate_otp.return_value = 123456
            
            mock_otp_instance = Mock()
            mock_otp_instance.insert = AsyncMock()
            mock_otp_model.return_value = mock_otp_instance

            result = await forgot_password(forgot_password_data, mock_background_tasks)

            assert result.message == "OTP code sent to email successfully"
            assert result.data == {}

            mock_user_model.find_one.assert_called_once()
            
            mock_generate_otp.assert_called_once()
            
            mock_otp_instance.insert.assert_called_once()
            
            mock_background_tasks.add_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_forgot_password_user_not_found(self, forgot_password_data, mock_background_tasks):
        """Test forgot password với user không tồn tại"""
        with patch('app.controllers.users_router.User') as mock_user_model:
            
            mock_user_model.find_one = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc_info:
                await forgot_password(forgot_password_data, mock_background_tasks)

            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
            assert "does not exist" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_forgot_password_otp_spam_protection(self, forgot_password_data, mock_background_tasks):
        """Test forgot password với OTP spam protection"""
        with patch('app.controllers.users_router.User') as mock_user_model, \
             patch('app.controllers.users_router.OtpCode') as mock_otp_model:
            
            mock_user = Mock()
            mock_user_model.find_one = AsyncMock(return_value=mock_user)
            
            existing_otp = Mock()
            mock_otp_model.find_one = AsyncMock(return_value=existing_otp)

            with pytest.raises(HTTPException) as exc_info:
                await forgot_password(forgot_password_data, mock_background_tasks)

            assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
            assert "spam" in exc_info.value.detail


class TestResetPassword:

    @pytest.fixture
    def reset_password_data(self):
        return ResetPasswordRequest(
            email="john.doe@example.com",
            code="123456",
            new_password="newpassword123"
        )

    @pytest.mark.asyncio
    async def test_reset_password_success(self, reset_password_data):
        with patch('app.controllers.users_router.User') as mock_user_model, \
             patch('app.controllers.users_router.OtpCode') as mock_otp_model, \
             patch('app.controllers.users_router.hash_password') as mock_hash_password, \
             patch('app.controllers.users_router.create_access_token') as mock_access_token, \
             patch('app.controllers.users_router.create_refresh_token') as mock_refresh_token:
            
            mock_otp = Mock()
            mock_otp.code = "123456"
            mock_otp.delete = AsyncMock()
            mock_otp_model.find_one = AsyncMock(return_value=mock_otp)
            
            mock_user = Mock()
            mock_user.id = PydanticObjectId()
            mock_user.save = AsyncMock()
            mock_user_model.find_one = AsyncMock(return_value=mock_user)
            
            mock_hash_password.return_value = "hashed_new_password"
            
            mock_access_token.return_value = "new_access_token"
            mock_refresh_token.return_value = "new_refresh_token"

            result = await reset_password(reset_password_data)

            assert result.message == "Change password and login successful"
            assert result.data["access_token"] == "new_access_token"
            assert result.data["refresh_token"] == "new_refresh_token"
            assert result.data["token_type"] == "bearer"

            mock_otp_model.find_one.assert_called_once()

            mock_user_model.find_one.assert_called_once()

            mock_hash_password.assert_called_once_with("newpassword123")

            assert mock_user.password == "hashed_new_password"
            mock_user.save.assert_called_once()

            mock_otp.delete.assert_called_once()

            mock_access_token.assert_called_once()
            mock_refresh_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_reset_password_invalid_otp(self, reset_password_data):
        with patch('app.controllers.users_router.OtpCode') as mock_otp_model:

            mock_otp_model.find_one = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc_info:
                await reset_password(reset_password_data)

            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "Invalid or expired OTP" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_reset_password_wrong_otp_code(self, reset_password_data):
        with patch('app.controllers.users_router.OtpCode') as mock_otp_model:

            mock_otp = Mock()
            mock_otp.code = "654321"
            mock_otp_model.find_one = AsyncMock(return_value=mock_otp)

            with pytest.raises(HTTPException) as exc_info:
                await reset_password(reset_password_data)

            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "Invalid or expired OTP" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_reset_password_user_not_found(self, reset_password_data):
        with patch('app.controllers.users_router.User') as mock_user_model, \
             patch('app.controllers.users_router.OtpCode') as mock_otp_model:

            mock_otp = Mock()
            mock_otp.code = "123456"
            mock_otp_model.find_one = AsyncMock(return_value=mock_otp)

            mock_user_model.find_one = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc_info:
                await reset_password(reset_password_data)

            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
            assert "does not exist" in exc_info.value.detail