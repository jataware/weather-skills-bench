"""Freeze evidence from the initial six-model v4 batch; never change scores."""
import collections,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'results/studies/20260930T155730Z-ae0a07.json'
s=json.loads(path.read_text());assert len(s['runs'])==s['planned_runs']==18
hybrids=[r for r in s['runs'] if r['arm']=='skills']
failures=[r for r in s['runs'] if not r['correctness']['passed']]
def stop(r):
    return 'task_timeout' if r['status']=='api_error' and r['solve_seconds']>=s['config']['task_timeout_seconds'] else r['status']
report={'scope':'Initial six-model batch only; one attempt per model and condition. Small-model extension excluded from these counts.',
 'study_id':s['study_id'],'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
 'attempts':len(s['runs']),'failures':len(failures),'failure_stop_reasons':dict(collections.Counter(stop(r) for r in failures)),
 'hybrid_attempts':len(hybrids),'hybrid_invoked_skill':sum(any(e['action']=='skill' for e in r['events']) for r in hybrids),
 'hybrid_read_guide':sum(any(e['action']=='read_skill' for e in r['events']) for r in hybrids),
 'hybrid_passed':sum(r['correctness']['passed'] for r in hybrids),'failed_runs':[]}
for r in failures:
    events=r['events'];errors=[e for e in events if e['action']=='protocol_error' or e.get('returncode')]
    report['failed_runs'].append({'run_id':r['run_id'],'model':r['model'],'arm':r['arm'],'stop_reason':stop(r),
      'tokens':r['usage']['total_tokens'],'prompt_tokens':r['usage']['prompt_tokens'],'seconds':r['solve_seconds'],
      'figure_delivered':r.get('figure',{}).get('passed',False),'answer_present':r.get('answer') is not None,
      'action_counts':dict(collections.Counter(e['action'] for e in events)),
      'skill_calls':sum(e['action']=='skill' for e in events),'failed_skill_calls':sum(e['action']=='skill' and bool(e.get('returncode')) for e in events),
      'errors':[{'turn':e.get('turn'),'action':e['action'],'skill':e.get('skill'),'args':e.get('args'),'message':e.get('message') or e.get('stderr','')[-1600:]} for e in errors]})
first=next(r for r in hybrids if r['model']=='qwen/qwen3.5-9b')
raw=json.loads((ROOT/'results/raw'/first['run_id']/'000.json').read_text())
system=raw['request']['messages'][0]['content']
report['hybrid_prompt_evidence']={'python_instruction':'Use Python for inspection, custom calculations, or serializing output as needed.',
 'skill_introduction':'You also have the following actions:',
 'requires_skill_use':False,'system_prompt_sha256':hashlib.sha256(system.encode()).hexdigest()}
assert report['hybrid_prompt_evidence']['python_instruction'] in system
report['interpretation']=[
 'Observed: 0/6 hybrid attempts invoked any skill; 1/6 read a guide. The four hybrid passes were Python implementations.',
 'The hybrid prompt leads with Python and adds optional skill actions. It does not require a discovery step or prefer relevant skills.',
 'This is a measured adoption/design problem, not evidence that executing skills reduces accuracy. Prompt effects on a particular trajectory remain hypotheses.',
 'Failed strict-skill runs include malformed/foreign tool-call envelopes, missing guide prerequisites, CLI-argument errors, composition-contract errors, and artifact serialization rejections.',
 'Sonnet executed 12 skills successfully and produced a figure; XML-like wrappers and a literal numeric array in artifact submission prevented delivery. This does not independently validate its intermediate numbers.',
 'Ministral Python attempts repeatedly failed indexing, datetime handling, syntax, and serialization. Qwen hybrid additionally used an incorrect longitude normalization.',
 'Six failures exhausted cumulative tokens; one exhausted task time. Stopping limits identify the endpoint, while traces identify the mechanisms.',
 'Do not change previous scores. Test skill discovery/preference plus Python recovery in a separately versioned condition; repeat matched attempts with controlled routing.']
(ROOT/'results/initial-panel-failure-modes.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['failed_runs','interpretation','hybrid_prompt_evidence']},indent=2))
