from __future__ import annotations

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

from Authentication.JobStreet import JobStreetSessionManager
from Config import load_config, get_banned_companies
from AgentUtils import JobScraper, JobApplier, JobFilter
from Logger import ConsoleManager

from Database.JobRepository import JobRepository
from Database.Database import Database


class JobAgent:
    """Thin orchestrator — wires the helper classes and runs the pipeline."""
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        apply_cfg = cfg["apply"]

        self.auto_apply: bool = apply_cfg["auto_apply"]
        self.max_apps: int = apply_cfg["max_apps_per_run"]
        self.headless: bool = apply_cfg["headless"]

        # Utils
        job_filter = JobFilter(banned_companies=get_banned_companies(cfg))

        self.console = ConsoleManager().instance
        self.session =JobStreetSessionManager()

        self.database = Database()
        self.repository = JobRepository(self.database.connection)

        self.scraper = JobScraper(search_cfg=cfg["search"], job_filter=job_filter, repository=self.repository)
        self.applier = JobApplier(apply_cfg=apply_cfg, full_cfg=cfg, repository=self.repository)

    def run(self) -> None:
        """Run the full job application pipeline."""

        with sync_playwright() as pw:
            browser: Browser = pw.chromium.launch(
                headless=self.headless
            )

            context: BrowserContext = self.session.create_context(browser)

            try:
                self.session.ensure_logged_in(context)
                page: Page = context.new_page()
                jobs = self.scraper.scrape(page)
                if not jobs:
                    self.console.print("[yellow]No new jobs found.[/yellow]")
                    return

                jobs_to_apply = self._get_jobs_to_apply(jobs)
                if jobs_to_apply:
                    self.console.print(f"[cyan]Applying to {len(jobs_to_apply)} jobs...[/cyan]")
                    self.applier.run(page, jobs_to_apply)
                else:
                    self.console.print("[yellow]No jobs selected for application.[/yellow]" )

            finally:
                context.close()
                browser.close()

        self.repository.to_csv()
        self.console.print(
            "[bold green]✓ Done. Check Data/applications.csv[/bold green]"
        )

    def _get_jobs_to_apply(self, jobs: list):
        if self.auto_apply:
            self.console.print("[cyan]Initiating Auto Apply...[/cyan]")
            return jobs

        self.console.print("[yellow]Manual application is not yet implemented.[/yellow]")
        return []


def main() -> None:
    cfg = load_config()
    bot = JobAgent(cfg)
    bot.run()


if __name__ == "__main__":
    main()