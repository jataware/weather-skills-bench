import copy
import json
from datetime import datetime, timezone
from types import SimpleNamespace
import httpx
import pytest
from weather_bench.reliability import provider_preferences, retry_wait, task_payload
from weather_bench import runner

POLICY={'max_retries_per_run':3,'max_consecutive_retries':2,'base_delay_seconds':2,'max_delay_seconds':30}

def test_retry_after_and_limits():
    assert retry_wait(POLICY,429,{},'12',0,0,100)==12
    assert retry_wait(POLICY,503,{},None,1,1,100)==4
    assert retry_wait(POLICY,429,{},'Tue, 29 Sep 2026 12:00:15 GMT',0,0,100,datetime(2026,9,29,12,tzinfo=timezone.utc))==15
    for code,header,retries,consecutive,remaining in [(401,None,0,0,100),(429,'60',0,0,100),(429,None,3,0,100),(503,None,0,2,100),(429,'12',0,0,10),(429,'NaN',0,0,100),(None,None,0,0,100)]:
        assert retry_wait(POLICY,code,{},header,retries,consecutive,remaining) is None
    assert retry_wait(POLICY,429,{'metadata':{'provider_error_code':'invalid_request_error'}},None,0,0,100) is None

def test_routing_and_clarification_preserve_original_protocol():
    old={'providers':{'m':['one','two']}}
    assert provider_preferences(old,'m')=={'only':['one','two'],'allow_fallbacks':False,'require_parameters':True}
    new={**old,'provider_allow_fallbacks':True,'provider_price_caps':{'m':{'prompt':1,'completion':2}}}
    assert provider_preferences(new,'m')['order']==['one','two']
    assert provider_preferences(new,'m')['max_price']=={'prompt':1,'completion':2}
    public={'brief':'original'}
    case=SimpleNamespace(id='c',public=lambda:public)
    assert task_payload(case,{'task_clarifications':{'c':'shared'}})['study_clarification']=='shared'
    assert task_payload(case,{})=={'brief':'original'}

