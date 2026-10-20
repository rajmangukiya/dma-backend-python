# DMA backend (Python)

Python rewrite of `dma-backend`. Stack: see [tech-stack.md](tech-stack.md).

## Commands

| Task | Command | Node equivalent |
| --- | --- | --- |
| Install / sync dependencies | `uv sync` | `npm install` |
| Add a dependency | `uv add <pkg>` (dev: `uv add --dev <pkg>`) | `npm i <pkg>` / `npm i -D` |
| Run the dev server (auto-reload) | `uv run fastapi dev src/main.py` | `npm run dev` |
| Run tests | `uv run pytest` | `npm test` |
| Lint | `uv run ruff check .` (auto-fix: `--fix`) | `eslint` |
| Format | `uv run ruff format .` | `prettier --write` |
| Create a migration from model changes | `uv run alembic revision --autogenerate -m "add users"` | `typeorm migration:generate` |
| Apply migrations | `uv run alembic upgrade head` | `typeorm migration:run` |
| Undo the last migration | `uv run alembic downgrade -1` | `typeorm migration:revert` |
| Show current / history | `uv run alembic current` · `uv run alembic history` | — |
| Create the super admin (from `.env`) | `uv run python -m scripts.seed_super_admin` | `npm run seed:super-admin` |
| Create the demo company + users | `uv run python -m scripts.seed_demo` | `npm run seed:demo` |

- API: http://localhost:8000/api/health
- Interactive docs (generated from the code): http://localhost:8000/docs
- Demo logins: `demo.admin`, `demo.designer`, `demo.ops`, `demo.viewer` — password `demo-pass-123`
- Tests use a separate database, `dma_py_test` (tables are rebuilt from the models on every run)

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
src/
  main.py             # creates the app: CORS, error handlers, mounts the API under /api
  router.py           # collects every module's views router
  common/             # shared, no feature logic; never imports from a module
    config.py         # Settings read from .env (pydantic-settings)
    errors.py         # AppError + handlers returning { success: false, message, details }
    schemas.py        # CamelModel, ApiResponse[T] envelope { success, message, data } + ok()
    cookies.py        # auth cookie names, paths, flags; set / clear helpers
    passwords.py      # bcrypt hash / verify
  database/
    base.py           # Base class, timestamp mixins, pg_enum helper, constraint naming
    session.py        # async engine, session factory, get_db + DbSession dependency
    models.py         # registry: imports every module's tables (for Alembic and tests)
  health/
    views.py          # GET /api/health (also checks the database)
  auth/               # owns no table
    views.py          # /api/auth endpoints — HTTP only (cookies, status, envelope)
    service.py        # login, refresh, change password, session shape
    schemas.py        # LoginRequest, ChangePasswordRequest, SessionUser
    dependencies.py   # CurrentUser, require(permission) — used by every protected module
    permissions.py    # Permission enum + role → permissions
    tokens.py         # JWT create / decode, issue_auth_cookies
  users/
    models.py         # users table
    enums.py          # UserRole
    service.py        # user reads/writes (auth uses these too)
    schemas.py        # PublicUser, Username, Password
  companies/
    models.py         # companies table
    service.py        # company reads
    schemas.py        # CompanyRef
  templates/          # models.py (3 skeleton tables), enums.py (FieldType) — API in step 3
  journeys/           # models.py (journeys, segments) — API in step 4
  documents/          # models.py (5 document tables), enums.py (DocumentStatus) — API in steps 4–5
scripts/
  seed_super_admin.py
  seed_demo.py
tests/
  conftest.py         # test database, per-test cleanup, client fixture, factories
  test_health.py
  test_errors.py      # error shapes: validation 400, AppError, 404, 500
  test_auth.py
