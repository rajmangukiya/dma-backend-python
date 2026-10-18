# commands

- dev
    - uv run fastapi dev app/main.py

- db
    - create migration
        - `uv run alembic revision --autogenerate -m "describe the change"`
    - apply migration to db
        - `uv run alembic upgrade head`
