import time

from pathlib import Path
from playwright.sync_api import Page, TimeoutError

from Database.JobRepository import JobRepository
from Appliers.BaseApplier import BaseApplier
from Constants import JobStatus
from Models import JobObject


class LinkedInApplier(BaseApplier):
    MODAL_SELECTOR = "div.jobs-easy-apply-modal"
    def __init__(self, repository: JobRepository, cfg: dict):
        super().__init__(repository, cfg)
        # check already applied
        # check fill out things

    def run_apply_step(self, page: Page, job: JobObject, resume: str,
                       steps: int = 20, error_intervein: bool = False) -> str:
        for step in range(steps):
            page.locator('[role="dialog"]').wait_for(state="visible",timeout=10000)
            if step == 0:
                self.console.print(f"[cyan]{self.app} using {resume}...[/cyan]")
                self.click_button(page, selectors=[
                    "[data-easy-apply-next-button]",
                ])
                self.upload_resume(page, resume)
                self.write_cover_letter(page, "")
            else:
                if not self.fill_form(page, threshold=90):
                    break

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

    def verify_job_item(self, page: Page, job: JobObject):
        is_already_applied, status = self._check_already_applied(page, job)
        if is_already_applied:
            return False, status
        status, self.apply_btn = self.check_apply_button(
            page,
            selector= "[aria-label*='Apply']",
            expected_text="Easy Apply"
        )
        return self._is_quick_apply(status, job)

    def is_already_applied(self, page: Page, timeout: float = 5.0) -> bool:
        old_locator = page.locator("#applied-date-message").get_by_text(
            "You applied", exact=False
        )

        new_locator = page.get_by_role("heading", name="Application status") \
            .locator("xpath=ancestor::div[1]/following-sibling::div") \
            .get_by_text("Application submitted", exact=False)

        end_time = time.time() + timeout

        while time.time() < end_time:
            if old_locator.count() > 0 or new_locator.count() > 0:
                return True
            time.sleep(0.2)

        return False

    def fill_form(self, page: Page, threshold: int = 90) -> bool:
        self.console.print(f'{self.app} AI filling out form...')
        modal = page.locator(self.MODAL_SELECTOR).first

        questions = []
        field_map = {}

        #
        # -----------------------------
        # Text / Numeric inputs
        # -----------------------------
        #
        text_inputs = modal.locator(
            "input[type='text'], input[type='number']"
        )

        for i in range(text_inputs.count()):
            field = text_inputs.nth(i)

            try:
                if not field.is_visible():
                    continue

                field_id = field.get_attribute("id")

                if not field_id:
                    continue

                # Skip already answered fields
                current_value = (field.input_value() or "").strip()
                if current_value:
                    continue

                label = modal.locator(f"label[for='{field_id}']").first

                question = (label.inner_text() or "").strip()

                if not question:
                    continue

                questions.append({
                    "id": field_id,
                    "type": "text",
                    "question": question,
                })

                field_map[field_id] = field

            except Exception:
                continue

        #
        # -----------------------------
        # Select dropdowns
        # -----------------------------
        #
        selects = modal.locator("select")

        for i in range(selects.count()):
            select = selects.nth(i)

            try:
                if not select.is_visible():
                    continue

                select_id = select.get_attribute("id")

                if not select_id:
                    continue

                # Skip already answered dropdowns
                current_value = (select.input_value() or "").strip()
                if current_value and current_value.lower() != "select an option":
                    continue

                label = modal.locator(f"label[for='{select_id}']").first

                question = (label.inner_text() or "").strip()

                options = []

                option_nodes = select.locator("option")

                for j in range(option_nodes.count()):
                    text = option_nodes.nth(j).inner_text().strip()

                    if text.lower().startswith("select"):
                        continue

                    options.append(text)

                questions.append({
                    "id": select_id,
                    "type": "select",
                    "question": question,
                    "choices": options,
                })

                field_map[select_id] = select

            except Exception:
                continue

        #
        # -----------------------------
        # Radio buttons
        # -----------------------------
        #
        fieldsets = modal.locator("fieldset")

        for i in range(fieldsets.count()):
            fieldset = fieldsets.nth(i)

            try:
                legend = (
                    fieldset
                    .locator("legend")
                    .first
                    .inner_text()
                    .strip()
                )

                radios = fieldset.locator("input[type='radio']")

                # Skip already answered radio groups
                already_answered = False

                for j in range(radios.count()):
                    if radios.nth(j).is_checked():
                        already_answered = True
                        break

                if already_answered:
                    continue

                choices = []

                for j in range(radios.count()):
                    radio = radios.nth(j)

                    value = radio.get_attribute("value")

                    if value:
                        choices.append(value)

                field_id = f"radio_{i}"

                questions.append({
                    "id": field_id,
                    "type": "radio",
                    "question": legend,
                    "choices": choices,
                })

                field_map[field_id] = fieldset

            except Exception:
                continue

        # Nothing to answer
        if not questions:
            return True

        answers = self.ai_helper.answer_application_questions(questions)

        question_lookup = {
            q["id"]: q["question"]
            for q in questions
        }

        for answer in answers:
            if answer["confidence"] < threshold:
                self.console.print(
                    f"{self.app} ERROR! AI confidence only {answer['confidence']}% "
                    f"for question '{answer['id']}'"
                )
                return False

            field = field_map[answer["id"]]

            field_type = next(
                q["type"]
                for q in questions
                if q["id"] == answer["id"]
            )

            value = str(answer["answer"]).strip()

            #
            # Text
            #
            if field_type == "text":
                field.fill(value)

            #
            # Dropdown
            #
            elif field_type == "select":
                field.select_option(label=value)

            #
            # Radio
            #
            elif field_type == "radio":
                label = field.get_by_text(value, exact=True).first

                if label.count():
                    label.click()
                else:
                    radio = field.locator(
                        f"input[type='radio'][value='{value}']"
                    ).first
                    radio.check()

            question = question_lookup.get(answer["id"], "")

            self.console.print(
                f"[cyan]{self.app} Answer:[/cyan] {value} | [yellow]{question}[/yellow]"
            )
        self.console.print(
            f"[cyan]{self.app} Done filling out form... ----------------------------[/cyan]"
        )
        return True

    def write_cover_letter(self, page: Page, body: str = ""):
        pass

    def get_job_description(self, page: Page) -> str:
        try:
            # Expand the description if possible
            more_btn = page.locator("[data-testid='expandable-text-button']").first
            if more_btn.count() > 0 and more_btn.is_visible():
                try:
                    more_btn.click(timeout=1000)
                except Exception:
                    pass

            # Method 1: Existing logic (works on some page layouts)
            try:
                heading = page.get_by_text("About the job", exact=True)
                heading.wait_for(timeout=3000)

                description = heading.locator(
                    "xpath=ancestor::div[1]/following-sibling::p//span[@data-testid='expandable-text-box']"
                )

                if description.count() > 0:
                    text = description.first.inner_text().strip()
                    if text:
                        return text[:3000]
            except Exception:
                pass

            # Method 2: Locate by data-testid (works on most layouts)
            try:
                description = page.locator(
                    "[data-testid='expandable-text-box']"
                ).first

                description.wait_for(timeout=3000)

                text = description.inner_text().strip()
                if text:
                    return text[:3000]
            except Exception:
                pass

            # Method 3: Relative to the H2
            try:
                description = page.locator(
                    "//h2[normalize-space()='About the job']"
                    "/following-sibling::p"
                    "//span[@data-testid='expandable-text-box']"
                ).first

                if description.count() > 0:
                    text = description.inner_text().strip()
                    if text:
                        return text[:3000]
            except Exception:
                pass

        except Exception:
            pass

        return ""

    def upload_resume(
            self,
            page: Page,
            resume_path: str,
    ):
        target_resume = Path(resume_path).name
        modal = page.locator(self.MODAL_SELECTOR).first

        #
        # 1. Is the correct resume already selected?
        #
        selected = modal.locator(
            ".jobs-document-upload-redesign-card__container--selected "
            ".jobs-document-upload-redesign-card__file-name"
        ).first

        if selected.count():
            selected_name = (selected.text_content() or "").strip()

            if selected_name == target_resume:
                return

        #
        # 2. Is the resume already uploaded?
        #
        cards = modal.locator(".jobs-document-upload-redesign-card__container")

        for i in range(cards.count()):
            card = cards.nth(i)

            filename = (
                    card.locator(".jobs-document-upload-redesign-card__file-name")
                    .text_content() or ""
            ).strip()

            if filename != target_resume:
                continue

            # Select this resume
            card.click()
            page.wait_for_timeout(500)
            return

        #
        # 3. Upload new resume
        #
        upload = modal.locator("input[type='file']").first

        if upload.count() == 0:
            raise RuntimeError("Resume upload input not found.")

        upload.set_input_files(str(Path(resume_path).resolve()))

        #
        # 4. Wait until it appears
        #
        modal.locator(
            f".jobs-document-upload-redesign-card__file-name:text-is('{target_resume}')"
        ).wait_for(timeout=10000)

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
        try:
            button = page.locator("[data-easy-apply-next-button]").first
            button.wait_for(state="visible", timeout=5000)
            button.click()
            return True

        except TimeoutError:
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