from __future__ import annotations

import time

from playwright.sync_api import Page
from rich.table import Table

from Logger import Logger, ConsoleManager
from Scrapers.JobStreet import JobStreetScraper
from Appliers.JobStreet import JobStreetApplier
from Constants import JobStatus
from Database.JobRepository import JobRepository
from Models.JobObject import JobObject

logger = Logger().instance
console = ConsoleManager().instance


class JobFilter:
    """Decides which scraped jobs are worth keeping."""
    def __init__(self, banned_companies: list[str]) -> None:
        self.banned = banned_companies

    def is_banned(self, job: JobObject) -> bool:
        company = job.company.lower()
        return any(banned in company for banned in self.banned)

    def should_skip(self, job: JobObject) -> bool:
        return self.is_banned(job)


class JobScraper:
    """Scrapes jobs and stores them in the tracker."""
    def __init__(
        self,
        search_cfg: dict,
        job_filter: JobFilter,
        repository: JobRepository
    ) -> None:
        self.cfg = search_cfg
        self.filter = job_filter
        self.repository = repository

    def get_scraper(self, site: str):
        if site.lower() == "jobstreet":
            return JobStreetScraper(self.repository, self.filter)
        return None

    def scrape(self, page: Page) -> list[JobObject]:
        for site in self.cfg["sites"]:
            scraper = self.get_scraper(site)

            if scraper is None:
                logger.warning( "No scraper registered for '%s'. Skipping.",site)
                continue

            for keyword in self.cfg["keywords"]:
                for location in self.cfg["locations"]:
                    console.print(f"[cyan]Scraping {site} → {keyword} ({location})[/cyan]")

                    scraper.scrape(page, keyword, location, self.cfg["max_results_per_site"])

        final_job_list = self.repository.get_jobs_by_status(status=JobStatus.FOUND)

        console.print(f"[green]Will apply to {len(final_job_list)} jobs.[/green]")
        console.print(f"--------------------------------------------------------")
        return final_job_list

    def scrape_job_info(self, page: Page, job: JobObject) -> str:
        scraper = self.get_scraper(job.site)
        job, apply_button = scraper.scrape_job_info(page, job)

        if apply_button is None:
            self.repository.update_status(
                job_id=job.job_id,status=JobStatus.REQUIRES_MANUAL_REVIEW)
            return None

        if apply_button == JobStatus.NOT_QUICK_APPLY:
            self.repository.update_status(
                job_id=job.job_id,status=JobStatus.NOT_QUICK_APPLY)
            return None

        self.repository.update_description(
            job_id=job.job_id, description=job.description)
        return job


class JobReviewer:
    """Displays matched jobs and lets the user decide which ones to apply to."""
    def select(self, jobs: list[JobObject]) -> list[JobObject]:
        self._print_table(jobs)

        while True:
            raw = input("\nSelect jobs (e.g. 1,3,5 | all | none): ").strip().lower()

            if raw == "none":
                return []

            if raw == "all":
                return jobs

            try:
                indexes = [int(x) - 1 for x in raw.split(",")]
                selected = [jobs[i] for i in indexes if 0 <= i < len(jobs)]
                if selected:
                    return selected
                console.print("[yellow]No valid selections. Try again.[/yellow]")
            except ValueError:
                console.print(
                    "[yellow]Invalid input. Use numbers, 'all', or 'none'.[/yellow]"
                )

    @staticmethod
    def _print_table(jobs: list[JobObject]) -> None:
        table = Table(title="Matched Jobs")
        for col in ("ID", "Score", "Title", "Company", "Site"):
            table.add_column(col)
        for i, job in enumerate(jobs, start=1):
            table.add_row(str(i), str(job.score), job.title, job.company, job.site)
        console.print(table)


class JobApplier:
    """Submits applications."""

    def __init__(
        self,
        apply_cfg: dict,
        full_cfg: dict,
        repository: JobRepository
    ) -> None:

        self.delay = apply_cfg["delay_between_apps"]
        self.cfg = full_cfg
        self.repository = repository

    def get_applier(self, site: str):
        if site.lower() == "jobstreet":
            return JobStreetApplier(self.repository, self.cfg)
        return None

    def run(self, page: Page, jobs: list[JobObject]) -> None:
        jobs_applied = 0
        for job in jobs:
            applier = self.get_applier(job.site)
            if applier is None:
                logger.warning("No applier registered for '%s'. Skipping '%s'.",
                               job.site, job.title)
                self.repository.update_status(job_id=job.job_id, status=JobStatus.FAILED)
                continue

            status = applier.apply(page, job)
            if status == JobStatus.APPLIED:
                jobs_applied += 1
            time.sleep(self.delay)
        console.print(f"[green]{jobs_applied} out of {len(jobs)} available jobs applied.[/green]")
