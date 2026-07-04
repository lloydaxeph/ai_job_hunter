from abc import ABC, abstractmethod
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext


class BaseSessionManager(ABC):
    def __init__(self, session_dir: str, session_file: str, home_url: str):
        self.session_dir = Path(session_dir)
        self.session_file = self.session_dir / session_file
        self.home_url = home_url

    def create_context(self, browser: Browser) -> BrowserContext:
        """Create a browser context using a saved session if available."""
        self.session_dir.mkdir(exist_ok=True)

        if self.session_file.exists():
            print(f"[SESSION] Loading existing session: {self.session_file.name}")
            return browser.new_context(storage_state=str(self.session_file))

        print("[SESSION] Creating new browser session...")
        return browser.new_context()

    def clear_session(self) -> None:
        """Delete the saved session."""
        if self.session_file.exists():
            self.session_file.unlink()
            print(f"[SESSION] Removed session: {self.session_file.name}")

    @abstractmethod
    def ensure_logged_in(self, context: BrowserContext) -> None:
        """Ensure the user is logged in."""
        pass