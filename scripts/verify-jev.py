"""Two synthetic Jev calls through the production privacy guard ordering."""

import asyncio
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter_ns

import httpx

from aictrl.guards.engine import GuardEngine
from aictrl.guards.jev import JevSemanticProvider, load_key
from aictrl.guards.models import InspectionSegment, Source
from aictrl.mcp.demo_backend import POISON
from aictrl.policy.loader import load_policy
from aictrl.runtime.secrets import stage_jev_key
from aictrl.runtime.workspace import PROJECT_ROOT


class QualificationProvider:
    def __init__(self, provider):
        self.provider=provider
        self.assessment=None
    async def evaluate(self,segments):
        self.assessment=await self.provider.evaluate(segments)
        return self.assessment


async def verify(key,settings):
    timeout=settings.semantic.timeout_ms/1000
    async with httpx.AsyncClient(trust_env=False,follow_redirects=False,
                                timeout=httpx.Timeout(connect=timeout,read=timeout,write=timeout,pool=timeout),
                                transport=httpx.AsyncHTTPTransport(retries=0)) as http:
        provider=QualificationProvider(JevSemanticProvider(http,key))
        engine=GuardEngine(settings,provider)
        records=[]
        for name,text,expected in (('safe','Synthetic public document: the build completed successfully.','ALLOW'),
                                   ('malicious',POISON,'BLOCK')):
            provider.assessment=None
            start=perf_counter_ns()
            evaluated=await engine.inspect_output((InspectionSegment('synthetic',text,Source.MCP_RESULT,mutable=False,untrusted_external=True),),semantic=True)
            elapsed=(perf_counter_ns()-start)/1_000_000
            passed=evaluated.action==expected and provider.assessment is not None
            record={'case':name,'passed':passed,'action':evaluated.action.value,'reason':evaluated.reason_code,'latency_ms':round(elapsed,3)}
            if provider.assessment:
                assessment=provider.assessment
                record.update(model=assessment.model,probabilities=assessment.probabilities,
                              input_tokens=assessment.input_tokens,output_tokens=assessment.output_tokens)
            records.append(record)
            print(json.dumps(record,sort_keys=True),flush=True)
        return records


def main():
    settings=load_policy(PROJECT_ROOT/'config/policy.yaml').guards
    with tempfile.TemporaryDirectory(prefix='aictrl-jev-qualification-') as directory:
        path=stage_jev_key(Path(directory))
        if path is None:
            print('Jev live qualification PENDING: configure AICTRL_JEV_API_KEY on the host, then run make verify-jev.')
            return 2
        records=asyncio.run(verify(load_key(path),settings))
    result={'measured_at':datetime.now(timezone.utc).isoformat(),'model_alias':'jev-latest','cases':records}
    output=PROJECT_ROOT/'.aictrl/benchmarks/jev-qualification.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n')
    passed=all(record['passed'] for record in records)
    print('JEV QUALIFICATION '+('PASS' if passed else 'FAIL'),flush=True)
    return 0 if passed else 1


if __name__=='__main__':
    try: status=main()
    except Exception:
        print('JEV QUALIFICATION FAIL: configuration or provider unavailable.',flush=True)
        status=1
    raise SystemExit(status)
