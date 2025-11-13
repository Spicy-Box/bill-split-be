# Divvy App - Backend

Đây là backend của dự án "Divvy App" (ứng dụng chia hoá đơn) viết bằng FastAPI.

## Tổng quan
- Framework: `FastAPI`
- Entrypoint: `app/main.py`
- Router chính: `app/controllers/users_router.py`
- Mục đích: API để quản lý người dùng, xác thực (JWT) và các chức năng liên quan đến chia hoá đơn.

## Yêu cầu
- Python 3.11+ (hoặc 3.10+ nếu tương thích)
- Các phụ thuộc có trong `requirements.txt`

## Cài đặt nhanh
1. Tạo virtual environment và kích hoạt:
   - macOS / Linux (zsh):
     ```bash
     python -m venv .venv
     source .venv/bin/activate
     ```
2. Cài đặt phụ thuộc:
   ```bash
   pip install -r requirements.txt
   ```

## Cấu hình
- Xem `configs/config.py` để biết các biến cấu hình (nếu có).
- Nếu dự án sử dụng biến môi trường (ví dụ cho JWT, DB), hãy export trước khi chạy.

## Chạy ứng dụng
- Khởi động server phát triển:
  ```bash
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
  ```
- OpenAPI / Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Xác thực
- Ứng dụng có cơ chế JWT (xem `app/utils/auth.py`).
- Để lấy token, gọi endpoint login có trong `app/controllers/users_router.py` (thường là `/users/login`).
- Trong Swagger UI bạn có thể nhấn nút "Authorize" và nhập `Bearer <token>` hoặc chỉ `<token>` phụ thuộc vào cấu hình trong `app/main.py`.

## CORS
- CORS được bật trong `app/main.py` với `allow_origins = ["*"]` (đang cho phép tất cả). Điều này giúp frontend truy cập API trong giai đoạn phát triển.

## Cấu trúc thư mục chính
- `app/` - mã nguồn backend
  - `controllers/` - định nghĩa route/endpoint (ví dụ: `users_router.py`)
  - `models/` - model dữ liệu
  - `dto/` - data transfer objects / schemas
  - `db/` - khởi tạo kết nối CSDL, lifespan
  - `services/` - các service phụ trợ (ví dụ `gmail.py`)
  - `utils/` - helper (ví dụ `auth.py`)
  - `main.py` - ứng dụng FastAPI và cấu hình OpenAPI/CORS

## Kiểm thử
- Chạy test với pytest:
  ```bash
  pytest -q
  ```
  Test mẫu có trong `tests/test_users_router.py`.

## Docker
- Project có `Dockerfile`. Bạn có thể build image và chạy container nếu muốn triển khai via Docker.

## Ghi chú
- Kiểm tra `app/db/database.py` để biết cách quản lý kết nối/khởi tạo CSDL.
- Nếu cần mở rộng API, thêm router mới vào `app/main.py` bằng `app.include_router(...)`.

Nếu muốn, tôi có thể cập nhật README này theo yêu cầu cụ thể hơn (ví dụ: hướng dẫn cấu hình biến môi trường, API reference chi tiết cho từng endpoint, hoặc cách cấu hình DB).