```

Every folder with Python files has an `__init__.py`, which marks it as a package so it can be imported (`from src.common.config import ...`).

### Module rules

Conventions come from `~/Desktop/Projects/docs/backend/A-architecture.md` and `M-folder-structure.md`.

- **views.py**: HTTP only. Reads the request, checks access, loads or 404s, calls the service, returns `ok(...)`. The decorated function *is* the controller.
- **service.py**: reusable reads/writes and business rules for the module's entity. No HTTP; raises `AppError`.
- **models.py**: the module's tables. Every table has exactly one owner module.
- **schemas.py**: Pydantic request/response classes. A shape lives in the module that owns the concept (`PublicUser` → users); others import it.
- **enums.py**, **permissions.py**, **flows.py**, **`<what_it_does>.py`**: added only when needed.
- **Other modules' data**: through the owner's service, never raw queries on its tables.
- **Imports**: a module may import another module's `service`, `schemas`, `models`, `enums`, `dependencies` — never its `views`. `common/` and `database/` never import modules (except the `database/models.py` registry).
- One file per module and layer, never one per endpoint; split by sub-entity or topic when a file gets too big.

## Phase 0 — what to look up

- **uv**: projects, `uv sync`, `uv run`, dependency groups, `uv python install`
- **Virtual environments**: why Python isolates packages per project (`.venv`)
- **`pyproject.toml`**: PEP 621 metadata; why `[tool.uv] package = false` for an app
- **Packages and imports**: `__init__.py`, absolute imports (`from src.main import app`)
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

## Auth — what to look up

- **Password hashing with bcrypt**: salt, cost factor (`rounds=10`), why hashing is slow on purpose; `run_in_threadpool` so it doesn't block the event loop
- **JWT with PyJWT**: `jwt.encode` / `jwt.decode`, claims (`sub`, `exp`), HS256; why access and refresh tokens use different secrets
- **Cookies**: `httpOnly`, `secure`, `samesite`, `path` (the refresh cookie is only sent to `/api/auth`); `response.set_cookie` / `delete_cookie`
- **Token versioning**: how `token_version` lets "log out everywhere" and password changes kill old tokens without a blocklist
- **FastAPI parameters from cookies**: `Cookie(alias=...)`; `Response` as a route parameter to set cookies
- **Dependencies that depend on dependencies**: `get_current_user` uses `DbSession`; `require(...)` is a *factory* that returns a dependency
- **`StrEnum`**: `Permission`, `UserRole` compare equal to plain strings
- **Pydantic validation**: `StringConstraints(strip_whitespace=True, to_lower=True)`, `field_validator`, `ValidationInfo.data` (fields validated before this one)
- **Aliases**: `alias_generator=to_camel`, `populate_by_name`, `from_attributes` (build a schema from an ORM object)
- **Seed scripts**: `python -m scripts.x` (run a module so `app` imports work); `asyncio.run(main())` as the entry point
- **Async tests**: `pytest-asyncio` (`asyncio_mode = "auto"`), fixtures with `yield`, `scope="session"` vs per-test; `httpx.AsyncClient` + `ASGITransport` (calls the app in-process); why the test engine uses `NullPool`
- **Test isolation**: `TRUNCATE ... RESTART IDENTITY CASCADE` before each test; factory helpers vs fixtures

## Project structure — what to look up

- **Package by feature vs by layer**; FastAPI docs "Bigger Applications"; `zhanymkanov/fastapi-best-practices`; Netflix `dispatch`
- **Circular imports** in Python and how to break them; why tables reference each other by string (`ForeignKey("users.id")`)
- **SQLAlchemy registry**: a table class is only known to `Base.metadata` once its module is imported — why `database/models.py` exists
- **`from package import module as alias`** (`from src.users import service as users`): importing a module, not names, so calls read `users.get_user(...)`

## Open questions for our next discussion

- Tests build tables with `Base.metadata.create_all` (fast, no migrations). The alternative is running `alembic upgrade head` on the test database, which also tests the migrations. Which do you prefer?
- Response envelope: kept `{ success, message, data }` so the React app works unchanged. Plain FastAPI responses (data only, errors as `{ detail }`) are more common in Python codebases — keep or drop?
# dma-backend-python
