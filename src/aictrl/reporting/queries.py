"""Read-only, bounded SQL and strictly selected safe dashboard fields."""

from contextlib import contextmanager
from datetime import datetime, timezone
import math
from pathlib import Path
import sqlite3
from uuid import UUID

from pydantic import AwareDatetime, TypeAdapter

from aictrl.contracts import Alert, AgentProtocol, ApprovalState, BudgetState, Channel, DecisionAction, SecurityEvent, SessionState
from aictrl.policy.loader import load_policy
from aictrl.policy.models import RiskSettings
from aictrl.guards.threat_feed import load_feed
from aictrl.governance.reload import ConfigSnapshotManager
from aictrl.reporting.models import ControlStatus
from aictrl.reporting.risk import RiskEngine
from aictrl.reporting.service import IDENTIFIER, KINDS, STAGES, ReportingStore
from aictrl.reporting.sink import StoreFailure

DATE = TypeAdapter(AwareDatetime)
SAFE_EVENT_FIELDS = {'event_id', 'session_id', 'request_id', 'agent_id', 'adapter', 'channel', 'action',
                     'reason_code', 'protocol', 'policy_version', 'occurred_at', 'inspection_level'}


def percentiles(values: list[float]) -> dict:
    if not values:
        return {'count': 0, 'p50': None, 'p95': None, 'p99': None}
    if any(type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 86400000 for value in values):
        raise ValueError('Invalid latency sample.')
    ordered = sorted(values)
    return {'count': len(ordered), **{f'p{p}': round(ordered[max(0, math.ceil(len(ordered)*p/100)-1)], 3) for p in (50, 95, 99)}}


