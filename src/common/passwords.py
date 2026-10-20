"""Password hashing (bcrypt). Used by auth (login, change password) and users (create, reset)."""

import bcrypt
from starlette.concurrency import run_in_threadpool

# Same cost as the Node backend (bcryptjs, 10 rounds), so hashes are interchangeable
BCRYPT_ROUNDS = 10

# bcrypt is deliberately slow (~50-100 ms). Running it in a thread keeps the
# event loop free to serve other requests meanwhile.


async def hash_password(plain: str) -> str:
    hashed = await run_in_threadpool(
        bcrypt.hashpw, plain.encode(), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    )
    return hashed.decode()


async def verify_password(plain: str, hashed: str) -> bool:
    return await run_in_threadpool(bcrypt.checkpw, plain.encode(), hashed.encode())
