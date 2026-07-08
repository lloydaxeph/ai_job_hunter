from playwright.sync_api import Page

from Database.JobRepository import JobRepository
from Models.JobObject import JobObject
from Scrapers.BaseScrapper import BaseScraper
from Constants import JobStatus


class LinkedInScraper(BaseScraper):
    def __init__(self, repository: JobRepository, filter: any = None):
        super().__init__(
            site_name="linkedin",
            base_url="https://www.linkedin.com",
            repository=repository,
            filter=filter
        )

    def build_url(self, keyword: str, location: str) -> str:
        keyword = keyword.replace(" ", "%20")
        location = location.replace(" ", "%20")

        return f"{self.base_url}/jobs/search/?keywords={keyword}&location={location}"

    def build_page_url(self, url: str, page_number: int) -> str:
        if page_number == 1:
            return url
        start = (page_number - 1) * 25
        return f"{url}&start={start}"

    def has_next_page(self, page: Page) -> bool:
        selectors = [
            "button[aria-label='View next page']",
            "button.jobs-search-pagination__button--next",
        ]

        for selector in selectors:
            btn = page.query_selector(selector)
            if btn and btn.get_attribute("disabled") is None:
                return True

        return False

    def get_job_items(self, page: Page):
        selectors = [
            "div[data-job-id]",  # Most reliable
            "div.job-card-container",
            "li[data-occludable-job-id]",
            ".job-card-list",
        ]

        for selector in selectors:
            try:
                page.wait_for_selector(selector, timeout=10000)
                items = page.query_selector_all(selector)

                if items:
                    return items

            except TimeoutError:
                continue
        return []

    def parse_job(self, item) -> JobObject | None:
        title_el = item.query_selector("a[href*='/jobs/view/']")

        if not title_el:
            return None

        company_el = item.query_selector(
            "[class*='entity-lockup__subtitle']"
        )

        href = title_el.get_attribute("href") or ""

        if href.startswith("/"):
            href = self.base_url + href

        href = href.split("?")[0]
        title = title_el.inner_text().strip()
        if "\n" in title:
            title = title.split("\n")[0]
        return JobObject(
            title=title,
            company=company_el.inner_text().strip() if company_el else "",
            url=href,
            site=self.site_name,
        )

    def scrape_job_info(self, page: Page, job: JobObject):
        try:
            page.goto(job.url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(1500)

            apply_btn = page.locator(
                "button[class*='jobs-apply-button'], button[data-live-test-job-apply-button]"
            ).first

            if apply_btn.count() == 0:
                return job, None

            if "Easy Apply" not in apply_btn.inner_text().strip():
                return job, JobStatus.NOT_QUICK_APPLY

            for sel in (
                    ".show-more-less-html__markup",
                    ".description__text",
                    "[class*='jobs-description__content']",
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