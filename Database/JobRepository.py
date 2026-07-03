import pandas as pd

from datetime import datetime
from pathlib import Path
from sqlite3 import Connection

from Models.JobObject import JobObject


class JobRepository:
    def __init__(self, connection: Connection):
        self.connection = connection

    def save(self, job: JobObject) -> bool:
        cursor = self.connection.cursor()

        cursor.execute(
            """
            INSERT OR IGNORE INTO jobs (
                job_id,
                job_title,
                company,
                url,
                site,
                score,
                description,
                resume_used,
                date,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.job_id,
                job.title,
                job.company,
                job.url,
                job.site,
                job.score,
                job.description,
                job.resume_used,
                job.date.isoformat(),
                job.status,
            ),
        )

        self.connection.commit()

        return cursor.rowcount == 1

    def exists(self, job_id: str) -> bool:
        cursor = self.connection.cursor()

        cursor.execute(
            """
            SELECT 1
            FROM jobs
            WHERE job_id = ?
            LIMIT 1
            """,
            (job_id,),
        )

        return cursor.fetchone() is not None

    def get(self, job_id: str) -> JobObject | None:
        cursor = self.connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM jobs
            WHERE job_id = ?
            """,
            (job_id,),
        )

        row = cursor.fetchone()

        if row is None:
            return None

        return self._row_to_job(row)

    def get_all(self) -> list[JobObject]:
        cursor = self.connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM jobs
            ORDER BY date DESC
            """
        )

        return [self._row_to_job(row) for row in cursor.fetchall()]

    def get_jobs_by_status(self, status: str) -> list[JobObject]:
        cursor = self.connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM jobs
            WHERE status = ?
            ORDER BY date DESC
            """,
            (status,),
        )

        return [self._row_to_job(row) for row in cursor.fetchall()]

    def delete(self, job_id: str) -> None:
        cursor = self.connection.cursor()

        cursor.execute(
            """
            DELETE FROM jobs
            WHERE job_id = ?
            """,
            (job_id,),
        )

        self.connection.commit()

    def update_description(self, job_id: str, description: str) -> None:
        cursor = self.connection.cursor()

        cursor.execute(
            """
            UPDATE jobs
            SET description = ?
            WHERE job_id = ?
            """,
            (description, job_id),
        )

        self.connection.commit()

    def update_status(self, job_id: str, status: str) -> None:
        cursor = self.connection.cursor()

        cursor.execute(
            """
            UPDATE jobs
            SET status = ?
            WHERE job_id = ?
            """,
            (status, job_id),
        )

        self.connection.commit()

    def update_score(self, job_id: str, score: int) -> None:
        cursor = self.connection.cursor()

        cursor.execute(
            """
            UPDATE jobs
            SET score = ?
            WHERE job_id = ?
            """,
            (score, job_id),
        )

        self.connection.commit()

    def update_resume_used(self, job_id: str, resume_used: str) -> None:
        cursor = self.connection.cursor()

        cursor.execute(
            """
            UPDATE jobs
            SET resume_used = ?
            WHERE job_id = ?
            """,
            (resume_used, job_id),
        )

        self.connection.commit()

    def to_csv(self, output_path: str = "Data/applications.csv") -> None:
        cursor = self.connection.cursor()

        cursor.execute(
            """
            SELECT
                job_id,
                job_title,
                company,
                url,
                site,
                score,
                description,
                resume_used,
                date,
                status
            FROM jobs
            ORDER BY date DESC
            """
        )

        rows = cursor.fetchall()

        if not rows:
            print("No jobs found.")
            return

        df = pd.DataFrame([dict(row) for row in rows])

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        df.to_csv(output, index=False)

        print(f"Exported {len(df)} jobs to {output}")

    def _row_to_job(self, row) -> JobObject:
        return JobObject(
            title=row["job_title"],
            company=row["company"],
            url=row["url"],
            site=row["site"],
            score=row["score"],
            description=row["description"],
            resume_used=row["resume_used"],
            date=datetime.fromisoformat(row["date"]),
            status=row["status"],
        )