def completion(action='submit',cost=.01):
    return {'id':'test','model':'m','provider':'P','choices':[{'finish_reason':'stop','message':{'content':json.dumps({'action':action,**({'code':'x=1'} if action=='python' else {})})}}],
            'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15,'cost':cost}}

@pytest.fixture
def harness(tmp_path,monkeypatch):
    from weather_bench import fixtures
    executions=[]
    class FakeSandbox:
        image_ids={'python':'test'}
        def __init__(self,*args,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def execute(self,action,timeout):
            executions.append(action);return {'seconds':0.,'returncode':0,'stdout':'ok'}
        def answer(self):return {'x':1}
    monkeypatch.setattr(runner,'ROOT',tmp_path)
    monkeypatch.setattr(runner,'Sandbox',FakeSandbox)
    monkeypatch.setattr(runner.time,'sleep',lambda _:None)
    monkeypatch.setattr(fixtures,'materialize',lambda case,path:path.mkdir(parents=True))
    case=SimpleNamespace(id='c',suite='diagnostic',datasets={},expected={'x':1},public=lambda:{'brief':'test','tolerance':{'atol':1e-4,'rtol':1e-6}})
    config={'max_calls':6,'max_executions':6,'max_total_tokens':1000,'max_output_tokens':100,'max_context_bytes':100000,
            'task_timeout_seconds':100,'request_timeout_seconds':10,'execution_timeout_seconds':10,'max_cost_usd':10,
            'model_metadata':{'m':{'supported_parameters':[]}},'provider_retry':POLICY,'json_mode':True,
            'unknown_cost_policy':'reserve','billing_prices':{'m':{'prompt':.000001,'completion':.000002}},'recover_model_response_errors':True}
    def run(replies,**overrides):
        arm=overrides.pop('arm','python')
        config.update(overrides);bodies=[];ledger={'spent':0.,'uncertain_cost':False}
        def transport(request):
            bodies.append(json.loads(request.content))
            response=replies[len(bodies)-1]
            if isinstance(response,Exception):raise response
            return httpx.Response(response[0],json=response[1],headers=response[2] if len(response)>2 else {})
        with httpx.Client(transport=httpx.MockTransport(transport)) as client:
            result=runner.run_one(case,'m',arm,0,config,client,ledger)
        return result,bodies,ledger
    return run,executions,tmp_path

def test_retries_preserve_messages_without_reexecuting_actions(harness):
    run,executions,path=harness
    result,bodies,ledger=run([(200,completion('python')),(429,{'error':{'code':429}}),(200,completion())])
    assert result['status']=='submitted' and result['provider_retries']==1 and result['http_attempts']==3
    assert len(executions)==1 and bodies[1]==bodies[2]
    assert bodies[0]['response_format']=={'type':'json_object'}
    assert result['usage']['known_cost_usd']==.02 and ledger['spent']==.02
    assert [r['turn'] for r in result['requests']]==[1,3]
    assert (path/'results/raw'/result['run_id']/'001.json').exists()

def test_retries_bounded(harness):
    run,_,_=harness
    result,bodies,_=run([(429,{'error':{'code':429}})]*3)
    assert result['status']=='api_error' and len(bodies)==3 and result['provider_retries']==2

def test_server_error_charge_and_time_are_retained(harness):
    run,_,_=harness
    error={'error':{'code':503},'usage':{'cost':.02,'total_tokens':7}}
    result,_,ledger=run([(503,error),(200,completion())])
    assert result['usage']['known_cost_usd']==.03 and result['usage']['total_tokens']==22
    assert ledger['spent']==.03 and result['provider_retries']==1 and result['usage']['cost_complete']

def test_unknown_charge_reserved_and_not_erased_by_rejected_retry(harness):
    run,_,_=harness
    result,_,ledger=run([(200,{'error':{'code':503}}),(429,{'error':{'code':429}}),(200,completion())])
    assert result['status']=='submitted' and not result['usage']['cost_complete']
    assert ledger['budget_reserve_usd']>0 and not ledger['uncertain_cost']
    assert result['provider_retries']==2

def test_malformed_response_never_executes_visible_action(harness):
    run,executions,_=harness
    malformed=completion('python');malformed['choices'][0].update(finish_reason='error',native_finish_reason='MALFORMED_FUNCTION_CALL')
    result,bodies,_=run([(200,malformed),(200,completion())])
    assert result['status']=='submitted' and result['provider_retries']==0 and not executions
    assert 'No action was executed' in bodies[1]['messages'][-1]['content']
    assert result['usage']['known_cost_usd']==.02

def test_transport_timeout_not_retried(harness):
    run,_,_=harness
    result,bodies,ledger=run([httpx.ReadTimeout('timeout')])
    assert result['status']=='api_error' and len(bodies)==1 and not result['usage']['cost_complete']
    assert ledger['budget_reserve_usd']>0


def test_opt_in_network_retry_has_reserves_and_no_duplicate_action(harness):
    run,executions,_=harness
    policy={**POLICY,'transport_errors':['ReadTimeout','RemoteProtocolError']}
    result,bodies,ledger=run([(200,completion('python')),httpx.RemoteProtocolError('closed'),(200,completion())],provider_retry=policy,max_total_tokens=100000)
    assert result['status']=='submitted' and result['provider_retries']==1
    assert len(executions)==1 and bodies[1]==bodies[2]
    assert not result['usage']['cost_complete'] and result['usage']['unconfirmed_token_reserve']>0
    assert ledger['budget_reserve_usd']>0


def test_endpoint_json_override_keeps_action_contract(harness):
    run,_,_=harness
    result,bodies,_=run([(200,completion())],model_json_mode={'m':False})
    assert 'response_format' not in bodies[0]
    assert result['status']=='submitted'
    result,bodies,_=run([(200,completion())],model_json_mode={'other':False})
    assert bodies[0]['response_format']=={'type':'json_object'}


def test_per_run_cap_blocks_next_request_before_charge(harness):
    run,executions,_=harness
    result,bodies,ledger=run([(200,completion('python'))],max_run_cost_usd=.03,max_total_tokens=None)
    assert len(bodies)==1 and len(executions)==1
    assert result['status']=='run_cost_budget' and ledger['spent']==.01
    assert result['events'][-1]['next_request_bound_usd']>result['events'][-1]['run_remaining_usd']
    assert result['budget']['reported_usd']==.01


def test_dollar_budget_can_continue_past_old_token_cap(harness):
    run,_,_=harness
    reply=completion('python');reply['usage']['total_tokens']=250000
    result,bodies,_=run([(200,reply),(200,completion())],max_run_cost_usd=2,max_total_tokens=None)
    assert result['status']=='submitted' and len(bodies)==2
    assert result['usage']['total_tokens']==250015


def test_unconfirmed_request_reserve_counts_toward_run_cap(harness):
    run,_,_=harness
    policy={**POLICY,'transport_errors':['ReadTimeout']}
    result,bodies,ledger=run([httpx.ReadTimeout('timeout')],max_run_cost_usd=.03,
                            max_total_tokens=None,provider_retry=policy)
    assert result['status']=='run_cost_budget' and len(bodies)==1
    assert result['budget']['reserved_usd']==ledger['budget_reserve_usd']>0
    assert result['budget']['reported_usd']==0 and not result['usage']['cost_complete']


def test_study_cap_also_admits_before_sending(harness):
    run,_,_=harness
    result,bodies,_=run([(200,completion('python'))],max_run_cost_usd=2,max_cost_usd=.03,max_total_tokens=None)
    assert result['status']=='study_budget' and len(bodies)==1


def test_guided_hybrid_requires_prior_guides_and_permits_python_recovery(harness,monkeypatch,tmp_path):
    run,executions,_=harness
    guide=tmp_path/'guide.md';guide.write_text('Use inspect-zarr --input STORE')
    monkeypatch.setattr(runner,'inventory',lambda _: {'inspect-zarr':{'name':'inspect-zarr','doc':str(guide)}})
    monkeypatch.setattr(runner,'workflow',lambda *_: {'passed':False})
    def action(value):
        result=completion();result['choices'][0]['message']['content']=json.dumps(value);return (200,result)
    read={'action':'read_skill','skill':'inspect-zarr'}
    skill={'action':'skill','skill':'inspect-zarr','args':['--input','/inputs/raw.zarr']}
    result,bodies,_=run([
        (200,completion('python')),  # refused before discovery
        action({'action':'batch','actions':[read,skill]}),  # read succeeds, same-turn call refused
        action(skill),
        (200,completion('python')),
        (200,completion())
    ],arm='skills',skill_policy='guided-v1',allow_batch=True)
    assert result['status']=='submitted'
    assert [a['action'] for a in executions]==['skill','python']
    assert len([e for e in result['events'] if e['action']=='protocol_error'])==2
    assert result['skill_adoption']=={'guides_read':['inspect-zarr'],'skill_calls':1,'python_calls':1}
    assert bodies[0]['messages'][0]['content'].startswith('Skill-guided workflow')
