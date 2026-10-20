# commands

- dev
    - uv run fastapi dev app/main.py

- db
    - create migration
        - `uv run alembic revision --autogenerate -m "describe the change"`
    - apply migration to db
        - `uv run alembic upgrade head`

- users
    - superadmin: change-me-please
    - demo.admin: demo-pass-123
    - demo.designer: demo-pass-123
    - demo.ops: demo-pass-123
    - demo.viewer: demo-pass-123