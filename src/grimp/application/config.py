from __future__ import annotations

from typing import Any


class Settings:
    def __init__(self) -> None:
        self._config: dict[str, Any] = {}

    def configure(self, **config_dict: Any) -> None:
        self._config.update(config_dict)

    def __getattr__(self, name: str) -> Any:
        if name[:2] != "__":
            return self._config[name]
        return super().__getattribute__(name)


settings = Settings()
