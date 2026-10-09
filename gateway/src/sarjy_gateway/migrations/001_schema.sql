-- Sarjy's tables (D-64, D-65). One row in turns is one exchange: what the traveller said
-- and what Sarjy answered, under the pipeline's turn id, which turn_timings refers to.

SET LOCAL lock_timeout = '5s';

CREATE TABLE IF NOT EXISTS users (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    created_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS facts (
    user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    key text NOT NULL,
    value text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, key)
);

CREATE TABLE IF NOT EXISTS sessions (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    started_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS sessions_user_id_idx ON sessions (user_id);

CREATE TABLE IF NOT EXISTS turns (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    session_id uuid NOT NULL REFERENCES sessions (id) ON DELETE CASCADE,
    transcript text NOT NULL,
    reply text NOT NULL,
    tool_results text [] NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS turns_session_id_idx ON turns (session_id);

CREATE TABLE IF NOT EXISTS turn_timings (
    turn_id uuid NOT NULL REFERENCES turns (id) ON DELETE CASCADE,
    mark text NOT NULL,
    at_ms double precision NOT NULL,
    PRIMARY KEY (turn_id, mark)
);
