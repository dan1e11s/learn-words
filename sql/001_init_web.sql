CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS words (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    korean TEXT NOT NULL,
    russian TEXT NOT NULL,
    progress INT NOT NULL DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    times_tested INT NOT NULL DEFAULT 0 CHECK (times_tested >= 0),
    last_tested TIMESTAMP,
    interval_days INT NOT NULL DEFAULT 1 CHECK (interval_days >= 1),
    next_review TIMESTAMP,
    UNIQUE (user_id, korean, russian)
);

CREATE TABLE IF NOT EXISTS test_sessions (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    current_index INT NOT NULL DEFAULT 0,
    correct_count INT NOT NULL DEFAULT 0,
    payload_json JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_words_user_progress ON words(user_id, progress);
CREATE INDEX IF NOT EXISTS idx_words_user_next_review ON words(user_id, next_review);
CREATE INDEX IF NOT EXISTS idx_sessions_user_started ON test_sessions(user_id, started_at DESC);
