# Divvy App - Backend

Đây là backend của dự án "Divvy App" (ứng dụng chia hoá đơn) viết bằng FastAPI.

## Tổng quan

- Framework: `FastAPI`
- Entrypoint: `app/main.py` (cấu hình FastAPI, CORS, OpenAPI, JWT)
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

- Xem `app/configs/config.py` để biết các biến cấu hình (JWT, DB, ...).
- Export biến môi trường cho JWT, DB trước khi chạy.

## Chạy ứng dụng

- Khởi động server phát triển:
  ```bash
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
  ```
- OpenAPI / Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Xác thực

- Cơ chế JWT trong `app/utils/auth.py`.
- Đăng nhập lấy token qua `/users/login` trong `app/controllers/users_router.py`.
- Swagger UI: nhấn "Authorize" và nhập `Bearer <token>` hoặc chỉ `<token>` (theo cấu hình ở `app/main.py`).

## CORS

- CORS bật trong `app/main.py` với `allow_origins = ["*"]` (cho phép tất cả origin khi phát triển).

## Cấu trúc thư mục chính

- `app/` - mã nguồn backend
  - `controllers/` - định nghĩa route/endpoint (ví dụ: `users_router.py`)
  - `models/` - model dữ liệu (ví dụ: `users.py`)
  - `dto/` - data transfer objects / schemas (ví dụ: `users.py`, `base.py`)
  - `db/` - khởi tạo kết nối CSDL, lifespan (ví dụ: `database.py`)
  - `services/` - các service phụ trợ (ví dụ: `gmail.py`)
  - `utils/` - helper (ví dụ: `auth.py`)
  - `main.py` - ứng dụng FastAPI và cấu hình OpenAPI/CORS

## Thêm endpoint mới

1. Tạo router mới trong `app/controllers/`.
2. Định nghĩa schema request/response trong `app/dto/`.
3. Logic nghiệp vụ ở `app/services/` hoặc `app/utils/` nếu cần.
4. Đăng ký router trong `app/main.py` bằng `app.include_router(...)`.

## Kiểm thử

- Chạy test với pytest:
  ```bash
  pytest -q
  ```
  Test mẫu có trong `tests/test_users_router.py`.

## Docker

- Có `Dockerfile` để build image và chạy container.

## Ghi chú

- Quản lý kết nối DB ở `app/db/database.py`.
- Mở rộng API: thêm router mới và đăng ký trong `app/main.py`.

Nếu cần hướng dẫn chi tiết hơn (ví dụ: cấu hình biến môi trường, API reference cho từng endpoint, hoặc cấu hình DB), hãy yêu cầu cập nhật README.
