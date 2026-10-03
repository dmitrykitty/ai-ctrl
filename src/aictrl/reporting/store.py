"""Durable safe events. No arbitrary metadata or payload persistence API."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID
from pydantic import ValidationError

from aictrl.contracts import SecurityEvent


class StoreFailure(RuntimeError):
    pass


class EventStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        try:
            if path.is_symlink() or not path.parent.is_dir():
                raise OSError('Unsafe or absent store directory')
            with self._connect() as connection:
                connection.execute('PRAGMA journal_mode=WAL')
                connection.execute('''CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, request_id TEXT,
                    agent_id TEXT NOT NULL, adapter TEXT NOT NULL, channel TEXT NOT NULL,
                    direction TEXT NOT NULL, protocol TEXT, inspection_level TEXT NOT NULL,
                    action TEXT NOT NULL, reason_code TEXT NOT NULL, policy_version TEXT NOT NULL,
                    timestamp TEXT NOT NULL, event_json TEXT NOT NULL)''')
                connection.execute('CREATE INDEX IF NOT EXISTS events_session ON events(session_id, timestamp)')
            path.chmod(0o600)
        except (OSError, sqlite3.Error):
            raise StoreFailure('Audit store initialization failed.') from None

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=2)
        try:
            connection.execute('PRAGMA synchronous=FULL')
            with connection:
                yield connection
        finally:
            connection.close()

    def append(self, event: SecurityEvent) -> None:
        record = event.model_dump(mode='json')
        try:
            with self._connect() as connection:
                connection.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (
                    record['event_id'], record['session_id'], record['request_id'], record['agent_id'],
                    record['adapter'], record['channel'], record['direction'], record['protocol'],
                    record['inspection_level'], record['action'], record['reason_code'], record['policy_version'],
                    record['occurred_at'], event.model_dump_json(),
                ))
        except (OSError, sqlite3.Error):
            raise StoreFailure('Audit event persistence failed.') from None

    def events(self, session_id: UUID) -> list[SecurityEvent]:
        try:
            with self._connect() as connection:
                rows = connection.execute('SELECT event_json FROM events WHERE session_id=? ORDER BY rowid', (str(session_id),)).fetchall()
            return [SecurityEvent.model_validate_json(row[0]) for row in rows]
        except (OSError, sqlite3.Error, ValidationError):
            raise StoreFailure('Audit event retrieval failed.') from None
