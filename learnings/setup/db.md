- SQLAlchemy
    - sqlalchemy[asyncio] `async/awaoit`
    - ORM (python -> SQL)
    - manages sessions and transactions

- asyncpg
    - the driver: sends SQL to Postgres over the network

- Alembic
    - for migrations
    - uses SQLAlchemy for migration