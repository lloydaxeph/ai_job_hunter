from playwright.sync_api import Page

from Database.JobRepository import JobRepository
from Models.JobObject import JobObject
from Scrapers.BaseScrapper import BaseScraper
from Constants import JobStatus


class JobStreetScraper(BaseScraper):
    def __init__(self, repository: JobRepository, filter: any = None):
        super().__init__(
            site_name="jobstreet",
            base_url="https://sg.jobstreet.com",
            repository=repository,
            filter=filter
        )

    def build_url(self, keyword: str, location: str) -> str:
        keyword = keyword.replace(" ", "-")
        location = location.replace(" ", "-")

        return f"{self.base_url}/{keyword}-jobs/in-{location}"

    def build_page_url(self, url: str, page_number: int) -> str:
        if page_number == 1:
            return url

        return f"{url}?page={page_number}"

    def has_next_page(self, page: Page) -> bool:
        return (
            page.query_selector("a[aria-label='Next']") is not None
            or page.query_selector("a[data-testid='pagination-page-next']") is not None
        )

    def get_job_items(self, page: Page):
        items = page.query_selector_all("[data-testid='job-card']")
        if not items:
            items = page.query_selector_all("article[class*='job']")
        return items

    def parse_job(self, item) -> JobObject | None:
        title = item.query_selector(
            "[data-testid='job-title'], h1, h2, h3"
        )

        if not title:
            return None

        company = item.query_selector(
            "[data-automation='jobCompany'], a[data-type='company']"
        )

        link = item.query_selector("a[href*='/job/']")

        href = ""

        if link:
            href = link.get_attribute("href") or ""

            if href.startswith("/"):
                href = self.base_url + href

        return JobObject(
            title=title.inner_text().strip(),
            company=company.inner_text().strip() if company else "",
            url=href,
            site=self.site_name,
        )

    def scrape_job_info(self, page: Page, job: JobObject):
        try:
            page.goto(job.url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(1500)

            apply_btn = page.locator("[data-automation='job-detail-apply']").first

            if apply_btn.count() == 0:
                return job, None

            if apply_btn.inner_text().strip() != "Quick Apply":
                return job, JobStatus.NOT_QUICK_APPLY

            for sel in (
                    ".description__text",
                    "#job-details",
                    ".jobsearch-jobDescriptionText",
                    "[data-testid='jobDescription']",
            ):
                el = page.query_selector(sel)
                if el:
                    job.description = el.inner_text()[:3000]
                    break
            else:
                job.description = page.inner_text("body")[:3000]

            return job, "Quick Apply"

        except Exception:
            return job, None