from playwright.sync_api import BrowserContext

from Authentication.BaseAuth import BaseSessionManager


class JobStreetSessionManager(BaseSessionManager):
    def __init__(self):
        super().__init__(
            session_dir="Sessions",
            session_file="jobstreet.json",
            home_url="https://sg.jobstreet.com",
        )

    def ensure_logged_in(self, context: BrowserContext) -> None:
        if self.session_file.exists():
            return

        page = context.new_page()
        page.goto(self.home_url)

        print("\n" + "=" * 60)
        print("MANUAL LOGIN REQUIRED")
        print("=" * 60)
        print("1. Log in to JobStreet.")
        print("2. Complete OTP/CAPTCHA if prompted.")
        print("3. Wait until the homepage is fully loaded.")
        print("=" * 60)

        input("[SESSION] Press ENTER after logging in...")

        context.storage_state(path=str(self.session_file))
        print(f"[SESSION] Session saved to {self.session_file}")

        page.close()