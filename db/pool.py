from __future__ import annotations

import asyncpg

from config import settings


CREATE_WORDS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS words (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    korean TEXT NOT NULL,
    russian TEXT NOT NULL,
    progress INT NOT NULL DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    times_tested INT NOT NULL DEFAULT 0 CHECK (times_tested >= 0),
    last_tested TIMESTAMP,
    interval_days INT NOT NULL DEFAULT 1 CHECK (interval_days >= 1),
    next_review TIMESTAMP,
    UNIQUE (user_id, korean, russian)
);
CREATE INDEX IF NOT EXISTS idx_words_user_progress ON words(user_id, progress);
CREATE INDEX IF NOT EXISTS idx_words_user_next_review ON words(user_id, next_review);
"""


async def create_pool() -> asyncpg.Pool:
    pool = await asyncpg.create_pool(dsn=settings.database_url, min_size=1, max_size=10)
    async with pool.acquire() as conn:
        await conn.execute(CREATE_WORDS_TABLE_SQL)
    return pool