class ReportingQueries:
    def __init__(self, path: Path, project: Path, *, clock=None) -> None:
        self.path, self.project = path, project
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @contextmanager
    def read(self):
        db = None
        try:
            if self.path.is_symlink() or not self.path.is_file():
                raise OSError('Unavailable reporting database')
            db = sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro', uri=True, timeout=1)
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA query_only=ON')
            yield db
        except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, OverflowError):
            raise StoreFailure('Reporting data temporarily unavailable.') from None
        finally:
            if db is not None:
                db.close()

    def status(self) -> dict:
        with self.read() as db:
            row = db.execute('SELECT safe_json,updated_at FROM control_status ORDER BY updated_at DESC LIMIT 1').fetchone()
            if row:
                status = ControlStatus.model_validate_json(row['safe_json']).model_dump(mode='json')
                status['observed_at'] = DATE.validate_python(row['updated_at']).isoformat()
                status['source'] = 'Latest gateway observation'
            else:
                policy = load_policy(self.project / 'config/policy.yaml')
                manager = ConfigSnapshotManager(policy, feed=load_feed(self.project / 'config/threat-feed.json'))
                status = ReportingStore.status_projection(manager.capture(), manager.status(), 'unavailable').model_dump(mode='json')
                status.update(observed_at=None, source='Host configuration; no gateway observation yet')
            status['audit_store'] = 'readable'
            status['active_sessions'] = db.execute("SELECT COUNT(*) FROM sessions WHERE state IN ('STARTING','ACTIVE','RESTRICTED','TERMINATING')").fetchone()[0]
            return status

    def summary(self) -> dict:
        with self.read() as db:
            counts = dict(db.execute('SELECT action,COUNT(*) FROM events GROUP BY action').fetchall())
            if any(action not in {item.value for item in DecisionAction} for action in counts):
                raise ValueError('Malformed event action.')
            def scalar(sql):
                return db.execute(sql).fetchone()[0]
            approvals = {ApprovalState(row[0]).value: row[1] for row in db.execute("SELECT CASE WHEN state IN ('PENDING','APPROVED') AND expires_at<=? THEN 'EXPIRED' ELSE state END,COUNT(*) FROM approvals GROUP BY 1", (self.clock().timestamp(),))}
            pending = db.execute("SELECT COUNT(*) FROM approvals WHERE state='PENDING' AND expires_at>?", (self.clock().timestamp(),)).fetchone()[0]
            top = [{'reason': IDENTIFIER.validate_python(row[0]), 'count': row[1]} for row in db.execute("SELECT reason_code,COUNT(*) FROM events WHERE action='BLOCK' GROUP BY reason_code ORDER BY COUNT(*) DESC LIMIT 6")]
            activity = [{'minute': DATE.validate_python(row[0] + ':00+00:00').isoformat(), 'action': DecisionAction(row[1]).value, 'count': row[2]}
                        for row in db.execute("SELECT strftime('%Y-%m-%dT%H:%M',timestamp),action,COUNT(*) FROM events WHERE action IN ('ALLOW','BLOCK','REDACT','REQUIRE_APPROVAL') GROUP BY 1,2 ORDER BY 1 DESC LIMIT 48")]
            return {'sessions': scalar('SELECT COUNT(DISTINCT session_id) FROM (SELECT session_id FROM sessions UNION SELECT session_id FROM events)'),
                    'events': sum(counts.values()), 'controlled_actions': scalar('SELECT COUNT(DISTINCT request_id) FROM events'),
                    'requests': scalar("SELECT COUNT(DISTINCT request_id) FROM events WHERE channel='LLM'"),
                    'tool_calls': scalar("SELECT COUNT(*) FROM events e WHERE action='ALLOW' AND channel='MCP' AND EXISTS (SELECT 1 FROM json_each(e.event_json,'$.rule_ids') WHERE value LIKE 'operation.tool.%')"),
                    'tokens': scalar("SELECT COALESCE(SUM(json_extract(usage_json,'$.input_tokens')+json_extract(usage_json,'$.output_tokens')),0) FROM reservations WHERE state='SETTLED' AND usage_json IS NOT NULL"),
                    'unknown_usage': scalar("SELECT COUNT(*) FROM reservations WHERE state IN ('UNKNOWN','DISPATCHED')"),
                    'allow': counts.get('ALLOW', 0), 'blocked': counts.get('BLOCK', 0), 'redacted': counts.get('REDACT', 0),
                    'approval_events': counts.get('REQUIRE_APPROVAL', 0), 'pending_approvals': pending,
                    'approval_states': approvals, 'alerts': scalar('SELECT COUNT(*) FROM alerts'),
                    'active_alerts': scalar('SELECT COUNT(*) FROM alerts WHERE response_completed_at IS NULL'),
                    'top_reasons': top, 'activity': list(reversed(activity))}

    def events(self, *, session: UUID | None = None, action: DecisionAction | None = None,
               channel: Channel | None = None, reason: str | None = None,
               since: datetime | None = None, until: datetime | None = None, page: int = 1, limit: int = 50) -> dict:
        if not 1 <= page <= 2000 or not 1 <= limit <= 100:
            raise ValueError('Invalid pagination.')
        terms, params = [], []
        for field, value in (('session_id', str(session) if session else None), ('action', DecisionAction(action).value if action else None),
                             ('channel', Channel(channel).value if channel else None), ('reason_code', IDENTIFIER.validate_python(reason) if reason else None)):
            if value is not None:
                terms.append(field + '=?'); params.append(value)
        for operator, value in (('>=', since), ('<=', until)):
            if value is not None:
                value = DATE.validate_python(value).astimezone(timezone.utc)
                terms.append('timestamp' + operator + '?'); params.append(value.isoformat())
        where = ' WHERE ' + ' AND '.join(terms) if terms else ''
        with self.read() as db:
            total = db.execute('SELECT COUNT(*) FROM events' + where, params).fetchone()[0]
            rows = db.execute('SELECT event_json FROM events' + where + ' ORDER BY timestamp DESC,rowid DESC LIMIT ? OFFSET ?', [*params, limit, (page-1)*limit]).fetchall()
            items = [SecurityEvent.model_validate_json(row[0]).model_dump(mode='json', include=SAFE_EVENT_FIELDS) for row in rows]
            return {'items': items, 'total': total, 'page': page, 'limit': limit}

    def risk(self, session: UUID, settings: RiskSettings | None = None) -> dict:
        settings = settings or RiskSettings.model_validate(self.status()['risk'])
        now = self.clock().timestamp()
        with self.read() as db:
            rows = db.execute('SELECT rule_id,COUNT(*),SUM(points) FROM risk_contributions WHERE session_id=? AND occurred_at>? AND occurred_at<=? GROUP BY rule_id ORDER BY SUM(points) DESC LIMIT 128',
                              (str(session), now-settings.window_seconds, now)).fetchall()
            contributions = [{'rule': IDENTIFIER.validate_python(row[0]), 'count': int(row[1]), 'points': int(row[2])} for row in rows]
            if any(item['count'] < 0 or item['points'] < 0 for item in contributions):
                raise ValueError('Invalid risk data.')
            score = sum(item['points'] for item in contributions)
            return {'score': score, 'severity': RiskEngine(settings).severity(score).value,
                    'window_seconds': settings.window_seconds, 'contributions': contributions}

    def sessions(self, *, page: int = 1, limit: int = 50) -> dict:
        if not 1 <= page <= 2000 or not 1 <= limit <= 100:
            raise ValueError('Invalid pagination.')
        settings = RiskSettings.model_validate(self.status()['risk'])
        with self.read() as db:
            rows = db.execute('''SELECT session_id,agent_id,adapter,protocol,state,started_at,ended_at,kind FROM sessions
                UNION ALL SELECT e.session_id,MAX(e.agent_id),MAX(e.adapter),MAX(e.protocol),'LEGACY',MIN(e.timestamp),NULL,'legacy-audit'
                FROM events e WHERE NOT EXISTS(SELECT 1 FROM sessions s WHERE s.session_id=e.session_id) GROUP BY e.session_id
                ORDER BY started_at DESC LIMIT ? OFFSET ?''', (limit, (page-1)*limit)).fetchall()
            items = []
            for row in rows:
                sid = UUID(row['session_id'])
                started = DATE.validate_python(row['started_at'])
                ended = DATE.validate_python(row['ended_at']) if row['ended_at'] else None
                state = SessionState(row['state']).value if row['state'] != 'LEGACY' else 'LEGACY'
                if row['kind'] not in (*KINDS, 'legacy-audit'):
                    raise ValueError('Invalid lifecycle kind.')
                counts = db.execute("SELECT COUNT(DISTINCT request_id),SUM(action='BLOCK') FROM events WHERE session_id=?", (str(sid),)).fetchone()
                tokens = db.execute("SELECT COALESCE(SUM(json_extract(usage_json,'$.input_tokens')+json_extract(usage_json,'$.output_tokens')),0) FROM reservations WHERE session_id=? AND state='SETTLED'", (str(sid),)).fetchone()[0]
                items.append({'session_id': str(sid), 'agent_id': IDENTIFIER.validate_python(row['agent_id']),
                              'adapter': IDENTIFIER.validate_python(row['adapter']), 'protocol': AgentProtocol(row['protocol']).value if row['protocol'] else None,
                              'state': state, 'kind': row['kind'], 'started_at': started.isoformat(), 'ended_at': ended.isoformat() if ended else None,
                              'duration_seconds': max(0, ((ended or self.clock())-started).total_seconds()) if state != 'LEGACY' else None,
                              'requests': counts[0], 'blocked': counts[1] or 0, 'tokens': tokens,
                              'alerts': db.execute('SELECT COUNT(*) FROM alerts WHERE session_id=?', (str(sid),)).fetchone()[0],
                              'risk': self.risk(sid, settings)})
            total = db.execute('SELECT COUNT(DISTINCT session_id) FROM (SELECT session_id FROM sessions UNION SELECT session_id FROM events)').fetchone()[0]
            return {'items': items, 'total': total, 'page': page, 'limit': limit}

    def budgets(self, session: UUID | None = None) -> list[dict]:
        now = self.clock().timestamp()
        with self.read() as db:
            rows = db.execute('SELECT * FROM budget_counters WHERE (? IS NULL OR scope_id=?) AND window_end>? ORDER BY dimension,scope,scope_id LIMIT 200',
                              (str(session) if session else None, str(session) if session else None, now)).fetchall()
            result = []
            for row in rows:
                IDENTIFIER.validate_python(row['budget_id']); scope_id = IDENTIFIER.validate_python(row['scope_id'])
                item = BudgetState(scope=row['scope'], scope_id=scope_id, dimension=row['dimension'], limit=row['limit_value'],
                                   used=row['used'], reserved=row['reserved'], window_start=datetime.fromtimestamp(row['window_start'],timezone.utc),
                                   window_end=datetime.fromtimestamp(row['window_end'],timezone.utc))
                percentage = round((item.used+item.reserved)/item.limit*100, 1) if item.limit else 100
                result.append({**item.model_dump(mode='json', exclude={'budget_id'}), 'rule': row['budget_id'], 'percentage': percentage,
                               'status': 'EXHAUSTED' if percentage>=100 else 'WARNING' if percentage>=80 else 'AVAILABLE',
                               'lifetime': row['window_start']==0})
            return result

    def alerts(self, session: UUID | None = None, *, page: int = 1, limit: int = 50) -> dict:
        if not 1 <= page <= 2000 or not 1 <= limit <= 100:
            raise ValueError('Invalid pagination.')
        with self.read() as db:
            rows = db.execute('SELECT alert_json,failures FROM alerts WHERE (? IS NULL OR session_id=?) ORDER BY created_at DESC LIMIT ? OFFSET ?',
                              (str(session) if session else None, str(session) if session else None, limit, (page-1)*limit)).fetchall()
            items = [{**Alert.model_validate_json(row[0]).model_dump(mode='json'), 'failures': row[1]} for row in rows]
            total = db.execute('SELECT COUNT(*) FROM alerts WHERE (? IS NULL OR session_id=?)', (str(session) if session else None, str(session) if session else None)).fetchone()[0]
            return {'items': items, 'total': total, 'page': page, 'limit': limit}

    def latency(self, session: UUID | None = None) -> dict:
        with self.read() as db:
            return {stage: percentiles([row[0] for row in db.execute('SELECT latency_ms FROM latency_samples WHERE stage=? AND (? IS NULL OR session_id=?) ORDER BY timestamp DESC LIMIT 2000',
                      (stage, str(session) if session else None, str(session) if session else None))]) for stage in STAGES}

    def overview(self) -> dict:
        sessions = self.sessions(limit=50)['items']
        return {'summary': self.summary(), 'sessions': sorted((item for item in sessions if item['risk']['score'] > 0), key=lambda item:item['risk']['score'], reverse=True)[:5],
                'latency': self.latency(), 'events': self.events(limit=8), 'status': self.status()}

    def detail(self, session: UUID) -> dict:
        return {'session_id': str(session), 'risk': self.risk(session), 'events': self.events(session=session),
                'budgets': self.budgets(session), 'latency': self.latency(session), 'alerts': self.alerts(session)}
