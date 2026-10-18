# DMA backend (Python)

Python rewrite of `dma-backend`. Stack: see [tech-stack.md](tech-stack.md).

## Commands

| Task | Command | Node equivalent |
| --- | --- | --- |
| Install / sync dependencies | `uv sync` | `npm install` |
| Add a dependency | `uv add <pkg>` (dev: `uv add --dev <pkg>`) | `npm i <pkg>` / `npm i -D` |
| Run the dev server (auto-reload) | `uv run fastapi dev app/main.py` | `npm run dev` |
| Run tests | `uv run pytest` | `npm test` |
| Lint | `uv run ruff check .` (auto-fix: `--fix`) | `eslint` |
| Format | `uv run ruff format .` | `prettier --write` |
| Create a migration from model changes | `uv run alembic revision --autogenerate -m "add users"` | `typeorm migration:generate` |
| Apply migrations | `uv run alembic upgrade head` | `typeorm migration:run` |
| Undo the last migration | `uv run alembic downgrade -1` | `typeorm migration:revert` |
| Show current / history | `uv run alembic current` · `uv run alembic history` | — |

- API: http://localhost:8000/api/health
- Interactive docs (generated from the code): http://localhost:8000/docs

## Layout

```
pyproject.toml        # package.json: dependencies + tool config (Ruff, pytest)
uv.lock               # package-lock.json — commit it
.python-version       # pins Python 3.13 (like .nvmrc)
.env / .env.example   # configuration (.env is gitignored)
alembic.ini           # Alembic settings (file naming, Ruff hooks); DB URL comes from .env
migrations/
  env.py              # connects Alembic to app settings + Base.metadata
  script.py.mako      # template for new migration files
  versions/           # the migration files themselves
app/
  main.py             # creates the app: CORS, error handlers, mounts the API under /api
  core/
    config.py         # Settings read from .env (pydantic-settings)
    errors.py         # AppError + handlers returning { success: false, message, details }
  db/
    base.py           # Base class, timestamp mixins, pg_enum helper, constraint naming
    session.py        # async engine, session factory, get_db dependency
    models/           # one module per area; __init__.py re-exports every model
      enums.py        # UserRole, FieldType, DocumentStatus
      company.py      # companies
      user.py         # users
      template.py     # document_templates, _fields, _field_matches (skeletons)
      journey.py      # journeys, segments
      document.py     # documents, document_fields, _match_rules, _values, uploaded_files
  schemas/
    common.py         # ApiResponse[T] envelope { success, message, data } + ok() helper
  api/
    router.py         # collects every feature router
    routes/
      health.py       # GET /api/health (also checks the database)
tests/
  test_health.py
  test_errors.py      # error shapes: validation 400, AppError, 404, 500
```

Every folder with Python files has an `__init__.py`, which marks it as a package so it can be imported (`from app.core.config import ...`).

## Phase 0 — what to look up

- **uv**: projects, `uv sync`, `uv run`, dependency groups, `uv python install`
- **Virtual environments**: why Python isolates packages per project (`.venv`)
- **`pyproject.toml`**: PEP 621 metadata; why `[tool.uv] package = false` for an app
- **Packages and imports**: `__init__.py`, absolute imports (`from app.main import app`)
- **Type hints**: `def health() -> dict:`; how they compare to TypeScript (checked by tools, not at runtime)
- **FastAPI basics**: path operation decorators (`@app.get`), sync `def` vs `async def` routes, automatic OpenAPI docs
- **ASGI and Uvicorn**: what `fastapi dev` runs under the hood (Express's `app.listen` equivalent)
- **pytest**: plain `assert`, test discovery, `TestClient`
- **Ruff**: the rule sets enabled in `pyproject.toml` (E, F, I, UP, B)

## FastAPI foundation — what to look up

- **APIRouter** and `include_router(prefix=...)`: splitting routes across files (Express `Router()` + `app.use('/api', router)`)
- **Pydantic `BaseModel`**: validation and serialization; `model_dump()`
- **Generics in Python 3.12+**: `class ApiResponse[T](BaseModel)`, `def ok[T](...)`
- **Response models**: how the return annotation (`-> ApiResponse[HealthData]`) validates output and documents it in `/docs`
- **Exception handlers**: `@app.exception_handler`, `RequestValidationError`, `HTTPException`; why FastAPI defaults to 422 and we return 400
- **pydantic-settings**: `BaseSettings`, env var mapping, `.env` loading
- **`functools.lru_cache`**: why `get_settings()` is cached (and how tests can override it later)
- **Middleware**: `CORSMiddleware`, `allow_credentials` with cookies
- **`async def` vs `def` routes**: FastAPI runs plain `def` routes in a thread pool
- **pytest**: building a throwaway app inside a test; `TestClient(raise_server_exceptions=False)`

## Database setup — what to look up

- **SQLAlchemy 2.0 overview**: Engine, Connection, Session; ORM vs Core
- **Async SQLAlchemy**: `create_async_engine`, `AsyncSession`, `async_sessionmaker`; why lazy loading doesn't work and what `selectinload` does
- **Database URLs and drivers**: `postgresql+asyncpg://...` (dialect + driver); asyncpg vs psycopg 3
- **Connection pooling**: what `pool_pre_ping` does; why one engine per process
- **`expire_on_commit=False`**: what "expired" attributes are
- **FastAPI dependencies with `yield`**: `get_db` opens a session per request and closes it afterwards
- **`Annotated[AsyncSession, Depends(get_db)]`**: the modern way to declare dependencies
- **Lifespan events**: `@asynccontextmanager` + `yield` for startup/shutdown
- **Alembic**: revisions, `upgrade head`, `downgrade`, autogenerate and its limits (always review generated migrations)
- **Constraint naming conventions**: why Alembic needs predictable names
- **`dependency_overrides`**: replacing dependencies in tests

## Models — what to look up

- **Declarative mapping (2.0 style)**: `Mapped[...]` + `mapped_column(...)`; nullability comes from the type (`int | None`)
- **Mixins**: sharing columns between models (`TimestampMixin`); method resolution order (why mixins come before `Base`)
- **`server_default` vs `default`**: database-side vs Python-side defaults; `onupdate`
- **`ForeignKey(..., ondelete="CASCADE" / "SET NULL")`**
- **`__table_args__`**: `UniqueConstraint`, `CheckConstraint`
- **Enums**: Python `StrEnum`; SQLAlchemy `Enum` with `values_callable` (store `"admin"`, not `"ADMIN"`)
- **Alembic autogenerate limits**: it doesn't drop PostgreSQL enum types in `downgrade()` — we added that by hand; `alembic check` to detect drift
- **`relationship()`**: not used yet; we'll add relationships when queries need them (and learn `selectinload` for async)

## Open questions for our next discussion

- Project layout: I used **by layer** (`api/routes`, `schemas`, `core`, later `models`, `services`), like FastAPI's official full-stack template. The alternative is **by feature** (`auth/`, `journeys/`, each with its own router, schemas, service). Which do you prefer after reading?
- Response envelope: kept `{ success, message, data }` so the React app works unchanged. Plain FastAPI responses (data only, errors as `{ detail }`) are more common in Python codebases — keep or drop?
# dma-backend-python
