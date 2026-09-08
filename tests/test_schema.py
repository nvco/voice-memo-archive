import pytest

from voice_memo_archive.schema import migrate


def test_migrate_noop_when_already_current():
    data = {"schema_version": 2, "x": 1}
    result = migrate(data, current_version=2, migrations={})
    assert result == data


def test_migrate_applies_chain_in_order():
    def v1_to_v2(d: dict) -> dict:
        d = dict(d)
        d["y"] = d.pop("x") * 10
        return d

    def v2_to_v3(d: dict) -> dict:
        d = dict(d)
        d["z"] = d["y"] + 1
        return d

    data = {"schema_version": 1, "x": 5}
    result = migrate(data, current_version=3, migrations={1: v1_to_v2, 2: v2_to_v3})
    assert result == {"schema_version": 3, "y": 50, "z": 51}


def test_migrate_rejects_future_version():
    with pytest.raises(ValueError):
        migrate({"schema_version": 5}, current_version=1, migrations={})


def test_migrate_rejects_missing_migration():
    with pytest.raises(ValueError):
        migrate({"schema_version": 1}, current_version=2, migrations={})


def test_migrate_rejects_missing_schema_version():
    with pytest.raises(ValueError):
        migrate({}, current_version=1, migrations={})
