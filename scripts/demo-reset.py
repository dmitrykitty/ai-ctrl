"""Delete only terminal, explicitly offline-demo rows; never touch Docker/state."""

from pathlib import Path
from uuid import UUID

from aictrl.reporting.service import ReportingStore
from aictrl.runtime.workspace import PROJECT_ROOT
from demo_support import save_report
import importlib.util

spec = importlib.util.spec_from_file_location('rehearsal_lock', Path(__file__).with_name('demo-rehearsal.py'))
rehearsal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rehearsal)


def reset_demo(path: Path) -> int:
    store = ReportingStore(path)
    with store.transaction() as db:
        rows = db.execute("SELECT session_id,state FROM sessions WHERE kind='offline-demo'").fetchall()
        if any(row['state'] not in ('TERMINATED', 'FAILED') for row in rows):
            raise ValueError('Active demo sessions cannot be reset.')
        sessions = [str(UUID(row['session_id'])) for row in rows]
        if len(sessions) > 2000:
            raise ValueError('Too many demo sessions for a bounded reset.')
        if not sessions:
            return 0
        params = ','.join('?' for _ in sessions)
        # A future demo with shared user/agent/profile budgets needs a fresh
        # profile; deleting those counters could affect native work. Refuse it.
        shared = db.execute(f'''SELECT 1 FROM reservation_claims c JOIN reservations r USING(reservation_id)
            WHERE r.session_id IN ({params}) AND (c.scope!='session' OR c.scope_id!=r.session_id) LIMIT 1''', sessions).fetchone()
        if shared:
            raise ValueError('Shared-scope demo accounting cannot be safely reset.')
        db.execute(f'DELETE FROM reservation_claims WHERE reservation_id IN (SELECT reservation_id FROM reservations WHERE session_id IN ({params}))', sessions)
        for table in ('reservations', 'approvals', 'governance_audit', 'events', 'latency_samples',
                      'risk_contributions', 'risk_checkpoint', 'alerts', 'control_status'):
            db.execute(f'DELETE FROM {table} WHERE session_id IN ({params})', sessions)
        db.execute(f"DELETE FROM budget_counters WHERE scope='session' AND scope_id IN ({params})", sessions)
        db.execute(f"DELETE FROM sessions WHERE kind='offline-demo' AND session_id IN ({params})", sessions)
        return len(sessions)


def main() -> int:
    path = PROJECT_ROOT / '.aictrl/audit/events.sqlite3'
    try:
        if not path.is_file():
            print('DEMO RESET PASS: no stored demo history.')
            return 0
        if path.resolve() != path or path.is_symlink():
            raise ValueError('Protected audit path required.')
        with rehearsal.demo_lock():
            count = reset_demo(path)
        save_report('demo-reset', {'sessions_removed': count, 'passed': True, 'scope': 'terminal-offline-demo-only'})
        print(f'DEMO RESET PASS: {count} terminal offline-demo sessions removed; native history, workspace and provider volumes preserved.')
        return 0
    except Exception:
        print('DEMO RESET FAIL: active/ambiguous demo state or unavailable reporting store. Existing data preserved.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
