# Copilot Instructions for Divvy App Backend

## Project Overview

- **Framework:** FastAPI
- **Entrypoint:** `app/main.py` (configures FastAPI, CORS, OpenAPI, JWT security)
- **Main Router:** `app/controllers/users_router.py`
- **Purpose:** User management, JWT authentication, bill splitting features.

## Architecture & Patterns

- **Routers:** All API endpoints are defined in `app/controllers/`. Add new routers and include them in `app/main.py` using `app.include_router(...)`.
- **Models:** Data models are in `app/models/`.
- **DTOs/Schemas:** Request/response schemas in `app/dto/`.
- **Database:** Connection and lifespan logic in `app/db/database.py`.
- **Services:** Auxiliary logic (e.g., email) in `app/services/`.
- **Utils:** Helpers (e.g., JWT auth) in `app/utils/`.

## Developer Workflows

- **Install dependencies:**
  ```bash
  pip install -r requirements.txt
  ```
- **Run development server:**
  ```bash
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
  ```
- **Run tests:**
  ```bash
  pytest -q
  ```
- **Swagger UI:**
  - Docs at `http://localhost:8000/docs` (JWT auth via "Authorize" button)

## Conventions & Integration

- **CORS:** Configured to allow all origins for development (`app/main.py`).
- **JWT Auth:**
  - Token issued via `/users/login` (see `users_router.py`).
  - Auth logic in `app/utils/auth.py`.
  - OpenAPI security scheme customized in `app/main.py`.
- **Docker:**
  - Build and run using provided `Dockerfile`.
- **Config:**
  - App config in `app/configs/config.py`.
  - Set environment variables for secrets (JWT, DB) before running.

## Example: Adding a New Endpoint

1. Create a new router in `app/controllers/`.
2. Define request/response schemas in `app/dto/`.
3. Add business logic in `app/services/` or `app/utils/` as needed.
4. Register the router in `app/main.py`.

## Key Files

- `app/main.py`: App setup, OpenAPI, CORS, router registration
- `app/controllers/users_router.py`: User endpoints
- `app/utils/auth.py`: JWT logic
- `app/db/database.py`: DB connection/lifespan
- `tests/`: Pytest-based tests

---

**Instruction:**
- Whenever you make any code change in the `./app` directory, always update `README.md` to reflect the change.
- Use a diff tool to detect changes since the last commit in the codebase and ensure those changes are reflected in `README.md`.

If any section is unclear or missing, please specify what needs improvement or additional detail.
