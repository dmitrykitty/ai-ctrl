"""Local durable governance. Every authorization mutation uses BEGIN IMMEDIATE.

Only identifiers, digests, timestamps, states and numeric accounting enter SQL.
The existing reporting events table is deliberately untouched.
"""

import sqlite3
import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator
from uuid import UUID, NAMESPACE_URL, uuid4, uuid5

from aictrl.contracts import Approval, BudgetState, UsageMetric
from aictrl.reporting.sink import StoreFailure


class GovernanceFailure(StoreFailure):
    def __init__(self) -> None:
        super().__init__('Governance store unavailable.')


@dataclass(frozen=True)
class BudgetClaim:
    budget_id: str
    scope: str
    scope_id: str
    dimension: str
    limit: int
    window_seconds: int
    amount: int

    def __post_init__(self) -> None:
        if (self.scope not in ('session', 'agent', 'user', 'profile')
                or self.dimension not in ('requests', 'tokens', 'tool_calls', 'agent_steps')
                or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}', self.budget_id)
                or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}', self.scope_id)
                or type(self.amount) is not int or not 0 < self.amount <= 100_000_000
                or type(self.limit) is not int or not 0 < self.limit <= 1_000_000_000
                or type(self.window_seconds) is not int or not 0 <= self.window_seconds <= 86400
                or (self.window_seconds == 0 and not self.budget_id.startswith('runaway.'))):
            raise ValueError('Invalid budget claim.')


@dataclass(frozen=True)
class Reservation:
    reservation_id: UUID
    session_id: UUID
    request_id: UUID


@dataclass(frozen=True)
class Admission:
    reservation: Reservation | None = None
    reason: str | None = None
    approval_id: UUID | None = None


@dataclass(frozen=True)
class ApprovalRecord:
    approval: Approval
    operation_id: str


