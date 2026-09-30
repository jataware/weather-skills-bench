import copy,json
import pytest
from weather_bench.catalog import ROOT
from weather_bench.retry_study import validate_retry_manifest
from weather_bench.comparison import repair_views


def test_registered_retry_selection(tmp_path):
    config=json.loads((ROOT/'configs/provider-error-retry-v2.json').read_text())
    sources=tmp_path/'results/studies';sources.mkdir(parents=True)
    for name in config['retry_sources']:
        source=json.loads((ROOT/'results/published'/f'{name}.json').read_text())
        source['catalog_tree_sha256']='pinned'
        (sources/f'{name}.json').write_text(json.dumps(source))
    pin={'catalog_tree_sha256':'pinned'}
    origins=validate_retry_manifest(config,tmp_path,pin)
    assert len(origins)==15
    bad=copy.deepcopy(config);bad['retry_attempts']=bad['retry_attempts'][:-1]
    with pytest.raises(ValueError):validate_retry_manifest(bad,tmp_path,pin)
    bad=copy.deepcopy(config);bad['max_calls']+=1
    with pytest.raises(ValueError):validate_retry_manifest(bad,tmp_path,pin)
    for key,value in [('skill_policy','guided-v1'),('max_run_cost_usd',2),('experiment_version','changed')]:
        bad=copy.deepcopy(config);bad[key]=value
        with pytest.raises(ValueError,match='Scientific settings changed'):validate_retry_manifest(bad,tmp_path,pin)


def test_repair_view_never_selects_best_or_hides_cost():
    def run(rid,status):return {'run_id':rid,'status':status,'model':'m','case_id':rid,'arm':'python','rep':0}
    base={'study_id':'base','config':{},'runs':[run('passed','submitted'),run('failed','token_budget'),run('provider','api_error')],'ledger':{'spent':2},'planned_runs':3}
    retry={'study_id':'new','config':{'comparison_parent':'base','retry_attempts':['provider']},'runs':[],'ledger':{'spent':.1},'health':{'state':'running'}}
    view=repair_views([base,retry])[0]
    assert len(view['runs'])==2 and view['planned_runs']==3 and view['ledger']['spent']==2.1
    replacement={**run('retry','token_budget'),'case_id':'provider','retry_of':{'run_id':'provider'}}
    retry['runs']=[replacement];view=repair_views([base,retry])[0]
    assert [r['run_id'] for r in view['runs']]==['passed','failed','retry']
    assert view['runs'][-1]['status']=='token_budget' and len(view['prior_provider_attempts'])==1
    assert base['runs'][-1]['status']=='api_error'
    retry['config'].update(comparison_label='Heat recovery',model_transport_note='Provider changed')
    retry['started_at']='2026-09-30T17:00:00Z'
    view=repair_views([base,retry])[0]
    assert view['config']['study_label']=='Heat recovery'
    assert view['config']['model_transport_note']=='Provider changed'
    assert view['latest_activity_at']==retry['started_at']


def test_shared_deadline_is_task_outcome_not_provider_outage():
    from weather_bench.report import effective_status,failure_detail
    raw={'status':'api_error','solve_seconds':1200.1,'events':[{'action':'api_error','message':'ReadTimeout'}]}
    status=effective_status(raw,{'hard_request_deadline':True,'task_timeout_seconds':1200})
    assert status=='task_timeout'
    detail=failure_detail({**raw,'status':status})
    assert detail['category']=='task_budget' and detail['code']=='task_timeout'
