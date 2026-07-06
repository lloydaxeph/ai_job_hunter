from pathlib import Path

from playwright.sync_api import Page, TimeoutError

from Database.JobRepository import JobRepository
from Appliers.BaseApplier import BaseApplier
from Constants import JobStatus
from Models import JobObject


class LinkedInApplier(BaseApplier):
    """
    Applier for LinkedIn's "Easy Apply" flow.

    Unlike JobStreet, LinkedIn's application flow happens inside a modal
    dialog (`div.jobs-easy-apply-modal`) that is paginated with
    Next / Review / Submit buttons rather than full page navigations.
    """

    MODAL_SELECTOR = "div.jobs-easy-apply-modal"

    def __init__(self, repository: JobRepository, cfg: dict):
        super().__init__(repository, cfg)

    # ------------------------------------------------------------------ #
    # Core apply loop
    # ------------------------------------------------------------------ #
    def run_apply_step(self, page: Page, job: JobObject, resume: str,
                       steps: int = 20, error_intervein: bool = False) -> str:
        for step in range(steps):
            if step == 0:
                self.console.print(f"[cyan]{self.app} using {resume}...[/cyan]")
                self.upload_resume(page, resume)
                self.write_cover_letter(page, "")
            else:
                self.fill_known_fields(page, self.cfg)
                self.fill_select_questions(page)
                self.answer_yes_questions(page)
                if self.check_for_errors(page):
                    if error_intervein:
                        self.wait_for_manual_intervention(page)
                    else:
                        break

            if self.click_continue(page):
                page.wait_for_timeout(1000)
                continue

            if self.click_next(page):
                page.wait_for_timeout(1000)
                continue

            if self.click_submit(page):
                page.wait_for_timeout(3000)
                self.console.print(f"[cyan]{self.app} JOB APPLIED![/cyan]")
                status = JobStatus.APPLIED
                self.repository.update_status(job_id=job.job_id, status=status)
                self.repository.update_resume_used(job_id=job.job_id, resume_used=resume)
                self._dismiss_post_apply_modal(page)
                return status

            status = JobStatus.REQUIRES_MANUAL_REVIEW
            self.repository.update_status(job_id=job.job_id, status=status)
            self.console.print(f"[cyan]{self.app} FAILED! Job needs manual review[/cyan]")
            return status

        status = JobStatus.REQUIRES_MANUAL_REVIEW
        self.repository.update_status(job_id=job.job_id, status=status)
        self.console.print(f"[cyan]{self.app} FAILED! Job needs manual review[/cyan]")
        return status

    # ------------------------------------------------------------------ #
    # Apply-button / status checks
    # ------------------------------------------------------------------ #
    def check_apply_button(self, page: Page) -> str:
        apply_btn = page.locator(
            "button.jobs-apply-button"
        ).locator("visible=true").first

        try:
            apply_btn.wait_for(state="visible", timeout=8000)
        except TimeoutError:
            print("[APPLIER] ERROR!: Can't find Apply button.")
            return JobStatus.REQUIRES_MANUAL_REVIEW

        label = apply_btn.inner_text().strip().lower()

        if "easy apply" not in label:
            return JobStatus.NOT_QUICK_APPLY

        return "Quick Apply"

    def get_job_description(self, page: Page) -> str:
        selectors = (
            "#job-details",
            ".jobs-description__content",
            ".jobs-box__html-content",
            ".jobs-description-content__text",
        )

        for selector in selectors:
            element = page.query_selector(selector)

            if element:
                text = element.inner_text().strip()

                if text:
                    return text[:3000]

        return page.locator("body").inner_text().strip()[:3000]

    def click_apply(self, page: Page):
        page.locator(
            "button.jobs-apply-button"
        ).first.click()

        page.locator(self.MODAL_SELECTOR).first.wait_for(
            state="visible", timeout=10000
        )

    # ------------------------------------------------------------------ #
    # Resume / cover letter
    # ------------------------------------------------------------------ #
    def upload_resume(
        self,
        page: Page,
        resume_path: str,
    ):
        target_resume = Path(resume_path).name
        modal = page.locator(self.MODAL_SELECTOR).first

        # LinkedIn shows a list of previously-uploaded resumes as selectable
        # cards, each with the filename in a title/span element.
        resume_cards = modal.locator("[data-test-resume-title], .jobs-document-upload-redesign-card__file-name")

        if resume_cards.count():
            for i in range(resume_cards.count()):
                card = resume_cards.nth(i)
                text = (card.text_content() or "").strip()

                if target_resume in text:
                    card.click()
                    page.wait_for_timeout(500)
                    return

        # Otherwise, upload a new resume via the hidden file input.
        upload = modal.locator("input[type='file']").first

        if not upload.count():
            raise RuntimeError("Resume upload input not found.")

        upload.set_input_files(str(Path(resume_path).resolve()))
        page.wait_for_timeout(1500)

        try:
            modal.locator(
                f"text={target_resume}"
            ).first.wait_for(state="visible", timeout=10000)
        except TimeoutError:
            # Some LinkedIn variants auto-select the newly uploaded resume
            # without surfacing its filename anywhere else in the DOM.
            pass

    def write_cover_letter(
        self,
        page: Page,
        body: str = "",
    ):
        modal = page.locator(self.MODAL_SELECTOR).first

        textarea = modal.locator(
            "textarea[id*='coverLetter' i], textarea[name*='coverLetter' i]"
        ).first

        if not textarea.count():
            return

        try:
            if not textarea.is_visible():
                return
        except Exception:
            return

        if not body or not body.strip():
            return

        # TODO: Implement custom cover letter.
        textarea.fill(body)
        page.wait_for_timeout(300)

    # ------------------------------------------------------------------ #
    # Field / question filling
    # ------------------------------------------------------------------ #
    def fill_known_fields(
        self,
        page: Page,
        cfg: dict,
    ):
        personal = cfg["personal"]
        credentials = cfg["credentials"]

        values = {
            "email": credentials.get("linkedin_email", ""),
            "phone": personal["phone"],
            "linkedin": personal["linkedin"],
            "github": personal["github"],
            "portfolio": personal["portfolio"],
            "first": personal["first_name"],
            "last": personal["last_name"],
            "full_name": (
                f"{personal['first_name']} "
                f"{personal['last_name']}"
            ),
        }

        modal = page.locator(self.MODAL_SELECTOR).first

        for key, value in values.items():
            if not value:
                continue

            locator = modal.locator(
                f"""
                input[name*="{key}" i],
                input[id*="{key}" i],
                input[aria-label*="{key}" i]
                """
            ).first

            try:
                if locator.is_visible():
                    locator.fill(value)
            except Exception:
                continue

    def fill_select_questions(
        self,
        page: Page,
    ):
        modal = page.locator(self.MODAL_SELECTOR).first
        selects = modal.locator("select")

        for i in range(selects.count()):
            select = selects.nth(i)

            try:
                options = select.locator("option")

                for j in range(options.count()):
                    option = options.nth(j)
                    text = option.inner_text().lower()

                    if "more than 5 years" in text or "yes" in text:
                        value = option.get_attribute("value")

                        if value:
                            select.select_option(value=value)

                        break

            except Exception:
                continue

        # Numeric "years of experience" text inputs are common on LinkedIn
        # and don't use <select> elements.
        number_inputs = modal.locator("input[type='text'][id*='numeric' i], input[type='number']")

        for i in range(number_inputs.count()):
            field = number_inputs.nth(i)

            try:
                if field.is_visible() and not (field.input_value() or "").strip():
                    field.fill("5")
            except Exception:
                continue

    def answer_yes_questions(
        self,
        page: Page,
    ):
        keywords = {
            "software",
            "developer",
            "development",
            "programming",
            "coding",
            "engineer",
            "ai",
            "artificial intelligence",
            "machine learning",
            "deep learning",
            "computer vision",
            "data science",
            "python",
            "java",
            "c#",
            "c++",
            "javascript",
            "typescript",
            "react",
            "angular",
            "vue",
            "django",
            "flask",
            "fastapi",
            ".net",
            "dotnet",
            "sql",
            "mongodb",
            "mysql",
            "postgres",
            "aws",
            "azure",
            "gcp",
            "docker",
            "kubernetes",
            "git",
            "github",
            "linux",
            "api",
            "backend",
            "frontend",
            "full stack",
            "devops",
            "cloud",
            "sponsorship",
            "authorized to work",
            "work authorization",
        }

        modal = page.locator(self.MODAL_SELECTOR).first
        fieldsets = modal.locator("fieldset")

        for i in range(fieldsets.count()):
            fieldset = fieldsets.nth(i)

            try:
                question = (
                    fieldset
                    .locator("legend, .fb-dash-form-element__label")
                    .first
                    .inner_text()
                    .lower()
                )

                if not any(
                    keyword in question
                    for keyword in keywords
                ):
                    continue

                labels = fieldset.locator("label")

                for j in range(labels.count()):
                    label = labels.nth(j)

                    if (
                        label.inner_text()
                        .strip()
                        .lower()
                        == "yes"
                    ):
                        label.click()
                        break

            except Exception:
                continue

    def check_for_errors(self, page: Page) -> bool:
        """Returns True if application validation errors are present."""
        modal = page.locator(self.MODAL_SELECTOR).first

        error_elements = modal.locator(
            ".artdeco-inline-feedback--error, [data-test-form-element-error-text]"
        )

        return error_elements.count() > 0 and error_elements.first.is_visible()

    # ------------------------------------------------------------------ #
    # Modal navigation buttons
    # ------------------------------------------------------------------ #
    def click_continue(
        self,
        page: Page,
    ) -> bool:
        # LinkedIn does not have a distinct "Continue" step separate from
        # "Next" / "Review" — this is a no-op kept only to satisfy the
        # BaseApplier contract.
        return False

    def click_next(
        self,
        page: Page,
    ) -> bool:
        modal = page.locator(self.MODAL_SELECTOR).first

        button = modal.locator(
            "button[aria-label='Continue to next step'], button[aria-label='Review your application']"
        ).locator("visible=true").first

        if not button.count():
            return False

        button.scroll_into_view_if_needed(timeout=5000)
        button.click(timeout=5000)

        return True

    def click_submit(self, page: Page) -> bool:
        modal = page.locator(self.MODAL_SELECTOR).first

        button = modal.locator(
            "button[aria-label='Submit application']"
        ).locator("visible=true").first

        if not button.count():
            return False

        button.scroll_into_view_if_needed(timeout=5000)
        button.click(timeout=5000)
        return True

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _dismiss_post_apply_modal(self, page: Page):
        """Close the 'Application sent' confirmation modal, if shown."""
        try:
            dismiss_btn = page.locator(
                "button[aria-label='Dismiss'], button[aria-label='Done']"
            ).locator("visible=true").first

            if dismiss_btn.count():
                dismiss_btn.click(timeout=3000)
        except Exception:
            pass