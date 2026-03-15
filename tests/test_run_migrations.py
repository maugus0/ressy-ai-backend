from pathlib import Path

import pytest
from mysql.connector import Error

from scripts import run_migrations


def _write_migration(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_classify_migrations_detects_applied_pending_and_mismatch(tmp_path: Path):
    first = _write_migration(tmp_path / "001_first.sql", "CREATE TABLE one (id INT);")
    second = _write_migration(tmp_path / "002_second.sql", "CREATE TABLE two (id INT);")

    applied = {
        first.name: run_migrations.calculate_checksum(first),
        second.name: "not-the-real-checksum",
    }

    plan = run_migrations.classify_migrations([first, second], applied)

    assert plan["applied"] == [first.name]
    assert plan["pending"] == []
    assert plan["mismatched"] == [second.name]


def test_resolve_baseline_target_requires_exact_filename(tmp_path: Path):
    files = [
        _write_migration(tmp_path / "001_first.sql", "SELECT 1;"),
        _write_migration(tmp_path / "002_second.sql", "SELECT 2;"),
    ]

    assert run_migrations.resolve_baseline_target(files, "002_second.sql") == 1

    with pytest.raises(run_migrations.MigrationError):
        run_migrations.resolve_baseline_target(files, "002")


def test_baseline_through_records_only_up_to_target(tmp_path: Path, monkeypatch):
    files = [
        _write_migration(tmp_path / "001_first.sql", "SELECT 1;"),
        _write_migration(tmp_path / "002_second.sql", "SELECT 2;"),
        _write_migration(tmp_path / "003_third.sql", "SELECT 3;"),
    ]
    recorded: list[tuple[str, str, int | None]] = []

    def fake_record(connection, filename, checksum, execution_time_ms):
        recorded.append((filename, checksum, execution_time_ms))

    monkeypatch.setattr(run_migrations, "record_applied_migration", fake_record)

    run_migrations.baseline_through(
        connection=object(),
        migration_files=files,
        applied_migrations={},
        target_filename="002_second.sql",
    )

    assert [item[0] for item in recorded] == ["001_first.sql", "002_second.sql"]
    assert all(item[2] is None for item in recorded)


def test_baseline_through_fails_on_recorded_checksum_mismatch(tmp_path: Path):
    first = _write_migration(tmp_path / "001_first.sql", "SELECT 1;")

    with pytest.raises(run_migrations.MigrationError):
        run_migrations.baseline_through(
            connection=object(),
            migration_files=[first],
            applied_migrations={first.name: "different-checksum"},
            target_filename=first.name,
        )


def test_apply_pending_migrations_skips_applied_and_records_pending(tmp_path: Path, monkeypatch):
    first = _write_migration(tmp_path / "001_first.sql", "SELECT 1;")
    second = _write_migration(tmp_path / "002_second.sql", "SELECT 2;")

    applied = {first.name: run_migrations.calculate_checksum(first)}
    executed: list[str] = []
    recorded: list[tuple[str, str, int | None]] = []

    def fake_run(connection, file_path):
        executed.append(file_path.name)
        return 42

    def fake_record(connection, filename, checksum, execution_time_ms):
        recorded.append((filename, checksum, execution_time_ms))

    monkeypatch.setattr(run_migrations, "run_migration_file", fake_run)
    monkeypatch.setattr(run_migrations, "record_applied_migration", fake_record)

    run_migrations.apply_pending_migrations(object(), [first, second], applied)

    assert executed == [second.name]
    assert recorded == [(second.name, run_migrations.calculate_checksum(second), 42)]


def test_apply_pending_migrations_fails_on_checksum_mismatch(tmp_path: Path):
    first = _write_migration(tmp_path / "001_first.sql", "SELECT 1;")

    with pytest.raises(run_migrations.MigrationError):
        run_migrations.apply_pending_migrations(
            connection=object(),
            migration_files=[first],
            applied_migrations={first.name: "different-checksum"},
        )


def test_get_connection_supports_mysql_env_aliases(monkeypatch):
    captured = {}

    def fake_connect(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.delenv("DB_HOST", raising=False)
    monkeypatch.delenv("DB_PORT", raising=False)
    monkeypatch.delenv("DB_USERNAME", raising=False)
    monkeypatch.delenv("DB_PASSWORD", raising=False)
    monkeypatch.setenv("MYSQL_HOST", "mysql-host")
    monkeypatch.setenv("MYSQL_PORT", "3307")
    monkeypatch.setenv("MYSQL_USER", "mysql-user")
    monkeypatch.setenv("MYSQL_PASSWORD", "mysql-pass")
    monkeypatch.setattr(run_migrations.mysql.connector, "connect", fake_connect)

    run_migrations.get_connection()

    assert captured == {
        "host": "mysql-host",
        "port": 3307,
        "user": "mysql-user",
        "password": "mysql-pass",
    }


def test_run_migration_file_tolerates_duplicate_style_recovery_errors(tmp_path: Path):
    migration = _write_migration(tmp_path / "001_first.sql", "SELECT 1; SELECT 2;")

    class FakeCursor:
        def __init__(self):
            self.executed = []
            self.calls = 0

        def execute(self, statement):
            self.calls += 1
            self.executed.append(statement)
            if self.calls == 1:
                raise Error(msg="Table already exists")

        def close(self):
            return None

    class FakeConnection:
        def __init__(self):
            self.cursor_obj = FakeCursor()
            self.commits = 0

        def cursor(self):
            return self.cursor_obj

        def commit(self):
            self.commits += 1

    connection = FakeConnection()

    duration_ms = run_migrations.run_migration_file(connection, migration)

    assert duration_ms >= 0
    assert connection.cursor_obj.executed == ["SELECT 1", "SELECT 2"]
    assert connection.commits == 1
