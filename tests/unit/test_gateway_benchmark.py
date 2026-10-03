"""Benchmark correctness only; no latency or throughput threshold."""

import asyncio
import importlib.util

from aictrl.runtime.workspace import PROJECT_ROOT

spec = importlib.util.spec_from_file_location('gateway_benchmark', PROJECT_ROOT / 'scripts/benchmark-gateway.py')
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def test_benchmark_smoke_uses_real_local_http_and_durable_pairs(tmp_path):
    result = asyncio.run(benchmark.run_benchmark(tmp_path, requests=4, concurrencies=(1, 2), policy_iterations=5, sqlite_iterations=3))
    assert result['microbenchmarks']['policy']['iterations'] == 5
    assert result['microbenchmarks']['sqlite_append']['iterations'] == 3
    for kind in ('direct', 'gateway'):
        for sample in result['http'][kind]:
            assert sample['successful'] == sample['requests'] == 4 and sample['failed'] == 0
            assert set(sample['latency_ms']) == {'p50', 'p95', 'p99'}
    proof = result['http']['verification']
    assert proof['paired'] and proof['admissions'] == proof['completions'] == 14
    assert proof['synthetic_hits'] == 28 and proof['internal_token_absent_from_db']
