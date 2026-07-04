from abc import ABC, abstractmethod
import tkinter as tk
from tkinter import messagebox

from playwright.sync_api import Page, TimeoutError

from Config import pick_resume
from Constants import JobStatus
from Database.JobRepository import JobRepository
from Logger import ConsoleManager
from Models.JobObject import JobObject
from AIHelpers.Scorers.OpenAI import AiJobScorer


class BaseApplier(ABC):
    def __init__(self, repository: JobRepository, cfg: dict):
        self.app = "[Applier]"
        self.repository = repository
        self.console = ConsoleManager().instance
        self.cfg = cfg
        self.scorer = AiJobScorer(cfg)
        self.score_threshold = cfg["ai"]["score_threshold"]

    def _score_job(self, page: Page, job: JobObject) -> JobObject:
        job.description = self.get_job_description(page)
        self.repository.update_description(job_id=job.job_id, description=job.description)
        ai_score = self.scorer.score_job(job.to_dict())
        job.score = ai_score.get("score", 0)
        self.repository.update_score(job_id=job.job_id, score=job.score)
        return job

    def apply(self, page: Page, job: JobObject) -> str:
        """Apply to a single job."""
        try:
            self.console.print(f"[cyan]{self.app} Opening {job.title} @ {job.company}...[/cyan]")
            page.goto(job.url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state("networkidle")

            status = self.check_apply_button(page)
            if status != "Quick Apply":
                self.console.print(f"[red]{self.app} FAILED: Job status = {status}[/red]")
                self.repository.update_status(job_id=job.job_id, status=status)
                return status
            self.console.print(f"[cyan]{self.app} Confirmed that job is Quick Apply.[/cyan]")

            if self.is_already_applied(page):
                status = JobStatus.APPLIED
                self.console.print(f"[red]{self.app} FAILED: You already applied to this job.[/red]")
                self.repository.update_status(job_id=job.job_id, status=status)
                return status

            # Check if job matched
            job = self._score_job(page, job)
            if job.score >= self.score_threshold:
                self.console.print(f"{self.app} MATCHED! Score:{job.score} ")
                self.click_apply(page)
                page.wait_for_load_state("networkidle")

                resume = pick_resume(job.title, self.cfg)
                for step in range(20):
                    if step == 0:
                        self.console.print(f"[cyan]{self.app} using {resume}...[/cyan]")
                        self.upload_resume(page, resume)
                        self.write_cover_letter(page, "")
                    else:
                        self.fill_known_fields(page, self.cfg)
                        self.fill_select_questions(page)
                        self.answer_yes_questions(page)
                        if self.check_for_errors(page):
                            break

                    if self.click_continue(page):
                        page.wait_for_load_state("networkidle")
                        continue

                    if self.click_next(page):
                        page.wait_for_load_state("networkidle")
                        continue

                    if self.click_submit(page):
                        page.wait_for_timeout(3000)
                        self.console.print(f"[cyan]{self.app} JOB APPLIED![/cyan]")
                        status = JobStatus.APPLIED
                        self.repository.update_status(job_id=job.job_id, status=status)
                        self.repository.update_resume_used(job_id=job.job_id, resume_used=resume)
                        return status

                    status = JobStatus.REQUIRES_MANUAL_REVIEW
                    self.repository.update_status(job_id=job.job_id, status=status)
                    self.console.print(f"[cyan]{self.app} FAILED! Job needs manual review[/cyan]")
                    return status
            else:
                status = JobStatus.DID_NOT_MATCH
                self.repository.update_status(job_id=job.job_id, status=status)
                return status

            status = JobStatus.REQUIRES_MANUAL_REVIEW
            self.repository.update_status(job_id=job.job_id, status=status)
            self.console.print(f"[cyan]{self.app} FAILED! Job needs manual review[/cyan]")
            return status

        except TimeoutError:
            self.console.print(f"[red]{self.app} FAILED! Cannot apply to {job.title} @ {job.company} due to timeout.[/red]")
            status = JobStatus.FAILED
            self.repository.update_status(job_id=job.job_id, status=status)
            return status

        except Exception as e:
            self.console.print(f"[red]{self.app} FAILED! Cannot apply to {job.title} @ {job.company}: {e}.[/red]")
            status = JobStatus.FAILED
            self.repository.update_status(job_id=job.job_id, status=status)
            return status

    def manual_apply(self, page: Page, job: JobObject) -> str:
        """Apply to a single job."""
        try:
            self.console.print(f"[cyan]{self.app} Opening {job.title} @ {job.company}...[/cyan]")
            page.goto(job.url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state("networkidle")

            # Check if already applied
            if self.is_already_applied(page):
                status = JobStatus.APPLIED
                self.console.print(f"[red]{self.app} FAILED: You already applied to this job.[/red]")
                self.repository.update_status(job_id=job.job_id, status=status)
                return status

            self.click_apply(page)
            page.wait_for_load_state("networkidle")

            resume = pick_resume(job.title, self.cfg)
            for step in range(10):
                if step == 0:
                    self.console.print(f"[cyan]{self.app} using {resume}...[/cyan]")
                    self.upload_resume(page, resume)
                    self.write_cover_letter(page, "")
                else:
                    self.fill_known_fields(page, self.cfg)
                    self.fill_select_questions(page)
                    self.answer_yes_questions(page)

                    if self.check_for_errors(page):
                        self.wait_for_manual_intervention(page)

                if self.click_continue(page):
                    page.wait_for_load_state("networkidle")
                    continue

                if self.click_next(page):
                    page.wait_for_load_state("networkidle")
                    continue

                if self.click_submit(page):
                    page.wait_for_timeout(3000)
                    self.console.print(f"[cyan]{self.app} JOB APPLIED![/cyan]")
                    status = JobStatus.APPLIED
                    self.repository.update_status(job_id=job.job_id, status=status)
                    self.repository.update_resume_used(job_id=job.job_id, resume_used=resume)

                    return status

                status = JobStatus.REQUIRES_MANUAL_REVIEW
                self.repository.update_status(job_id=job.job_id, status=status)
                self.console.print(f"[cyan]{self.app} FAILED! Job needs manual review[/cyan]")
                return status

            status = JobStatus.REQUIRES_MANUAL_REVIEW
            self.repository.update_status(job_id=job.job_id, status=status)
            self.console.print(f"[cyan]{self.app} FAILED! Job needs manual review again.[/cyan]")
            return status

        except TimeoutError:
            self.console.print(
                f"[red]{self.app} FAILED! Cannot apply to {job.title} @ {job.company} due to timeout.[/red]")
            status = JobStatus.FAILED
            self.repository.update_status(job_id=job.job_id, status=status)
            return status

        except Exception as e:
            self.console.print(f"[red]{self.app} FAILED! Cannot apply to {job.title} @ {job.company}: {e}.[/red]")
            status = JobStatus.FAILED
            self.repository.update_status(job_id=job.job_id, status=status)
            return status

    def is_already_applied(self, page: Page) -> bool:
        body = page.locator("body").inner_text().lower()
        return (
            "already applied" in body
            or "application submitted" in body
        )

    def wait_for_manual_intervention(self, page: Page):
        """Pause automation until all validation errors are resolved."""

        while True:
            error_panel = page.locator("#errorPanel")

            if error_panel.count() == 0 or not error_panel.is_visible():
                self.console.print("[green]Validation errors resolved. Continuing...[/green]")
                return

            errors = error_panel.locator("li").all_inner_texts()

            self.console.print("")
            self.console.print("[red]========== Validation Errors ==========[/red]")

            for i, error in enumerate(errors, start=1):
                self.console.print(f"[yellow]{i}. {error.strip()}[/yellow]")

            # Native Windows popup
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)

            messagebox.showwarning(
                "AI Job Hunter",
                "Manual intervention required!\n\n"
                "Please complete the missing fields in the browser.\n\n"
                "When finished, close this dialog and press ENTER in the terminal."
            )

            root.destroy()

            self.console.print("")
            self.console.print("[cyan]Please complete the form in the browser.[/cyan]")
            input("Press ENTER when you're ready to continue... ")

            page.wait_for_timeout(500)

    @abstractmethod
    def check_apply_button(self, page: Page) -> str:
        pass

    @abstractmethod
    def get_job_description(self, page: Page) -> str:
        pass

    @abstractmethod
    def click_apply(self, page: Page):
        pass

    @abstractmethod
    def upload_resume(self,page: Page,resume_path: str):
        pass

    @abstractmethod
    def write_cover_letter(self, page: Page, body: str = ""):
        pass

    @abstractmethod
    def fill_known_fields(
        self,
        page: Page,
        cfg: dict,
    ):
        pass

    @abstractmethod
    def fill_select_questions(
        self,
        page: Page,
    ):
        pass

    @abstractmethod
    def answer_yes_questions(
        self,
        page: Page,
    ):
        pass

    @abstractmethod
    def click_continue(
        self,
        page: Page,
    ) -> bool:
        pass

    @abstractmethod
    def click_next(
        self,
        page: Page,
    ) -> bool:
        pass

    @abstractmethod
    def click_submit(
        self,
        page: Page,
    ) -> bool:
        pass

    @abstractmethod
    def check_for_errors(self, page: Page) -> bool :
        pass