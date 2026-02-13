"""Database schema definitions for the GRC pipeline."""

# All CREATE TABLE statements for the SQLite database

CREATE_EVENT_SOURCES = """
CREATE TABLE IF NOT EXISTS event_sources (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    is_excluded BOOLEAN NOT NULL DEFAULT 0,
    week_key TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(id, week_key)
)
"""

CREATE_SESSION_DATA_KEYS = """
CREATE TABLE IF NOT EXISTS session_data_keys (
    id INTEGER PRIMARY KEY,
    key_name TEXT NOT NULL,
    week_key TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(id, week_key)
)
"""

CREATE_RAW_USER_QUESTIONS = """
CREATE TABLE IF NOT EXISTS raw_user_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    user_question TEXT,
    date TEXT,
    session_id TEXT,
    log_id TEXT,
    source INTEGER,
    week_key TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(event_id, week_key)
)
"""

CREATE_RAW_UQ_MATCHINGS = """
CREATE TABLE IF NOT EXISTS raw_uq_matchings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    id_content INTEGER NOT NULL,
    weight REAL,
    is_external BOOLEAN DEFAULT 0,
    week_key TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES raw_user_questions(event_id)
)
"""

CREATE_RAW_SESSIONS = """
CREATE TABLE IF NOT EXISTS raw_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    session_id TEXT,
    key TEXT,
    value TEXT,
    user_question TEXT,
    date TEXT,
    log_id TEXT,
    week_key TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_RAW_CLICKS = """
CREATE TABLE IF NOT EXISTS raw_clicks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    session_id TEXT,
    id_content INTEGER,
    click_type TEXT,
    log_id TEXT,
    date TEXT,
    week_key TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_RAW_RATINGS = """
CREATE TABLE IF NOT EXISTS raw_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    session_id TEXT,
    rating TEXT,
    comment TEXT,
    log_id TEXT,
    date TEXT,
    week_key TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_AGG_SESSION_DETAILS = """
CREATE TABLE IF NOT EXISTS agg_session_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    source TEXT,
    duration INTEGER,
    environment TEXT,
    date TEXT,
    log_ids TEXT,
    ids_contents TEXT,
    week_key TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, week_key)
)
"""

CREATE_CONTENT_LOOKUP = """
CREATE TABLE IF NOT EXISTS content_lookup (
    id_content INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_INGESTION_RUNS = """
CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_key TEXT NOT NULL,
    status TEXT NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    record_counts TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# Index definitions for better query performance
CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_raw_sessions_session_id ON raw_sessions(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_raw_sessions_log_id ON raw_sessions(log_id)",
    "CREATE INDEX IF NOT EXISTS idx_raw_sessions_week_key ON raw_sessions(week_key)",
    "CREATE INDEX IF NOT EXISTS idx_raw_user_questions_event_id ON raw_user_questions(event_id)",
    "CREATE INDEX IF NOT EXISTS idx_raw_user_questions_log_id ON raw_user_questions(log_id)",
    "CREATE INDEX IF NOT EXISTS idx_raw_user_questions_session_id ON raw_user_questions(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_raw_uq_matchings_event_id ON raw_uq_matchings(event_id)",
    "CREATE INDEX IF NOT EXISTS idx_raw_uq_matchings_id_content ON raw_uq_matchings(id_content)",
    "CREATE INDEX IF NOT EXISTS idx_raw_clicks_log_id ON raw_clicks(log_id)",
    "CREATE INDEX IF NOT EXISTS idx_raw_clicks_id_content ON raw_clicks(id_content)",
    "CREATE INDEX IF NOT EXISTS idx_raw_ratings_log_id ON raw_ratings(log_id)",
    "CREATE INDEX IF NOT EXISTS idx_agg_session_details_session_id ON agg_session_details(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_agg_session_details_week_key ON agg_session_details(week_key)",
]

# All create statements in order
ALL_TABLES = [
    CREATE_EVENT_SOURCES,
    CREATE_SESSION_DATA_KEYS,
    CREATE_RAW_USER_QUESTIONS,
    CREATE_RAW_UQ_MATCHINGS,
    CREATE_RAW_SESSIONS,
    CREATE_RAW_CLICKS,
    CREATE_RAW_RATINGS,
    CREATE_AGG_SESSION_DETAILS,
    CREATE_CONTENT_LOOKUP,
    CREATE_INGESTION_RUNS,
]
