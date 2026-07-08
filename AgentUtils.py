from __future__ import annotations

import time

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from rich.table import Table

from Logger import Logger, ConsoleManager
from Scrapers.JobStreet import JobStreetScraper
from Scrapers.Linkedin import LinkedInScraper
from Appliers.JobStreet import JobStreetApplier
from Appliers.LinkedIn import LinkedInApplier
from Authentication.JobStreet import JobStreetSessionManager
from Authentication.LinkedIn import LinkedInSessionManager
from Constants import JobStatus, JobAgentModes
from Database.JobRepository import JobRepository
from Models.JobObject import JobObject

logger = Logger().instance
console = ConsoleManager().instance


class JobFilter:
    """Decides which scraped jobs are worth keeping."""

    def __init__(
        self,
        banned_companies: list[str],
        avoid_titles: list[str] | None = None,
    ) -> None:
        self.banned_companies = [c.lower() for c in banned_companies]
        self.avoid_titles = [t.lower() for t in (avoid_titles or [])]

    def is_banned_company(self, job: JobObject) -> bool:
        company = job.company.lower()

        for banned in self.banned_companies:
            if banned in company:
                console.print(f"[FILTER] Skipping '{job.title}' at '{job.company}'")
                return True

        return False

    def is_avoided_title(self, job: JobObject) -> bool:
        title = job.title.lower()

        for keyword in self.avoid_titles:
            if keyword in title:
                console.print(f"[FILTER] Skipping '{job.title}' at '{job.company}'")
                return True

        return False

    def should_skip(self, job: JobObject) -> bool:
        return (
            self.is_banned_company(job)
            or self.is_avoided_title(job)
        )


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
        elif site.lower() == "linkedin":
            return LinkedInScraper(self.repository, self.filter)
        return None

    def scrape(self, page: Page, site: str) -> list[JobObject]:
        site_jobs = []
        scraper = self.get_scraper(site)
        if scraper is None:
            logger.warning( "No scraper registered for '%s'. Skipping.",site)
        else:
            for keyword in self.cfg["keywords"]:
                for location in self.cfg["locations"]:
                    console.print(f"[cyan][SCRAPPER] Scraping {site} → {keyword} ({location})[/cyan]")
                    key_loc_jobs = scraper.scrape(page, keyword, location, self.cfg["max_results_per_site"])
                    site_jobs = site_jobs + key_loc_jobs

        final_job_list = site_jobs
        console.print(f"[green][SCRAPPER] Found {len(final_job_list)} jobs from {site}.[/green]")
        return final_job_list


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
        elif site.lower() == "linkedin":
            return LinkedInApplier(self.repository, self.cfg)
        return None

    def run(self, page: Page, jobs: list[JobObject], mode: JobAgentModes) -> int:
        jobs_applied = 0
        for i, job in enumerate(jobs):
            console.print(f"[green][APPLIER] Job {i+1} out of {len(jobs)} ---------------------------[/green]")
            applier = self.get_applier(job.site)
            if applier is None:
                logger.warning("[APPLIER] No applier registered for '%s'. Skipping '%s'.",
                               job.site, job.title)
                self.repository.update_status(job_id=job.job_id, status=JobStatus.FAILED)
                continue

            if mode == JobAgentModes.MANUAL_REVIEW:
                status = applier.manual_apply(page, job)
            else:
                status = applier.apply(page, job)

            if status == JobStatus.APPLIED:
                jobs_applied += 1
                console.print(f"[bold green]Jobs Applied: {jobs_applied} --------------------------[/bold green]")
            time.sleep(self.delay)
        return jobs_applied


class SessionManager:
    def __init__(self, site: str) -> None:
        self.site = site
        self.session = self.get_manager(site)

    def create_context(self, browser: Browser) -> BrowserContext:
        return self.session.create_context(browser)

    def ensure_logged_in(self, context: BrowserContext) -> None:
        return self.session.ensure_logged_in(context)

    def get_manager(self, site: str):
        if site.lower() == "jobstreet":
            return JobStreetSessionManager()
        elif site.lower() == "linkedin":
            return LinkedInSessionManager()
        return None