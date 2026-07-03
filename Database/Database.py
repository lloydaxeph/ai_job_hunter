import sqlite3
from pathlib import Path


class Database:
    CREATE_JOBS_TABLE = """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            job_title TEXT NOT NULL,
            company TEXT NOT NULL,
            url TEXT NOT NULL,
            site TEXT NOT NULL,
            score INTEGER NOT NULL DEFAULT 0,
            description TEXT NOT NULL DEFAULT '',
            resume_used TEXT NOT NULL DEFAULT 'NA',
            date TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """

    def __init__(self, db_path: str = "Data/jobs.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.connection = sqlite3.connect(db_path)
        self.connection.row_factory = sqlite3.Row

        self.create_tables()

    def create_tables(self) -> None:
        cursor = self.connection.cursor()

        cursor.execute(self.CREATE_JOBS_TABLE)

        self.connection.commit()

    def close(self) -> None:
        self.connection.close()