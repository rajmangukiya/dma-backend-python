Core backend
• FastAPI: the most in-demand modern Python web framework. It’s async, uses type hints like TypeScript, and generates API docs automatically. It will feel familiar after Express.
• Pydantic v2: validates and shapes data, like Zod. FastAPI is built on it, and so are most AI libraries.
• SQLAlchemy 2.0 and Alembic: the standard way to work with databases in Python, plus migrations. Keep Postgres.
• uv: a fast package and project manager, now the default in new projects. Ruff for linting and formatting, and mypy or pyright for type checks.
• pytest: for testing.

Background work
• Celery with Redis: the most common choice in job posts for long-running tasks like parsing documents. Learn it first. Temporal is a strong bonus later for multi-step journeys.

AI layer, which is where the demand is
• Call model APIs like Claude or OpenAI directly with their Python SDKs at first, so you learn what’s really happening.
• pgvector: vector search inside Postgres, so you don’t need a separate vector database.
• Docling, Unstructured or a vision-capable model: to turn PDFs and scans into structured data.
• LangGraph: add this once you build the multi-step journey agent. It’s the agent framework that shows up most in job posts.
• Langfuse or OpenTelemetry: for tracing and evaluating agent runs. Few candidates have this.

Shipping it
• Docker and docker-compose, GitHub Actions for CI, and one cloud provider. AWS is the safest pick for jobs.