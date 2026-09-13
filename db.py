import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent / "data" / "hub.sqlite3"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS follower_snapshot (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                taken_at TEXT NOT NULL,
                followers INTEGER NOT NULL,
                following INTEGER,
                media_count INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_snap_user_time
                ON follower_snapshot(username, taken_at);

            CREATE TABLE IF NOT EXISTS post (
                shortcode TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                posted_at TEXT NOT NULL,
                media_type TEXT NOT NULL,
                caption TEXT,
                likes INTEGER,
                comments INTEGER,
                video_views INTEGER,
                video_duration REAL,
                url TEXT,
                is_carousel INTEGER DEFAULT 0,
                fetched_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_post_user_time
                ON post(username, posted_at);

            CREATE TABLE IF NOT EXISTS post_hashtag (
                shortcode TEXT NOT NULL,
                hashtag TEXT NOT NULL,
                PRIMARY KEY (shortcode, hashtag)
            );
            """
        )


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
