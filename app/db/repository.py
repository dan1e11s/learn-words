from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Sequence

import asyncpg


class UsersRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def create_user(self, email: str, password_hash: str) -> int | None:
        query = """
        INSERT INTO users (email, password_hash)
        VALUES ($1, $2)
        ON CONFLICT (email) DO NOTHING
        RETURNING id
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, email, password_hash)
        return row["id"] if row else None

    async def get_user_by_email(self, email: str) -> asyncpg.Record | None:
        query = "SELECT id, email, password_hash FROM users WHERE email = $1"
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, email)


class WordsRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def add_words(self, user_id: int, pairs: Sequence[tuple[str, str]]) -> int:
        if not pairs:
            return 0
        query = """
        INSERT INTO words (user_id, korean, russian)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id, korean, russian) DO NOTHING
        """
        async with self.pool.acquire() as conn:
            inserted = 0
            async with conn.transaction():
                for korean, russian in pairs:
                    result = await conn.execute(query, user_id, korean, russian)
                    if result.endswith("1"):
                        inserted += 1
        return inserted

    async def get_test_words(self, user_id: int, limit: int = 30) -> list[asyncpg.Record]:
        query = """
        SELECT *
        FROM words
        WHERE user_id = $1
          AND (
              progress < 100
              OR (progress = 100 AND COALESCE(next_review, NOW()) <= NOW())
          )
        ORDER BY progress ASC, COALESCE(next_review, NOW()) ASC, RANDOM()
        LIMIT $2
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, user_id, limit)
        return list(rows)

    async def get_random_russian_options(
        self, user_id: int, exclude_word_id: int, limit: int
    ) -> list[str]:
        query = """
        SELECT russian
        FROM (
            SELECT DISTINCT russian
            FROM words
            WHERE user_id = $1 AND id <> $2
        ) AS distinct_words
        ORDER BY RANDOM()
        LIMIT $3
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, user_id, exclude_word_id, limit)
        return [row["russian"] for row in rows]

    async def update_word_after_answer(
        self,
        word_id: int,
        is_correct: bool,
        progress_delta: int,
        new_interval_days: int | None,
        new_next_review: datetime | None,
    ) -> None:
        query = """
        UPDATE words
        SET times_tested = times_tested + 1,
            last_tested = NOW(),
            progress = CASE WHEN $2 THEN LEAST(100, progress + $3) ELSE progress END,
            interval_days = COALESCE($4, interval_days),
            next_review = COALESCE($5, next_review)
        WHERE id = $1
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                query, word_id, is_correct, progress_delta, new_interval_days, new_next_review
            )

    async def get_progress_rows(
        self,
        user_id: int,
        progress_min: int = 0,
        progress_max: int = 100,
        last_days: int | None = None,
        limit: int = 5000,
    ) -> list[asyncpg.Record]:
        if last_days is None:
            query = """
            SELECT id, korean, russian, progress, times_tested, last_tested, next_review
            FROM words
            WHERE user_id = $1 AND progress BETWEEN $2 AND $3
            ORDER BY progress ASC, korean ASC
            LIMIT $4
            """
            params = (user_id, progress_min, progress_max, limit)
        else:
            query = """
            SELECT id, korean, russian, progress, times_tested, last_tested, next_review
            FROM words
            WHERE user_id = $1
              AND progress BETWEEN $2 AND $3
              AND COALESCE(last_tested, NOW() - INTERVAL '100 years') >= NOW() - ($4::text || ' days')::INTERVAL
            ORDER BY progress ASC, korean ASC
            LIMIT $5
            """
            params = (user_id, progress_min, progress_max, last_days, limit)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        return list(rows)

    async def delete_word(self, word_id: int, user_id: int) -> None:
        query = "DELETE FROM words WHERE id = $1 AND user_id = $2"
        async with self.pool.acquire() as conn:
            await conn.execute(query, word_id, user_id)

    async def get_word_by_id(self, word_id: int, user_id: int) -> asyncpg.Record | None:
        query = "SELECT id, korean, russian, progress, times_tested FROM words WHERE id = $1 AND user_id = $2"
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, word_id, user_id)

    async def update_word(self, word_id: int, user_id: int, korean: str, russian: str) -> bool:
        query = """
        UPDATE words SET korean = $3, russian = $4
        WHERE id = $1 AND user_id = $2
        """
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(query, word_id, user_id, korean, russian)
            return result == "UPDATE 1"
        except asyncpg.UniqueViolationError:
            return False

    async def get_total_words_count(self, user_id: int) -> int:
        query = "SELECT COUNT(*) AS cnt FROM words WHERE user_id = $1"
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, user_id)
        return int(row["cnt"]) if row else 0


class TestSessionRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def start_session(self, user_id: int, queue: list[dict[str, Any]]) -> int:
        query = """
        INSERT INTO test_sessions (user_id, payload_json)
        VALUES ($1, $2::jsonb)
        RETURNING id
        """
        payload = {"queue": queue, "current_index": 0, "correct_count": 0}
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, user_id, json.dumps(payload))
        return row["id"]

    async def get_session(self, session_id: int, user_id: int) -> dict[str, Any] | None:
        query = "SELECT id, payload_json FROM test_sessions WHERE id = $1 AND user_id = $2"
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, session_id, user_id)
        if not row:
            return None
        raw_payload = row["payload_json"]
        if isinstance(raw_payload, str):
            payload = json.loads(raw_payload)
        else:
            payload = dict(raw_payload)
        return {"id": row["id"], "payload": payload}

    async def save_session(self, session_id: int, payload: dict[str, Any]) -> None:
        query = "UPDATE test_sessions SET payload_json = $2::jsonb WHERE id = $1"
        async with self.pool.acquire() as conn:
            await conn.execute(query, session_id, json.dumps(payload))

    async def delete_session(self, session_id: int, user_id: int) -> None:
        query = "DELETE FROM test_sessions WHERE id = $1 AND user_id = $2"
        async with self.pool.acquire() as conn:
            await conn.execute(query, session_id, user_id)
