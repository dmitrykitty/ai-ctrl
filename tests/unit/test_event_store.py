import sqlite3
from uuid import uuid4

import pytest

from aictrl.reporting.store import EventStore, StoreFailure


def test_corrupt_event_retrieval_does_not_echo_stored_data(tmp_path):
    store = EventStore(tmp_path / 'events.sqlite3')
    session = uuid4()
    with sqlite3.connect(store.path) as connection:
        connection.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                           (str(uuid4()), str(session), None, 'claude', 'claude', 'LLM', 'OUTBOUND', 'ANTHROPIC_MESSAGES',
                            'STRUCTURED', 'BLOCK', 'llm.test', 't03', 'synthetic', '{"private":"synthetic-private-details"}'))
    with pytest.raises(StoreFailure) as error:
        store.events(session)
    assert str(error.value) == 'Audit event retrieval failed.'


def test_missing_directory_and_symlink_store_are_refused(tmp_path):
    with pytest.raises(StoreFailure):
        EventStore(tmp_path / 'missing' / 'events.sqlite3')
    target = tmp_path / 'target'
    target.touch()
    link = tmp_path / 'link'
    link.symlink_to(target)
    with pytest.raises(StoreFailure):
        EventStore(link)
