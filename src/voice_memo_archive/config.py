"""`config.json`: versioned user settings.

Per AGENTS.md, `config.json` holds user settings (as opposed to `state.py`'s
operational/retry data). A missing file is not an error — it means defaults,
so settings survive a state reset or a fresh checkout.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .errors import ConfigError, ErrorCategory
from .io_utils import atomic_write
from .paths import redact_home_path
from .schema import MigrationFn, migrate

CURRENT_SCHEMA_VERSION = 1

# Confirmed by real-sample inspection in
# tasks/005-platform-feasibility-and-data-contract.md.
DEFAULT_RECORDINGS_SOURCE = (
    "~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings"
)
# Recorded in tasks/000-initial-build.md's Plan history.
DEFAULT_ARCHIVE_ROOT = "~/Documents/Voice Memo Archive"

# No migrations exist yet — schema_version has always been 1. Registered
# here so a future bump has a tested chain to join (see schema.py).
_MIGRATIONS: dict[int, MigrationFn] = {}


@dataclass(frozen=True)
class Config:
    schema_version: int = CURRENT_SCHEMA_VERSION
    recordings_source: str = DEFAULT_RECORDINGS_SOURCE
    archive_root: str = DEFAULT_ARCHIVE_ROOT

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Config:
        try:
            migrated = migrate(data, current_version=CURRENT_SCHEMA_VERSION, migrations=_MIGRATIONS)
            return cls(
                schema_version=migrated["schema_version"],
                recordings_source=migrated["recordings_source"],
                archive_root=migrated["archive_root"],
            )
        except (KeyError, ValueError) as exc:
            raise ConfigError(ErrorCategory.CONFIG_INVALID, str(exc)) from exc


def load_config(path: Path) -> Config:
    if not path.exists():
        return Config()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(
            ErrorCategory.CONFIG_INVALID,
            "config.json could not be read or parsed",
            detail={"path": redact_home_path(path)},
        ) from exc
    if not isinstance(raw, dict):
        raise ConfigError(
            ErrorCategory.CONFIG_INVALID,
            "config.json did not contain a JSON object",
            detail={"path": redact_home_path(path)},
        )
    return Config.from_dict(raw)


def save_config(path: Path, config: Config) -> None:
    atomic_write(path, json.dumps(config.to_dict(), indent=2, sort_keys=True) + "\n")
