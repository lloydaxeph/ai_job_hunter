from abc import ABC, abstractmethod
import tkinter as tk
from tkinter import messagebox

from playwright.sync_api import Page, TimeoutError, Locator

from Config import pick_resume
from Constants import JobStatus
from Database.JobRepository import JobRepository
from Logger import ConsoleManager
from Models.JobObject import JobObject
from AIHelpers.OpenAI import AIHelper


class BaseApplier(ABC):
    def __init__(self, repository: JobRepository, cfg: dict):
        self.app = "[Applier]"
        self.repository = repository
        self.console = ConsoleManager().instance
        self.cfg = cfg
        self.ai_helper = AIHelper(cfg)
        self.score_threshold = cfg["ai"]["score_threshold"]

        self.apply_btn = None

    def _score_job(self, page: Page, job: JobObject) -> JobObject:
        jd = self.get_job_description(page)
        if jd:
            job.description = jd
        else:
            raise Exception("Job has no description.")
        self.repository.update_description(job_id=job.job_id, description=job.description)
        ai_score = self.ai_helper.score_job(job.to_dict())
        job.score = ai_score.get("score", 0)
        self.repository.update_score(job_id=job.job_id, score=job.score)
        return job

    def _open_job_item(self, page: Page, job: JobObject):
        self.console.print(f"[cyan]{self.app} Opening {job.title} @ {job.company}...[/cyan]")
        page.goto(job.url, wait_until="domcontentloaded", timeout=30000)
        #page.wait_for_load_state("networkidle")

    def _check_already_applied(self, page: Page, job: JobObject):
        if self.is_already_applied(page):
            status = JobStatus.APPLIED
            self.console.print(f"[red]{self.app} FAILED: You already applied to this job.[/red]")
            self.repository.update_status(job_id=job.job_id, status=status)
            return True, status
        return False, None

    def _score_and_match_job(self, page: Page, job: JobObject):
        job = self._score_job(page, job)
        if job.score >= self.score_threshold:
            self.console.print(f"{self.app} MATCHED! Score:{job.score} ")
            self.click_apply()

            resume = pick_resume(job.title, self.cfg)
            status = self.run_apply_step(page, job, resume)
            return status
        else:
            self.console.print(f"{self.app} DID NOT MATCH! Score:{job.score} ")
            status = JobStatus.DID_NOT_MATCH
            self.repository.update_status(job_id=job.job_id, status=status)
            return status

    def _apply_timeout(self, job: JobObject) -> str:
        self.console.print(f"[red]{self.app} FAILED! Cannot apply to {job.title} @ {job.company} due to timeout.[/red]")
        status = JobStatus.FAILED
        self.repository.update_status(job_id=job.job_id, status=status)
        return status

    def _apply_exception(self, job: JobObject, e: Exception) -> str:
        self.console.print(f"[red]{self.app} FAILED! Cannot apply to {job.title} @ {job.company}: {e}.[/red]")
        status = JobStatus.FAILED
        self.repository.update_status(job_id=job.job_id, status=status)
        return status

    def _is_quick_apply(self, status: str, job: JobObject):
        if status != "Quick Apply":
            self.console.print(f"[red]{self.app} FAILED: Job status = {status}[/red]")
            self.repository.update_status(job_id=job.job_id, status=status)
            return False, status
        self.console.print(f"[cyan]{self.app} Confirmed that job is Quick Apply.[/cyan]")
        return True, None

    def apply(self, page: Page, job: JobObject) -> str:
        try:
            self._open_job_item(page, job)
            is_quick_apply, status = self.verify_job_item(page, job)
            if not is_quick_apply:
                return status

            is_already_applied, status = self._check_already_applied(page, job)
            if is_already_applied:
                return status

            status = self._score_and_match_job(page, job)
            return status

        except TimeoutError:
            return self._apply_timeout(job)

        except Exception as e:
            return self._apply_exception(job, e)

    def manual_apply(self, page: Page, job: JobObject) -> str:
        try:
            self._open_job_item(page, job)
            self.click_apply()
            is_already_applied, status = self._check_already_applied(page, job)
            if is_already_applied:
                return status
            page.wait_for_load_state("networkidle")

            resume = pick_resume(job.title, self.cfg)
            status = self.run_apply_step(page, job, resume,
                                         steps=10, error_intervein=True)
            return status

        except TimeoutError:
            return self._apply_timeout(job)

        except Exception as e:
            return self._apply_exception(job, e)

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

    def submit_success(self, job: JobObject, resume: str) -> str:
        self.console.print(f"[cyan]{self.app} JOB APPLIED![/cyan]")
        status = JobStatus.APPLIED
        self.repository.update_status(job_id=job.job_id, status=status)
        self.repository.update_resume_used(job_id=job.job_id, resume_used=resume)
        return status

    def check_apply_button(self, page: Page, selector: str, expected_text: str = None) -> (str, Locator):
        apply_btn = page.locator(selector).first
        try:
            apply_btn.wait_for(state="visible", timeout=8000)
        except TimeoutError:
            print("[APPLIER] ERROR!: Can't find Apply button.")
            return JobStatus.NOT_QUICK_APPLY, None
        if expected_text is not None:
            if apply_btn.inner_text().strip().lower() != expected_text.lower():
                return JobStatus.NOT_QUICK_APPLY, None
        return "Quick Apply", apply_btn

    def click_apply(self):
        if self.apply_btn:
            self.apply_btn.click()
        else:
            raise Exception(f"{self.app} ERROR! There's no apply button")

    def click_button(self, page: Page, selectors: list[str]) -> bool:
        for selector in selectors:
            button = page.locator(selector).locator("visible=true").first
            if button.count():
                button.scroll_into_view_if_needed(timeout=5000)
                button.click(timeout=5000)
                return True
        return False

    @abstractmethod
    def verify_job_item(self, page: Page, job: JobObject):
        pass

    @abstractmethod
    def is_already_applied(self, page: Page) -> bool:
        pass

    @abstractmethod
    def get_job_description(self, page: Page) -> str:
        pass

    @abstractmethod
    def upload_resume(self,page: Page,resume_path: str):
        pass

    @abstractmethod
    def write_cover_letter(self, page: Page, body: str = ""):
        pass

    @abstractmethod
    def fill_known_fields(self,page: Page, cfg: dict):
        pass

    @abstractmethod
    def fill_select_questions(self, page: Page):
        pass

    @abstractmethod
    def answer_yes_questions(self, page: Page):
        pass

    @abstractmethod
    def fill_form(self, page: Page) -> bool:
        pass

    @abstractmethod
    def click_next(self, page: Page) -> bool:
        pass

    @abstractmethod
    def click_submit(self, page: Page) -> bool:
        pass

    @abstractmethod
    def check_for_errors(self, page: Page) -> bool :
        pass

    @abstractmethod
    def run_apply_step(self, page: Page, job: JobObject, resume: str, steps: int = 20,
                       error_intervein: bool = False) -> str :
        pass