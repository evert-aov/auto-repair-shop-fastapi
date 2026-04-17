# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the development server
fastapi run app/main.py

# Install dependencies
pip install -r requirements.txt

# Database migrations
alembic upgrade head          # apply all migrations
alembic revision --autogenerate -m "description"  # generate new migration

# Seed initial data (roles, permissions, admin user)
python -m app.seed
```

Default admin credentials after seed: `admin` / `admin123`

## Environment

`.env` and `alembic.ini` both have two DATABASE_URL variants — `localhost:5432` for local dev and `db:5432` for Docker. Keep them in sync when switching environments.

Required env vars: `DATABASE_URL`, `JWT_SECRET`

## Architecture

Two-layer module structure: `app/module_users/` owns the core domain (users, roles, permissions); `app/security/` owns auth and the client subtype.

**Inheritance pattern** — `Client` extends `User` via SQLAlchemy joined-table inheritance (`type` discriminator column). `Client` lives in `app/security/models/models.py`, not in `module_users`. All files that query the `users` table polymorphically must have `Client` imported first (handled automatically at startup since `auth_controller` → `client_service` → `Client`).

**Module layout** (repeated for each module):
```
controller/   → FastAPI routers
services/     → business logic
repositories/ → SQLAlchemy queries
models/       → SQLAlchemy ORM models (__init__.py re-exports)
dtos/         → Pydantic request/response schemas
```

**Auth flow** — JWT via `python-jose`. `POST /api/auth/login` accepts `OAuth2PasswordRequestForm` (form data). `get_current_user` and `require_role(*roles)` are FastAPI dependencies in `app/security/config/security.py`.

**Cross-module imports** — `vehicle_service` (in `module_users`) imports `client_repository` from `app.security.repository` and `Vehicle`/`Client` from `app.security.models`. This is intentional: vehicles and clients are owned by the security module.

**Package `__init__.py` convention** — model packages re-export their classes (see `app/module_users/models/__init__.py`). Service and repository packages are plain (submodules are imported directly, e.g. `from app.security.service import client_service`).