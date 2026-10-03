"""Offline hot-path timings. Fake semantic latency is explicitly separate."""

import asyncio
import json
import math
import os
import platform
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter_ns

from aictrl.guards.engine import GuardEngine
from aictrl.guards.models import InspectionSegment, Source
from aictrl.guards.semantic import QUESTIONS, SemanticAssessment
from aictrl.policy.models import GuardSettings


class BenchmarkSemanticFake:
    async def evaluate(self, segments):
        return SemanticAssessment(dict.fromkeys(QUESTIONS, 0.01))


def percentiles(values):
    ordered=sorted(values)
    return {name:round(ordered[math.ceil(len(ordered)*quantile)-1],3)
            for name,quantile in (('p50_us',.5),('p95_us',.95),('p99_us',.99))}


async def benchmark(samples=200):
    engine=GuardEngine(GuardSettings(),BenchmarkSemanticFake())
    cohorts=[]
    for size in (1024,10240,32768):
        seed='def public_add(a, b): return a + b\n# ordinary public code fixture\n'
        text=(seed*(size//len(seed)+1))[:size]
        trusted=(InspectionSegment('fixture',text,Source.USER_INPUT,('content',)),)
        external=(InspectionSegment('fixture',text,Source.TOOL_RESULT,('content',),True,True),)
        for name in ('secret','pii','combined_deterministic','with_fake_semantic'):
            timings=[]
            for index in range(samples+5):
                start=perf_counter_ns()
                if name=='secret': engine.secrets.scan(text)
                elif name=='pii': engine.pii.scan(text)
                else:
                    evaluated=await engine.inspect_input(external if name=='with_fake_semantic' else trusted)
                    if evaluated.action!='ALLOW': raise RuntimeError('Benchmark fixture blocked.')
                if index>=5: timings.append((perf_counter_ns()-start)/1000)
            cohorts.append({'path':name,'chars':size,'samples':samples,**percentiles(timings)})
    return {'measured_at':datetime.now(timezone.utc).isoformat(),'python':platform.python_version(),
            'platform':platform.platform(),'logical_cpus':os.cpu_count(),'external_api_calls':0,
            'warmup':5,'cohorts':cohorts}


def main():
    result=asyncio.run(benchmark())
    path=Path('.aictrl/benchmarks/guards-latest.json')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2)+'\n')
    for cohort in result['cohorts']:
        print(f"{cohort['path']:24s} {cohort['chars']:5d} chars: p50/p95/p99 {cohort['p50_us']}/{cohort['p95_us']}/{cohort['p99_us']} us")
    print('Offline local guards; fake semantic only; zero external API calls.')


if __name__=='__main__': main()