class GovernanceStore:
    def __init__(self, path: Path, *, clock: Callable[[], datetime] | None = None) -> None:
        self.path = path
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        try:
            with self._connection() as db:
                db.execute('PRAGMA journal_mode=WAL')
                db.executescript('''
                    CREATE TABLE IF NOT EXISTS budget_counters (
                        budget_id TEXT NOT NULL, scope TEXT NOT NULL, scope_id TEXT NOT NULL,
                        dimension TEXT NOT NULL, window_start INTEGER NOT NULL,
                        window_end INTEGER NOT NULL, limit_value INTEGER NOT NULL,
                        used INTEGER NOT NULL DEFAULT 0 CHECK(used >= 0),
                        reserved INTEGER NOT NULL DEFAULT 0 CHECK(reserved >= 0),
                        PRIMARY KEY (budget_id, scope, scope_id, dimension, window_start, window_end));
                    CREATE TABLE IF NOT EXISTS approvals (
                        approval_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                        request_id TEXT NOT NULL, request_digest TEXT NOT NULL,
                        policy_version TEXT NOT NULL, snapshot_key TEXT NOT NULL,
                        operation_id TEXT NOT NULL, state TEXT NOT NULL,
                        requested_at REAL NOT NULL, expires_at REAL NOT NULL, consumed_at REAL);
                    CREATE INDEX IF NOT EXISTS approval_request ON approvals
                        (session_id, request_digest, policy_version, snapshot_key);
                    CREATE TABLE IF NOT EXISTS reservations (
                        reservation_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                        request_id TEXT NOT NULL, policy_version TEXT NOT NULL,
                        state TEXT NOT NULL, approval_id TEXT, created_at REAL NOT NULL,
                        usage_json TEXT);
                    CREATE TABLE IF NOT EXISTS reservation_claims (
                        reservation_id TEXT NOT NULL, budget_id TEXT NOT NULL,
                        scope TEXT NOT NULL, scope_id TEXT NOT NULL, dimension TEXT NOT NULL,
                        window_start INTEGER NOT NULL, window_end INTEGER NOT NULL, amount INTEGER NOT NULL,
                        PRIMARY KEY (reservation_id, budget_id, scope, scope_id, dimension, window_start, window_end));
                    CREATE TABLE IF NOT EXISTS governance_audit (
                        record_id TEXT PRIMARY KEY, approval_id TEXT NOT NULL,
                        session_id TEXT NOT NULL, policy_version TEXT NOT NULL,
                        action TEXT NOT NULL, occurred_at REAL NOT NULL);
                ''')
            path.chmod(0o600)
        except (OSError, sqlite3.Error):
            raise GovernanceFailure() from None

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        db = None
        try:
            if self.path.is_symlink() or not self.path.parent.is_dir():
                raise OSError('Unsafe store directory')
            db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA synchronous=FULL')
            yield db
        except (OSError, sqlite3.Error):
            raise GovernanceFailure() from None
        finally:
            if db is not None:
                db.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                yield db
                db.execute('COMMIT')
            except BaseException:
                db.execute('ROLLBACK')
                raise

    @staticmethod
    def _expire(db: sqlite3.Connection, now: float) -> None:
        db.execute("UPDATE approvals SET state='EXPIRED' WHERE state IN ('PENDING','APPROVED') AND expires_at<=?", (now,))

    @staticmethod
    def _window(claim: BudgetClaim, now: float) -> tuple[int, int]:
        if not claim.window_seconds:
            return 0, 253402300799  # session lifetime: never reset on a fixed-window boundary
        start = int(now) // claim.window_seconds * claim.window_seconds
        return start, start + claim.window_seconds

    def reserve(self, claims: tuple[BudgetClaim, ...], *, session_id: UUID, request_id: UUID,
                policy_version: str, snapshot_key: str, approval_digest: str | None = None,
                operation_id: str = 'unsupported', approval_ttl: int = 60) -> Admission:
        """Validate all counters + approval, then consume/reserve in ONE commit.

        A failed claim cannot burn the approval or increment any other counter.
        Concurrent exact retries serialize on this same SQLite write transaction.
        """
        keys = [(c.budget_id, c.scope, c.scope_id, c.dimension, c.window_seconds) for c in claims]
        if len(keys) != len(set(keys)):
            raise GovernanceFailure()
        if approval_digest is not None and not re.fullmatch('[a-f0-9]{64}', approval_digest):
            raise GovernanceFailure()
        with self.transaction() as db:
            now = self.clock().timestamp()
            self._expire(db, now)
            approval_id = None
            if approval_digest is not None:
                row = db.execute('''SELECT * FROM approvals WHERE session_id=? AND request_digest=?
                    AND policy_version=? AND snapshot_key=? ORDER BY rowid DESC LIMIT 1''',
                    (str(session_id), approval_digest, policy_version, snapshot_key)).fetchone()
                if row is None:
                    approval_id = str(uuid4())
                    db.execute('INSERT INTO approvals VALUES (?,?,?,?,?,?,?,?,?,?,?)', (
                        approval_id, str(session_id), str(request_id), approval_digest, policy_version,
                        snapshot_key, operation_id, 'PENDING', now, now + approval_ttl, None))
                    return Admission(reason='governance.approval.required', approval_id=UUID(approval_id))
                approval_id = row['approval_id']
                if row['state'] != 'APPROVED':
                    return Admission(reason='governance.approval.' + {
                        'PENDING': 'required', 'CONSUMED': 'consumed', 'DENIED': 'denied', 'EXPIRED': 'expired'
                    }[row['state']], approval_id=UUID(approval_id))
            windows = []
            for claim in claims:
                start, end = self._window(claim, now)
                key = (claim.budget_id, claim.scope, claim.scope_id, claim.dimension, start, end)
                row = db.execute('''SELECT used,reserved FROM budget_counters WHERE
                    budget_id=? AND scope=? AND scope_id=? AND dimension=? AND window_start=? AND window_end=?''', key).fetchone()
                used, reserved = (row['used'], row['reserved']) if row else (0, 0)
                if used + reserved + claim.amount > claim.limit:
                    prefix = 'governance.runaway.' if claim.budget_id.startswith('runaway.') else 'governance.budget.'
                    return Admission(reason=prefix + claim.dimension + '_exceeded')
                windows.append((claim, key))
            reservation = Reservation(uuid4(), session_id, request_id)
            rid = str(reservation.reservation_id)
            db.execute('INSERT INTO reservations VALUES (?,?,?,?,?,?,?,?)', (
                rid, str(session_id), str(request_id), policy_version, 'RESERVED', approval_id, now, None))
            for claim, key in windows:
                db.execute('''INSERT INTO budget_counters VALUES (?,?,?,?,?,?,?,0,?)
                    ON CONFLICT DO UPDATE SET reserved=reserved+excluded.reserved, limit_value=excluded.limit_value''',
                    (*key, claim.limit, claim.amount))
                db.execute('INSERT INTO reservation_claims VALUES (?,?,?,?,?,?,?,?)', (rid, *key, claim.amount))
            if approval_id is not None:
                db.execute("UPDATE approvals SET state='CONSUMED',consumed_at=? WHERE approval_id=?", (now, approval_id))
                db.execute('INSERT INTO governance_audit VALUES (?,?,?,?,?,?)', (str(uuid4()), approval_id,
                    str(session_id), policy_version, 'governance.approval.consumed', now))
            return Admission(reservation=reservation, approval_id=UUID(approval_id) if approval_id else None)

    @staticmethod
    def _claims(db: sqlite3.Connection, rid: str):
        return db.execute('SELECT * FROM reservation_claims WHERE reservation_id=?', (rid,)).fetchall()

    @staticmethod
    def _key(row: sqlite3.Row) -> tuple:
        return tuple(row[name] for name in ('budget_id', 'scope', 'scope_id', 'dimension', 'window_start', 'window_end'))

    @staticmethod
    def _adjust(db: sqlite3.Connection, row: sqlite3.Row, used: int, reserved: int) -> None:
        db.execute('''UPDATE budget_counters SET used=used+?,reserved=reserved+? WHERE
            budget_id=? AND scope=? AND scope_id=? AND dimension=? AND window_start=? AND window_end=?''',
            (used, reserved, *GovernanceStore._key(row)))

    def dispatch(self, reservation: Reservation) -> None:
        """Mark intent durable after ALLOW and before side effects; never refund it.

        A crash between this commit and the send conservatively spends the action.
        """
        rid = str(reservation.reservation_id)
        with self.transaction() as db:
            row = db.execute('SELECT state FROM reservations WHERE reservation_id=?', (rid,)).fetchone()
            if row is None or row['state'] != 'RESERVED':
                raise GovernanceFailure()
            for claim in self._claims(db, rid):
                if claim['dimension'] != 'tokens':
                    self._adjust(db, claim, claim['amount'], -claim['amount'])
            db.execute("UPDATE reservations SET state='DISPATCHED' WHERE reservation_id=?", (rid,))

    def cancel(self, reservation: Reservation) -> None:
        """Only undo a reservation that has never been marked for dispatch."""
        rid = str(reservation.reservation_id)
        with self.transaction() as db:
            row = db.execute('SELECT * FROM reservations WHERE reservation_id=?', (rid,)).fetchone()
            if row is None or row['state'] != 'RESERVED':
                return
            for claim in self._claims(db, rid):
                self._adjust(db, claim, 0, -claim['amount'])
            if row['approval_id']:
                db.execute("UPDATE approvals SET state='APPROVED',consumed_at=NULL WHERE approval_id=? AND state='CONSUMED'", (row['approval_id'],))
                db.execute('INSERT INTO governance_audit VALUES (?,?,?,?,?,?)', (str(uuid4()), row['approval_id'],
                    row['session_id'], row['policy_version'], 'governance.approval.reservation_cancelled', self.clock().timestamp()))
            db.execute("UPDATE reservations SET state='CANCELLED' WHERE reservation_id=?", (rid,))

    def settle(self, reservation: Reservation, usage: UsageMetric | None) -> None:
        rid = str(reservation.reservation_id)
        with self.transaction() as db:
            row = db.execute('SELECT state FROM reservations WHERE reservation_id=?', (rid,)).fetchone()
            if row is None or row['state'] != 'DISPATCHED':
                return
            if usage is not None:
                if usage.request_id != reservation.request_id or usage.session_id != reservation.session_id:
                    raise GovernanceFailure()
                for claim in self._claims(db, rid):
                    if claim['dimension'] == 'tokens':
                        self._adjust(db, claim, usage.input_tokens + usage.output_tokens, -claim['amount'])
            db.execute('UPDATE reservations SET state=?,usage_json=? WHERE reservation_id=?', (
                'SETTLED' if usage is not None else 'UNKNOWN', usage.model_dump_json() if usage else None, rid))

    @staticmethod
    def _approval(row: sqlite3.Row) -> ApprovalRecord:
        def dt(value):
            return datetime.fromtimestamp(value, timezone.utc) if value is not None else None
        return ApprovalRecord(Approval(approval_id=row['approval_id'], session_id=row['session_id'],
            request_id=row['request_id'], request_digest=row['request_digest'], policy_version=row['policy_version'],
            state=row['state'], requested_at=dt(row['requested_at']), expires_at=dt(row['expires_at']),
            consumed_at=dt(row['consumed_at'])), row['operation_id'])

    def approvals(self, session_id: UUID | None = None) -> list[ApprovalRecord]:
        with self.transaction() as db:
            self._expire(db, self.clock().timestamp())
            rows = db.execute('SELECT * FROM approvals' + (' WHERE session_id=?' if session_id else '') + ' ORDER BY rowid DESC LIMIT 200',
                              (str(session_id),) if session_id else ()).fetchall()
            return [self._approval(row) for row in rows]

    def decide_approval(self, approval_id: UUID, *, approve: bool) -> ApprovalRecord | None:
        with self.transaction() as db:
            now = self.clock().timestamp()
            self._expire(db, now)
            row = db.execute('SELECT * FROM approvals WHERE approval_id=?', (str(approval_id),)).fetchone()
            if row is None:
                return None
            if row['state'] == 'PENDING':
                action = 'APPROVED' if approve else 'DENIED'
                db.execute('UPDATE approvals SET state=? WHERE approval_id=?', (action, str(approval_id)))
                db.execute('INSERT INTO governance_audit VALUES (?,?,?,?,?,?)', (str(uuid4()), str(approval_id),
                    row['session_id'], row['policy_version'], 'governance.approval.' + action.lower(), now))
            return self._approval(db.execute('SELECT * FROM approvals WHERE approval_id=?', (str(approval_id),)).fetchone())

    def budgets(self) -> list[BudgetState]:
        with self._connection() as db:
            rows = db.execute('SELECT * FROM budget_counters ORDER BY rowid').fetchall()
            return [BudgetState(budget_id=uuid5(NAMESPACE_URL, 'aictrl.budget.' + row['budget_id']),
                scope=row['scope'], scope_id=row['scope_id'], dimension=row['dimension'],
                limit=row['limit_value'], used=row['used'], reserved=row['reserved'],
                window_start=datetime.fromtimestamp(row['window_start'], timezone.utc),
                window_end=datetime.fromtimestamp(row['window_end'], timezone.utc)) for row in rows]
