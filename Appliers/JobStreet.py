import time

from pathlib import Path
from playwright.sync_api import Page

from Database.JobRepository import JobRepository
from Appliers.BaseApplier import BaseApplier
from Constants import JobStatus
from Models import JobObject


class JobStreetApplier(BaseApplier):
    def __init__(self, repository: JobRepository, cfg: dict):
        super().__init__(repository, cfg)

    def run_apply_step(self, page: Page, job: JobObject, resume: str,
                       steps: int = 20, error_intervein: bool = False) -> str:
        for step in range(steps):
            if step == 0:
                self.console.print(f"[cyan]{self.app} using {resume}...[/cyan]")
                self.handle_aus_work_rights_popup(page)
                self.upload_resume(page, resume)
                self.write_cover_letter(page, "")
            else:
                self.fill_form(page, threshold=90)
                if self.check_for_errors(page):
                    if error_intervein:
                        self.wait_for_manual_intervention(page)
                    else:
                        break

            if self.click_button(page, selectors=[
                "[data-testid='continue-button']",
                "button:has-text('Next')",
            ]):
                page.wait_for_load_state("networkidle")
                continue

            if self.click_submit(page):
                page.wait_for_timeout(3000)
                return self.submit_success(job, resume)

            status = JobStatus.REQUIRES_MANUAL_REVIEW
            self.repository.update_status(job_id=job.job_id, status=status)
            self.console.print(f"[cyan]{self.app} FAILED! Job needs manual review[/cyan]")
            return status

        status = JobStatus.REQUIRES_MANUAL_REVIEW
        self.repository.update_status(job_id=job.job_id, status=status)
        self.console.print(f"[cyan]{self.app} FAILED! Job needs manual review[/cyan]")
        return status

    def handle_aus_work_rights_popup(self, page: Page, timeout: float = 3.0, poll_interval: float = 0.25) -> bool:
        """
            Wait briefly for the work rights popup to appear.
            If found, click 'I require sponsorship to work for a new employer'.

            Returns:
                True if the popup was found and handled.
                False if the popup never appeared.
            """
        self.console.print(f"{self.app} Waiting for work rights popup.")
        popup = page.get_by_text(
            "Verify your work rights to continue applying",
            exact=False,
        )

        end_time = time.time() + timeout

        while time.time() < end_time:
            if popup.count() > 0:
                page.get_by_role(
                    "button",
                    name="I require sponsorship to work for a new employer",
                ).click()
                return True

            time.sleep(poll_interval)
        return False

    def fill_form(self, page: Page, threshold: int = 90):
        form = page.locator("form").first

        questions = []
        field_map = {}

        #
        # -----------------------------
        # Text / Number / Textarea
        # -----------------------------
        #
        text_inputs = form.locator(
            "input[type='text'], input[type='number'], textarea"
        )

        for i in range(text_inputs.count()):
            field = text_inputs.nth(i)

            try:
                if not field.is_visible():
                    continue

                field_id = field.get_attribute("id")

                if not field_id:
                    continue

                # Skip already answered
                current_value = (field.input_value() or "").strip()
                if current_value:
                    continue

                label = form.locator(f"label[for='{field_id}']").first

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
        # Selects
        # -----------------------------
        #
        selects = form.locator("select")

        for i in range(selects.count()):
            select = selects.nth(i)

            try:
                if not select.is_visible():
                    continue

                select_id = select.get_attribute("id")

                if not select_id:
                    continue

                # Skip already answered
                current_value = (select.input_value() or "").strip()

                if current_value:
                    continue

                label = form.locator(f"label[for='{select_id}']").first

                question = (label.inner_text() or "").strip()

                if not question:
                    continue

                options = []

                option_nodes = select.locator("option")

                for j in range(option_nodes.count()):
                    option = option_nodes.nth(j)

                    text = option.inner_text().strip()

                    if not text:
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
        # Radio Groups
        # -----------------------------
        #
        fieldsets = form.locator("fieldset")

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

                if not legend:
                    continue

                radios = fieldset.locator("input[type='radio']")

                # Skip already answered
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

                    radio_id = radio.get_attribute("id")

                    if not radio_id:
                        continue

                    label = fieldset.locator(
                        f"label[for='{radio_id}']"
                    ).first

                    text = (label.inner_text() or "").strip()

                    if text:
                        choices.append(text)

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

        #
        # Nothing to answer
        #
        if not questions:
            return True

        answers = self.ai_helper.answer_application_questions(questions)

        question_lookup = {
            q["id"]: q["question"]
            for q in questions
        }

        #
        # Fill answers
        #
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
            # Text / Number / Textarea
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
                try:
                    field.get_by_label(value, exact=True).check()
                except Exception:
                    field.get_by_text(value, exact=True).click()

            question = question_lookup.get(answer["id"], "")

            self.console.print(
                f"[cyan]Answer:[/cyan] {value} | [yellow]{question}[/yellow]"
            )
        self.console.print(
            f"[cyan]{self.app} Done filling out form... ----------------------------[/cyan]"
        )
        return True

    def verify_job_item(self, page: Page, job: JobObject):
        status, self.apply_btn = self.check_apply_button(
            page,
            selector="[data-automation='job-detail-apply']",
            expected_text="Quick Apply",
        )
        return self._is_quick_apply(status, job)

    def is_already_applied(self, page: Page, timeout: float = 5.0) -> bool:
        locator = page.locator("#applied-date-message").get_by_text(
            "You applied", exact=False
        )
        end_time = time.time() + timeout

        while time.time() < end_time:
            if locator.count() > 0:
                return True
            time.sleep(0.2)

        return False

    def get_job_description(self, page: Page) -> str:
        try:
            selectors = (
                "[data-automation='jobAdDetails']",  # JobStreet
                "[data-testid='jobDescription']",
                "#job-details",
                ".jobsearch-jobDescriptionText",
                ".description__text",
            )
            for selector in selectors:
                element = page.query_selector(selector)
                if element:
                    text = element.inner_text().strip()
                    if text:
                        return text[:3000]
            return page.locator("body").inner_text().strip()[:3000]
        except Exception:
            return ""

    def upload_resume(self, page: Page, resume_path: str):
        target_resume = Path(resume_path).name
        resume_container = page.locator("[data-testid='resumeSelectInput']")
        resume_container.wait_for(timeout=10000)

        select = resume_container.locator("select[data-testid='select-input']")
        select.wait_for(timeout=10000)

        if select.count():
            options = select.locator("option")
            for i in range(options.count()):
                option = options.nth(i)
                text = (option.text_content() or "").strip()

                if not text or text == "Please select a resumé":
                    continue

                if target_resume in text:
                    value = option.get_attribute("value")

                    select.select_option(value=value)
                    page.wait_for_timeout(500)
                    return

        upload = page.locator("input[type='file']").first

        if not upload.count():
            raise RuntimeError("Resume upload input not found.")

        upload.set_input_files(str(Path(resume_path).resolve()))

        page.wait_for_timeout(1000)

        page.wait_for_function(
            """(filename) => {
                const select = document.querySelector(
                    "select[data-testid='select-input']"
                );

                if (!select) return false;

                return Array.from(select.options)
                    .some(o => (o.textContent || '').includes(filename));
            }""",
            arg=target_resume,
            timeout=15000,
        )

        options = select.locator("option")

        for i in range(options.count()):
            option = options.nth(i)
            text = (option.text_content() or "").strip()

            if target_resume in text:
                value = option.get_attribute("value")
                select.select_option(value=value)
                page.wait_for_timeout(500)
                return

        raise RuntimeError(f"Unable to upload/select resume: {target_resume}" )

    def write_cover_letter(self, page: Page, body: str = ""):
        option = page.locator(
            "[data-testid='coverLetter-method-none']"
        ).first

        option.wait_for(timeout=10000)

        if not body or not body.strip():
            option.check()
            page.wait_for_timeout(500)
            return

        # TODO: Implement custom cover letter.
        pass

    def fill_known_fields(self, page: Page, cfg: dict):
        personal = cfg["personal"]
        credentials = cfg["credentials"]

        values = {
            "email": credentials["jobstreet_email"],
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

        for key, value in values.items():
            if not value:
                continue

            locator = page.locator(
                f"""
                input[name*="{key}" i],
                input[id*="{key}" i],
                input[placeholder*="{key}" i]
                """
            ).first

            try:
                if locator.is_visible():
                    locator.fill(value)
            except Exception:
                continue

    def fill_select_questions(self, page: Page):
        selects = page.locator("select")

        for i in range(selects.count()):
            select = selects.nth(i)

            try:
                options = select.locator("option")

                for j in range(options.count()):
                    option = options.nth(j)
                    text = option.inner_text().lower()

                    if "more than 5 years" in text:
                        value = option.get_attribute("value")

                        if value:
                            select.select_option(value=value)

                        break

            except Exception:
                continue

    def answer_yes_questions(self, page: Page):
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
        }

        fieldsets = page.locator("fieldset")

        for i in range(fieldsets.count()):
            fieldset = fieldsets.nth(i)

            try:
                question = (
                    fieldset
                    .locator("legend")
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
        error_panel = page.locator("#errorPanel")

        return (
                error_panel.count() > 0
                and error_panel.is_visible()
        )

    def click_next(self, page: Page) -> bool:
        selectors = [
            "[data-testid='continue-button']",
            "button:has-text('Next')",
        ]

        for selector in selectors:
            button = page.locator(selector).locator("visible=true").first

            if button.count():
                button.scroll_into_view_if_needed(timeout=5000)
                button.click(timeout=5000)
                return True

        return False



    def click_submit(self, page: Page) -> bool:
        button = page.locator(
            "button[type='submit'], button:has-text('Submit application')"
        ).locator("visible=true").first

        if not button.count():
            return False

        button.scroll_into_view_if_needed(timeout=5000)
        button.click(timeout=5000)
        return True