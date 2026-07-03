from pathlib import Path

from playwright.sync_api import Page

from Database.JobRepository import JobRepository
from Appliers.BaseApplier import BaseApplier
from Constants import JobStatus


class JobStreetApplier(BaseApplier):
    def __init__(self, repository: JobRepository, cfg: dict):
        super().__init__(repository, cfg)

    def check_apply_button(self, page: Page) -> str:
        apply_btn = page.locator("[data-automation='job-detail-apply']").first
        if apply_btn.count() == 0:
            return JobStatus.REQUIRES_MANUAL_REVIEW

        if apply_btn.inner_text().strip().lower() != "quick apply":
            return JobStatus.NOT_QUICK_APPLY
        return "Quick Apply"

    def get_job_description(self, page: Page) -> str:
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

    def click_apply(self, page: Page):
        page.locator(
            "[data-automation='job-detail-apply']"
        ).first.click()

    def upload_resume(
        self,
        page: Page,
        resume_path: str,
    ):
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

    def write_cover_letter(
            self,
            page: Page,
            body: str = "",
    ):
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

    def fill_known_fields(
        self,
        page: Page,
        cfg: dict,
    ):
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

    def fill_select_questions(
        self,
        page: Page,
    ):
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

    def click_continue(
        self,
        page: Page,
    ) -> bool:
        button = page.locator(
            "[data-testid='continue-button']"
        ).first

        if not button.count():
            return False

        button.scroll_into_view_if_needed()
        button.click()

        return True

    def click_next(
        self,
        page: Page,
    ) -> bool:
        button = page.locator(
            "button:has-text('Next')"
        ).first

        if not button.count():
            return False

        button.click()

        return True

    def click_submit(
        self,
        page: Page,
    ) -> bool:
        button = page.locator(
            """
            button[type='submit'],
            button:has-text('Submit application')
            """
        ).first

        if not button.count():
            return False

        button.scroll_into_view_if_needed()
        button.click()

        return True