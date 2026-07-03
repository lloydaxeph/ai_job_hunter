from __future__ import annotations
from rich.console import Console
import logging


class Logger:
    def __init__(self) -> None:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )

        self._logger = logging.getLogger(__name__)

    @property
    def instance(self) -> logging.Logger:
        return self._logger


class ConsoleManager:
    def __init__(self) -> None:
        self._console = Console()

    @property
    def instance(self) -> Console:
        return self._console