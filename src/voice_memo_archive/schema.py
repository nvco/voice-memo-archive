"""Generic, testable schema-version migration used by config.py and state.py.

Both `config.json` and `state.json` are currently at schema version 1 with
no migrations registered yet — there is no prior version to migrate from.
This module exists so that when a breaking change to either shape does
happen, it plugs into an already-tested migration chain instead of a
one-off, unverified upgrade path.
"""

from __future__ import annotations

from collections.abc import Callable

MigrationFn = Callable[[dict], dict]


def migrate(
    data: dict,
    *,
    current_version: int,
    migrations: dict[int, MigrationFn],
) -> dict:
    """Apply registered migrations until `data` reaches `current_version`.

    `migrations[v]` transforms a dict at schema_version `v` into one at
    `v + 1`; it must not set `schema_version` itself — this function does,
    so a migration can't forget the bump.
    """
    version = data.get("schema_version")
    if not isinstance(version, int):
        raise ValueError("missing or non-integer schema_version")
    if version > current_version:
        raise ValueError(f"schema_version {version} is newer than supported {current_version}")

    data = dict(data)
    while version < current_version:
        migration = migrations.get(version)
        if migration is None:
            raise ValueError(f"no migration registered from schema_version {version}")
        data = migration(data)
        version += 1
        data["schema_version"] = version
    return data
