"""Additive safe reporting state; no payload, credential or path columns."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
from typing import Callable, Iterator
from uuid import UUID

from aictrl.contracts import Alert, AgentProtocol, Identifier, SecurityEvent, SessionState
from aictrl.policy.models import RiskSettings, ResponseSettings
from aictrl.reporting.risk import LEVELS, RiskEngine
from aictrl.reporting.sink import StoreFailure
from aictrl.reporting.store import EventStore
from aictrl.reporting.models import ControlStatus
from pydantic import TypeAdapter

IDENTIFIER = TypeAdapter(Identifier)
STAGES = ('deterministic_guards', 'semantic_jev', 'governance', 'upstream_stream', 'mcp_backend', 'total')
KINDS = ('native', 'demo', 'offline-demo', 'verification')


class ReportingStore:
    def __init__(self, path: Path, *, clock: Callable[[], datetime] | None = None) -> None:
        self.path, self.clock = path, clock or (lambda: datetime.now(timezone.utc))
        EventStore(path)  # Preserve its schema and durable append semantics.
        with self.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, adapter TEXT NOT NULL,
                    protocol TEXT, state TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT,
                    kind TEXT NOT NULL, exit_code INTEGER);
                CREATE INDEX IF NOT EXISTS events_recent ON events(timestamp DESC);
                CREATE INDEX IF NOT EXISTS events_filters ON events(action,channel,timestamp DESC);
                CREATE INDEX IF NOT EXISTS sessions_started ON sessions(started_at DESC);
                CREATE TABLE IF NOT EXISTS latency_samples (
                    session_id TEXT NOT NULL, request_id TEXT NOT NULL, stage TEXT NOT NULL,
                    latency_ms REAL NOT NULL CHECK(latency_ms>=0), timestamp TEXT NOT NULL,
                    PRIMARY KEY(session_id,request_id,stage));
                CREATE INDEX IF NOT EXISTS latency_session ON latency_samples(session_id,stage);
                CREATE TABLE IF NOT EXISTS risk_contributions (
                    event_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, rule_id TEXT NOT NULL,
                    points INTEGER NOT NULL CHECK(points>=0), occurred_at REAL NOT NULL,
                    policy_version TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS risk_window ON risk_contributions(session_id,occurred_at);
                CREATE TABLE IF NOT EXISTS risk_checkpoint (
                    session_id TEXT PRIMARY KEY, severity TEXT NOT NULL, updated_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS alerts (
                    alert_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, rule_id TEXT NOT NULL,
                    severity TEXT NOT NULL, response TEXT NOT NULL, created_at REAL NOT NULL,
                    response_completed_at REAL, failures INTEGER NOT NULL DEFAULT 0,
                    last_attempt_at REAL, alert_json TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS alerts_pending ON alerts(session_id,response_completed_at,created_at);
                CREATE TABLE IF NOT EXISTS control_status (
                    session_id TEXT PRIMARY KEY, updated_at TEXT NOT NULL, safe_json TEXT NOT NULL);
            ''')

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        db = None
        try:
            if self.path.is_symlink() or not self.path.parent.is_dir():
                raise OSError('Unsafe reporting store')
            db = sqlite3.connect(self.path, timeout=2, isolation_level=None)
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA synchronous=FULL')
            yield db
        except (OSError, sqlite3.Error):
            raise StoreFailure('Reporting store unavailable.') from None
        finally:
            if db is not None:
                db.close()

    @contextmanager
    def transaction(self):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                yield db
                db.execute('COMMIT')
            except BaseException:
                db.execute('ROLLBACK')
                raise

    def start_session(self, session_id: UUID, agent: str, adapter: str, protocol: AgentProtocol | None,
                      started: datetime, *, kind: str = 'native') -> None:
        agent, adapter = IDENTIFIER.validate_python(agent), IDENTIFIER.validate_python(adapter)
        if kind not in KINDS or started.tzinfo is None:
            raise ValueError('Invalid safe lifecycle metadata.')
        with self.transaction() as db:
            db.execute('INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?)',
                       (str(session_id), agent, adapter, protocol.value if protocol else None,
                        'STARTING', started.isoformat(), None, kind, None))

    def lifecycle(self, session_id: UUID, state: SessionState, *, ended: datetime | None = None,
                  exit_code: int | None = None) -> None:
        state = SessionState(state)
        with self.transaction() as db:
            db.execute('UPDATE sessions SET state=?,ended_at=COALESCE(?,ended_at),exit_code=COALESCE(?,exit_code) WHERE session_id=?',
                       (state.value, ended.isoformat() if ended else None, exit_code, str(session_id)))

    def observe_event(self, event: SecurityEvent, risk: RiskSettings, response: ResponseSettings) -> None:
        now = self.clock()
        engine = RiskEngine(risk)
        contribution = engine.contribution(event)
        with self.transaction() as db:
            if contribution:
                rule, points = contribution
                db.execute('INSERT OR IGNORE INTO risk_contributions VALUES (?,?,?,?,?,?)',
                           (str(event.event_id), str(event.session_id), rule, points,
                            event.occurred_at.timestamp(), event.policy_version))
            score = db.execute('SELECT COALESCE(SUM(points),0) FROM risk_contributions WHERE session_id=? AND occurred_at>? AND occurred_at<=?',
                               (str(event.session_id), now.timestamp()-risk.window_seconds, now.timestamp())).fetchone()[0]
            severity = engine.severity(score).value
            previous = db.execute('SELECT severity,updated_at FROM risk_checkpoint WHERE session_id=?', (str(event.session_id),)).fetchone()
            old = previous['severity'] if previous and previous['updated_at'] > now.timestamp()-risk.window_seconds else 'LOW'
            db.execute('INSERT INTO risk_checkpoint VALUES (?,?,?) ON CONFLICT(session_id) DO UPDATE SET severity=excluded.severity,updated_at=excluded.updated_at',
                       (str(event.session_id), severity, now.timestamp()))
            if not contribution or LEVELS[severity] <= LEVELS[old] or severity == 'LOW':
                return
            rule_id = 'risk.' + severity.lower()
            recent = db.execute('SELECT 1 FROM alerts WHERE session_id=? AND rule_id=? AND created_at>?',
                                (str(event.session_id), rule_id, now.timestamp()-response.alert_cooldown_seconds)).fetchone()
            if recent:
                return
            ids = tuple(UUID(row[0]) for row in db.execute('SELECT event_id FROM risk_contributions WHERE session_id=? AND occurred_at>? AND occurred_at<=? ORDER BY occurred_at DESC LIMIT 16',
                        (str(event.session_id), now.timestamp()-risk.window_seconds, now.timestamp())))
            alert = Alert(session_id=event.session_id, event_ids=ids, rule_id=rule_id, severity=severity,
                          response=getattr(response, severity.lower()), created_at=now)
            db.execute('INSERT INTO alerts (alert_id,session_id,rule_id,severity,response,created_at,alert_json) VALUES (?,?,?,?,?,?,?)',
                       (str(alert.alert_id), str(event.session_id), rule_id, severity, alert.response, now.timestamp(), alert.model_dump_json()))

    def latency(self, session_id: UUID, request_id: UUID, samples: dict[str, float]) -> None:
        if any(stage not in STAGES or type(ms) not in (int, float) or not math.isfinite(ms) or not 0 <= ms <= 86400000
               for stage, ms in samples.items()):
            raise ValueError('Invalid safe timing metadata.')
        with self.transaction() as db:
            for stage, value in samples.items():
                db.execute('INSERT OR IGNORE INTO latency_samples VALUES (?,?,?,?,?)',
                           (str(session_id), str(request_id), stage, value, self.clock().isoformat()))

    def pending(self, session_id: UUID) -> list[Alert]:
        with self.connection() as db:
            rows = db.execute('SELECT alert_json FROM alerts WHERE session_id=? AND response_completed_at IS NULL AND (last_attempt_at IS NULL OR last_attempt_at<?) ORDER BY created_at LIMIT 20',
                              (str(session_id), self.clock().timestamp()-2)).fetchall()
        try:
            alerts = [Alert.model_validate_json(row[0]) for row in rows]
            if any(alert.session_id != session_id for alert in alerts):
                raise ValueError('Invalid alert ownership.')
            return alerts
        except ValueError:
            raise StoreFailure('Reporting alert unavailable.') from None

    def complete(self, alert: Alert) -> None:
        now = self.clock()
        with self.transaction() as db:
            row = db.execute('SELECT alert_json FROM alerts WHERE alert_id=? AND session_id=? AND response_completed_at IS NULL',
                             (str(alert.alert_id), str(alert.session_id))).fetchone()
            if row:
                current = Alert.model_validate_json(row[0]).model_copy(update={'response_completed_at': now})
                db.execute('UPDATE alerts SET response_completed_at=?,alert_json=? WHERE alert_id=? AND session_id=?',
                           (now.timestamp(), current.model_dump_json(), str(alert.alert_id), str(alert.session_id)))

    def failed_response(self, alert: Alert) -> None:
        with self.transaction() as db:
            db.execute('UPDATE alerts SET failures=failures+1,last_attempt_at=? WHERE alert_id=? AND session_id=? AND response_completed_at IS NULL',
                       (self.clock().timestamp(), str(alert.alert_id), str(alert.session_id)))

    @staticmethod
    def status_projection(snapshot, reload_status: dict[str, str], semantic: str) -> ControlStatus:
        policy = snapshot.policy
        if semantic not in ('configured', 'unavailable', 'explicit-offline-fixture'):
            raise ValueError('Invalid semantic status.')
        safe = {**reload_status, 'policy_schema': policy.schema_version,
                'enabled_signatures': sum(signature.enabled for signature in snapshot.feed.signatures),
                'signature_ids': [signature.signature_id for signature in snapshot.feed.signatures if signature.enabled],
                'semantic': {'provider': 'Jev', 'status': semantic, 'enabled': policy.guards.semantic.enabled,
                             'thresholds': policy.guards.semantic.thresholds.model_dump(),
                             'timeout_ms': policy.guards.semantic.timeout_ms, 'max_chars': policy.guards.semantic.max_chars},
                'guards': {'secrets': policy.guards.secrets.enabled, 'pii': list(policy.guards.pii.entities),
                           'output_max_bytes': policy.guards.output.max_bytes, 'output_timeout_ms': policy.guards.output.timeout_ms},
                'governance': {'approval_ttl_seconds': policy.governance.approval_ttl_seconds,
                               'max_agent_steps': policy.governance.runaway.max_agent_steps,
                               'max_tool_calls': policy.governance.runaway.max_tool_calls},
                'risk': policy.risk.model_dump(mode='json')}
        return ControlStatus.model_validate_json(json.dumps(safe, allow_nan=False))

    def status(self, session_id: UUID, snapshot, reload_status: dict[str, str], semantic: str) -> None:
        safe = self.status_projection(snapshot, reload_status, semantic)
        with self.transaction() as db:
            db.execute('INSERT INTO control_status VALUES (?,?,?) ON CONFLICT(session_id) DO UPDATE SET updated_at=excluded.updated_at,safe_json=excluded.safe_json',
                       (str(session_id), self.clock().isoformat(), safe.model_dump_json()))
