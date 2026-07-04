from __future__ import annotations

from playwright.sync_api import sync_playwright, Page

from Config import load_config, get_banned_companies
from AgentUtils import JobScraper, JobApplier, JobFilter, SessionManager
from Logger import ConsoleManager
from Constants import JobStatus, JobAgentModes

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
        self.database = Database()
        self.repository = JobRepository(self.database.connection)
        self.scraper = JobScraper(search_cfg=cfg["search"], job_filter=job_filter, repository=self.repository)
        self.applier = JobApplier(apply_cfg=apply_cfg, full_cfg=cfg, repository=self.repository)

    def _create_session(self, pw, site: str):
        session_manager = SessionManager(site)
        browser = pw.chromium.launch(headless=self.headless)
        context = session_manager.create_context(browser=browser)

        return session_manager, browser, context

    def default_apply_mode(self, page: Page, site: str) -> None:
        self.console.print(f"[cyan][AGENT] ----- QUICK APPLY MODE -----[/cyan]")
        jobs = self.scraper.scrape(page, site)
        if not jobs:
            self.console.print("[yellow][AGENT] No jobs found.[/yellow]")
            return

        jobs_to_apply = self._get_jobs_to_apply(jobs)
        if jobs_to_apply:
            self.console.print(f"[cyan][AGENT] Applying to {len(jobs_to_apply)} jobs...[/cyan]")
            total_jobs_applied = self.applier.run(page, jobs_to_apply, mode=JobAgentModes.QUICK_APPLY)
            self.console.print(
                f"[green][AGENT] {total_jobs_applied} out of {len(jobs)} "
                f"available jobs applied for {site}.[/green]")
        else:
            self.console.print("[yellow][AGENT] No jobs selected for application.[/yellow]")

    def status_based_run(self, page: Page, site: str, mode: JobAgentModes, status: str) -> None:
        self.console.print(f"[cyan][AGENT] ----- {mode} MODE -----[/cyan]")
        jobs = self.repository.get_jobs_by_status(status=status)
        if not jobs:
            self.console.print("[yellow][AGENT] No jobs found.[/yellow]")
            return
        self.console.print(f"[cyan][AGENT] Applying to {len(jobs)} jobs...[/cyan]")
        total_jobs_applied = self.applier.run(page, jobs, mode=mode)
        self.console.print(
            f"[green][AGENT] {total_jobs_applied} out of {len(jobs)} "
            f"available jobs applied for {site}.[/green]")

    def _run_site(self, pw, site: str, mode: JobAgentModes):
        self.console.print(f"[green][AGENT] Starting run for site: {site}[/green]")
        session_manager, browser, context = self._create_session(pw, site)
        try:
            session_manager.ensure_logged_in(context)
            page: Page = context.new_page()
            if mode == JobAgentModes.QUICK_APPLY:
                self.default_apply_mode(page, site)
            else:
                mode_status_map = {
                    JobAgentModes.MANUAL_REVIEW: JobStatus.REQUIRES_MANUAL_REVIEW,
                    JobAgentModes.RERUN: JobStatus.FOUND
                }
                self.status_based_run(page, site, mode, mode_status_map[mode])
        finally:
            context.close()
            browser.close()

    def run(self, mode: JobAgentModes) -> None:
        """Run the full job application pipeline."""
        with sync_playwright() as pw:
            sites =  self.cfg["search"]["sites"]
            for site in sites:
                self._run_site(pw, site, mode)
            self.repository.to_csv()
            self.console.print(f"[bold green][AGENT] ✓ Done for site: {site}. Check Data/applications.csv[/bold green]")
            self.console.print(f"[bold green]----------------------------------------------------[/bold green]")

    def _get_jobs_to_apply(self, jobs: list):
        if self.auto_apply:
            self.console.print("[cyan][AGENT] --- AUTO APPLY ENABLED ---[/cyan]")
            return jobs

        self.console.print("[yellow][AGENT] Manual application is not yet implemented.[/yellow]")
        return []


def main(mode, max_jobs):
    cfg = load_config()
    keyword_num = len(cfg["search"]["keywords"])
    location_num = len(cfg["search"]["locations"])
    if max_jobs:
        max_results_per_site = max_jobs // (keyword_num * location_num)
        cfg["search"]["max_results_per_site"] = max_results_per_site
    total_expected_jobs = int(cfg["search"]["max_results_per_site"]) * (keyword_num * location_num)

    print("JobHunter Agent INITIATED!")
    print(f"MODE: {mode}")
    print(f"TOTAL EXPECTED JOBS: {total_expected_jobs}")
    print(f"----------------------------------------------------")
    bot = JobAgent(cfg)
    bot.run(mode)


if __name__ == "__main__":
    # EDIT HERE ----------------------------------------------------------------------
    mode = JobAgentModes.QUICK_APPLY
    max_jobs = None

    # --------------------------------------------------------------------------------
    main(mode, max_jobs)
    # TODO:
    # Dynamic Session Manager
    # Manual Review process
    # Not Quick Apply process