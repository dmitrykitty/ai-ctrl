"""Validated immutable config snapshots, swapped once without request parsing."""

import asyncio
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from aictrl.guards.engine import GuardEngine
from aictrl.guards.semantic import SemanticDecisionProvider
from aictrl.guards.threat_feed import ThreatFeed, load_feed
from aictrl.policy.engine import PolicyEngine
from aictrl.policy.loader import load_policy
from aictrl.policy.models import Policy


@dataclass(frozen=True)
class ConfigSnapshot:
    policy: Policy
    feed: ThreatFeed
    engine: PolicyEngine
    guards: GuardEngine
    key: str


def snapshot(policy: Policy, feed: ThreatFeed, provider: SemanticDecisionProvider | None) -> ConfigSnapshot:
    # Revalidation also freezes dictionaries supplied by model_copy callers.
    policy = Policy.model_validate_json(policy.model_dump_json())
    feed = ThreatFeed.model_validate_json(feed.model_dump_json())
    canonical = json.dumps({'policy': policy.model_dump(mode='json'), 'feed': feed.model_dump(mode='json')},
                           sort_keys=True, separators=(',', ':'))
    return ConfigSnapshot(policy, feed, PolicyEngine(policy), GuardEngine(policy.guards, provider, feed=feed),
                          hashlib.sha256(canonical.encode()).hexdigest())


class ConfigSnapshotManager:
    def __init__(self, policy: Policy, provider: SemanticDecisionProvider | None = None, *,
                 feed: ThreatFeed | None = None, policy_path: Path | None = None,
                 feed_path: Path | None = None, poll_seconds: float = 0.5) -> None:
        if not 0.05 <= poll_seconds <= 10:
            raise ValueError('Reload polling interval outside bounds.')
        self.provider, self.policy_path, self.feed_path = provider, policy_path, feed_path
        self.poll_seconds = poll_seconds
        self._current = snapshot(policy, feed or ThreatFeed(), provider)
        self._lock = RLock()
        # First poll revalidates watched files, covering a rename between the
        # factory's initial read and watcher construction.
        self._stamps = {'policy': None, 'feed': None}
        self._status = {'policy': 'loaded' if policy_path else 'static', 'feed': 'loaded' if feed_path else 'static'}

    @staticmethod
    def _stamp(path: Path | None):
        if path is None:
            return None
        try:
            info = path.stat()
            return info.st_ino, info.st_mtime_ns, info.st_size
        except OSError:
            return 'unavailable'

    def capture(self) -> ConfigSnapshot:
        return self._current

    def status(self) -> dict[str, str]:
        with self._lock:
            current = self._current
            return {'active_policy_version': current.policy.policy_version,
                    'active_feed_version': current.feed.feed_version,
                    'last_policy_reload_status': self._status['policy'],
                    'last_feed_reload_status': self._status['feed']}

    def poll(self) -> None:
        with self._lock:
            policy, feed = self._current.policy, self._current.feed
            changed = False
            for kind, path, loader in (('policy', self.policy_path, load_policy), ('feed', self.feed_path, load_feed)):
                if path is None:
                    continue
                stamp = self._stamp(path)
                if stamp == self._stamps[kind]:
                    continue
                self._stamps[kind] = stamp
                try:
                    candidate = loader(path)
                    # Fully build before publishing. A bad feed cannot reject a
                    # valid independent policy reload (and conversely).
                    trial = snapshot(candidate if kind == 'policy' else policy,
                                     candidate if kind == 'feed' else feed, self.provider)
                except (ValueError, OSError):
                    self._status[kind] = 'invalid_candidate'
                    continue
                policy, feed = trial.policy, trial.feed
                self._status[kind] = 'applied'
                changed = True
            if changed:
                self._current = snapshot(policy, feed, self.provider)

    async def watch(self) -> None:
        while True:
            await asyncio.sleep(self.poll_seconds)
            await asyncio.to_thread(self.poll)
