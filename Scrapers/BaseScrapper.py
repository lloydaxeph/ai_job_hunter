from abc import ABC, abstractmethod

from playwright.sync_api import Page

from Models.JobObject import JobObject
from Database.JobRepository import JobRepository
from Logger import ConsoleManager


class BaseScraper(ABC):
    def __init__(self, site_name: str, base_url: str, repository: JobRepository, filter: any = None):
        self.site_name = site_name
        self.base_url = base_url
        self.repository = repository
        self.filter = filter
        self.console = ConsoleManager().instance

    def scrape(self, page: Page, keyword: str, location: str, max_results: int) -> list:
        jobs = []
        page_number = 1
        try:
            base_url = self.build_url(keyword, location)
            while len(jobs) < max_results:
                page_url = self.build_page_url(base_url, page_number)
                page.goto(page_url, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)

                items = self.get_job_items(page)
                if not items:
                    break

                for item in items:
                    if len(jobs) >= max_results:
                        break
                    try:
                        job = self.parse_job(item)
                        if not job:
                            continue

                        if self.filter and self.filter.is_banned(job):
                            continue

                        if self.repository.save(job):
                            jobs.append(job)

                    except Exception:
                        continue

                self.console.print(f"[cyan][SCRAPPER] Found {len(jobs)} new jobs so far...[/cyan]")

                if len(jobs) >= max_results:
                    break

                if not self.has_next_page(page):
                    break

                page_number += 1 # Next page
            return jobs

        except Exception as e:
            self.console.print(f"[red][SCRAPPER] Scraping failed: {e}[/red]")
            return []

    @abstractmethod
    def build_url(self, keyword: str, location: str) -> str:
        """Build the search URL."""
        pass

    @abstractmethod
    def build_page_url(self, url: str, page_number: int) -> str:
        """Build the URL for a specific page."""
        pass

    @abstractmethod
    def has_next_page(self, page: Page) -> bool:
        """Return True if another results page exists."""
        pass

    @abstractmethod
    def get_job_items(self, page: Page):
        pass

    @abstractmethod
    def parse_job(self, item):
        pass

    @abstractmethod
    def scrape_job_info(self, page: Page, job: JobObject):
        pass