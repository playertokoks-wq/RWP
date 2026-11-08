import json
import logging
import os
from pathlib import Path

import config

log = logging.getLogger("rwp-bot.storage")


class Store:
    """Prosty magazyn JSON (słownik zapisywany na dysk po każdej zmianie)."""

    def __init__(self, name: str):
        Path(config.DATA_DIR).mkdir(parents=True, exist_ok=True)
        self.path = Path(config.DATA_DIR) / f"{name}.json"
        self.data: dict = {}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                log.exception("Uszkodzony plik %s, tworzę kopię i zaczynam od nowa", self.path)
                self.path.rename(self.path.with_suffix(".broken"))
                self.data = {}

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)
